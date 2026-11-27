"""Executable ETL/model benchmark runner with empirical tables, artifacts, and figures."""

import argparse
import asyncio
import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from finhealth.core.config import Settings
from finhealth.core.constants import EXCLUDED_INDUSTRIAL_CIKS
from finhealth.core.exceptions import FinHealthError, ModelPipelineError, SecRateLimitError
from finhealth.db.models import Company
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.annual import as_reported_annual_payload as as_reported_annual_payload
from finhealth.etl.annual import load_annual_companyfacts
from finhealth.etl.pipeline import FinancialEtlPipeline, require_industrial_company
from finhealth.ingestion.schemas import (
    CompanyMetadata,
    is_financial_institution_sic,
    map_sic_to_sector,
)
from finhealth.ingestion.sec_client import SecEdgarClient, atomic_write_json
from finhealth.ml.benchmark_data import build_benchmark_panel
from finhealth.ml.distress_classifier import ImbalanceStrategy
from finhealth.ml.kaggle_loader import load_kaggle_bankruptcy_panel
from finhealth.ml.pca_clustering import CLUSTER_LABELS
from finhealth.ml.registry import (
    ModelArtifactBundle,
    save_bundle,
    sync_company_prediction,
    train_and_evaluate_kaggle_v2_pipeline,
    train_and_evaluate_pipeline,
)
from finhealth.ml.splitter import (
    TemporalSplitter,
    build_next_period_panel,
    derive_distress_label,
    prepare_validation_test,
)
from finhealth.ml.visualization import EvaluationPlotGenerator

logger = logging.getLogger(__name__)
SEC_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOG",
    "META",
    "NVDA",
    "INTC",
    "IBM",
    "ORCL",
    "CSCO",
    "ADBE",
    "CRM",
    "AMD",
    "QCOM",
    "TXN",
    "HPQ",
    "DELL",
    "LUMN",
    "WBD",
    "T",
    "VZ",
    "DIS",
    "NFLX",
    "AMZN",
    "WMT",
    "TGT",
    "COST",
    "HD",
    "LOW",
    "NKE",
    "SBUX",
    "MCD",
    "KO",
    "PEP",
    "PG",
    "CL",
    "WBA",
    "CVS",
    "KR",
    "DG",
    "DLTR",
    "BBY",
    "M",
    "KSS",
    "GME",
    "AMC",
    "PTON",
    "BYND",
    "F",
    "GM",
    "TSLA",
    "BA",
    "CAT",
    "DE",
    "HON",
    "GE",
    "MMM",
    "FDX",
    "UPS",
    "DAL",
    "UAL",
    "AAL",
    "LUV",
    "JBLU",
    "CCL",
    "RCL",
    "NCLH",
    "MAR",
    "HLT",
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "HAL",
    "OXY",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "BMY",
    "LLY",
    "AMGN",
    "GILD",
    "BIIB",
    "UNH",
    "TMO",
    "DHR",
    "ABT",
    "RTX",
    "LMT",
    "UNP",
    "CSX",
    "WM",
    "LIN",
    "NEM",
    "FCX",
    "CLF",
    "AA",
    "X",
    "PLUG",
    "FCEL",
    "ENPH",
    "SEDG",
    "RUN",
    "SAVE",
    "NKLA",
    "FSR",
    "BIG",
    "TUP",
)


def has_real_contact(settings: Settings) -> bool:
    """Reject documentation-only contacts before any automated SEC network request."""
    agent = settings.sec_user_agent.lower()
    return not any(
        marker in agent
        for marker in (".local", ".invalid", "example.com", "example.org", "example.net")
    )


