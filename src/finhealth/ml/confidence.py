"""Bankruptcy risk tiers, monotonic health scoring, 4-layer confidence, and Cash-Flow Overlay."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from finhealth.ml.feature_contracts import (
    CORE_BANKRUPTCY_FEATURES,
    ConfidenceLevel,
    RiskTier,
    ScoringMode,
)

# Risk tier cutoffs calibrated to ~1%/year empirical US corporate bankruptcy base rate.
TIER_STRONG_MAX_PD: float = 0.01
TIER_STABLE_MAX_PD: float = 0.03
TIER_WATCH_MAX_PD: float = 0.08

# 4-layer confidence thresholds.
COMPLETENESS_LOW_CUTOFF: float = 0.70
COMPLETENESS_HIGH_CUTOFF: float = 0.90
OOD_FEATURE_COUNT_THRESHOLD: int = 3
ENSEMBLE_SPREAD_THRESHOLD: float = 0.08

_CONFIDENCE_ORDER: tuple[ConfidenceLevel, ...] = ("LOW", "MODERATE", "HIGH")
_CONFIDENCE_RANK: dict[ConfidenceLevel, int] = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
_TIER_RANK: dict[RiskTier, int] = {"STRONG": 0, "STABLE": 1, "WATCH": 2, "CRITICAL": 3}

_OOD_FEATURE_LABELS_VI: dict[str, str] = {
    "roa": "Tỷ suất sinh lời trên tài sản (ROA)",
    "ebit_to_assets": "Lợi nhuận hoạt động / Tổng tài sản",
    "ebitda_to_assets": "EBITDA / Tổng tài sản",
    "gross_margin": "Biên lợi nhuận gộp",
    "operating_margin": "Biên lợi nhuận hoạt động",
    "opex_to_revenue": "Tổng chi phí hoạt động / Doanh thu",
    "asset_turnover": "Vòng quay tổng tài sản",
    "current_ratio": "Hệ số thanh toán hiện hành",
    "quick_ratio": "Hệ số thanh toán nhanh",
    "working_capital_ratio": "Vốn lưu động ròng / Tổng tài sản",
    "debt_ratio": "Nợ phải trả / Tổng tài sản",
    "short_term_debt_share": "Tỷ trọng nợ ngắn hạn / Tổng nợ",
    "long_term_debt_to_assets": "Nợ dài hạn / Tổng tài sản",
    "retained_earnings_ratio": "Lợi nhuận giữ lại / Tổng tài sản",
    "equity_to_assets": "Vốn chủ sở hữu / Tổng tài sản",
    "is_negative_equity": "Tình trạng âm vốn chủ sở hữu",
    "inventory_to_assets": "Hàng tồn kho / Tổng tài sản",
    "receivables_to_revenue": "Phải thu ngắn hạn / Doanh thu",
    "depreciation_to_assets": "Khấu hao / Tổng tài sản",
}


def classify_bankruptcy_tier(pd_12m: float) -> RiskTier:
    """Map calibrated 12-month bankruptcy probability to credit-aligned risk tiers."""
    if not math.isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < TIER_STRONG_MAX_PD:
        return "STRONG"
    if pd_12m < TIER_STABLE_MAX_PD:
        return "STABLE"
    if pd_12m < TIER_WATCH_MAX_PD:
        return "WATCH"
    return "CRITICAL"


def map_pd_to_health_score(pd_12m: float) -> float:
    """Convert calibrated PD monotonically onto [0, 100] aligned with the four risk bands.

    Exact piecewise mapping:
    - ``[0.00, 0.01)`` (STRONG):   ``(80.0, 100.0]``
    - ``[0.01, 0.03)`` (STABLE):   ``(60.0, 80.0]``
    - ``[0.03, 0.08)`` (WATCH):    ``(35.0, 60.0]``
    - ``[0.08, 1.00]`` (CRITICAL): ``[0.0, 35.0]`` (log-compressed tail)
    """
    if not math.isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < TIER_STRONG_MAX_PD:
        score = 100.0 - 20.0 * (pd_12m / TIER_STRONG_MAX_PD)
        return round(score, 4)
    if pd_12m < TIER_STABLE_MAX_PD:
        score = 80.0 - 20.0 * ((pd_12m - TIER_STRONG_MAX_PD) / 0.02)
        return round(score, 4)
    if pd_12m < TIER_WATCH_MAX_PD:
        score = 60.0 - 25.0 * ((pd_12m - TIER_STABLE_MAX_PD) / 0.05)
        return round(score, 4)
    tail = min(
        1.0,
        math.log1p((pd_12m - TIER_WATCH_MAX_PD) / TIER_WATCH_MAX_PD)
        / math.log1p((1.0 - TIER_WATCH_MAX_PD) / TIER_WATCH_MAX_PD),
    )
    return round(max(0.0, 35.0 * (1.0 - tail)), 4)


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Four-layer reliability evaluation for an individual bankruptcy assessment."""

    level: ConfidenceLevel
    input_completeness: float
    is_ood: bool
    ood_features: list[str]
    ensemble_spread: float
    ensemble_std: float
    audit_status: str
    reasons_vi: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize confidence assessment into a strict JSON-compatible dictionary."""
        return {
            "level": self.level,
            "input_completeness": float(self.input_completeness),
            "is_ood": bool(self.is_ood),
            "ood_features": list(self.ood_features),
            "ensemble_spread": float(self.ensemble_spread),
            "ensemble_std": float(self.ensemble_std),
            "audit_status": self.audit_status,
            "reasons_vi": list(self.reasons_vi),
        }


@dataclass(frozen=True)
class CashFlowOverlayResult:
    """Cash-flow and audit risk overlay applied without distorting calibrated PD."""

    triggered: bool
    flags: list[str]
    reasons_vi: list[str]
    base_tier: RiskTier
    adjusted_tier: RiskTier

    def to_dict(self) -> dict[str, Any]:
        """Serialize cash-flow overlay result into a JSON-compatible dictionary."""
        return {
            "triggered": bool(self.triggered),
            "flags": list(self.flags),
            "reasons_vi": list(self.reasons_vi),
            "base_tier": self.base_tier,
            "adjusted_tier": self.adjusted_tier,
        }


@dataclass(frozen=True)
class BankruptcyAssessmentResult:
    """Boundary contract returned by the V1.0 production bankruptcy scoring engine."""

    model_version: str
    scoring_mode: ScoringMode
    pd_12m: float
    risk_tier: RiskTier
    health_score: float
    confidence: ConfidenceAssessment
    cash_flow_overlay: CashFlowOverlayResult
    shap_explanation: dict[str, Any]
    model_probabilities: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete assessment into a JSON-compatible dictionary."""
        return {
            "model_version": self.model_version,
            "scoring_mode": self.scoring_mode,
            "pd_12m": float(self.pd_12m),
            "risk_tier": self.risk_tier,
            "health_score": float(self.health_score),
            "confidence": self.confidence.to_dict(),
            "cash_flow_overlay": self.cash_flow_overlay.to_dict(),
            "shap_explanation": self.shap_explanation,
            "model_probabilities": {
                str(k): float(v) for k, v in self.model_probabilities.items()
            },
        }


