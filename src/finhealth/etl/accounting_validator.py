"""Accounting balance-sheet structural validator and business-warning assistant."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from typing import Any, Literal

from finhealth.etl.financial_ratios import _finite

IssueSeverity = Literal["error", "warning"]
DEFAULT_BALANCE_TOLERANCE_PCT = 0.005


@dataclass(frozen=True)
class FieldCheckIssue:
    """One actionable structural error or business warning tied to exact statement fields."""

    code: str
    severity: IssueSeverity
    field: str
    message: str
    related_fields: list[str] = dataclass_field(default_factory=list)
    expected: float | None = None
    actual: float | None = None
    discrepancy: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the issue into a JSON-compatible dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    """Complete balance-sheet validation result separating hard errors from soft warnings."""

    is_balanced: bool
    errors: list[FieldCheckIssue] = dataclass_field(default_factory=list)
    warnings: list[FieldCheckIssue] = dataclass_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for API responses and statement persistence."""
        return {
            "is_balanced": self.is_balanced,
            "errors": [item.to_dict() for item in self.errors],
            "warnings": [item.to_dict() for item in self.warnings],
        }


def validate_financial_statement(
    stmt: Mapping[str, Any],
    *,
    balance_tolerance_pct: float = DEFAULT_BALANCE_TOLERANCE_PCT,
) -> ValidationReport:
    """Validate accounting identities, sub-item bounds, and key solvency warnings.

    Hard errors block statement finalization. Soft warnings allow continuation while
    surfacing negative equity, thin equity buffers, gross-profit discrepancies, or
    cash-flow divergence.
    """
    errors: list[FieldCheckIssue] = []
    warnings: list[FieldCheckIssue] = []
    eps = 1e-6

    total_assets = _finite(stmt.get("total_assets"))
    current_assets = _finite(stmt.get("current_assets"))
    cash = _finite(stmt.get("cash_and_equivalents"))
    receivables = _finite(stmt.get("accounts_receivable"))
    inventory = _finite(stmt.get("inventory"))

    total_liabilities = _finite(stmt.get("total_liabilities"))
    current_liabilities = _finite(stmt.get("current_liabilities"))
    short_term_debt = _finite(stmt.get("short_term_debt"))
    long_term_debt = _finite(stmt.get("long_term_debt"))
    equity = _finite(stmt.get("stockholders_equity"))

    revenues = _finite(stmt.get("revenues"))
    cogs = _finite(stmt.get("cost_of_goods_sold"))
    gross_profit = _finite(stmt.get("gross_profit"))
    net_income = _finite(stmt.get("net_income"))
    ocf = _finite(stmt.get("operating_cash_flow"))

    if total_assets is not None and total_assets <= 0.0:
        errors.append(
            FieldCheckIssue(
                code="NON_POSITIVE_TOTAL_ASSETS",
                severity="error",
                field="total_assets",
                message="Tổng cộng tài sản phải lớn hơn 0.",
                expected=1.0,
                actual=total_assets,
                discrepancy=total_assets,
            )
        )

    if (
        total_assets is not None
        and total_liabilities is not None
        and equity is not None
    ):
        expected_total = total_liabilities + equity
        discrepancy = total_assets - expected_total
        tolerance = max(1.0, balance_tolerance_pct * abs(total_assets))
        if abs(discrepancy) > tolerance:
            errors.append(
                FieldCheckIssue(
                    code="BALANCE_SHEET_IMBALANCE",
                    severity="error",
                    field="total_assets",
                    related_fields=["total_liabilities", "stockholders_equity"],
                    message=(
                        "Tổng tài sản không khớp Tổng nợ phải trả + Vốn chủ sở hữu "
                        f"(lệch {discrepancy:,.2f}, vượt ngưỡng dung sai {tolerance:,.2f})."
                    ),
                    expected=expected_total,
                    actual=total_assets,
                    discrepancy=discrepancy,
                )
            )

    if (
        current_assets is not None
        and total_assets is not None
        and current_assets > total_assets + eps
    ):
        diff = current_assets - total_assets
        errors.append(
            FieldCheckIssue(
                code="CURRENT_ASSETS_EXCEED_TOTAL",
                severity="error",
                field="current_assets",
                related_fields=["total_assets"],
                message=f"Tài sản ngắn hạn vượt quá Tổng cộng tài sản ({diff:,.2f}).",
                expected=total_assets,
                actual=current_assets,
                discrepancy=diff,
            )
        )

    if (
        current_liabilities is not None
        and total_liabilities is not None
        and current_liabilities > total_liabilities + eps
    ):
        diff = current_liabilities - total_liabilities
        errors.append(
            FieldCheckIssue(
                code="CURRENT_LIABILITIES_EXCEED_TOTAL",
                severity="error",
                field="current_liabilities",
                related_fields=["total_liabilities"],
                message=f"Nợ ngắn hạn vượt quá Tổng nợ phải trả ({diff:,.2f}).",
                expected=total_liabilities,
                actual=current_liabilities,
                discrepancy=diff,
            )
        )

    if current_assets is not None:
        for sub_field, sub_value, code, label in (
            (
                "cash_and_equivalents",
                cash,
                "CASH_EXCEEDS_CURRENT_ASSETS",
                "Tiền và tương đương tiền",
            ),
            (
                "inventory",
                inventory,
                "INVENTORY_EXCEEDS_CURRENT_ASSETS",
                "Hàng tồn kho",
            ),
            (
                "accounts_receivable",
                receivables,
                "RECEIVABLES_EXCEEDS_CURRENT_ASSETS",
                "Các khoản phải thu ngắn hạn",
            ),
        ):
            if sub_value is not None and sub_value > current_assets + eps:
                diff = sub_value - current_assets
                errors.append(
                    FieldCheckIssue(
                        code=code,
                        severity="error",
                        field=sub_field,
                        related_fields=["current_assets"],
                        message=f"{label} vượt quá Tài sản ngắn hạn ({diff:,.2f}).",
                        expected=current_assets,
                        actual=sub_value,
                        discrepancy=diff,
                    )
                )

    if (
        short_term_debt is not None
        and current_liabilities is not None
        and short_term_debt > current_liabilities + eps
    ):
        diff = short_term_debt - current_liabilities
        errors.append(
            FieldCheckIssue(
                code="SHORT_TERM_DEBT_EXCEEDS_CURRENT_LIABILITIES",
                severity="error",
                field="short_term_debt",
                related_fields=["current_liabilities"],
                message=f"Vay và nợ thuê tài chính ngắn hạn vượt quá Nợ ngắn hạn ({diff:,.2f}).",
                expected=current_liabilities,
                actual=short_term_debt,
                discrepancy=diff,
            )
        )

    if (
        long_term_debt is not None
        and total_liabilities is not None
        and current_liabilities is not None
        and total_liabilities >= current_liabilities - eps
    ):
        non_current_liabilities = max(0.0, total_liabilities - current_liabilities)
        if long_term_debt > non_current_liabilities + eps:
            diff = long_term_debt - non_current_liabilities
            errors.append(
                FieldCheckIssue(
                    code="LONG_TERM_DEBT_EXCEEDS_NONCURRENT_LIABILITIES",
                    severity="error",
                    field="long_term_debt",
                    related_fields=["total_liabilities", "current_liabilities"],
                    message=(
                        "Vay và nợ thuê tài chính dài hạn vượt quá Nợ dài hạn "
                        f"({diff:,.2f})."
                    ),
                    expected=non_current_liabilities,
                    actual=long_term_debt,
                    discrepancy=diff,
                )
            )

    if equity is not None and equity <= 0.0:
        warnings.append(
            FieldCheckIssue(
                code="NEGATIVE_EQUITY",
                severity="warning",
                field="stockholders_equity",
                related_fields=["total_assets", "total_liabilities"],
                message=(
                    "Doanh nghiệp đang bị âm vốn chủ sở hữu (VCSH <= 0); "
                    "ROE và Nợ/VCSH sẽ được bỏ trống thay vì chia cho số âm."
                ),
                expected=0.0,
                actual=equity,
                discrepancy=equity,
            )
        )
    elif (
        equity is not None
        and total_assets is not None
        and total_assets > 0.0
        and equity / total_assets < 0.05
    ):
        warnings.append(
            FieldCheckIssue(
                code="THIN_EQUITY",
                severity="warning",
                field="stockholders_equity",
                related_fields=["total_assets"],
                message=(
                    "Đệm vốn chủ sở hữu mỏng (VCSH/Tổng tài sản < 5%); "
                    "cần lưu ý rủi ro đòn bẩy cao."
                ),
                expected=0.05 * total_assets,
                actual=equity,
                discrepancy=equity - 0.05 * total_assets,
            )
        )

    if revenues is not None and cogs is not None and gross_profit is not None:
        expected_gp = revenues - cogs
        diff = gross_profit - expected_gp
        gp_tolerance = max(1.0, 0.01 * max(abs(revenues), abs(expected_gp), 1.0))
        if abs(diff) > gp_tolerance:
            warnings.append(
                FieldCheckIssue(
                    code="GROSS_PROFIT_MISMATCH",
                    severity="warning",
                    field="gross_profit",
                    related_fields=["revenues", "cost_of_goods_sold"],
                    message=(
                        "Lợi nhuận gộp lệch quá 1% so với Doanh thu thuần - Giá vốn hàng bán "
                        f"(lệch {diff:,.2f})."
                    ),
                    expected=expected_gp,
                    actual=gross_profit,
                    discrepancy=diff,
                )
            )

    if net_income is not None and ocf is not None and net_income > 0.0 and ocf < 0.0:
        warnings.append(
            FieldCheckIssue(
                code="PROFIT_NEGATIVE_OCF",
                severity="warning",
                field="operating_cash_flow",
                related_fields=["net_income"],
                message=(
                    "Lợi nhuận sau thuế dương nhưng dòng tiền hoạt động kinh doanh âm; "
                    "cần kiểm tra chất lượng thu tiền và vốn lưu động."
                ),
                expected=0.0,
                actual=ocf,
                discrepancy=ocf,
            )
        )

    return ValidationReport(is_balanced=len(errors) == 0, errors=errors, warnings=warnings)