def load_cached_panel(settings: Settings) -> pd.DataFrame:
    """Run valid cached companyfacts through actual ETL without relabeling synthetic data as SEC."""
    rows: list[dict[str, Any]] = []
    for path in sorted((settings.raw_sec_path / "companyfacts").glob("CIK*.json")):
        try:
            payload = load_annual_companyfacts(path)
            cik = str(payload["cik"]).zfill(10)
            metadata_path = settings.raw_sec_path / "submissions" / f"CIK{cik}.json"
            metadata = (
                json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata_path.exists()
                else {}
            )
            if cik in EXCLUDED_INDUSTRIAL_CIKS or is_financial_institution_sic(metadata.get("sic")):
                logger.info(
                    "Excluding out-of-scope registrant CIK %s from the industrial panel", cik
                )
                continue
            parsed = FinancialEtlPipeline().process_company_facts_payload(
                cik, payload, metadata.get("sic")
            )
            for row in parsed:
                row.update(
                    company_id=f"sec:{cik}",
                    data_source="cached_sec",
                    company_name=payload.get("entityName"),
                    sic_code=metadata.get("sic"),
                    ticker=(metadata.get("tickers") or [None])[0],
                )
            rows.extend(parsed)
        except (OSError, ValueError, KeyError, TypeError, FinHealthError) as error:
            logger.warning("Skipping invalid SEC cache %s: %s", path.name, error)
    return pd.DataFrame(rows)


