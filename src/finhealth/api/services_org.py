"""Organization-scoped risk analytics orchestrator: scoring, M11 history, S01 peers, C03 compare."""

from collections.abc import Mapping, Sequence
from datetime import date
from importlib import import_module
from math import exp, isfinite, log1p
from statistics import median
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.schemas.analytics import (
    LEGAL_DISCLAIMER_VI,
    AltmanView,
    AssessmentSummaryView,
    BusinessDriverView,
    CashFlowOverlayView,
    CompanyAssessmentView,
    ConfidenceView,
    DiagnosticsView,
    DriversSplitView,
    MultiPeriodHistoryPointView,
    OrgCompanyMetaView,
    OrgCompareCompanyItemView,
    OrgCompareResponseView,
    PeerContextView,
    PeerMetricPositionView,
    PillarsOverviewView,
)
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.org_models import OrgAssessment, OrgCompany, OrgFinancialStatement
from finhealth.db.repositories import latest_annual_statement_id
from finhealth.etl.altman import compute_altman_assessment
from finhealth.etl.corporate_finance import (
    compute_accounting_checklist,
    compute_dupont,
    compute_health_pillars_v2,
    compute_quality_of_earnings,
)
from finhealth.etl.driver_narrative import translate_drivers_to_business
from finhealth.etl.financial_ratios import _finite, _safe_div, compute_statement_ratios
from finhealth.etl.metric_catalog import METRIC_CATALOG
from finhealth.ml.feature_contracts import (
    CORE_BANKRUPTCY_FEATURES,
    ConfidenceLevel,
    RiskTier,
    ScoringMode,
)

RULE_VERSION = "v1.0"
DEFAULT_FALLBACK_MODEL_VERSION = "v2.0.0-deterministic-adapter"
MIN_PEER_COHORT_SIZE = 5

FI_EXCLUSION_REASON_VI = (
    "Mô hình đánh giá rủi ro phá sản doanh nghiệp phi tài chính không áp dụng cho "
    "Ngân hàng, Bảo hiểm và Tổ chức tài chính."
)

RISK_TIER_LABELS_VI: dict[RiskTier, str] = {
    "STRONG": "Vững mạnh",
    "STABLE": "Ổn định",
    "WATCH": "Cần theo dõi sát",
    "CRITICAL": "Nguy cơ khủng hoảng cao",
}

_COMPARE_CORE_METRICS: tuple[str, ...] = (
    "current_ratio",
    "quick_ratio",
    "debt_ratio",
    "equity_to_assets",
    "interest_coverage",
    "gross_margin",
    "operating_margin",
    "roa",
    "roe",
    "asset_turnover",
    "ocf_ratio",
    "cash_conversion_qoe",
)

_VSIC_TO_SEC_SECTOR: dict[str, str] = {
    "A": "Agriculture",
    "B": "Mining",
    "C": "Manufacturing",
    "D": "Utilities",
    "E": "Utilities",
    "F": "Construction",
    "G": "Retail Trade",
    "H": "Transportation",
    "I": "Services",
    "J": "Information",
    "L": "Real Estate",
    "M": "Services",
    "N": "Services",
}

_SECTOR_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sản xuất", "chế biến", "chế tạo", "công nghiệp", "manufactur"), "Manufacturing"),
    (("xây dựng", "xây lắp", "hạ tầng", "construct"), "Construction"),
    (("bán lẻ", "bán buôn", "thương mại", "retail", "wholesale", "trade"), "Retail Trade"),
    (
        ("công nghệ", "phần mềm", "viễn thông", "thông tin", "tech", "software", "info"),
        "Information",
    ),
    (("vận tải", "logistics", "kho bãi", "hàng không", "transport"), "Transportation"),
    (("bất động sản", "địa ốc", "real estate"), "Real Estate"),
    (("điện", "nước", "năng lượng", "utilit"), "Utilities"),
    (("khai khoáng", "dầu khí", "mining"), "Mining"),
    (("nông nghiệp", "thủy sản", "lâm nghiệp", "agricult"), "Agriculture"),
    (("dịch vụ", "du lịch", "y tế", "giáo dục", "service"), "Services"),
)

_STATEMENT_COLUMNS: tuple[str, ...] = (
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "total_liabilities",
    "current_liabilities",
    "short_term_debt",
    "long_term_debt",
    "accounts_payable",
    "stockholders_equity",
    "retained_earnings",
    "revenues",
    "cost_of_goods_sold",
    "gross_profit",
    "operating_expenses",
    "operating_income",
    "depreciation_amortization",
    "ebitda",
    "interest_expense",
    "net_income",
    "operating_cash_flow",
    "capex",
    "market_value_equity",
    "eps_basic",
    "eps_diluted",
)


def classify_bankruptcy_tier(pd_12m: float) -> RiskTier:
    """Map calibrated 12-month bankruptcy probability to credit-aligned risk tiers."""
    if not isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < 0.01:
        return "STRONG"
    if pd_12m < 0.03:
        return "STABLE"
    if pd_12m < 0.08:
        return "WATCH"
    return "CRITICAL"


