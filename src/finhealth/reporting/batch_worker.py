"""DB-backed asynchronous Excel batch assessment worker with per-row error isolation."""

import logging
from datetime import date
from math import isfinite
from pathlib import PurePath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.services_org import (
    DEFAULT_FALLBACK_MODEL_VERSION,
    FI_EXCLUSION_REASON_VI,
    RISK_TIER_LABELS_VI,
    _score_statement_with_adapter,
)
from finhealth.db.base import utc_now
from finhealth.db.batch_models import OrgBatchJob, OrgBatchJobRow
from finhealth.etl.accounting_validator import validate_financial_statement
from finhealth.etl.altman import compute_altman_assessment
from finhealth.etl.driver_narrative import translate_drivers_to_business
from finhealth.etl.financial_ratios import _finite, _safe_div, compute_statement_ratios
from finhealth.reporting.batch_excel import parse_batch_excel_bytes

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str | None) -> str:
    """Keep only a safe basename capped to 255 characters."""
    raw = (filename or "batch_upload.xlsx").strip()
    name = PurePath(raw).name or "batch_upload.xlsx"
    return name[:255]


def create_batch_job_from_upload(
    db: Session,
    *,
    org_id: int,
    user_id: int,
    filename: str | None,
    raw_bytes: bytes,
) -> OrgBatchJob:
    """Validate an uploaded batch workbook and enqueue OrgBatchJob + OrgBatchJobRow records."""
    parsed = parse_batch_excel_bytes(raw_bytes)
    job = OrgBatchJob(
        organization_id=org_id,
        created_by=user_id,
        filename=_sanitize_filename(filename),
        status="queued",
        total_rows=len(parsed.rows),
        processed_rows=0,
        succeeded_rows=0,
        failed_rows=0,
    )
    db.add(job)
    db.flush()

    for row in parsed.rows:
        db.add(
            OrgBatchJobRow(
                job_id=job.id,
                organization_id=org_id,
                row_index=row.row_index,
                company_name=row.company_name[:255],
                tax_code=row.tax_code,
                fiscal_year=row.fiscal_year,
                status="pending",
                input_json=row.to_input_json(),
            )
        )

    db.commit()
    db.refresh(job)
    return job


def _build_batch_analytical_record(
    input_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float | None]]:
    """Scale raw batch numeric inputs and compute normalized financial ratios."""
    unit_scale = int(input_payload.get("unit_scale") or 1)
    raw_nums: dict[str, Any] = input_payload.get("numeric_fields") or {}
    scaled: dict[str, float | None] = {}
    for key, val in raw_nums.items():
        num = _finite(val)
        scaled[key] = float(num) * float(unit_scale) if num is not None else None

    revenues_val = scaled.get("revenues")
    cogs_val = scaled.get("cost_of_goods_sold")
    if scaled.get("gross_profit") is None and revenues_val is not None and cogs_val is not None:
        scaled["gross_profit"] = revenues_val - cogs_val
    ebit_val = scaled.get("operating_income")
    da_val = scaled.get("depreciation_amortization")
    if scaled.get("ebitda") is None and ebit_val is not None and da_val is not None:
        scaled["ebitda"] = ebit_val + da_val

    fiscal_year = int(input_payload.get("fiscal_year") or 2025)
    business_type = str(input_payload.get("business_type") or "manufacturing")
    is_mfg = business_type == "manufacturing"

    raw_record: dict[str, Any] = {
        **scaled,
        "fiscal_year": fiscal_year,
        "fiscal_period": "FY",
        "form_type": "10-K",
        "filed_date": date(fiscal_year, 12, 31),
        "period_end_date": date(fiscal_year, 12, 31),
        "accounting_standard": str(input_payload.get("accounting_standard") or "TT99_2025"),
        "currency": str(input_payload.get("currency") or "VND"),
        "audit_status": str(input_payload.get("audit_status") or "unaudited"),
    }
    ratios = compute_statement_ratios(raw_record, is_manufacturing=is_mfg)

    assets = _finite(scaled.get("total_assets"))
    liabilities = _finite(scaled.get("total_liabilities"))
    current_assets = _finite(scaled.get("current_assets"))
    current_liabilities = _finite(scaled.get("current_liabilities"))
    equity = _finite(scaled.get("stockholders_equity"))
    revenues = _finite(scaled.get("revenues"))
    cogs = _finite(scaled.get("cost_of_goods_sold"))
    inventory = _finite(scaled.get("inventory"))
    receivables = _finite(scaled.get("accounts_receivable"))
    da = _finite(scaled.get("depreciation_amortization"))
    ebitda = _finite(scaled.get("ebitda"))
    gross_profit = _finite(scaled.get("gross_profit"))

    equity_to_assets = _safe_div(equity, assets, True)
    is_neg_eq = bool(equity is not None and equity <= 0.0)
    extended: dict[str, Any] = {
        "gross_margin": _safe_div(gross_profit, revenues, True),
        "ebitda_margin": _safe_div(ebitda, revenues, True),
        "ebitda_to_assets": _safe_div(ebitda, assets, True),
        "opex_to_revenue": _safe_div(scaled.get("operating_expenses"), revenues, True),
        "quick_ratio": (
            _safe_div(current_assets - inventory, current_liabilities, True)
            if current_assets is not None and inventory is not None
            else None
        ),
        "short_term_debt_share": _safe_div(current_liabilities, liabilities, True),
        "long_term_debt_to_assets": _safe_div(scaled.get("long_term_debt"), assets, True),
        "equity_to_assets": equity_to_assets,
        "is_negative_equity": is_neg_eq,
        "inventory_to_assets": _safe_div(inventory, assets, True),
        "receivables_to_revenue": _safe_div(receivables, revenues, True),
        "depreciation_to_assets": _safe_div(da, assets, True),
        "dso_days": (
            val * 365.0 if (val := _safe_div(receivables, revenues, True)) is not None else None
        ),
        "dio_days": (
            val * 365.0 if (val := _safe_div(inventory, cogs, True)) is not None else None
        ),
        "cash_conversion_qoe": _safe_div(
            scaled.get("operating_cash_flow"), scaled.get("net_income"), True
        ),
    }
    record = {**raw_record, **extended, **ratios}
    for key, val in extended.items():
        if record.get(key) is None and val is not None:
            record[key] = val
    record["is_negative_equity"] = is_neg_eq
    return record, scaled