async def ingest_live_panel(settings: Settings, database_url: str | None = None) -> None:
    """Retrieve the real universe with one shared limiter and optionally persist to migrated SQL."""
    if not has_real_contact(settings):
        raise ModelPipelineError(
            "sec-live requires a monitored SEC_USER_AGENT contact, not an example"
        )
    engine = create_db_engine(database_url) if database_url else None
    try:
        async with SecEdgarClient(settings) as client:
            for ticker in SEC_UNIVERSE:
                try:
                    entry = await client.resolve_cik(ticker)
                    metadata: CompanyMetadata = await client.fetch_company_metadata(entry.cik)
                    require_industrial_company(metadata.cik, metadata.sic_code)
                    _, payload = await client.fetch_company_facts(entry.cik)
                    if engine is not None:
                        pipeline = FinancialEtlPipeline()
                        records = pipeline.process_company_facts_payload(
                            entry.cik, as_reported_annual_payload(payload), metadata.sic_code
                        )
                        with create_session_factory(engine).begin() as session:
                            pipeline.persist_to_database(session, metadata, records)
                    logger.info("SEC ingestion complete: %s", ticker)
                except SecRateLimitError:
                    raise
                except FinHealthError as error:
                    logger.warning("SEC ingestion failed for %s: %s", ticker, error)
    finally:
        if engine is not None:
            engine.dispose()


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render deterministic ASCII tables using computed values and explicit unavailable cells."""

    def cell(value: Any) -> str:
        """Format a single value without inventing a number for missing metrics."""
        return (
            "N/A" if value is None else f"{value:.6f}" if isinstance(value, float) else str(value)
        )

    formatted = [headers, *[[cell(value) for value in row] for row in rows]]
    widths = [max(len(row[i]) for row in formatted) for i in range(len(headers))]
    line = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def render(row: list[str]) -> str:
        """Align a row to the measured table widths."""
        return (
            "| "
            + " | ".join(value.ljust(width) for value, width in zip(row, widths, strict=True))
            + " |"
        )

    return "\n".join(
        [line, render(formatted[0]), line, *[render(row) for row in formatted[1:]], line]
    )


def benchmark_tables(bundle: ModelArtifactBundle, panel: pd.DataFrame) -> str:
    """Format required benchmark tables directly from the fitted evaluation report."""
    report = bundle.evaluation_report
    summary = report["split_summary"]
    is_kaggle_v2 = report.get("scoring_contract") == "scale_free_v2"
    panels = [
        ["Panel rows", len(panel)],
        ["Companies", panel["company_id"].nunique()],
        *(
            [
                [
                    "Kaggle US bankruptcy rows",
                    int(panel["data_source"].eq("kaggle_us_bankruptcy").sum()),
                ],
                [
                    "Total 1Y bankruptcy events (year == max_year)",
                    summary.get("total_positive_rows"),
                ],
                ["Train positive events", summary.get("train_positive_rows")],
                ["Validation positive events", summary.get("validation_positive_rows")],
                ["Test positive events", summary.get("test_positive_rows")],
                [
                    "Entity leakage (Train/Val vs Test bankrupt overlap)",
                    summary.get("entity_leakage_positive_overlap", 0),
                ],
            ]
            if is_kaggle_v2
            else [
                ["Synthetic rows", int(panel["data_source"].eq("synthetic_benchmark").sum())],
                ["Cached SEC rows", int(panel["data_source"].eq("cached_sec").sum())],
            ]
        ),
        ["Training feature rows", summary["train_feature_rows"]],
        ["Training supervised rows", summary["train_supervised_rows"]],
        ["Non-forward supervised rows", summary["non_forward_supervised_rows"]],
        ["Validation labeled rows", summary["validation_rows"]],
        ["Test feature rows", summary["test_rows"]],
        ["Test labeled rows", summary["test_classification_rows"]],
        *(
            [
                [
                    "Panel 1Y bankruptcy prevalence (%)",
                    float(panel["next_is_bankrupt"].mean() * 100),
                ]
            ]
            if is_kaggle_v2 and "next_is_bankrupt" in panel.columns
            else [
                [
                    "Panel proxy distress prevalence (%)",
                    float(derive_distress_label(panel).mean() * 100),
                ]
            ]
        ),
        ["Threshold source", summary["threshold_source"]],
        ["Calibration publication date", summary.get("threshold_calibration_asof")],
    ]
    parts = ["DATASET AND TEMPORAL SPLITS", _table(["Measure", "Value"], panels)]
    diagnostics = report["clustering"]
    variance = diagnostics["explained_variance_ratio"]
    parts.extend(
        [
            "PCA VARIANCE",
            _table(
                ["Component", "Variance", "Cumulative"],
                [
                    [i + 1, float(value), float(sum(variance[: i + 1]))]
                    for i, value in enumerate(variance)
                ],
            ),
        ]
    )
    parts.append(f"Silhouette Score: {diagnostics['silhouette_score']:.6f}")
    parts.extend(
        [
            "TRAINING CLUSTER PROFILES (original-space centroids)",
            _table(
                ["ID", "Label", "Health", "ROA", "ROE", "OCF", "Current", "Debt"],
                [
                    [
                        key,
                        CLUSTER_LABELS[int(key)],
                        profile["health_score"],
                        *[
                            profile["centroid"][feature]
                            for feature in (
                                "roa",
                                "roe",
                                "ocf_ratio",
                                "current_ratio",
                                "debt_ratio",
                            )
                        ],
                    ]
                    for key, profile in sorted(diagnostics["cluster_profiles"].items())
                ],
            ),
        ]
    )
    for key, title in (
        ("forecasting", "NEXT-PERIOD REGRESSION (unclipped test targets)"),
        (
            "forecasting_winsorized",
            "NEXT-PERIOD REGRESSION (test targets clipped to training bounds)",
        ),
    ):
        parts.extend(
            [
                title,
                _table(
                    ["Target", "MAE", "RMSE", "R2", "N_Test"],
                    [
                        [target, row["mae"], row["rmse"], row["r2"], row["n_samples"]]
                        for target, row in report[key].items()
                    ],
                ),
            ]
        )
    parts.append(
        _table(
            ["Target", "Training lower bound", "Training upper bound"],
            [
                [target.removeprefix("next_"), *bounds]
                for target, bounds in report["forecast_target_bounds"].items()
            ],
        )
    )
    parts.extend(
        [
            "DISTRESS RELIABILITY BY SCORE DECILE",
            _table(
                ["Score", "Lower", "Upper", "N", "Positive", "Mean score", "Observed rate"],
                [
                    [
                        row[key]
                        for key in (
                            "model",
                            "lower",
                            "upper",
                            "n",
                            "positives",
                            "mean_probability",
                            "observed_prevalence",
                        )
                    ]
                    for row in report["test_reliability_bins"]
                ],
            ),
        ]
    )
    paired = report["forecasting_paired"]
    parts.extend(
        [
            "PAIRED FORECASTS VS. NAIVE PERSISTENCE (same observed test targets)",
            _table(
                [
                    "Target",
                    "N",
                    "Candidate",
                    "Weight",
                    "Model MAE",
                    "Naive MAE",
                    "Model R2",
                    "Naive R2",
                ],
                [
                    [
                        name,
                        scores["n_samples"],
                        *report["forecast_shrinkage"].get(name, ("level", 1.0)),
                        scores["mae"],
                        paired["persistence"][name]["mae"],
                        scores["r2"],
                        paired["persistence"][name]["r2"],
                    ]
                    for name, scores in paired["model"].items()
                ],
            ),
        ]
    )
    candidates = report.get("classification_candidates")
    if candidates:
        classification = {
            **candidates,
            "xgboost_raw": report["classification_xgboost_raw"],
        }
    else:
        classification = {
            "XGBoost calibrated": report["classification_xgboost"],
            "XGBoost raw": report["classification_xgboost_raw"],
            **report["classification_baselines"],
        }
    selected_name = report.get("selected_model_name", "xgboost")
    parts.extend(
        [
            "DISTRESS CLASSIFICATION BENCHMARK",
            _table(
                [
                    "Model",
                    "Threshold",
                    "Accuracy",
                    "Precision",
                    "Recall",
                    "F1",
                    "F2",
                    "ROC-AUC",
                    "PR-AUC",
                    "Brier",
                    "Log loss",
                    "Mean score",
                    "TP",
                    "FP",
                    "TN",
                    "FN",
                ],
                [
                    [
                        name,
                        *[
                            row[key]
                            for key in (
                                "threshold",
                                "accuracy",
                                "precision",
                                "recall",
                                "f1_score",
                                "f2_score",
                                "roc_auc",
                                "pr_auc",
                                "brier_score",
                                "log_loss",
                                "mean_probability",
                            )
                        ],
                        *[row["confusion_matrix"][key] for key in ("tp", "fp", "tn", "fn")],
                    ]
                    for name, row in classification.items()
                ],
            ),
        ]
    )
    parts.append(
        f"Selected best model: {selected_name}. "
        f"Test prevalence: {report['classification_xgboost']['prevalence']:.6f}. "
        f"Raw TreeSHAP maximum margin error: {report['shap_margin_max_abs_error']:.9g}."
    )
    importance = report["global_shap_importance"]
    parts.extend(
        [
            "TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)",
            _table(
                ["Feature", "Mean |SHAP|"],
                [[key, value] for key, value in list(importance.items())[:10]],
            ),
        ]
    )
    return "\n\n".join(parts)


def persist_real_panel(
    settings: Settings,
    panel: pd.DataFrame,
    database_url: str | None,
    *,
    bundle: ModelArtifactBundle | None = None,
) -> str:
    """Persist annual SEC facts and any fitted bundle predictions in one SQL transaction."""
    settings.parquet_path.mkdir(parents=True, exist_ok=True)
    url = database_url or settings.database_url
    engine = create_db_engine(url)
    try:
        config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with create_session_factory(engine).begin() as session:
            pipeline = FinancialEtlPipeline()
            for company in session.scalars(select(Company)):
                if company.cik in EXCLUDED_INDUSTRIAL_CIKS or is_financial_institution_sic(
                    company.sic_code
                ):
                    session.delete(company)
            for cik, group in panel.groupby("cik"):
                row = group.iloc[-1]
                metadata = CompanyMetadata(
                    cik=str(cik),
                    name=row["company_name"],
                    ticker=row.get("ticker"),
                    sic_code=row.get("sic_code"),
                    sector=map_sic_to_sector(row.get("sic_code")),
                )
                company = pipeline.persist_to_database(
                    session,
                    metadata,
                    [
                        {
                            str(k): (None if isinstance(v, float) and not math.isfinite(v) else v)
                            for k, v in row.items()
                        }
                        for row in group.to_dict("records")
                    ],
                )
                if bundle is not None:
                    sync_company_prediction(session, company.id, bundle)
    except SQLAlchemyError as error:
        raise ModelPipelineError(
            "SEC panel database persistence failed; check database and temporary disk space"
        ) from error
    finally:
        engine.dispose()
    return "configured database"


def run_training(
    settings: Settings,
    mode: str = "benchmark",
    model_version: str = "v1.0.0",
    train_end_year: int | None = None,
    validation_end_year: int | None = None,
    offline: bool = False,
    database_url: str | None = None,
    *,
    replace_existing: bool = False,
    require_real: bool = False,
    dataset: str = "sec",
    kaggle_path: Path | None = None,
    activate: bool = True,
    imbalance_strategy: ImbalanceStrategy = "class_weight",
) -> tuple[Path, str]:
    """Build a provenance-marked ETL panel, fit/evaluate models, and publish actual outputs."""
    if mode not in {"benchmark", "sec-live"}:
        raise ModelPipelineError("Mode must be benchmark or sec-live")
    if dataset not in {"sec", "kaggle"}:
        raise ModelPipelineError("Dataset must be sec or kaggle")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", model_version):
        raise ModelPipelineError("Invalid model version")
    if (
        (settings.model_path / model_version).exists()
        and mode != "sec-live"
        and not replace_existing
    ):
        raise ModelPipelineError("Artifact version exists; choose a new --model-version")
    pipeline = FinancialEtlPipeline()
    if dataset == "kaggle":
        live_status = "not applicable (Kaggle US Company Bankruptcy dataset)"
        csv_file = kaggle_path or (
            settings.raw_sec_path.parent / "kaggle" / "american_bankruptcy.csv"
        )
        panel = load_kaggle_bankruptcy_panel(csv_file)
        real_only = False
        train_end_year = train_end_year if train_end_year is not None else 2014
        validation_end_year = validation_end_year if validation_end_year is not None else 2016
        name = "kaggle_bankruptcy_panel.parquet"
    else:
        cached = load_cached_panel(settings)
        cached_companies = cached["company_id"].nunique() if not cached.empty else 0
        live_status = "not attempted (offline or no monitored SEC contact)"
        if mode == "sec-live":
            if offline:
                raise ModelPipelineError("sec-live cannot be combined with --offline")
            asyncio.run(ingest_live_panel(settings))
            live_status = "attempted SEC universe; see ingestion logs"
            cached = load_cached_panel(settings)
        elif not offline and has_real_contact(settings) and cached_companies < 40:
            asyncio.run(ingest_live_panel(settings))
            live_status = "attempted SEC universe; see ingestion logs"
            cached = load_cached_panel(settings)
        frames = [cached] if not cached.empty else []
        real_annual = (
            cached.loc[cached["form_type"].eq("10-K") & cached["fiscal_year"].between(2010, 2025)]
            if not cached.empty
            else cached
        )
        if require_real and len(real_annual) < 300:
            raise ModelPipelineError(
                "The cache contains fewer than 300 eligible real annual records"
            )
        if mode == "benchmark" and not require_real and len(real_annual) < 300:
            frames.append(build_benchmark_panel(settings.random_seed))
        if not frames:
            raise ModelPipelineError("No usable SEC data was retrieved or cached")
        panel = pd.concat(frames, ignore_index=True)
        panel = panel.loc[
            panel["form_type"].eq("10-K") & panel["fiscal_year"].between(2010, 2025)
        ].copy()
        panel = panel.sort_values(["company_id", "fiscal_year", "period_end_date"]).reset_index(
            drop=True
        )
        real_only = bool(panel["data_source"].eq("cached_sec").all())
        default_train = 2021 if real_only else 2020
        train_end_year = train_end_year if train_end_year is not None else default_train
        validation_end_year = (
            validation_end_year if validation_end_year is not None else train_end_year + 1
        )
        name = "sec_real_panel.parquet" if real_only else "benchmark_panel.parquet"
    if dataset == "kaggle":
        bundle = train_and_evaluate_kaggle_v2_pipeline(
            panel,
            train_end_year,
            model_version,
            settings.random_seed,
            validation_end_year=validation_end_year,
            imbalance_strategy=imbalance_strategy,
        )
    else:
        bundle = train_and_evaluate_pipeline(
            panel,
            train_end_year,
            model_version,
            settings.random_seed,
            validation_end_year=validation_end_year,
            imbalance_strategy=imbalance_strategy,
        )
    pipeline.export_to_parquet(
        [{str(k): v for k, v in row.items()} for row in panel.to_dict("records")],
        settings.parquet_path / name,
    )
    database_location = (
        persist_real_panel(settings, panel, database_url, bundle=bundle) if real_only else None
    )
    bundle.evaluation_report["data_provenance"] = {
        "mode": mode,
        "dataset": dataset,
        "live_ingestion": live_status,
        "random_seed": settings.random_seed,
        "source_counts": {
            str(key): int(value) for key, value in panel["data_source"].value_counts().items()
        },
        "database": database_location,
        "annual_selection": (
            "1-year-ahead bankruptcy event on final observed fiscal year (year == max_year); "
            "all prior years labeled 0"
            if dataset == "kaggle"
            else "first-observed filing per annual period; later revisions excluded"
        ),
        "excluded_ciks": sorted(EXCLUDED_INDUSTRIAL_CIKS),
        "purpose": (
            "out-of-time US corporate bankruptcy validation (Kaggle 1999-2018)"
            if dataset == "kaggle"
            else (
                "real SEC EDGAR fundamental distress evaluation"
                if real_only
                else "software benchmark; not validated real-world bankruptcy performance"
            )
        ),
        "labels": (
            "observed 1-year-ahead US corporate bankruptcy outcomes "
            "(Chapter 7/11, year == max_year only)"
            if dataset == "kaggle"
            else (
                "operational, cash-flow, and solvency distress rules applied to SEC financials"
                if real_only
                else "synthetic stochastic outcomes plus financial proxy for any SEC rows"
            )
        ),
    }
    split = TemporalSplitter().split(
        build_next_period_panel(panel), train_end_year, validation_end_year
    )
    train = split["train"]
    if "filed_date" in train:
        train = train.loc[
            pd.to_datetime(train["filed_date"]) <= pd.Timestamp(train_end_year, 12, 31)
        ]
    figures = (
        settings.data_dir / "artifacts" / "figures"
        if activate
        else settings.data_dir / "artifacts" / f"figures_{model_version}"
    )
    if dataset == "kaggle":
        held_out = split["test"].copy()
        held_out["next_is_distressed"] = held_out["next_is_bankrupt"].astype(float)
    else:
        _, held_out, _ = prepare_validation_test(split["val"], split["test"], validation_end_year)
    paths = EvaluationPlotGenerator(bundle, train, held_out, figures).generate()
    tables = benchmark_tables(bundle, panel)
    existing = settings.model_path / model_version
    archive = None
    if existing.exists():
        archive_root = settings.data_dir / "artifacts" / "model_archive"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive = (
            archive_root
            / f"{model_version}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        )
        existing.replace(archive)
    try:
        destination = save_bundle(bundle, settings.model_path)
    except BaseException:
        if archive is not None and not existing.exists():
            archive.replace(existing)
        raise
    report = render_benchmark_report(
        model_version=model_version,
        dataset=dataset,
        real_only=real_only,
        live_status=live_status,
        train_end_year=train_end_year,
        validation_end_year=validation_end_year,
        tables=tables,
        paths=paths,
        destination=destination,
    )
    with TemporaryDirectory(prefix=".report-", dir=destination) as temporary:
        staging = Path(temporary) / "BENCHMARK_REPORT.md"
        staging.write_text(report, encoding="utf-8")
        staging.replace(destination / staging.name)
    if activate:
        atomic_write_json(
            settings.model_path / "latest.json",
            {
                "model_version": bundle.model_version,
                "bundle_dir": bundle.model_version,
                "created_at": bundle.created_at,
                "mode": mode,
                "dataset": dataset,
            },
        )
    return destination, tables


def render_benchmark_report(
    *,
    model_version: str,
    dataset: str,
    real_only: bool,
    live_status: str,
    train_end_year: int,
    validation_end_year: int,
    tables: str,
    paths: list[Path],
    destination: Path,
) -> str:
    """Render BENCHMARK_REPORT.md with provenance statements matching the actual dataset."""
    if dataset == "kaggle":
        provenance = (
            "This run uses the Kaggle US Company Bankruptcy dataset (1999-2018 historical annual "
            "financial statements with observed bankruptcy status labels). "
            "All metrics below come from real fitted models and held-out predictions. "
            "Labels reflect observed corporate bankruptcy outcomes from the Kaggle dataset, "
            "rather than synthetic simulations or SEC distress proxy rules.\n\n"
        )
    elif real_only:
        provenance = (
            "This run uses only real SEC EDGAR annual financial statements. "
            "All metrics below come from real fitted models and held-out predictions. "
            "Labels are a financial distress proxy, not observed bankruptcy outcomes.\n\n"
        )
    else:
        provenance = (
            "Synthetic rows are simulated accounting records, not actual SEC issuers. "
            "All metrics below come from real fitted models and held-out predictions. "
            "Labels are a financial distress proxy, not observed bankruptcy outcomes.\n\n"
        )
    return (
        f"# FinHealth empirical benchmark: {model_version}\n\n"
        + provenance
        + f"Live ingestion: {live_status}. Training through {train_end_year}; "
        f"validation through {validation_end_year}; later years are test data.\n\n"
        f"```text\n{tables}\n```\n\n"
        "Calibration, threshold selection and forecast shrinkage use only eligible validation "
        "labels. The test origins are embargoed until those labels are observable. "
        "SEC caches still require point-in-time revision controls for market backtests.\n\n"
        "Regression tables report both original test targets and targets clipped to the "
        "training 2.5th and 97.5th percentiles. The parity chart uses original test targets. "
        "Cluster labels rank relative centroid health.\n\n"
        + "\n".join(
            f"- [{path.name}]({os.path.relpath(path, destination).replace(chr(92), '/')})"
            for path in paths
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Execute the CLI and print complete dynamically computed tables to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["benchmark", "sec-live"], default="benchmark")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--require-real", action="store_true", help="Require a real SEC panel.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--model-version", default="v1.0.0")
    parser.add_argument("--train-end-year", type=int)
    parser.add_argument("--validation-end-year", type=int)
    parser.add_argument("--database-url")
    parser.add_argument("--dataset", choices=["sec", "kaggle"], default="sec")
    parser.add_argument("--kaggle-path", type=Path)
    parser.add_argument("--no-activate", action="store_true", help="Do not update latest.json.")
    parser.add_argument(
        "--imbalance-strategy",
        choices=["class_weight", "smote"],
        default="class_weight",
        help="Class imbalance handling strategy for training.",
    )
    parser.add_argument(
        "--replace-existing", action="store_true", help="Archive and replace the requested version."
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    try:
        try:
            settings = Settings(data_dir=args.data_dir)
        except ValidationError as error:
            if any(
                item["loc"] != ("sec_user_agent",) or item["type"] != "missing"
                for item in error.errors()
            ):
                raise
            settings = Settings(
                data_dir=args.data_dir,
                sec_user_agent="FinHealthOffline/1.0 (offline@example.invalid)",
            )
        destination, tables = run_training(
            settings,
            args.mode,
            args.model_version,
            args.train_end_year,
            args.validation_end_year,
            args.offline,
            args.database_url,
            replace_existing=args.replace_existing,
            require_real=args.require_real,
            dataset=args.dataset,
            kaggle_path=args.kaggle_path,
            activate=not args.no_activate,
            imbalance_strategy=args.imbalance_strategy,
        )
    except (FinHealthError, ValueError, OSError) as error:
        parser.exit(1, f"Training failed: {error}\n")
    if args.dataset == "kaggle":
        print(
            "Computed out-of-time US bankruptcy evaluation "
            "(Kaggle 1999-2018, 1-year-ahead year == max_year labels, 0% entity leakage).\n"
        )
    else:
        print(
            "Computed model evaluation - proxy or simulated distress labels "
            "are not bankruptcy outcomes.\n"
        )
    print(tables)
    print(f"\nArtifacts: {destination.resolve()}")
    print(f"Figures: {(settings.data_dir / 'artifacts' / 'figures').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