def map_pd_to_health_score(pd_12m: float) -> float:
    """Convert calibrated PD monotonically onto [0, 100] aligned with the four risk bands."""
    if not isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < 0.01:
        return round(100.0 - 20.0 * (pd_12m / 0.01), 2)
    if pd_12m < 0.03:
        return round(80.0 - 20.0 * ((pd_12m - 0.01) / 0.02), 2)
    if pd_12m < 0.08:
        return round(60.0 - 25.0 * ((pd_12m - 0.03) / 0.05), 2)
    tail = min(1.0, log1p((pd_12m - 0.08) / 0.08) / log1p((1.0 - 0.08) / 0.08))
    return round(max(0.0, 35.0 * (1.0 - tail)), 2)


def _statement_to_record(
    stmt: OrgFinancialStatement,
    company: OrgCompany,
    prior_stmt: OrgFinancialStatement | None = None,
) -> dict[str, Any]:
    """Normalize an OrgFinancialStatement plus extended ratios into a flat analytical dict."""
    raw: dict[str, Any] = {col: getattr(stmt, col, None) for col in _STATEMENT_COLUMNS}
    raw["fiscal_year"] = stmt.fiscal_year
    raw["fiscal_period"] = stmt.fiscal_period
    raw["form_type"] = "10-K"
    raw["filed_date"] = stmt.period_end_date or date(stmt.fiscal_year, 12, 31)
    raw["period_end_date"] = stmt.period_end_date or date(stmt.fiscal_year, 12, 31)
    raw["accounting_standard"] = stmt.accounting_standard
    raw["currency"] = stmt.currency
    raw["audit_status"] = stmt.audit_status

    is_mfg = company.business_type == "manufacturing"
    ratios = compute_statement_ratios(raw, is_manufacturing=is_mfg)

    # Ensure extended V1.0 ratios exist even before Lane B merges into financial_ratios.py.
    assets = _finite(raw.get("total_assets"))
    liabilities = _finite(raw.get("total_liabilities"))
    current_assets = _finite(raw.get("current_assets"))
    current_liabilities = _finite(raw.get("current_liabilities"))
    equity = _finite(raw.get("stockholders_equity"))
    revenues = _finite(raw.get("revenues"))
    cogs = _finite(raw.get("cost_of_goods_sold"))
    gross_profit = _finite(raw.get("gross_profit"))
    if gross_profit is None and revenues is not None and cogs is not None:
        gross_profit = revenues - cogs
    operating_income = _finite(raw.get("operating_income"))
    da = _finite(raw.get("depreciation_amortization"))
    ebitda = _finite(raw.get("ebitda"))
    if ebitda is None and operating_income is not None and da is not None:
        ebitda = operating_income + da
    inventory = _finite(raw.get("inventory"))
    receivables = _finite(raw.get("accounts_receivable"))

    equity_to_assets = _safe_div(equity, assets, True)
    is_neg_eq = bool(equity is not None and equity <= 0.0)
    is_thin_eq = bool(equity_to_assets is not None and 0.0 < equity_to_assets < 0.05)

    extended: dict[str, Any] = {
        "gross_margin": _safe_div(gross_profit, revenues, True),
        "ebitda_margin": _safe_div(ebitda, revenues, True),
        "ebitda_to_assets": _safe_div(ebitda, assets, True),
        "opex_to_revenue": _safe_div(raw.get("operating_expenses"), revenues, True),
        "quick_ratio": (
            _safe_div(current_assets - inventory, current_liabilities, True)
            if current_assets is not None and inventory is not None
            else None
        ),
        "short_term_debt_share": _safe_div(current_liabilities, liabilities, True),
        "long_term_debt_to_assets": _safe_div(raw.get("long_term_debt"), assets, True),
        "equity_to_assets": equity_to_assets,
        "is_negative_equity": 1.0 if is_neg_eq else 0.0,
        "is_thin_equity": is_thin_eq,
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
            raw.get("operating_cash_flow"), raw.get("net_income"), True
        ),
    }

    record = {**raw, **extended, **ratios}
    # Preserve explicit extended fields if Wave-0 ratios omitted them or returned None.
    for key, val in extended.items():
        if record.get(key) is None and val is not None:
            record[key] = val
    record["is_negative_equity"] = bool(is_neg_eq)

    if prior_stmt is not None and prior_stmt.fiscal_year == stmt.fiscal_year - 1:
        prior_rec = _statement_to_record(prior_stmt, company, None)
        for cur_k, delta_k in (
            ("roa", "roa_yoy_delta"),
            ("gross_margin", "gross_margin_yoy_delta"),
            ("debt_ratio", "debt_ratio_yoy_delta"),
            ("working_capital_ratio", "working_capital_yoy_delta"),
            ("ocf_ratio", "ocf_ratio_yoy_delta"),
            ("roe", "roe_yoy_delta"),
        ):
            cur_v, prev_v = _finite(record.get(cur_k)), _finite(prior_rec.get(cur_k))
            record[delta_k] = cur_v - prev_v if cur_v is not None and prev_v is not None else None
        cur_rev, prev_rev = _finite(record.get("revenues")), _finite(prior_rec.get("revenues"))
        record["revenue_growth_yoy"] = (
            (cur_rev - prev_rev) / prev_rev
            if cur_rev is not None and prev_rev is not None and prev_rev > 0
            else None
        )
    return record


def _load_lane_c_confidence_module() -> Any | None:
    """Lazily load Lane C's confidence module when present in the integrated workspace."""
    try:
        return import_module("finhealth.ml.confidence")
    except ImportError:
        return None