def _score_single_batch_row(
    row: OrgBatchJobRow,
    *,
    model_registry: ModelRegistryState | None,
) -> str | None:
    """Process one OrgBatchJobRow with complete error isolation; returns model_version if scored."""
    payload = row.input_json or {}
    fiscal_year = payload.get("fiscal_year")
    if fiscal_year is None or not (1990 <= int(fiscal_year) <= 2100):
        row.status = "failed"
        row.error_message = "Thiếu hoặc sai năm tài chính hợp lệ (1990–2100)."
        return None

    business_type = str(payload.get("business_type") or "manufacturing")
    if business_type == "financial_institution":
        row.status = "excluded"
        row.pd_12m = None
        row.health_score = None
        row.risk_tier = None
        row.confidence_level = None
        row.error_message = FI_EXCLUSION_REASON_VI[:500]
        row.result_json = {"scoring_eligible": False, "reason_vi": FI_EXCLUSION_REASON_VI}
        return None

    record, scaled = _build_batch_analytical_record(payload)
    validation = validate_financial_statement(scaled)
    if not validation.is_balanced:
        error_msgs = [issue.message for issue in validation.errors]
        joined = "; ".join(error_msgs) or "Báo cáo tài chính không đạt kiểm tra cân đối."
        row.status = "failed"
        row.error_message = joined[:500]
        row.result_json = {"validation": validation.to_dict()}
        return None

    ocf = _finite(record.get("operating_cash_flow"))
    neg_ocf_streak = 1 if (ocf is not None and ocf < 0.0) else 0
    scored = _score_statement_with_adapter(
        record,
        prior_record=None,
        has_prior=False,
        negative_ocf_streak=neg_ocf_streak,
        audit_status=str(payload.get("audit_status") or "unaudited"),
        model_registry=model_registry,
    )
    altman = compute_altman_assessment(
        record,
        business_type=business_type,
        listing_status=str(payload.get("listing_status") or "unlisted"),
    )
    drivers = translate_drivers_to_business(scored["shap_explanation"], record)
    bottlenecks = drivers.get("bottlenecks") or []
    top_bottleneck = (
        str(bottlenecks[0]["headline_vi"])[:300]
        if bottlenecks
        else None
    )

    row.status = "succeeded"
    row.pd_12m = float(scored["pd_12m"])
    row.health_score = float(scored["health_score"])
    row.risk_tier = str(scored["risk_tier"])
    row.confidence_level = str(scored["confidence"]["level"])
    row.top_bottleneck_vi = top_bottleneck
    row.error_message = None
    row.result_json = {
        "model_version": scored["model_version"],
        "risk_label_vi": RISK_TIER_LABELS_VI.get(scored["risk_tier"], scored["risk_tier"]),
        "altman_variant": altman["variant"],
        "altman_z_score": altman["score"],
        "altman_zone": altman["zone"],
        "cash_flow_overlay_triggered": bool(scored["cash_flow_overlay"]["triggered"]),
        "ratios": {
            "current_ratio": _finite(record.get("current_ratio")),
            "debt_ratio": _finite(record.get("debt_ratio")),
            "roa": _finite(record.get("roa")),
            "roe": _finite(record.get("roe")),
            "operating_margin": _finite(record.get("operating_margin")),
        },
    }
    return str(scored["model_version"])