def _cap_confidence(current: ConfidenceLevel, maximum: ConfidenceLevel) -> ConfidenceLevel:
    """Cap confidence at the specified maximum level."""
    return _CONFIDENCE_ORDER[min(_CONFIDENCE_RANK[current], _CONFIDENCE_RANK[maximum])]


def _downgrade_confidence(current: ConfidenceLevel, steps: int = 1) -> ConfidenceLevel:
    """Downgrade confidence by the requested number of tiers (floored at LOW)."""
    return _CONFIDENCE_ORDER[max(0, _CONFIDENCE_RANK[current] - steps)]


def _is_finite_number(value: Any) -> bool:
    """Return True when value can be interpreted as a finite real number."""
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def assess_confidence(
    raw_features: Mapping[str, Any],
    *,
    feature_ood_bounds: Mapping[str, Sequence[float]] | None = None,
    model_probabilities: Mapping[str, float] | None = None,
    audit_status: str = "audited_unqualified",
    core_features: Sequence[str] = CORE_BANKRUPTCY_FEATURES,
    ood_count_threshold: int = OOD_FEATURE_COUNT_THRESHOLD,
    spread_threshold: float = ENSEMBLE_SPREAD_THRESHOLD,
) -> ConfidenceAssessment:
    """Evaluate 4-layer reliability: completeness, OOD bounds, ensemble spread, and audit status."""
    level: ConfidenceLevel = "HIGH"
    reasons_vi: list[str] = []

    # Layer 1: Input completeness across core features.
    total_core = max(len(core_features), 1)
    observed = sum(1 for col in core_features if _is_finite_number(raw_features.get(col)))
    input_completeness = observed / total_core
    if input_completeness < COMPLETENESS_LOW_CUTOFF:
        level = _cap_confidence(level, "LOW")
        reasons_vi.append(
            f"Dữ liệu báo cáo tài chính chỉ đầy đủ {input_completeness * 100:.0f}% "
            f"(< 70% chỉ tiêu cốt lõi), độ tin cậy bị giới hạn ở mức THẤP."
        )
    elif input_completeness < COMPLETENESS_HIGH_CUTOFF:
        level = _cap_confidence(level, "MODERATE")
        reasons_vi.append(
            f"Dữ liệu báo cáo tài chính đầy đủ {input_completeness * 100:.0f}% "
            f"(70%–90% chỉ tiêu cốt lõi), độ tin cậy tối đa ở mức TRUNG BÌNH."
        )

    # Layer 2: Out-of-distribution detection against training [1%, 99%] bounds.
    ood_features: list[str] = []
    if feature_ood_bounds:
        for feat in core_features:
            if feat not in feature_ood_bounds:
                continue
            val = raw_features.get(feat)
            if val is None or not _is_finite_number(val):
                continue
            bounds = feature_ood_bounds[feat]
            if len(bounds) != 2:
                continue
            low, high = float(bounds[0]), float(bounds[1])
            numeric = float(val)
            if numeric < low or numeric > high:
                ood_features.append(feat)
    is_ood = len(ood_features) >= ood_count_threshold
    if is_ood:
        level = _downgrade_confidence(level, 1)
        ood_labels = [
            _OOD_FEATURE_LABELS_VI.get(feat, feat.replace("_", " "))
            for feat in ood_features[:5]
        ]
        reasons_vi.append(
            f"Phát hiện {len(ood_features)} chỉ số tài chính nằm ngoài vùng phân bố lịch sử "
            f"(1%–99%): {', '.join(ood_labels)}."
        )

    # Layer 3: Calibrated 4-model ensemble disagreement.
    probs = [
        float(v)
        for v in (model_probabilities or {}).values()
        if _is_finite_number(v)
    ]
    if len(probs) >= 2:
        ensemble_spread = float(max(probs) - min(probs))
        ensemble_std = float(np.std(probs, ddof=0))
    else:
        ensemble_spread = 0.0
        ensemble_std = 0.0
    if ensemble_spread > spread_threshold:
        level = _downgrade_confidence(level, 1)
        reasons_vi.append(
            f"Các mô hình đánh giá độc lập có mức chênh lệch dự báo đáng kể "
            f"(biên độ {ensemble_spread * 100:.1f} điểm phần trăm)."
        )

    # Layer 4: Audit quality of financial statements.
    normalized_audit = (audit_status or "unaudited").strip().lower()
    if normalized_audit == "audited_adverse_disclaimer":
        level = _cap_confidence(level, "LOW")
        reasons_vi.append(
            "Báo cáo tài chính có ý kiến kiểm toán trái ngược hoặc từ chối đưa ra ý kiến "
            "(rủi ro sai lệch trọng yếu cao)."
        )
    elif normalized_audit == "unaudited":
        level = _cap_confidence(level, "MODERATE")
        reasons_vi.append(
            "Báo cáo tài chính chưa được kiểm toán độc lập; độ tin cậy tối đa ở mức TRUNG BÌNH."
        )
    elif normalized_audit == "audited_qualified":
        reasons_vi.append(
            "Báo cáo tài chính có ý kiến kiểm toán ngoại trừ; cần lưu ý các khoản mục ngoại trừ."
        )

    if not reasons_vi:
        reasons_vi.append(
            "Dữ liệu báo cáo tài chính đầy đủ, trong vùng phân bố chuẩn "
            "và các mô hình đồng thuận cao."
        )

    return ConfidenceAssessment(
        level=level,
        input_completeness=round(input_completeness, 4),
        is_ood=is_ood,
        ood_features=ood_features,
        ensemble_spread=round(ensemble_spread, 6),
        ensemble_std=round(ensemble_std, 6),
        audit_status=normalized_audit,
        reasons_vi=reasons_vi,
    )


