"""Vietnamese financial metric catalog, reference ranges, and status rules for 5 health pillars."""

from dataclasses import dataclass
from typing import Literal

from finhealth.etl.financial_ratios import _finite

PillarKey = Literal["liquidity", "solvency", "profitability", "efficiency", "cash_flow"]
MetricUnit = Literal["ratio", "percent", "times", "days"]
GoodDirection = Literal["higher", "lower"]
MetricStatus = Literal["GOOD", "NEUTRAL", "WARNING", "CRITICAL", "UNAVAILABLE"]


@dataclass(frozen=True)
class PillarSpec:
    """Metadata for one financial health pillar."""

    key: PillarKey
    label_vi: str
    description_vi: str
    weight: float


@dataclass(frozen=True)
class MetricSpec:
    """Business definition, scoring bounds, and Vietnamese tooltip for a core ratio."""

    key: str
    pillar: PillarKey
    label_vi: str
    unit: MetricUnit
    good_direction: GoodDirection
    reference_range_vi: str
    tooltip_vi: str
    score_low: float
    score_high: float
    good_threshold: float
    warning_threshold: float
    critical_threshold: float


PILLAR_SPECS: tuple[PillarSpec, ...] = (
    PillarSpec(
        key="liquidity",
        label_vi="Khả năng thanh toán ngắn hạn",
        description_vi="Đo lường khả năng đáp ứng các nghĩa vụ nợ đến hạn trong vòng 12 tháng.",
        weight=0.20,
    ),
    PillarSpec(
        key="solvency",
        label_vi="Cơ cấu vốn & Áp lực nợ vay",
        description_vi="Đánh giá mức độ phụ thuộc nợ, đệm vốn chủ sở hữu và sức chịu lãi vay.",
        weight=0.25,
    ),
    PillarSpec(
        key="profitability",
        label_vi="Khả năng sinh lời",
        description_vi=(
            "Phản ánh biên lợi nhuận cốt lõi và hiệu quả tạo lợi nhuận trên tài sản/vốn."
        ),
        weight=0.20,
    ),
    PillarSpec(
        key="efficiency",
        label_vi="Hiệu quả luân chuyển vốn",
        description_vi="Theo dõi tốc độ quay vòng tài sản, thu hồi công nợ và giải phóng tồn kho.",
        weight=0.15,
    ),
    PillarSpec(
        key="cash_flow",
        label_vi="Sức mạnh dòng tiền thực",
        description_vi="Kiểm chứng khả năng chuyển hóa lợi nhuận kế toán thành dòng tiền thực tế.",
        weight=0.20,
    ),
)

PILLAR_SPEC_MAP: dict[PillarKey, PillarSpec] = {spec.key: spec for spec in PILLAR_SPECS}