def process_batch_job(
    db: Session,
    *,
    job_id: int,
    model_registry: ModelRegistryState | None = None,
) -> OrgBatchJob:
    """Execute a queued OrgBatchJob, isolating per-row errors and persisting progress."""
    job = db.get(OrgBatchJob, job_id)
    if job is None:
        raise ValueError(f"Batch job not found: {job_id}")

    job.status = "running"
    job.started_at = utc_now()
    job.processed_rows = 0
    job.succeeded_rows = 0
    job.failed_rows = 0
    job.error_message = None
    db.commit()

    rows = list(
        db.execute(
            select(OrgBatchJobRow)
            .where(
                OrgBatchJobRow.job_id == job.id,
                OrgBatchJobRow.organization_id == job.organization_id,
            )
            .order_by(OrgBatchJobRow.row_index.asc())
        ).scalars()
    )

    active_model_version: str | None = None
    tier_dist: dict[str, int] = {"STRONG": 0, "STABLE": 0, "WATCH": 0, "CRITICAL": 0}
    pds: list[float] = []
    scores: list[float] = []
    excluded_rows = 0

    for row in rows:
        try:
            mv = _score_single_batch_row(row, model_registry=model_registry)
            if mv is not None:
                active_model_version = mv
        except Exception as exc:  # noqa: BLE001 — isolate unexpected row-level errors
            logger.warning(
                "Batch job %s row %s failed: %s", job.id, row.row_index, type(exc).__name__
            )
            row.status = "failed"
            row.error_message = f"Lỗi xử lý dòng dữ liệu: {exc}"[:500]

        job.processed_rows += 1
        if row.status == "succeeded":
            job.succeeded_rows += 1
            if row.risk_tier in tier_dist:
                tier_dist[row.risk_tier] += 1
            if row.pd_12m is not None and isfinite(row.pd_12m):
                pds.append(float(row.pd_12m))
            if row.health_score is not None and isfinite(row.health_score):
                scores.append(float(row.health_score))
        elif row.status == "excluded":
            excluded_rows += 1
        else:
            job.failed_rows += 1

    job.model_version = active_model_version or DEFAULT_FALLBACK_MODEL_VERSION
    job.summary_json = {
        "tier_distribution": tier_dist,
        "avg_pd_12m": round(sum(pds) / len(pds), 6) if pds else None,
        "avg_health_score": round(sum(scores) / len(scores), 2) if scores else None,
        "excluded_rows": excluded_rows,
        "succeeded_rows": job.succeeded_rows,
        "failed_rows": job.failed_rows,
    }
    job.status = "completed"
    job.finished_at = utc_now()
    db.commit()
    db.refresh(job)
    return job


def run_batch_job_background(
    session_factory: sessionmaker[Session],
    job_id: int,
    model_registry: ModelRegistryState | None = None,
) -> None:
    """BackgroundTasks entrypoint executing a batch job in an isolated DB session."""
    with session_factory() as session:
        try:
            process_batch_job(session, job_id=job_id, model_registry=model_registry)
        except Exception as exc:  # noqa: BLE001 — never crash background worker loop
            logger.exception("Unhandled batch worker error for job %s", job_id)
            session.rollback()
            job = session.get(OrgBatchJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = f"Lỗi hệ thống khi xử lý lô: {type(exc).__name__}"[:500]
                job.finished_at = utc_now()
                session.commit()
