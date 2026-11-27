"""Repository-backed analysis orchestration; routers contain no financial or ML logic."""

import math
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from statistics import median
from threading import RLock
from typing import Any

import pandas as pd
from sqlalchemy import Engine, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from starlette.concurrency import run_in_threadpool

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.schemas import (
    ClusterPointSchema,
    CompanyFullAnalysisSchema,
    CompanySummarySchema,
    HistoricalMetricPointSchema,
    ManualPredictionResponseSchema,
    ManualStatementInputSchema,
    ModelEvaluationResponseSchema,
    PredictionDetailSchema,
    TrainModelRequest,
)
from finhealth.api.schemas.models import (
    AccountingChecklistSchema,
    ActionableRecommendationSchema,
    BatchPredictionItemSchema,
    BatchPredictionRequestSchema,
    BatchPredictionResponseSchema,
    CompanyComparisonItemSchema,
    CompanyComparisonResponseSchema,
    CompanyScreeningFilters,
    DupontSchema,
    HealthPillarsSchema,
    PeerMetricSchema,
    QualityOfEarningsSchema,
    SectorPeerContextSchema,
    ShapShiftSchema,
    StressScenarioRequestSchema,
    StressSimulationResponseSchema,
    StressSnapshotSchema,
)
from finhealth.core.config import Settings
from finhealth.core.constants import EXCLUDED_INDUSTRIAL_CIKS
from finhealth.core.exceptions import (
    EtlProcessingError,
    ModelPipelineError,
    SecResourceNotFoundError,
)
from finhealth.db.models import Company, FinancialMetric, FinancialStatement, ModelPrediction
from finhealth.db.repositories import CompanyRepository, latest_annual_statement_id, normalize_cik
from finhealth.etl.annual import as_reported_annual_payload
from finhealth.etl.corporate_finance import (
    CompositeBenchmark,
    compute_accounting_checklist,
    compute_dupont,
    compute_health_pillars,
    compute_quality_of_earnings,
    generate_actionable_recommendations,
)
from finhealth.etl.feature_engineering import compute_temporal_features
from finhealth.etl.financial_ratios import (
    CREDIT_RATIO_COLUMNS,
    _finite,
    compute_altman_z_score,
    compute_statement_ratios,
)
from finhealth.etl.pipeline import FinancialEtlPipeline, require_industrial_company
from finhealth.etl.stress import SCENARIO_ASSUMPTIONS, stress_statement
from finhealth.ingestion.schemas import (
    CompanyMetadata,
    is_financial_institution_sic,
    is_manufacturing_sic,
)
from finhealth.ingestion.sec_client import SecEdgarClient, atomic_write_json
from finhealth.ml.preprocessing import FinancialPreprocessor
from finhealth.ml.registry import (
    ModelArtifactBundle,
    industrial_panel,
    predict_for_company_records,
    save_bundle,
    sync_company_prediction,
    train_and_evaluate_pipeline,
)
from finhealth.ml.splitter import (
    FORECAST_TARGET_COLUMNS,
    RATIO_FEATURE_COLUMNS,
    TemporalSplitter,
    build_next_period_panel,
    prepare_validation_test,
)

FINANCIAL_RATIOS = RATIO_FEATURE_COLUMNS + CREDIT_RATIO_COLUMNS
FORECAST_FIELDS = tuple(f"pred_{key}" for key in FORECAST_TARGET_COLUMNS)

PEER_METRICS = (
    "roa",
    "roe",
    "operating_margin",
    "debt_ratio",
    "ocf_ratio",
    "current_ratio",
    "interest_coverage",
    "fcf_to_liabilities",
)


def _screening_conditions(filters: CompanyScreeningFilters) -> list[ColumnElement[bool]]:
    """Build parameterized SQL filters without treating missing metrics as zero."""
    conditions = []
    if filters.q and (query := filters.q.strip().lower()):
        conditions.append(or_(
            func.lower(Company.name).contains(query, autoescape=True),
            func.lower(Company.ticker).contains(query, autoescape=True),
            Company.cik.contains(query, autoescape=True),
        ))
    for value, column in (
        (filters.sector, Company.sector), (filters.risk_level, ModelPrediction.risk_level),
        (filters.cluster_id, FinancialMetric.cluster_id),
        (filters.fiscal_year, FinancialStatement.fiscal_year),
    ):
        if value is not None:
            conditions.append(column == value)
    for bound, metric in (
        (filters.min_roa, FinancialMetric.roa),
        (filters.min_current_ratio, FinancialMetric.current_ratio),
    ):
        if bound is not None:
            conditions.append(metric >= bound)
    if filters.max_debt_ratio is not None:
        conditions.append(FinancialMetric.debt_ratio <= filters.max_debt_ratio)
    return conditions


def _stress_snapshot(record: dict[str, Any], bundle: ModelArtifactBundle) -> StressSnapshotSchema:
    """Score one statement with the same inference path used by persisted predictions."""
    scored = predict_for_company_records(bundle, [record])
    return StressSnapshotSchema(
        metrics=HistoricalMetricPointSchema.model_validate({**record, **scored}),
        prediction=PredictionDetailSchema.model_validate(
            {
                **scored,
                **scored["shap_explanations"],
                "target_fiscal_year": record["fiscal_year"] + 1,
                "target_fiscal_period": "FY",
            }
        ),
    )