METRIC_SPECS: tuple[MetricSpec, ...] = (
    # 1. Liquidity (4 metrics)
    MetricSpec(
        key="current_ratio",
        pillar="liquidity",
        label_vi="Hệ số thanh toán hiện hành",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 1,50x",
        tooltip_vi=(
            "Tỷ lệ Tài sản ngắn hạn trên Nợ ngắn hạn; cho biết mức đệm thanh khoản "
            "để chi trả các nghĩa vụ đến hạn trong năm tới."
        ),
        score_low=0.50,
        score_high=2.50,
        good_threshold=1.50,
        warning_threshold=1.10,
        critical_threshold=0.80,
    ),
    MetricSpec(
        key="quick_ratio",
        pillar="liquidity",
        label_vi="Hệ số thanh toán nhanh",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 1,00x",
        tooltip_vi=(
            "Khả năng trả nợ ngắn hạn bằng tài sản thanh khoản cao không phụ thuộc "
            "vào việc bán hàng tồn kho."
        ),
        score_low=0.30,
        score_high=1.80,
        good_threshold=1.00,
        warning_threshold=0.70,
        critical_threshold=0.50,
    ),
    MetricSpec(
        key="cash_ratio",
        pillar="liquidity",
        label_vi="Hệ số thanh toán tiền mặt",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 0,30x",
        tooltip_vi=(
            "Tỷ lệ Tiền và tương đương tiền trên Nợ ngắn hạn; đo lường khả năng "
            "thanh toán tức thì khi thị trường căng thẳng."
        ),
        score_low=0.05,
        score_high=0.80,
        good_threshold=0.30,
        warning_threshold=0.15,
        critical_threshold=0.05,
    ),
    MetricSpec(
        key="working_capital_ratio",
        pillar="liquidity",
        label_vi="Vốn lưu động ròng / Tổng tài sản",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 10%",
        tooltip_vi=(
            "Tỷ trọng vốn lưu động ròng (TSNH - Nợ NH) trên Tổng tài sản; giá trị âm "
            "cho thấy doanh nghiệp đang dùng nợ ngắn hạn tài trợ tài sản dài hạn."
        ),
        score_low=-0.20,
        score_high=0.35,
        good_threshold=0.10,
        warning_threshold=0.00,
        critical_threshold=-0.10,
    ),
    # 2. Solvency (5 metrics)
    MetricSpec(
        key="debt_ratio",
        pillar="solvency",
        label_vi="Nợ phải trả / Tổng tài sản",
        unit="percent",
        good_direction="lower",
        reference_range_vi="<= 60%",
        tooltip_vi=(
            "Tỷ lệ tài sản được tài trợ bằng nợ phải trả; tỷ lệ càng cao thì áp lực "
            "nghĩa vụ tài chính và rủi ro mất cân đối vốn càng lớn."
        ),
        score_low=0.20,
        score_high=0.95,
        good_threshold=0.60,
        warning_threshold=0.75,
        critical_threshold=0.85,
    ),
    MetricSpec(
        key="equity_to_assets",
        pillar="solvency",
        label_vi="Vốn chủ sở hữu / Tổng tài sản",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 40%",
        tooltip_vi=(
            "Đệm vốn tự có của chủ sở hữu trên tổng tài sản; giá trị âm cảnh báo "
            "lỗ lũy kế đã bào mòn toàn bộ vốn chủ sở hữu."
        ),
        score_low=0.00,
        score_high=0.65,
        good_threshold=0.40,
        warning_threshold=0.25,
        critical_threshold=0.10,
    ),
    MetricSpec(
        key="short_term_debt_share",
        pillar="solvency",
        label_vi="Tỷ trọng nợ ngắn hạn / Tổng nợ",
        unit="percent",
        good_direction="lower",
        reference_range_vi="<= 60%",
        tooltip_vi=(
            "Tỷ phần nợ phải trả đến hạn trong 12 tháng trên tổng nợ; tỷ trọng quá cao "
            "làm tăng áp lực đáo hạn và rủi ro tái cấp vốn."
        ),
        score_low=0.25,
        score_high=0.95,
        good_threshold=0.60,
        warning_threshold=0.75,
        critical_threshold=0.85,
    ),
    MetricSpec(
        key="interest_coverage",
        pillar="solvency",
        label_vi="Khả năng thanh toán lãi vay (EBIT/Lãi vay)",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 3,00x",
        tooltip_vi=(
            "Số lần lợi nhuận hoạt động (EBIT) đủ bù đắp chi phí lãi vay; dưới 1,5x "
            "báo hiệu doanh nghiệp chật vật trả lãi."
        ),
        score_low=-1.00,
        score_high=10.00,
        good_threshold=3.00,
        warning_threshold=1.50,
        critical_threshold=1.00,
    ),
    MetricSpec(
        key="retained_earnings_ratio",
        pillar="solvency",
        label_vi="Lợi nhuận giữ lại / Tổng tài sản",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 15%",
        tooltip_vi=(
            "Thước đo khả năng tự tích lũy vốn từ lợi nhuận qua nhiều năm; giá trị âm "
            "phản ánh lỗ lũy kế kéo dài."
        ),
        score_low=-0.40,
        score_high=0.40,
        good_threshold=0.15,
        warning_threshold=0.00,
        critical_threshold=-0.15,
    ),
    # 3. Profitability (5 metrics)
    MetricSpec(
        key="gross_margin",
        pillar="profitability",
        label_vi="Biên lợi nhuận gộp",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 20%",
        tooltip_vi=(
            "Tỷ lệ lợi nhuận gộp trên doanh thu thuần; phản ánh sức mạnh định giá "
            "và khả năng kiểm soát giá vốn hàng bán."
        ),
        score_low=0.00,
        score_high=0.45,
        good_threshold=0.20,
        warning_threshold=0.10,
        critical_threshold=0.05,
    ),
    MetricSpec(
        key="operating_margin",
        pillar="profitability",
        label_vi="Biên lợi nhuận hoạt động (EBIT)",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 8%",
        tooltip_vi=(
            "Tỷ suất sinh lời từ hoạt động kinh doanh cốt lõi trước lãi vay và thuế "
            "trên mỗi đồng doanh thu."
        ),
        score_low=-0.15,
        score_high=0.25,
        good_threshold=0.08,
        warning_threshold=0.02,
        critical_threshold=0.00,
    ),
    MetricSpec(
        key="ebitda_margin",
        pillar="profitability",
        label_vi="Biên EBITDA",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 12%",
        tooltip_vi=(
            "Lợi nhuận hoạt động cộng khấu hao trên doanh thu; thể hiện năng lực tạo "
            "dòng tiền hoạt động trước tác động tài trợ và thuế."
        ),
        score_low=-0.10,
        score_high=0.30,
        good_threshold=0.12,
        warning_threshold=0.05,
        critical_threshold=0.00,
    ),
    MetricSpec(
        key="roa",
        pillar="profitability",
        label_vi="Tỷ suất sinh lời trên tài sản (ROA)",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 5%",
        tooltip_vi=(
            "Lợi nhuận sau thuế trên Tổng tài sản; đo lường hiệu quả sử dụng toàn bộ "
            "tài sản để tạo ra lợi nhuận ròng."
        ),
        score_low=-0.15,
        score_high=0.20,
        good_threshold=0.05,
        warning_threshold=0.01,
        critical_threshold=-0.02,
    ),
    MetricSpec(
        key="roe",
        pillar="profitability",
        label_vi="Tỷ suất sinh lời trên VCSH (ROE)",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 12%",
        tooltip_vi=(
            "Lợi nhuận sau thuế trên Vốn chủ sở hữu; khi âm VCSH chỉ số không có ý nghĩa "
            "dương và bị phạt mức rủi ro nghiêm trọng."
        ),
        score_low=-0.30,
        score_high=0.35,
        good_threshold=0.12,
        warning_threshold=0.04,
        critical_threshold=0.00,
    ),
    # 4. Efficiency (3 metrics)
    MetricSpec(
        key="asset_turnover",
        pillar="efficiency",
        label_vi="Vòng quay tổng tài sản",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 0,70x",
        tooltip_vi=(
            "Doanh thu thuần trên Tổng tài sản; cho biết mỗi đồng tài sản tạo ra bao nhiêu "
            "đồng doanh thu trong kỳ."
        ),
        score_low=0.15,
        score_high=1.50,
        good_threshold=0.70,
        warning_threshold=0.40,
        critical_threshold=0.20,
    ),
    MetricSpec(
        key="dso_days",
        pillar="efficiency",
        label_vi="Số ngày thu tiền bình quân (DSO)",
        unit="days",
        good_direction="lower",
        reference_range_vi="<= 60 ngày",
        tooltip_vi=(
            "Số ngày trung bình doanh nghiệp thu được tiền từ khách hàng; DSO kéo dài "
            "cảnh báo rủi ro bị chiếm dụng vốn hoặc nợ xấu."
        ),
        score_low=15.0,
        score_high=150.0,
        good_threshold=60.0,
        warning_threshold=90.0,
        critical_threshold=120.0,
    ),
    MetricSpec(
        key="dio_days",
        pillar="efficiency",
        label_vi="Số ngày tồn kho bình quân (DIO)",
        unit="days",
        good_direction="lower",
        reference_range_vi="<= 75 ngày",
        tooltip_vi=(
            "Số ngày trung bình hàng hóa lưu kho trước khi tiêu thụ; DIO tăng đột biến "
            "báo hiệu hàng chậm luân chuyển và ứ đọng vốn."
        ),
        score_low=15.0,
        score_high=180.0,
        good_threshold=75.0,
        warning_threshold=110.0,
        critical_threshold=150.0,
    ),
    # 5. Cash Flow (3 metrics)
    MetricSpec(
        key="ocf_ratio",
        pillar="cash_flow",
        label_vi="Dòng tiền hoạt động / Tổng nợ",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 15%",
        tooltip_vi=(
            "Tỷ lệ Dòng tiền thuần từ hoạt động kinh doanh (OCF) trên Tổng nợ phải trả; "
            "phản ánh khả năng tự tạo tiền để trả nợ mà không cần vay mới."
        ),
        score_low=-0.15,
        score_high=0.35,
        good_threshold=0.15,
        warning_threshold=0.05,
        critical_threshold=0.00,
    ),
    MetricSpec(
        key="fcf_to_liabilities",
        pillar="cash_flow",
        label_vi="Dòng tiền tự do (FCF) / Tổng nợ",
        unit="percent",
        good_direction="higher",
        reference_range_vi=">= 5%",
        tooltip_vi=(
            "Dòng tiền còn lại sau chi đầu tư tài sản cố định (CapEx) trên Tổng nợ; "
            "thể hiện dư địa tiền mặt thực để giảm nợ và chi trả cổ tức."
        ),
        score_low=-0.20,
        score_high=0.25,
        good_threshold=0.05,
        warning_threshold=-0.02,
        critical_threshold=-0.10,
    ),
    MetricSpec(
        key="cash_conversion_qoe",
        pillar="cash_flow",
        label_vi="Tỷ lệ chuyển hóa lợi nhuận thành tiền (OCF/LNST)",
        unit="times",
        good_direction="higher",
        reference_range_vi=">= 0,80x",
        tooltip_vi=(
            "Đo lường chất lượng lợi nhuận; giá trị >= 0,8x cho thấy lợi nhuận kế toán "
            "được bảo chứng bằng dòng tiền thực thu."
        ),
        score_low=-0.50,
        score_high=1.50,
        good_threshold=0.80,
        warning_threshold=0.40,
        critical_threshold=0.00,
    ),
)