def apply_cash_flow_overlay(
    base_tier: RiskTier,
    *,
    negative_ocf_streak: int = 0,
    interest_coverage: float | None = None,
    operating_cash_flow: float | None = None,
    audit_status: str = "audited_unqualified",
) -> CashFlowOverlayResult:
    """Apply Cash-Flow & Audit Risk Overlay without mutating the calibrated model PD.

    When triggered, escalates STRONG/STABLE to at least WATCH while preserving WATCH/CRITICAL.
    """
    flags: list[str] = []
    reasons_vi: list[str] = []

    if negative_ocf_streak >= 2:
        flags.append("NEGATIVE_OCF_STREAK")
        reasons_vi.append(
            f"Dòng tiền thuần từ hoạt động kinh doanh âm {negative_ocf_streak} năm liên tiếp."
        )

    if (
        interest_coverage is not None
        and _is_finite_number(interest_coverage)
        and float(interest_coverage) < 1.0
        and operating_cash_flow is not None
        and _is_finite_number(operating_cash_flow)
        and float(operating_cash_flow) < 0.0
    ):
        flags.append("WEAK_INTEREST_COVERAGE_NEGATIVE_OCF")
        reasons_vi.append(
            "Khả năng trả lãi vay dưới 1,0x đi kèm dòng tiền hoạt động kinh doanh âm."
        )

    normalized_audit = (audit_status or "audited_unqualified").strip().lower()
    if normalized_audit == "audited_adverse_disclaimer":
        flags.append("ADVERSE_OR_DISCLAIMER_AUDIT")
        reasons_vi.append(
            "Ý kiến kiểm toán trái ngược hoặc từ chối đưa ra ý kiến về báo cáo tài chính."
        )

    triggered = len(flags) > 0
    if triggered and _TIER_RANK[base_tier] < _TIER_RANK["WATCH"]:
        adjusted_tier: RiskTier = "WATCH"
    else:
        adjusted_tier = base_tier

    return CashFlowOverlayResult(
        triggered=triggered,
        flags=flags,
        reasons_vi=reasons_vi,
        base_tier=base_tier,
        adjusted_tier=adjusted_tier,
    )