def _evaluate_cash_flow_overlay(
    record: Mapping[str, Any],
    *,
    base_tier: RiskTier,
    negative_ocf_streak: int,
    audit_status: str,
) -> dict[str, Any]:
    """Apply the supplementary cash-flow and audit stress overlay without mutating raw PD."""
    flags: list[str] = []
    reasons_vi: list[str] = []
    ocf = _finite(record.get("operating_cash_flow"))
    icr = _finite(record.get("interest_coverage"))

    if negative_ocf_streak >= 2:
        flags.append("NEGATIVE_OCF_STREAK")
        reasons_vi.append(
            f"Dòng tiền hoạt động kinh doanh âm {negative_ocf_streak} năm liên tiếp."
        )
    if ocf is not None and ocf < 0.0 and icr is not None and icr < 1.0:
        flags.append("WEAK_INTEREST_COVERAGE_AND_NEGATIVE_OCF")
        reasons_vi.append(
            "Khả năng thanh toán lãi vay dưới 1,0x đồng thời dòng tiền hoạt động âm."
        )
    if audit_status == "audited_adverse_disclaimer":
        flags.append("ADVERSE_OR_DISCLAIMER_AUDIT")
        reasons_vi.append("Báo cáo tài chính có ý kiến kiểm toán trái ngược hoặc từ chối.")

    triggered = bool(flags)
    adjusted_tier: RiskTier = base_tier
    if triggered and base_tier in ("STRONG", "STABLE"):
        adjusted_tier = "WATCH"

    return {
        "triggered": triggered,
        "flags": flags,
        "reasons_vi": reasons_vi,
        "original_tier": base_tier,
        "adjusted_tier": adjusted_tier,
    }