METRIC_CATALOG: dict[str, MetricSpec] = {spec.key: spec for spec in METRIC_SPECS}

PILLAR_METRIC_KEYS: dict[PillarKey, tuple[str, ...]] = {
    pillar.key: tuple(spec.key for spec in METRIC_SPECS if spec.pillar == pillar.key)
    for pillar in PILLAR_SPECS
}


def evaluate_metric_status(
    key: str,
    value: float | None,
    *,
    is_negative_equity: bool = False,
) -> MetricStatus:
    """Classify an observed financial ratio into GOOD/NEUTRAL/WARNING/CRITICAL/UNAVAILABLE."""
    spec = METRIC_CATALOG.get(key)
    if spec is None:
        return "UNAVAILABLE"
    if is_negative_equity and key in ("roe", "equity_to_assets", "debt_to_equity"):
        return "CRITICAL"
    finite_val = _finite(value)
    if finite_val is None:
        return "UNAVAILABLE"
    if spec.good_direction == "higher":
        if finite_val >= spec.good_threshold:
            return "GOOD"
        if finite_val >= spec.warning_threshold:
            return "NEUTRAL"
        if finite_val >= spec.critical_threshold:
            return "WARNING"
        return "CRITICAL"
    if finite_val <= spec.good_threshold:
        return "GOOD"
    if finite_val <= spec.warning_threshold:
        return "NEUTRAL"
    if finite_val <= spec.critical_threshold:
        return "WARNING"
    return "CRITICAL"


def format_metric_value_vi(key: str, value: float | None) -> str:
    """Format a ratio value using Vietnamese locale conventions for plain-language explanations."""
    finite_val = _finite(value)
    if finite_val is None:
        return "Không khả dụng"
    spec = METRIC_CATALOG.get(key)
    unit = spec.unit if spec is not None else "ratio"
    if unit == "percent":
        return f"{finite_val * 100:.1f}%".replace(".", ",")
    if unit == "times":
        return f"{finite_val:.2f}x".replace(".", ",")
    if unit == "days":
        return f"{round(finite_val):d} ngày"
    return f"{finite_val:.2f}".replace(".", ",")