def _peer_metric(value: float | None, observations: list[float]) -> PeerMetricSchema:
    """Report the fraction below plus half the fraction tied, counting observed firms only."""
    percentile = None
    if value is not None and math.isfinite(value) and observations:
        below = sum(peer < value for peer in observations)
        tied = sum(peer == value for peer in observations)
        percentile = 100 * (below + 0.5 * tied) / len(observations)
    return PeerMetricSchema(
        median=median(observations) if observations else None,
        percentile=percentile,
        n_observed=len(observations),
    )


@lru_cache(maxsize=256)
def _model_inputs(
    preprocessor: FinancialPreprocessor, observations: tuple[float | None, ...]
) -> tuple[float, ...]:
    """Reuse inputs for an immutable fitted preprocessor and identical statement values."""
    frame = pd.DataFrame([dict(zip(preprocessor.columns, observations, strict=True))])
    return tuple(float(value) for value in preprocessor.transform(frame)[0])


def _columns(obj: Any) -> dict[str, Any]:
    """Read a mapped object's persisted scalar values without exposing SQLAlchemy internals."""
    return (
        {}
        if obj is None
        else {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
    )


def _default_validation_year(panel: pd.DataFrame, train_end_year: int) -> int | None:
    """Use the next year if it has observable validation and held-out targets."""
    next_year = train_end_year + 1
    if panel.empty or not panel["fiscal_year"].eq(next_year).any():
        return None
    labeled = build_next_period_panel(panel)
    if not labeled.loc[labeled["fiscal_year"] > next_year, "next_is_distressed"].notna().any():
        return None
    split = TemporalSplitter().split(labeled, train_end_year, next_year)
    if not split["val"]["next_is_distressed"].notna().any():
        return None
    # An explicit window is validated by the trainer. For a default, check eligibility first.
    admitted = split["val"].dropna(subset=["next_is_distressed"])
    if (
        "next_filed_date" in admitted
        and not (
            pd.to_datetime(admitted["next_filed_date"]) <= pd.Timestamp(next_year + 2, 12, 31)
        ).any()
    ):
        return None
    _, test, _ = prepare_validation_test(split["val"], split["test"], next_year)
    return next_year if test["next_is_distressed"].notna().any() else None


class CompositeBenchmarkCache:
    """Thread-safe in-memory cache for annual composite benchmarks scoped by database engine."""

    def __init__(self, max_entries: int = 64) -> None:
        """Initialize an empty bounded benchmark cache with hit, miss, and invalidation stats."""
        self._lock = RLock()
        self._max_entries = max_entries
        self._entries: dict[
            tuple[str, int, int | None], tuple[tuple[dict[str, Any], ...], CompositeBenchmark]
        ] = {}
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    @staticmethod
    def _scope(session_or_engine: Session | Engine) -> tuple[str, int]:
        """Identify the bound engine so distinct databases and tests never share cached rows."""
        bind = (
            session_or_engine.get_bind()
            if isinstance(session_or_engine, Session)
            else session_or_engine
        )
        engine = getattr(bind, "engine", bind)
        return (str(getattr(engine, "url", "")), id(engine))

    def get_or_compute(
        self,
        session: Session,
        fiscal_year: int | None,
        loader: Callable[[], list[dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], CompositeBenchmark]:
        """Return cached (peers, benchmark) for this database and year, computing on miss."""
        url, engine_id = self._scope(session)
        key = (url, engine_id, fiscal_year)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self.hits += 1
                return list(cached[0]), cached[1]
        rows = loader()
        benchmark = CompositeBenchmark.from_rows(rows)
        with self._lock:
            if len(self._entries) >= self._max_entries and key not in self._entries:
                self._entries.pop(next(iter(self._entries)))
            self._entries[key] = (tuple(rows), benchmark)
            self.misses += 1
        return rows, benchmark

    def invalidate(self, session_or_engine: Session | Engine | None = None) -> int:
        """Clear cached benchmarks for a database scope, or all entries when scope is omitted."""
        with self._lock:
            if session_or_engine is None:
                removed = len(self._entries)
                self._entries.clear()
            else:
                url, engine_id = self._scope(session_or_engine)
                targets = [
                    key
                    for key in self._entries
                    if key[1] == engine_id
                    or (bool(url) and ":memory:" not in url and key[0] == url)
                ]
                removed = len(targets)
                for key in targets:
                    del self._entries[key]
            if removed:
                self.invalidations += 1
            return removed


_BENCHMARK_CACHE = CompositeBenchmarkCache()


def invalidate_benchmark_cache(session_or_engine: Session | Engine | None = None) -> int:
    """Invalidate cached composite benchmarks after writes or engine disposal."""
    return _BENCHMARK_CACHE.invalidate(session_or_engine)


class FinancialAnalysisService:
    """Compose SEC retrieval, pure ETL, real inference, and transactional persistence."""

    def resolve_company(self, session: Session, identifier: str) -> Company:
        """Resolve canonical CIK or exact case-insensitive ticker from persisted companies."""
        repository = CompanyRepository(session)
        try:
            cik = normalize_cik(identifier)
        except ValueError:
            company = repository.get_by_ticker(identifier)
        else:
            company = repository.get_by_cik(cik)
        if company is None:
            raise SecResourceNotFoundError(f"Company not found: {identifier}")
        require_industrial_company(company.cik, company.sic_code)
        return company

    def _joined_history(
        self,
        session: Session,
        company_id: int | None = None,
        form_type: str | None = None,
        *,
        company_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Join statements to metrics once, preserving all available chronological periods."""
        query = select(FinancialStatement, FinancialMetric).outerjoin(
            FinancialMetric, FinancialMetric.statement_id == FinancialStatement.id
        )
        if company_id is not None:
            query = query.where(FinancialStatement.company_id == company_id)
        if company_ids is not None:
            query = query.where(FinancialStatement.company_id.in_(company_ids))
        if form_type is not None:
            query = query.where(FinancialStatement.form_type == form_type)
        rows = session.execute(
            query.order_by(FinancialStatement.period_end_date, FinancialStatement.form_type)
        ).all()
        result: list[dict[str, Any]] = []
        for statement, metric in rows:
            data = _columns(statement)
            if metric is not None:
                data.update(
                    {
                        key: value
                        for key, value in _columns(metric).items()
                        if key not in {"id", "company_id", "statement_id"}
                    }
                )
            result.append(data)
        return result

    def _latest_prediction(
        self,
        session: Session,
        company_id: int,
        form_type: str | None = None,
        model_version: str | None = None,
        source_statement_id: int | None = None,
    ) -> ModelPrediction | None:
        """Find the newest-created prediction scoped to the requested source form."""
        query = (
            select(ModelPrediction)
            .join(FinancialStatement, ModelPrediction.source_statement_id == FinancialStatement.id)
            .where(ModelPrediction.company_id == company_id)
        )
        if form_type is not None:
            query = query.where(FinancialStatement.form_type == form_type)
        if model_version is not None:
            query = query.where(ModelPrediction.model_version == model_version)
        if source_statement_id is not None:
            query = query.where(ModelPrediction.source_statement_id == source_statement_id)
        return session.scalar(
            query.order_by(ModelPrediction.created_at.desc(), ModelPrediction.id.desc()).limit(1)
        )

    def _summary(
        self,
        company: Company,
        history: list[dict[str, Any]],
        prediction: ModelPrediction | None,
        composite: dict[str, Any] | None = None,
    ) -> CompanySummarySchema:
        """Assemble a nullable snapshot from actual latest statement/metric/prediction rows."""
        values = _columns(company)
        values.update(composite or {})
        if history:
            latest = history[-1]
            values.update(
                {key: latest[key] for key in CompanySummarySchema.model_fields if key in latest}
            )
            values.update(
                latest_fiscal_year=latest["fiscal_year"],
                latest_period_end_date=latest["period_end_date"],
            )
        if prediction is not None:
            values.update(
                distress_probability=prediction.distress_probability,
                risk_level=prediction.risk_level,
                model_version=prediction.model_version,
            )
        return CompanySummarySchema.model_validate(values)

    def get_company_full_analysis(
        self,
        session: Session,
        identifier: str,
        form_type: str = "10-K",
        bundle: ModelArtifactBundle | None = None,
        *,
        include_provenance: bool = False,
    ) -> CompanyFullAnalysisSchema:
        """Read real chronological history and flatten persisted SHAP into the response schema."""
        company = self.resolve_company(session, identifier)
        history = self._joined_history(session, company.id, form_type)
        latest = history[-1] if history else None
        prediction = (
            self._latest_prediction(
                session,
                company.id,
                form_type,
                bundle.model_version if bundle else None,
                latest["id"],
            )
            if latest
            else None
        )
        annual = latest if form_type == "10-K" else None
        if annual:
            peers, benchmark = self._benchmark_and_peers(session)
            composite = benchmark.score(annual, company.sector)
        else:
            peers, composite = [], None
        prior = history[-2] if len(history) >= 2 else None
        detail = None
        if prediction is not None:
            explanation = prediction.shap_explanations or {}
            feature_values = explanation.get("fitted_inputs") or {}
            source = next(
                (row for row in history if row["id"] == prediction.source_statement_id), None
            )
            if (
                not feature_values and source and bundle is not None
                and bundle.model_version == prediction.model_version
            ):
                values = _model_inputs(
                    bundle.classifier.preprocessor,
                    tuple(source[name] for name in bundle.classifier.feature_columns),
                )
                feature_values = dict(zip(bundle.classifier.feature_columns, values, strict=True))
            detail = PredictionDetailSchema.model_validate(
                {
                    **_columns(prediction),
                    "feature_values": feature_values,
                    **{
                        key: explanation[key]
                        for key in (
                            "base_value",
                            "top_drivers",
                            "contributions",
                            "output_space",
                            "raw_margin",
                            "raw_probability",
                        )
                        if key in explanation
                    },
                }
            )
        return CompanyFullAnalysisSchema(
            company=self._summary(company, history, prediction, composite),
            history=[
                HistoricalMetricPointSchema.model_validate(
                    row
                    if include_provenance or index == len(history) - 1
                    else {**row, "field_provenance": None}
                )
                for index, row in enumerate(history)
            ],
            latest_prediction=detail,
            altman_components=self._altman_components(history[-1]) if history else {},
            sector_peer_context=self._sector_peers(peers, company, annual) if annual else None,
            dupont=DupontSchema.model_validate(compute_dupont(history)) if annual else None,
            quality_of_earnings=QualityOfEarningsSchema.model_validate(
                compute_quality_of_earnings(annual, prior)
            )
            if annual
            else None,
            accounting_checklist=AccountingChecklistSchema.model_validate(
                compute_accounting_checklist(annual, prior)
            )
            if annual
            else None,
            health_pillars=HealthPillarsSchema.model_validate(compute_health_pillars(annual))
            if annual
            else None,
            recommendations=[
                ActionableRecommendationSchema.model_validate(item)
                for item in generate_actionable_recommendations(
                    annual,
                    [driver.model_dump() for driver in detail.top_drivers]
                    if detail is not None
                    else None,
                    detail.risk_level if detail is not None else None,
                )
            ]
            if annual
            else [],
        )

    def _benchmark_and_peers(
        self,
        session: Session,
        fiscal_year: int | None = None,
    ) -> tuple[list[dict[str, Any]], CompositeBenchmark]:
        """Return cached eligible annual peers and their CompositeBenchmark for this DB scope."""
        return _BENCHMARK_CACHE.get_or_compute(
            session, fiscal_year, lambda: self._annual_metrics(session, fiscal_year)
        )

    def _annual_metrics(
        self,
        session: Session,
        fiscal_year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read one eligible snapshot per company for shared peer and composite benchmarks."""
        source = latest_annual_statement_id(fiscal_year)
        rows = (
            session.execute(
                select(
                    Company.cik,
                    Company.sic_code,
                    Company.sector,
                    *(getattr(FinancialMetric, name) for name in PEER_METRICS),
                ).join_from(
                    Company,
                    FinancialMetric,
                    FinancialMetric.statement_id == source,
                )
            )
            .mappings()
            .all()
        )
        return [
            dict(row)
            for row in rows
            if row["cik"] not in EXCLUDED_INDUSTRIAL_CIKS
            and not is_financial_institution_sic(row["sic_code"])
        ]

    def _sector_peers(
        self, eligible: list[dict[str, Any]], company: Company, latest: dict[str, Any]
    ) -> SectorPeerContextSchema:
        """Compare the subject to the annual snapshots already read for its benchmark."""
        sector_peers = [
            row
            for row in eligible
            if company.sector not in (None, "Unknown") and row["sector"] == company.sector
        ]
        use_sector = len(sector_peers) >= 5
        cohort = sector_peers if use_sector else eligible
        return SectorPeerContextSchema(
            sector=company.sector,
            cohort="sector" if use_sector else "universe",
            cohort_size=len(cohort),
            metrics={
                name: _peer_metric(
                    latest.get(name),
                    [
                        value
                        for row in cohort
                        if (value := row[name]) is not None and math.isfinite(value)
                    ],
                )
                for name in PEER_METRICS
            },
        )

    def simulate_company(
        self,
        session: Session,
        identifier: str,
        scenario: StressScenarioRequestSchema,
        bundle: ModelArtifactBundle | None,
    ) -> StressSimulationResponseSchema:
        """Recompute statement ratios, features and inference in memory on an annual snapshot."""
        company = self.resolve_company(session, identifier)
        history = self._joined_history(session, company.id, "10-K")
        if not history or bundle is None:
            raise EtlProcessingError("Simulation requires an annual statement and a fitted model")
        latest = history[-1]
        stressed = stress_statement(latest, **scenario.model_dump())
        stressed.update(compute_statement_ratios(stressed, is_manufacturing_sic(company.sic_code)))
        stressed = compute_temporal_features([*history[:-1], stressed])[-1]
        baseline_result, stressed_result = (
            _stress_snapshot(latest, bundle),
            _stress_snapshot(stressed, bundle),
        )
        reference = baseline_result.prediction
        alternative = stressed_result.prediction
        drivers = []
        for name, value in reference.contributions.items():
            changed = alternative.contributions[name]
            if value is not None and changed is not None:
                drivers.append(
                    ShapShiftSchema(
                        feature=name, baseline=value, stressed=changed, delta=changed - value
                    )
                )
        drivers.sort(key=lambda driver: (-abs(driver.delta), driver.feature))
        bounds = bundle.evaluation_report.get("feature_ood_bounds", {})
        outside = [
            name
            for name, (lower, upper) in bounds.items()
            if (value := stressed.get(name)) is not None and not lower <= value <= upper
        ]
        original_z, stressed_z = latest.get("altman_z_score"), stressed.get("altman_z_score")
        assert (
            reference.distress_probability is not None
            and alternative.distress_probability is not None
        )
        return StressSimulationResponseSchema(
            cik=company.cik,
            baseline=baseline_result,
            stressed=stressed_result,
            probability_delta=alternative.distress_probability - reference.distress_probability,
            altman_z_delta=stressed_z - original_z
            if original_z is not None and stressed_z is not None
            else None,
            cluster_shift=baseline_result.metrics.cluster_id != stressed_result.metrics.cluster_id,
            is_ood_scenario=bool(outside) if bounds else None,
            ood_features=outside,
            top_shifted_shap_drivers=drivers[:5],
            assumptions=SCENARIO_ASSUMPTIONS,
        )

    def _altman_components(self, latest: dict[str, Any]) -> dict[str, float | None]:
        """Expose the stored Altman ratio inputs and positive-liability book-equity ratio."""
        equity, liabilities = latest.get("stockholders_equity"), latest.get("total_liabilities")
        return {
            "X1": latest.get("working_capital_ratio"),
            "X2": latest.get("retained_earnings_ratio"),
            "X3": latest.get("ebit_to_assets"),
            "X4": equity / liabilities
            if equity is not None and liabilities is not None and liabilities >= 1e-9
            else None,
            "X5": latest.get("asset_turnover"),
        }

    async def ingest_and_analyze_company(
        self,
        session: Session,
        sec_client: SecEdgarClient,
        identifier: str,
        bundle: ModelArtifactBundle | None = None,
        form_type: str = "10-K",
        force_refresh: bool = False,
    ) -> CompanyFullAnalysisSchema:
        """Fetch SEC resources asynchronously, then run blocking ETL/inference/SQL on a worker."""
        try:
            cik = normalize_cik(identifier)
        except ValueError:
            cik = (await sec_client.resolve_cik(identifier)).cik
        metadata = await sec_client.fetch_company_metadata(cik, force_refresh)
        require_industrial_company(metadata.cik, metadata.sic_code)
        _, payload = await sec_client.fetch_company_facts(cik, force_refresh)
        return await run_in_threadpool(
            self._analyze_and_store, session, metadata, payload, bundle, form_type
        )

    def _analyze_and_store(
        self,
        session: Session,
        metadata: CompanyMetadata,
        payload: dict[str, Any],
        bundle: ModelArtifactBundle | None,
        form_type: str,
    ) -> CompanyFullAnalysisSchema:
        """Commit company, statements, metrics, and annual prediction as one complete unit."""
        pipeline = FinancialEtlPipeline()
        records = pipeline.process_company_facts_payload(
            metadata.cik, payload, metadata.sic_code, exclude_ambiguous=True,
            quarter_report_dates=metadata.quarter_report_dates,
        )
        annual = pipeline.process_company_facts_payload(
            metadata.cik, as_reported_annual_payload(payload), metadata.sic_code
        )
        records = [row for row in records if row["form_type"] != "10-K"] + annual
        if not records:
            raise EtlProcessingError("SEC companyfacts contains no supported financial periods")
        try:
            company = pipeline.persist_to_database(session, metadata, records)
            pipeline.archive_amendments(session, metadata, payload)
            if bundle is not None:
                sync_company_prediction(session, company.id, bundle)
            session.flush()
            invalidate_benchmark_cache(session)
            response = self.get_company_full_analysis(session, company.cik, form_type, bundle)
            session.commit()
            invalidate_benchmark_cache(session)
            return response
        except BaseException:
            session.rollback()
            invalidate_benchmark_cache(session)
            raise

    def _snapshots(
        self,
        session: Session,
        *,
        clustered: bool = False,
        limit: int | None = None,
        offset: int = 0,
        model_version: str | None = None,
        filters: CompanyScreeningFilters | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve each latest snapshot in one bounded SQL query."""
        candidate = ModelPrediction.__table__.alias("latest_prediction")
        forecast = (
            select(candidate.c.id)
            .where(
                candidate.c.company_id == Company.id,
                candidate.c.source_statement_id == FinancialStatement.id,
            )
            .order_by(candidate.c.created_at.desc(), candidate.c.id.desc())
            .limit(1)
            .correlate(Company.__table__, FinancialStatement.__table__)
        )
        if model_version is not None:
            forecast = forecast.where(candidate.c.model_version == model_version)
        identity = (Company.cik, Company.ticker, Company.name)
        risk = ModelPrediction.distress_probability
        columns = (
            (
                *identity,
                FinancialStatement.fiscal_year,
                FinancialMetric.pca_comp_1,
                FinancialMetric.pca_comp_2,
                FinancialMetric.pca_comp_3,
                FinancialMetric.cluster_id,
                FinancialMetric.cluster_label,
                risk,
                FinancialMetric.altman_z_score,
            )
            if clustered
            else (
                *identity,
                Company.sic_code,
                Company.sector,
                FinancialStatement.fiscal_year.label("latest_fiscal_year"),
                FinancialStatement.period_end_date.label("latest_period_end_date"),
                FinancialStatement.filed_date,
                FinancialStatement.accession_number,
                *(getattr(FinancialMetric, name) for name in FINANCIAL_RATIOS),
                FinancialMetric.altman_z_score,
                FinancialMetric.altman_zone,
                FinancialMetric.cluster_id,
                FinancialMetric.cluster_label,
                risk,
                ModelPrediction.risk_level,
                ModelPrediction.model_version,
            )
        )
        query = (
            select(*columns)
            .join_from(
                Company,
                FinancialStatement,
                FinancialStatement.id == latest_annual_statement_id(),
                isouter=True,
            )
            .join_from(
                FinancialStatement,
                FinancialMetric,
                FinancialMetric.statement_id == FinancialStatement.id,
                isouter=True,
            )
            .join_from(
                Company,
                ModelPrediction,
                ModelPrediction.id == forecast.scalar_subquery(),
                isouter=True,
            )
            .order_by(Company.cik)
        )
        if clustered:
            query = query.where(
                FinancialMetric.pca_comp_1.is_not(None), FinancialMetric.cluster_id.is_not(None)
            )
        if filters is not None:
            query = query.where(*_screening_conditions(filters))
        return [dict(row) for row in session.execute(query.limit(limit).offset(offset)).mappings()]

    def list_company_summaries(
        self,
        session: Session,
        limit: int = 100,
        offset: int = 0,
        model_version: str | None = None,
        *,
        filters: CompanyScreeningFilters | None = None,
    ) -> list[CompanySummarySchema]:
        """Read a paginated snapshot without loading every historical period."""
        filtered = filters is not None and bool(filters.model_dump(exclude_none=True))
        rows = self._snapshots(
            session, limit=limit, offset=offset, model_version=model_version,
            filters=filters if filtered else None,
        )
        _, benchmark = self._benchmark_and_peers(session)
        return [
            CompanySummarySchema.model_validate({**row, **benchmark.score(row, row["sector"])})
            for row in rows
        ]

    def get_cluster_map_points(
        self,
        session: Session,
        model_version: str | None = None,
    ) -> list[ClusterPointSchema]:
        """Read one latest assigned cluster point per company."""
        return [
            ClusterPointSchema.model_validate(row)
            for row in self._snapshots(session, clustered=True, model_version=model_version)
        ]

    def compare_companies(
        self,
        session: Session,
        identifiers: str,
        common_fiscal_year: int | None,
        bundle: ModelArtifactBundle | None,
    ) -> CompanyComparisonResponseSchema:
        """Compare annual observations and only attach persisted origin-matched forecasts."""
        requested = [value.strip() for value in identifiers.split(",")]
        if not all(requested):
            raise EtlProcessingError("Provide 2 to 4 distinct company tickers or CIKs")
        companies: dict[int, Company] = {}
        for value in dict.fromkeys(token.upper() for token in requested):
            company = self.resolve_company(session, value)
            companies[company.id] = company
        if not 2 <= len(companies) <= 4:
            raise EtlProcessingError("Select 2 to 4 distinct companies")
        histories: dict[int, list[dict[str, Any]]] = {key: [] for key in companies}
        for record in self._joined_history(session, form_type="10-K", company_ids=list(companies)):
            if common_fiscal_year is None or record["fiscal_year"] <= common_fiscal_year:
                histories[record["company_id"]].append(record)
        latest = {}
        for key, company in companies.items():
            history = histories[key]
            if not history or (
                common_fiscal_year is not None and history[-1]["fiscal_year"] != common_fiscal_year
            ):
                period = (
                    f"FY {common_fiscal_year}" if common_fiscal_year is not None else "any year"
                )
                raise EtlProcessingError(
                    f"No annual statement for {company.ticker or company.cik} in {period}"
                )
            latest[key] = history[-1]
        version = bundle.model_version if bundle else None
        predictions = (
            {
                prediction.source_statement_id: prediction
                for prediction in session.scalars(
                    select(ModelPrediction).where(
                        ModelPrediction.source_statement_id.in_(
                            [row["id"] for row in latest.values()]
                        ),
                        ModelPrediction.model_version == version,
                    )
                )
            }
            if version is not None
            else {}
        )
        _, benchmark = self._benchmark_and_peers(session, common_fiscal_year)
        items = []
        series = {}
        for key, company in companies.items():
            row, history = latest[key], histories[key]
            forecast = predictions.get(row["id"])
            items.append(
                CompanyComparisonItemSchema.model_validate(
                    {
                        **row,
                        "field_provenance": None,
                        **{
                            name: getattr(company, name)
                            for name in ("cik", "ticker", "name", "sector")
                        },
                        **benchmark.score(row, company.sector),
                        **{
                            name: getattr(forecast, name, None)
                            for name in (
                                *FORECAST_FIELDS,
                                "model_version",
                                "target_fiscal_year",
                                "distress_probability",
                            )
                        },
                        "altman_model_variant": "Z"
                        if is_manufacturing_sic(company.sic_code)
                        else "Z″",
                        "dupont": compute_dupont(history),
                        "quality_of_earnings": compute_quality_of_earnings(
                            row,
                            history[-2] if len(history) >= 2 else None,
                        ),
                    }
                )
            )
            series[company.cik] = [
                HistoricalMetricPointSchema.model_validate({**record, "field_provenance": None})
                for record in history
            ]
        medians = {}
        for name in (
            *FINANCIAL_RATIOS,
            "altman_z_score",
            "composite_health_score",
            "distress_probability",
            *FORECAST_FIELDS,
        ):
            observed = [
                metric_value
                for item in items
                if (metric_value := _finite(getattr(item, name))) is not None
            ]
            medians[name] = median(observed) if observed else None
        for name, values in {
            "roe_dupont_avg": [item.dupont.roe_dupont_avg for item in items],
            "cash_conversion_qoe": [item.quality_of_earnings.cash_conversion_qoe for item in items],
        }.items():
            available = [item for item in values if item is not None]
            medians[name] = median(available) if available else None
        return CompanyComparisonResponseSchema(
            requested_identifiers=requested,
            period_policy="latest_annual" if common_fiscal_year is None else "common_fiscal_year",
            common_fiscal_year=common_fiscal_year,
            active_model_version=version,
            companies=items,
            cohort_medians=medians,
            historical_series=series,
        )

    def train_models(
        self,
        session: Session,
        options: TrainModelRequest,
        settings: Settings,
        state: ModelRegistryState,
    ) -> ModelEvaluationResponseSchema:
        """Train on persisted annual panel rows, save completely, then activate the bundle."""
        with state.training_lock:
            records = self._joined_history(session, form_type="10-K")
            if not records:
                raise ModelPipelineError(
                    "No persisted annual financial panel is available for training"
                )
            if (settings.model_path / options.model_version).exists():
                raise ModelPipelineError("Requested model version already exists")
            companies = {company.id: company for company in session.scalars(select(Company))}
            panel = industrial_panel(
                pd.DataFrame(
                    [
                        {
                            **row,
                            "cik": companies[row["company_id"]].cik,
                            "sic_code": companies[row["company_id"]].sic_code,
                        }
                        for row in records
                    ]
                )
            )
            bundle = train_and_evaluate_pipeline(
                panel,
                options.train_end_year,
                options.model_version,
                settings.random_seed,
                validation_end_year=(
                    options.validation_end_year
                    if options.validation_end_year is not None
                    else _default_validation_year(panel, options.train_end_year)
                ),
                imbalance_strategy=options.imbalance_strategy,
            )
            for company_id in sorted(panel["company_id"].unique()):
                sync_company_prediction(session, int(company_id), bundle)
            destination = save_bundle(bundle, settings.model_path, pending=True)
            session.commit()
            invalidate_benchmark_cache(session)
            atomic_write_json(
                settings.model_path / "latest.json",
                {
                    "model_version": bundle.model_version,
                    "bundle_dir": bundle.model_version,
                    "created_at": bundle.created_at,
                    "mode": "api",
                },
            )
            state.set(bundle)
            (destination / ".unpublished").unlink(missing_ok=True)
            return ModelEvaluationResponseSchema(
                model_version=bundle.model_version,
                created_at=bundle.created_at,
                evaluation_report=bundle.evaluation_report,
            )

    def predict_manual_statement(
        self,
        payload: ManualStatementInputSchema,
        bundle: ModelArtifactBundle | None,
    ) -> ManualPredictionResponseSchema:
        """Compute ratios, Altman Z, PCA cluster, and TreeSHAP for user-entered figures."""
        if bundle is None:
            raise ModelPipelineError("No active model bundle is loaded")
        current_stmt: dict[str, Any] = {
            "cik": "MANUAL0001",
            "fiscal_year": payload.fiscal_year,
            "fiscal_period": "FY",
            "form_type": "10-K",
            "period_end_date": date(payload.fiscal_year, 12, 31),
            "filed_date": date(payload.fiscal_year, 12, 31),
            "total_assets": payload.total_assets,
            "current_assets": payload.current_assets,
            "total_liabilities": payload.total_liabilities,
            "current_liabilities": payload.current_liabilities,
            "stockholders_equity": payload.stockholders_equity,
            "retained_earnings": payload.retained_earnings,
            "revenues": payload.revenues,
            "operating_income": payload.operating_income,
            "net_income": payload.net_income,
            "operating_cash_flow": payload.operating_cash_flow,
            "cash_and_equivalents": payload.cash_and_equivalents,
            "interest_expense": payload.interest_expense,
            "capex": payload.capex,
            "eps_basic": payload.eps_diluted,
            "eps_diluted": payload.eps_diluted,
            "field_provenance": {},
        }
        current_ratios = compute_statement_ratios(
            current_stmt, is_manufacturing=payload.is_manufacturing
        )
        current_altman = compute_altman_z_score(
            current_stmt, is_manufacturing=payload.is_manufacturing
        )
        records: list[dict[str, Any]] = []
        prior_enriched: dict[str, Any] | None = None
        has_prior = any(
            getattr(payload, field) is not None
            for field in (
                "prior_total_assets",
                "prior_current_assets",
                "prior_total_liabilities",
                "prior_current_liabilities",
                "prior_stockholders_equity",
                "prior_revenues",
                "prior_operating_income",
                "prior_net_income",
                "prior_operating_cash_flow",
            )
        )
        if has_prior:
            prior_stmt: dict[str, Any] = {
                "cik": "MANUAL0001",
                "fiscal_year": payload.fiscal_year - 1,
                "fiscal_period": "FY",
                "form_type": "10-K",
                "period_end_date": date(payload.fiscal_year - 1, 12, 31),
                "filed_date": date(payload.fiscal_year - 1, 12, 31),
                "total_assets": payload.prior_total_assets,
                "current_assets": payload.prior_current_assets,
                "total_liabilities": payload.prior_total_liabilities,
                "current_liabilities": payload.prior_current_liabilities,
                "stockholders_equity": payload.prior_stockholders_equity,
                "revenues": payload.prior_revenues,
                "operating_income": payload.prior_operating_income,
                "net_income": payload.prior_net_income,
                "operating_cash_flow": payload.prior_operating_cash_flow,
                "field_provenance": {},
            }
            prior_ratios = compute_statement_ratios(
                prior_stmt, is_manufacturing=payload.is_manufacturing
            )
            prior_enriched = {**prior_stmt, **prior_ratios}
            records.append(prior_enriched)
        records.append({**current_stmt, **current_ratios, **current_altman})
        enriched = compute_temporal_features(records)[-1]
        scored = predict_for_company_records(bundle, [enriched])
        shap_payload = scored.get("shap_explanations") or {}
        prediction = PredictionDetailSchema.model_validate(
            {
                **scored,
                **shap_payload,
                "target_fiscal_year": payload.fiscal_year + 1,
                "target_fiscal_period": "FY",
            }
        )
        bounds = bundle.evaluation_report.get("feature_ood_bounds")
        ood_features: list[str] = []
        if isinstance(bounds, dict):
            for name, limits in bounds.items():
                val = _finite(enriched.get(name))
                if (
                    val is not None
                    and isinstance(limits, (list, tuple))
                    and len(limits) == 2
                    and (val < limits[0] or val > limits[1])
                ):
                    ood_features.append(name)
        ratio_keys = (
            "roa",
            "roe",
            "eps",
            "debt_ratio",
            "debt_to_equity",
            "current_ratio",
            "operating_margin",
            "ocf_ratio",
            "working_capital_ratio",
            "retained_earnings_ratio",
            "ebit_to_assets",
            "asset_turnover",
            "cash_ratio",
            "interest_coverage",
            "fcf_to_liabilities",
            "roa_yoy_delta",
            "roe_yoy_delta",
            "debt_ratio_yoy_delta",
            "ocf_ratio_yoy_delta",
            "negative_ocf_streak",
        )
        equity_to_liabilities = (
            payload.stockholders_equity / payload.total_liabilities
            if payload.stockholders_equity is not None and payload.total_liabilities > 0
            else None
        )
        altman_components: dict[str, float | None] = {
            "X1": _finite(enriched.get("working_capital_ratio")),
            "X2": _finite(enriched.get("retained_earnings_ratio")),
            "X3": _finite(enriched.get("ebit_to_assets")),
            "X4": _finite(equity_to_liabilities),
            "X5": _finite(enriched.get("asset_turnover")),
        }
        selected_eval = (
            bundle.evaluation_report.get("classification_selected")
            or bundle.evaluation_report.get("classification_xgboost")
            or {}
        )
        return ManualPredictionResponseSchema(
            company_name=payload.company_name.strip(),
            fiscal_year=payload.fiscal_year,
            is_manufacturing=payload.is_manufacturing,
            ratios={key: _finite(enriched.get(key)) for key in ratio_keys},
            altman_z_score=_finite(current_altman.get("altman_z_score")),
            altman_zone=current_altman.get("altman_zone"),
            altman_components=altman_components,
            cluster_id=scored.get("cluster_id"),
            cluster_label=scored.get("cluster_label"),
            prediction=prediction,
            classification_threshold=_finite(selected_eval.get("threshold")),
            is_ood_scenario=bool(ood_features) if isinstance(bounds, dict) else None,
            ood_features=ood_features,
            health_pillars=HealthPillarsSchema.model_validate(compute_health_pillars(enriched)),
            dupont=DupontSchema.model_validate(compute_dupont(records)),
            quality_of_earnings=QualityOfEarningsSchema.model_validate(
                compute_quality_of_earnings(enriched, prior_enriched)
            ),
            accounting_checklist=AccountingChecklistSchema.model_validate(
                compute_accounting_checklist(enriched, prior_enriched)
            ),
            recommendations=[
                ActionableRecommendationSchema.model_validate(item)
                for item in generate_actionable_recommendations(
                    enriched,
                    [driver.model_dump() for driver in prediction.top_drivers],
                    prediction.risk_level,
                )
            ],
        )

    def predict_batch_statements(
        self,
        payload: BatchPredictionRequestSchema,
        bundle: ModelArtifactBundle | None,
    ) -> BatchPredictionResponseSchema:
        """Score a portfolio of financial statements and aggregate risk distribution."""
        if bundle is None:
            raise ModelPipelineError("No active model bundle is loaded")
        results: list[BatchPredictionItemSchema] = []
        risk_counts: dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        probs: list[float] = []
        health_scores: list[float] = []
        threshold: float | None = None
        for item in payload.items:
            scored = self.predict_manual_statement(item, bundle)
            if threshold is None:
                threshold = scored.classification_threshold
            prob = _finite(scored.prediction.distress_probability)
            if prob is not None:
                probs.append(prob)
            h_score = (
                _finite(scored.health_pillars.overall_score)
                if scored.health_pillars is not None
                else None
            )
            if h_score is not None:
                health_scores.append(h_score)
            r_level = scored.prediction.risk_level
            if r_level in risk_counts:
                risk_counts[r_level] += 1
            top_driver = next(
                (
                    d.feature
                    for d in scored.prediction.top_drivers
                    if (d.shap_value is not None and d.shap_value > 0)
                    or d.direction == "INCREASES_RISK"
                ),
                scored.prediction.top_drivers[0].feature
                if scored.prediction.top_drivers
                else None,
            )
            top_rec = scored.recommendations[0].action_vi if scored.recommendations else None
            results.append(
                BatchPredictionItemSchema(
                    company_name=scored.company_name,
                    fiscal_year=scored.fiscal_year,
                    is_manufacturing=scored.is_manufacturing,
                    distress_probability=prob,
                    risk_level=r_level,
                    overall_health_score=h_score,
                    overall_health_grade=(
                        scored.health_pillars.overall_grade
                        if scored.health_pillars is not None
                        else "UNSCORED"
                    ),
                    altman_z_score=scored.altman_z_score,
                    altman_zone=scored.altman_zone,
                    cluster_id=scored.cluster_id,
                    cluster_label=scored.cluster_label,
                    roa=scored.ratios.get("roa"),
                    roe=scored.ratios.get("roe"),
                    debt_ratio=scored.ratios.get("debt_ratio"),
                    current_ratio=scored.ratios.get("current_ratio"),
                    ocf_ratio=scored.ratios.get("ocf_ratio"),
                    top_risk_driver=top_driver,
                    top_recommendation_vi=top_rec,
                )
            )
        return BatchPredictionResponseSchema(
            model_version=bundle.model_version,
            classification_threshold=threshold,
            total_companies=len(results),
            risk_counts=risk_counts,
            average_distress_probability=sum(probs) / len(probs) if probs else None,
            average_health_score=(
                sum(health_scores) / len(health_scores) if health_scores else None
            ),
            results=results,
        )