def _evaluate_confidence(
    record: Mapping[str, Any],
    *,
    audit_status: str,
    ensemble_spread: float | None = None,
    ood_bounds: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Compute the 4-layer reliability indicator (completeness, OOD, spread, audit status)."""
    observed = sum(1 for key in CORE_BANKRUPTCY_FEATURES if _finite(record.get(key)) is not None)
    completeness = round(observed / len(CORE_BANKRUPTCY_FEATURES), 4)
    ood_features: list[str] = []
    if ood_bounds:
        for feat, bounds in ood_bounds.items():
            val = _finite(record.get(feat))
            if val is not None and len(bounds) == 2 and (val < bounds[0] or val > bounds[1]):
                ood_features.append(feat)
    is_ood = len(ood_features) >= 3

    rank = 3  # 3=HIGH, 2=MODERATE, 1=LOW
    reasons_vi: list[str] = []

    if completeness < 0.70:
        rank = min(rank, 1)
        reasons_vi.append(
            f"Độ đầy đủ dữ liệu đầu vào thấp ({completeness * 100:.0f}% chỉ tiêu cốt lõi)."
        )
    elif completeness < 0.90:
        rank = min(rank, 2)
        reasons_vi.append(
            f"Một số chỉ tiêu tài chính chưa đầy đủ ({completeness * 100:.0f}% chỉ tiêu cốt lõi)."
        )

    if is_ood:
        rank = max(1, rank - 1)
        reasons_vi.append(
            f"Có {len(ood_features)} chỉ tiêu nằm ngoài khoảng phân phối phổ biến "
            "của tập kiểm định."
        )

    if ensemble_spread is not None and ensemble_spread > 0.08:
        rank = max(1, rank - 1)
        reasons_vi.append("Mức độ đồng thuận giữa các mô hình thành phần còn phân tán.")

    if audit_status == "audited_adverse_disclaimer":
        rank = 1
        reasons_vi.append("Báo cáo tài chính có ý kiến kiểm toán trái ngược hoặc từ chối.")
    elif audit_status == "unaudited":
        rank = min(rank, 2)
        reasons_vi.append("Báo cáo tài chính chưa được kiểm toán độc lập.")
    elif audit_status == "audited_qualified":
        rank = min(rank, 2)
        reasons_vi.append("Báo cáo tài chính có ý kiến kiểm toán ngoại trừ.")

    if not reasons_vi:
        reasons_vi.append("Dữ liệu đầy đủ, trong vùng phân phối chuẩn và đã được kiểm toán.")

    level: ConfidenceLevel = "HIGH" if rank >= 3 else "MODERATE" if rank == 2 else "LOW"
    return {
        "level": level,
        "input_completeness": completeness,
        "is_ood": is_ood,
        "ood_features": ood_features,
        "ensemble_spread": round(ensemble_spread, 4) if ensemble_spread is not None else None,
        "audit_status": audit_status,
        "reasons_vi": reasons_vi,
    }


def _deterministic_pd_and_attributions(
    record: Mapping[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Scale-free deterministic bankruptcy PD & feature attributions fallback when no v2 bundle."""
    # Calibrated around real-world ~1% annual base rate (log-odds intercept ~ -4.5).
    base_logit = -4.55
    contribs: dict[str, float] = {}

    debt = _finite(record.get("debt_ratio"))
    if debt is not None:
        contribs["debt_ratio"] = 3.2 * (debt - 0.55)

    roa = _finite(record.get("roa"))
    if roa is not None:
        contribs["roa"] = -8.5 * (roa - 0.04)

    curr = _finite(record.get("current_ratio"))
    if curr is not None:
        contribs["current_ratio"] = -0.9 * (min(curr, 3.0) - 1.4)

    wc = _finite(record.get("working_capital_ratio"))
    if wc is not None:
        contribs["working_capital_ratio"] = -2.2 * (wc - 0.12)

    re_ratio = _finite(record.get("retained_earnings_ratio"))
    if re_ratio is not None:
        contribs["retained_earnings_ratio"] = -2.0 * (re_ratio - 0.15)

    eq_ratio = _finite(record.get("equity_to_assets"))
    if eq_ratio is not None:
        contribs["equity_to_assets"] = -2.4 * (eq_ratio - 0.40)

    if bool(record.get("is_negative_equity")):
        contribs["is_negative_equity"] = 1.65

    ocf_ratio = _finite(record.get("ocf_ratio"))
    if ocf_ratio is not None:
        contribs["ocf_ratio"] = -2.5 * (ocf_ratio - 0.12)

    op_margin = _finite(record.get("operating_margin"))
    if op_margin is not None:
        contribs["operating_margin"] = -2.8 * (op_margin - 0.08)

    icr = _finite(record.get("interest_coverage"))
    if icr is not None:
        contribs["interest_coverage"] = -0.25 * (min(max(icr, -2.0), 10.0) - 3.0)

    raw_margin = base_logit + sum(contribs.values())
    clamped_margin = min(max(raw_margin, -8.5), 4.0)
    pd_12m = round(1.0 / (1.0 + exp(-clamped_margin)), 6)
    shap_payload = {
        "output_space": "log_odds",
        "base_value": base_logit,
        "model_name": DEFAULT_FALLBACK_MODEL_VERSION,
        "contributions": contribs,
        "fitted_inputs": {
            key: float(val)
            for key in contribs
            if (val := _finite(record.get(key))) is not None
        },
    }
    return pd_12m, shap_payload


def _score_statement_with_adapter(
    record: Mapping[str, Any],
    *,
    has_prior: bool,
    negative_ocf_streak: int,
    audit_status: str,
    model_registry: ModelRegistryState | None,
) -> dict[str, Any]:
    """Score one statement using Lane C's v2 bundle when available, else deterministic adapter."""
    scoring_mode: ScoringMode = "multi_period" if has_prior else "single_period"
    bundle = model_registry.get() if model_registry is not None else None
    model_version = DEFAULT_FALLBACK_MODEL_VERSION
    ensemble_spread: float | None = None
    ood_bounds: Mapping[str, Sequence[float]] | None = None
    pd_12m: float | None = None
    shap_explanation: dict[str, Any] | None = None

    if bundle is not None:
        # Support Lane C's dual-mode bundle (assess_company_record) if present,
        # or Wave-0 bundle if feature columns match scale-free contract.
        assess_fn = getattr(bundle, "assess_record", None)
        if callable(assess_fn):
            lane_c_res = assess_fn(record, scoring_mode=scoring_mode, audit_status=audit_status)
            pd_12m = _finite(getattr(lane_c_res, "pd_12m", None))
            shap_explanation = getattr(lane_c_res, "shap_explanation", None)
            model_version = str(getattr(lane_c_res, "model_version", bundle.model_version))
        elif hasattr(bundle, "classifier") and bundle.classifier is not None:
            feat_cols = tuple(getattr(bundle.classifier, "feature_columns", ()))
            # Only invoke a live ML bundle if it uses scale-free features (never EPS/USD-only).
            if feat_cols and "eps" not in feat_cols:
                import pandas as pd

                from finhealth.ml.explainer import ShapExplainer

                row_df = pd.DataFrame([{col: record.get(col) for col in feat_cols}])
                probs = bundle.classifier.predict_proba(row_df)
                pd_12m = float(probs[0])
                model_version = bundle.model_version
                shap_explanation = ShapExplainer(bundle.classifier).explain_instance(row_df)
                ood_bounds = bundle.evaluation_report.get("feature_ood_bounds")

    if pd_12m is None or not isfinite(pd_12m) or shap_explanation is None:
        pd_12m, shap_explanation = _deterministic_pd_and_attributions(record)
        model_version = DEFAULT_FALLBACK_MODEL_VERSION

    # Delegate to Lane C confidence module if available and compatible.
    _ = _load_lane_c_confidence_module()
    base_tier = classify_bankruptcy_tier(pd_12m)
    overlay = _evaluate_cash_flow_overlay(
        record,
        base_tier=base_tier,
        negative_ocf_streak=negative_ocf_streak,
        audit_status=audit_status,
    )
    effective_tier: RiskTier = overlay["adjusted_tier"]
    health_score = map_pd_to_health_score(pd_12m)
    if overlay["triggered"] and effective_tier == "WATCH" and health_score >= 60.0:
        health_score = 59.5

    confidence = _evaluate_confidence(
        record,
        audit_status=audit_status,
        ensemble_spread=ensemble_spread,
        ood_bounds=ood_bounds,
    )
    return {
        "model_version": model_version,
        "scoring_mode": scoring_mode,
        "pd_12m": pd_12m,
        "health_score": health_score,
        "risk_tier": effective_tier,
        "confidence": confidence,
        "cash_flow_overlay": overlay,
        "shap_explanation": shap_explanation,
    }


def _map_org_sector_to_sec(company: OrgCompany) -> str | None:
    """Map Vietnamese VSIC sector code/name or business_type to SEC macro-sector cohort."""
    if company.sector_code:
        prefix = company.sector_code.strip().upper()[:1]
        if prefix in _VSIC_TO_SEC_SECTOR:
            return _VSIC_TO_SEC_SECTOR[prefix]
    if company.sector_name:
        lowered = company.sector_name.strip().lower()
        for keywords, sec_sector in _SECTOR_KEYWORDS:
            if any(kw in lowered for kw in keywords):
                return sec_sector
    if company.business_type == "manufacturing":
        return "Manufacturing"
    if company.business_type == "trade_service":
        return "Services"
    return None


def _compute_peer_context(
    db: Session,
    company: OrgCompany,
    record: Mapping[str, Any],
) -> tuple[PeerContextView, dict[str, dict[str, Any]]]:
    """Compute S01 industry peer percentiles against latest annual SEC cohort."""
    mapped_sector = _map_org_sector_to_sec(company)
    rows = db.execute(
        select(Company.sector, FinancialMetric)
        .join(FinancialStatement, FinancialStatement.company_id == Company.id)
        .join(FinancialMetric, FinancialMetric.statement_id == FinancialStatement.id)
        .where(FinancialStatement.id == latest_annual_statement_id())
    ).all()

    if not rows:
        return (
            PeerContextView(
                benchmark_scope="unavailable",
                mapped_sector=mapped_sector,
                cohort_size=0,
                summary_label_vi="Chưa có dữ liệu chuẩn ngành để đối chiếu.",
                metrics={},
            ),
            {},
        )

    sector_rows = [
        metric for sector, metric in rows if mapped_sector and sector == mapped_sector
    ]
    if len(sector_rows) >= MIN_PEER_COHORT_SIZE:
        cohort = sector_rows
        scope: Literal["sector", "universe", "unavailable"] = "sector"
        scope_noun = "ngành"
    elif len(rows) >= MIN_PEER_COHORT_SIZE:
        cohort = [metric for _, metric in rows]
        scope = "universe"
        scope_noun = "thị trường"
    else:
        return (
            PeerContextView(
                benchmark_scope="unavailable",
                mapped_sector=mapped_sector,
                cohort_size=len(rows),
                summary_label_vi="Cỡ mẫu chuẩn ngành chưa đủ tối thiểu 5 doanh nghiệp.",
                metrics={},
            ),
            {},
        )

    peer_views: dict[str, PeerMetricPositionView] = {}
    peer_dicts: dict[str, dict[str, Any]] = {}
    best_percentiles: list[float] = []

    for key, spec in METRIC_CATALOG.items():
        if not hasattr(FinancialMetric, key):
            continue
        obs = [
            val
            for metric_obj in cohort
            if (val := _finite(getattr(metric_obj, key, None))) is not None
        ]
        if len(obs) < MIN_PEER_COHORT_SIZE:
            continue
        value = _finite(record.get(key))
        peer_med = round(median(obs), 4)
        percentile: float | None = None
        if value is not None:
            below = sum(1 for item in obs if item < value)
            tied = sum(1 for item in obs if item == value)
            raw_pct = 100.0 * (below + 0.5 * tied) / len(obs)
            best_pct = raw_pct if spec.good_direction == "higher" else 100.0 - raw_pct
            percentile = round(best_pct, 1)
            best_percentiles.append(percentile)
            if percentile >= 75.0:
                label_vi = f"Top 25% tốt nhất {scope_noun}"
            elif percentile >= 40.0:
                label_vi = f"Ngang mức trung bình {scope_noun}"
            else:
                label_vi = f"Thấp hơn trung bình {scope_noun}"
        else:
            label_vi = f"Chưa có số liệu để đối chiếu {scope_noun}"

        pos = PeerMetricPositionView(
            metric_key=key,
            peer_median=peer_med,
            percentile=percentile,
            n_observed=len(obs),
            benchmark_scope=scope,
            position_label_vi=label_vi,
        )
        peer_views[key] = pos
        peer_dicts[key] = pos.model_dump()

    if best_percentiles:
        avg_pct = sum(best_percentiles) / len(best_percentiles)
        if avg_pct >= 75.0:
            summary_label_vi = f"Top 25% tốt nhất {scope_noun}"
        elif avg_pct >= 40.0:
            summary_label_vi = f"Ngang mức trung bình {scope_noun}"
        else:
            summary_label_vi = f"Thấp hơn trung bình {scope_noun}"
    else:
        summary_label_vi = f"Đối chiếu theo nhóm {scope_noun} ({len(cohort)} doanh nghiệp)"

    return (
        PeerContextView(
            benchmark_scope=scope,
            mapped_sector=mapped_sector if scope == "sector" else None,
            cohort_size=len(cohort),
            summary_label_vi=summary_label_vi,
            metrics=peer_views,
        ),
        peer_dicts,
    )


def _build_top_3_takeaways(
    *,
    company: OrgCompany,
    summary_tier: RiskTier | None,
    health_score: float | None,
    pd_12m: float | None,
    altman: Mapping[str, Any],
    drivers: Mapping[str, Any],
    overlay: Mapping[str, Any] | None,
) -> list[str]:
    """Generate up to 3 concise plain-Vietnamese executive takeaways for the 3-second rule."""
    if company.business_type == "financial_institution":
        return [
            FI_EXCLUSION_REASON_VI,
            "Hồ sơ tổ chức tài chính vẫn được lưu trữ trong danh bạ để quản lý thông tin đối tác.",
            "Vui lòng sử dụng bộ chuẩn phân tích chuyên biệt (CAMELS/CAR) cho "
            "ngân hàng và bảo hiểm.",
        ]

    takeaways: list[str] = []
    if summary_tier is not None and health_score is not None and pd_12m is not None:
        pd_pct = f"{pd_12m * 100:.2f}%".replace(".", ",")
        score_str = f"{health_score:.1f}".replace(".", ",")
        takeaways.append(
            f"Sức khỏe tài chính đạt {score_str}/100 ({RISK_TIER_LABELS_VI[summary_tier]}), "
            f"xác suất rủi ro 12 tháng ở mức {pd_pct}."
        )

    bottlenecks = drivers.get("bottlenecks") or []
    strengths = drivers.get("strengths") or []
    if bottlenecks:
        top_b = bottlenecks[0]
        takeaways.append(f"Điểm nghẽn chính: {top_b['headline_vi']}.")
    elif altman.get("applicable") and altman.get("score") is not None:
        z_str = f"{altman['score']:.2f}".replace(".", ",")
        takeaways.append(
            f"Chỉ số Altman {altman['variant']} đạt {z_str} ({altman['zone_label_vi']})."
        )

    if overlay and overlay.get("triggered") and overlay.get("reasons_vi"):
        takeaways.append(f"Cảnh báo dòng tiền/kiểm toán: {overlay['reasons_vi'][0]}")
    elif strengths:
        top_s = strengths[0]
        takeaways.append(f"Điểm tựa nổi bật: {top_s['headline_vi']}.")

    return takeaways[:3]


def _ensure_org_assessment(
    db: Session,
    company: OrgCompany,
    stmt: OrgFinancialStatement,
    prior_stmt: OrgFinancialStatement | None,
    *,
    negative_ocf_streak: int,
    model_registry: ModelRegistryState | None,
    force_recompute: bool = False,
) -> tuple[OrgAssessment, dict[str, Any], dict[str, Any]]:
    """Compute or load the frozen OrgAssessment snapshot for one finalized statement."""
    record = _statement_to_record(stmt, company, prior_stmt)
    altman = compute_altman_assessment(
        record,
        business_type=company.business_type,
        listing_status=company.listing_status,
    )

    if company.business_type == "financial_institution":
        target_model_version = "excluded-fi"
        existing = db.execute(
            select(OrgAssessment).where(
                OrgAssessment.org_statement_id == stmt.id,
                OrgAssessment.model_version == target_model_version,
            )
        ).scalar_one_or_none()
        if existing is not None and not force_recompute:
            return existing, record, altman
        if existing is None:
            existing = OrgAssessment(
                organization_id=company.organization_id,
                org_company_id=company.id,
                org_statement_id=stmt.id,
                model_version=target_model_version,
                rule_version=RULE_VERSION,
                scoring_mode="excluded",
            )
            db.add(existing)
        existing.scoring_mode = "excluded"
        existing.pd_12m = None
        existing.health_score = None
        existing.risk_tier = None
        existing.altman_variant = None
        existing.altman_z_score = None
        existing.altman_zone = None
        existing.confidence_level = None
        existing.cash_flow_overlay_triggered = False
        existing.confidence_json = None
        existing.drivers_json = {"strengths": [], "bottlenecks": [], "total_impact_share_pct": 0.0}
        existing.pillars_json = None
        existing.diagnostics_json = None
        db.commit()
        db.refresh(existing)
        return existing, record, altman

    scored = _score_statement_with_adapter(
        record,
        has_prior=prior_stmt is not None and prior_stmt.fiscal_year == stmt.fiscal_year - 1,
        negative_ocf_streak=negative_ocf_streak,
        audit_status=stmt.audit_status,
        model_registry=model_registry,
    )
    model_version = str(scored["model_version"])
    existing = db.execute(
        select(OrgAssessment).where(
            OrgAssessment.org_statement_id == stmt.id,
            OrgAssessment.model_version == model_version,
        )
    ).scalar_one_or_none()
    if existing is not None and not force_recompute:
        return existing, record, altman

    drivers_payload = translate_drivers_to_business(scored["shap_explanation"], record)
    if existing is None:
        existing = OrgAssessment(
            organization_id=company.organization_id,
            org_company_id=company.id,
            org_statement_id=stmt.id,
            model_version=model_version,
            rule_version=RULE_VERSION,
            scoring_mode=scored["scoring_mode"],
        )
        db.add(existing)

    existing.scoring_mode = scored["scoring_mode"]
    existing.pd_12m = scored["pd_12m"]
    existing.health_score = scored["health_score"]
    existing.risk_tier = scored["risk_tier"]
    existing.altman_variant = altman["variant"]
    existing.altman_z_score = altman["score"]
    existing.altman_zone = altman["zone"]
    existing.confidence_level = scored["confidence"]["level"]
    existing.cash_flow_overlay_triggered = bool(scored["cash_flow_overlay"]["triggered"])
    existing.confidence_json = {
        "confidence": scored["confidence"],
        "cash_flow_overlay": scored["cash_flow_overlay"],
    }
    existing.drivers_json = drivers_payload
    db.commit()
    db.refresh(existing)
    return existing, record, altman


def _load_org_company_or_404(db: Session, org_id: int, company_id: int) -> OrgCompany:
    """Fetch an organization-scoped company or fail closed with 404."""
    company = db.execute(
        select(OrgCompany).where(
            OrgCompany.id == company_id,
            OrgCompany.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy doanh nghiệp trong không gian làm việc hiện tại.",
        )
    return company


def get_org_company_assessment(
    db: Session,
    *,
    org_id: int,
    company_id: int,
    model_registry: ModelRegistryState | None = None,
    fiscal_year: int | None = None,
    force_recompute: bool = False,
) -> CompanyAssessmentView:
    """Build the complete V1.0 CompanyAssessmentView with M11 history and S01 peer context."""
    company = _load_org_company_or_404(db, org_id, company_id)
    statements = list(
        db.execute(
            select(OrgFinancialStatement)
            .where(
                OrgFinancialStatement.organization_id == org_id,
                OrgFinancialStatement.org_company_id == company_id,
                OrgFinancialStatement.status == "finalized",
            )
            .order_by(OrgFinancialStatement.fiscal_year.asc(), OrgFinancialStatement.id.asc())
        ).scalars()
    )
    if not statements:
        raise HTTPException(
            status_code=422,
            detail="Doanh nghiệp chưa có báo cáo tài chính đã chốt (finalized) để đánh giá.",
        )

    history_points: list[MultiPeriodHistoryPointView] = []
    stmt_records: list[dict[str, Any]] = []
    stmt_assessments: list[OrgAssessment] = []
    stmt_altmans: list[dict[str, Any]] = []

    neg_ocf_streak = 0
    for idx, stmt in enumerate(statements):
        prior_stmt = statements[idx - 1] if idx > 0 else None
        ocf = _finite(stmt.operating_cash_flow)
        if ocf is not None and ocf < 0.0:
            neg_ocf_streak += 1
        else:
            neg_ocf_streak = 0
        assessment, record, altman = _ensure_org_assessment(
            db,
            company,
            stmt,
            prior_stmt,
            negative_ocf_streak=neg_ocf_streak,
            model_registry=model_registry,
            force_recompute=force_recompute,
        )
        stmt_records.append(record)
        stmt_assessments.append(assessment)
        stmt_altmans.append(altman)
        history_points.append(
            MultiPeriodHistoryPointView(
                statement_id=stmt.id,
                fiscal_year=stmt.fiscal_year,
                fiscal_period=stmt.fiscal_period,
                accounting_standard=stmt.accounting_standard,
                currency=stmt.currency,
                audit_status=stmt.audit_status,
                revenues=_finite(stmt.revenues),
                net_income=_finite(stmt.net_income),
                operating_cash_flow=_finite(stmt.operating_cash_flow),
                total_assets=_finite(stmt.total_assets),
                total_liabilities=_finite(stmt.total_liabilities),
                stockholders_equity=_finite(stmt.stockholders_equity),
                debt_ratio=_finite(record.get("debt_ratio")),
                roa=_finite(record.get("roa")),
                current_ratio=_finite(record.get("current_ratio")),
                altman_variant=altman["variant"],
                altman_z_score=altman["score"],
                altman_zone=altman["zone"],
                health_score=_finite(assessment.health_score),
                pd_12m=_finite(assessment.pd_12m),
                risk_tier=assessment.risk_tier,  # type: ignore[arg-type]
            )
        )

    target_idx = len(statements) - 1
    if fiscal_year is not None:
        matches = [i for i, item in enumerate(statements) if item.fiscal_year == fiscal_year]
        if not matches:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy báo cáo tài chính đã chốt cho năm {fiscal_year}.",
            )
        target_idx = matches[-1]

    target_stmt = statements[target_idx]
    target_record = stmt_records[target_idx]
    prior_record = stmt_records[target_idx - 1] if target_idx > 0 else None
    target_assessment = stmt_assessments[target_idx]
    target_altman = stmt_altmans[target_idx]

    peer_context, peer_dicts = _compute_peer_context(db, company, target_record)
    pillars_raw = compute_health_pillars_v2(
        target_record,
        prior_record=prior_record,
        peer_positions=peer_dicts,
    )

    dupont = compute_dupont(stmt_records[: target_idx + 1])
    qoe = compute_quality_of_earnings(target_record, prior_record)
    checklist = compute_accounting_checklist(target_record, prior_record)

    drivers_raw = target_assessment.drivers_json or {
        "strengths": [],
        "bottlenecks": [],
        "total_impact_share_pct": 0.0,
    }
    drivers_view = DriversSplitView(
        strengths=[
            BusinessDriverView.model_validate(item) for item in drivers_raw.get("strengths", [])
        ],
        bottlenecks=[
            BusinessDriverView.model_validate(item) for item in drivers_raw.get("bottlenecks", [])
        ],
        total_impact_share_pct=float(drivers_raw.get("total_impact_share_pct", 0.0)),
    )

    conf_bundle = target_assessment.confidence_json or {}
    conf_dict = conf_bundle.get("confidence")
    overlay_dict = conf_bundle.get("cash_flow_overlay")

    is_fi = company.business_type == "financial_institution"
    tier: RiskTier | None = target_assessment.risk_tier  # type: ignore[assignment]
    summary = AssessmentSummaryView(
        scoring_eligible=not is_fi,
        scoring_mode=target_assessment.scoring_mode,  # type: ignore[arg-type]
        model_version=target_assessment.model_version,
        health_score=_finite(target_assessment.health_score),
        risk_tier=tier,
        risk_label_vi=(
            "Không áp dụng (Tổ chức tài chính)"
            if is_fi
            else RISK_TIER_LABELS_VI[tier]
            if tier is not None
            else "Chưa xếp loại"
        ),
        pd_12m=_finite(target_assessment.pd_12m),
        confidence=ConfidenceView.model_validate(conf_dict) if conf_dict else None,
        cash_flow_overlay=CashFlowOverlayView.model_validate(overlay_dict)
        if overlay_dict
        else None,
        top_3_takeaways_vi=_build_top_3_takeaways(
            company=company,
            summary_tier=tier,
            health_score=_finite(target_assessment.health_score),
            pd_12m=_finite(target_assessment.pd_12m),
            altman=target_altman,
            drivers=drivers_raw,
            overlay=overlay_dict,
        ),
        unavailable_reason_vi=FI_EXCLUSION_REASON_VI if is_fi else None,
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )

    meta = OrgCompanyMetaView(
        id=company.id,
        organization_id=company.organization_id,
        name=company.name,
        tax_code=company.tax_code,
        ticker=company.ticker,
        sector_code=company.sector_code,
        sector_name=company.sector_name,
        business_type=company.business_type,
        listing_status=company.listing_status,
        relationship_tag=company.relationship_tag,
        is_sample=company.is_sample,
        fiscal_year=target_stmt.fiscal_year,
        accounting_standard=target_stmt.accounting_standard,
        currency=target_stmt.currency,
    )

    return CompanyAssessmentView(
        company=meta,
        summary=summary,
        altman=AltmanView.model_validate(target_altman),
        pillars=PillarsOverviewView.model_validate(pillars_raw),
        drivers=drivers_view,
        diagnostics=DiagnosticsView(
            dupont=dupont,
            quality_of_earnings=qoe,
            accounting_checklist=checklist,
        ),
        history=history_points[: target_idx + 1] if fiscal_year is not None else history_points,
        peer_context=peer_context,
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )


def compare_org_companies(
    db: Session,
    *,
    org_id: int,
    company_ids: Sequence[int],
    common_fiscal_year: int | None = None,
    model_registry: ModelRegistryState | None = None,
) -> OrgCompareResponseView:
    """Compare 2 to 4 companies strictly within one organization workspace (C03)."""
    unique_ids: list[int] = []
    for cid in company_ids:
        if cid not in unique_ids:
            unique_ids.append(cid)

    if len(unique_ids) < 2 or len(unique_ids) > 4:
        raise HTTPException(
            status_code=422,
            detail="So sánh trực diện yêu cầu từ 2 đến 4 doanh nghiệp khác nhau.",
        )

    found_companies = list(
        db.execute(
            select(OrgCompany).where(
                OrgCompany.organization_id == org_id,
                OrgCompany.id.in_(unique_ids),
            )
        ).scalars()
    )
    if len(found_companies) != len(unique_ids):
        raise HTTPException(
            status_code=404,
            detail="Một hoặc nhiều doanh nghiệp không tồn tại trong không gian làm việc này.",
        )

    items: list[OrgCompareCompanyItemView] = []
    historical_series: dict[int, list[MultiPeriodHistoryPointView]] = {}
    active_model_version = DEFAULT_FALLBACK_MODEL_VERSION

    for cid in unique_ids:
        try:
            assessment = get_org_company_assessment(
                db,
                org_id=org_id,
                company_id=cid,
                model_registry=model_registry,
                fiscal_year=common_fiscal_year,
            )
        except HTTPException as exc:
            if common_fiscal_year is not None and exc.status_code == 404:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Doanh nghiệp #{cid} không có báo cáo tài chính đã chốt cho năm "
                        f"{common_fiscal_year}."
                    ),
                ) from exc
            raise

        active_model_version = assessment.summary.model_version
        metric_map: dict[str, float | None] = {}
        pillar_scores: dict[str, float | None] = {}
        for pillar in assessment.pillars.pillars:
            pillar_scores[pillar.key] = pillar.score
            for metric in pillar.metrics:
                if metric.key in _COMPARE_CORE_METRICS:
                    metric_map[metric.key] = metric.value

        items.append(
            OrgCompareCompanyItemView(
                company=assessment.company,
                fiscal_year=assessment.company.fiscal_year or 0,
                accounting_standard=assessment.company.accounting_standard or "TT99_2025",
                health_score=assessment.summary.health_score,
                risk_tier=assessment.summary.risk_tier,
                risk_label_vi=assessment.summary.risk_label_vi,
                pd_12m=assessment.summary.pd_12m,
                altman=assessment.altman,
                pillar_scores=pillar_scores,
                core_metrics=metric_map,
            )
        )
        historical_series[cid] = assessment.history

    cohort_medians: dict[str, float | None] = {}
    for metric_key in _COMPARE_CORE_METRICS:
        vals = [
            val
            for item in items
            if (val := _finite(item.core_metrics.get(metric_key))) is not None
        ]
        cohort_medians[metric_key] = round(median(vals), 4) if vals else None

    health_vals = [val for item in items if (val := _finite(item.health_score)) is not None]
    cohort_medians["health_score"] = round(median(health_vals), 2) if health_vals else None

    return OrgCompareResponseView(
        organization_id=org_id,
        requested_ids=unique_ids,
        period_policy=(
            "common_fiscal_year" if common_fiscal_year is not None else "latest_finalized"
        ),
        common_fiscal_year=common_fiscal_year,
        active_model_version=active_model_version,
        companies=items,
        historical_series=historical_series,
        cohort_medians=cohort_medians,
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )
