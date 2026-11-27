import { AlertCircle, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { FieldCheckIssue, OrgStatementNumericFields, ValidationReport } from '@/types/api';

export const STATEMENT_FIELD_LABELS_VI: Record<string, string> = {
  total_assets: 'Tổng cộng tài sản (270)',
  current_assets: 'Tài sản ngắn hạn (100)',
  cash_and_equivalents: 'Tiền và tương đương tiền (110)',
  accounts_receivable: 'Các khoản phải thu ngắn hạn (130)',
  inventory: 'Hàng tồn kho (140)',
  total_liabilities: 'Nợ phải trả (300)',
  current_liabilities: 'Nợ ngắn hạn (310)',
  accounts_payable: 'Phải trả người bán ngắn hạn (311)',
  short_term_debt: 'Vay và nợ thuê tài chính ngắn hạn',
  long_term_debt: 'Vay và nợ thuê tài chính dài hạn',
  stockholders_equity: 'Vốn chủ sở hữu (400)',
  retained_earnings: 'Lợi nhuận sau thuế chưa phân phối',
  revenues: 'Doanh thu thuần (10)',
  cost_of_goods_sold: 'Giá vốn hàng bán (11)',
  gross_profit: 'Lợi nhuận gộp (20)',
  operating_expenses: 'Chi phí hoạt động (BH + QLDN)',
  operating_income: 'Lợi nhuận thuần từ HĐKD (30)',
  depreciation_amortization: 'Khấu hao TSCĐ & phân bổ',
  ebitda: 'EBITDA',
  interest_expense: 'Chi phí lãi vay (23)',
  net_income: 'Lợi nhuận sau thuế (60)',
  operating_cash_flow: 'Lưu chuyển tiền thuần từ HĐKD (20)',
  capex: 'Chi mua sắm TSCĐ (CAPEX)',
};

function isNum(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** Client-side live mirror of backend `accounting_validator.py` (0.5% tolerance). */
export function evaluateStatementBalance(
  values: OrgStatementNumericFields,
): ValidationReport {
  const errors: FieldCheckIssue[] = [];
  const warnings: FieldCheckIssue[] = [];

  const ta = values.total_assets;
  const ca = values.current_assets;
  const cash = values.cash_and_equivalents;
  const ar = values.accounts_receivable;
  const inv = values.inventory;
  const tl = values.total_liabilities;
  const cl = values.current_liabilities;
  const stDebt = values.short_term_debt;
  const ltDebt = values.long_term_debt;
  const eq = values.stockholders_equity;
  const rev = values.revenues;
  const cogs = values.cost_of_goods_sold;
  const gp = values.gross_profit;
  const ni = values.net_income;
  const ocf = values.operating_cash_flow;

  if (isNum(ta) && ta <= 0) {
    errors.push({
      code: 'NON_POSITIVE_TOTAL_ASSETS',
      severity: 'error',
      field: 'total_assets',
      message: 'Tổng cộng tài sản phải lớn hơn 0.',
      related_fields: ['total_assets'],
      actual: ta,
    });
  }

  if (isNum(ta) && isNum(tl) && isNum(eq)) {
    const expected = tl + eq;
    const diff = ta - expected;
    const tolerance = Math.max(1, 0.005 * Math.abs(ta));
    if (Math.abs(diff) > tolerance) {
      errors.push({
        code: 'BALANCE_SHEET_IMBALANCE',
        severity: 'error',
        field: 'total_assets',
        message: `Bảng cân đối bị lệch: Tổng tài sản (${ta.toLocaleString('vi-VN')}) ≠ Nợ phải trả + Vốn chủ sở hữu (${expected.toLocaleString('vi-VN')}). Mức chênh lệch: ${diff.toLocaleString('vi-VN')}.`,
        related_fields: ['total_assets', 'total_liabilities', 'stockholders_equity'],
        expected,
        actual: ta,
        discrepancy: diff,
      });
    }
  }

  if (isNum(ca) && isNum(ta) && ca > ta) {
    errors.push({
      code: 'CURRENT_ASSETS_EXCEEDS_TOTAL',
      severity: 'error',
      field: 'current_assets',
      message: 'Tài sản ngắn hạn không được lớn hơn Tổng cộng tài sản.',
      related_fields: ['current_assets', 'total_assets'],
      expected: ta,
      actual: ca,
      discrepancy: ca - ta,
    });
  }

  if (isNum(cl) && isNum(tl) && cl > tl) {
    errors.push({
      code: 'CURRENT_LIABILITIES_EXCEEDS_TOTAL',
      severity: 'error',
      field: 'current_liabilities',
      message: 'Nợ ngắn hạn không được lớn hơn Tổng nợ phải trả.',
      related_fields: ['current_liabilities', 'total_liabilities'],
      expected: tl,
      actual: cl,
      discrepancy: cl - tl,
    });
  }

  if (isNum(ca)) {
    for (const [field, val, label] of [
      ['cash_and_equivalents', cash, 'Tiền và tương đương tiền'],
      ['accounts_receivable', ar, 'Phải thu ngắn hạn'],
      ['inventory', inv, 'Hàng tồn kho'],
    ] as const) {
      if (isNum(val) && val > ca) {
        errors.push({
          code: 'COMPONENT_EXCEEDS_CURRENT_ASSETS',
          severity: 'error',
          field,
          message: `${label} không được lớn hơn Tài sản ngắn hạn.`,
          related_fields: [field, 'current_assets'],
          expected: ca,
          actual: val,
          discrepancy: val - ca,
        });
      }
    }
  }

  if (isNum(stDebt) && isNum(cl) && stDebt > cl) {
    errors.push({
      code: 'SHORT_TERM_DEBT_EXCEEDS_CURRENT_LIABILITIES',
      severity: 'error',
      field: 'short_term_debt',
      message: 'Vay ngắn hạn không được lớn hơn Nợ ngắn hạn.',
      related_fields: ['short_term_debt', 'current_liabilities'],
      expected: cl,
      actual: stDebt,
      discrepancy: stDebt - cl,
    });
  }

  if (isNum(ltDebt) && isNum(tl) && isNum(cl)) {
    const nonCurrentLiab = tl - cl;
    if (ltDebt > nonCurrentLiab + 1e-6) {
      errors.push({
        code: 'LONG_TERM_DEBT_EXCEEDS_NON_CURRENT_LIABILITIES',
        severity: 'error',
        field: 'long_term_debt',
        message: 'Vay dài hạn không được lớn hơn Nợ dài hạn (Tổng nợ - Nợ ngắn hạn).',
        related_fields: ['long_term_debt', 'total_liabilities', 'current_liabilities'],
        expected: nonCurrentLiab,
        actual: ltDebt,
        discrepancy: ltDebt - nonCurrentLiab,
      });
    }
  }

  // Business Warnings (non-blocking)
  if (isNum(eq) && eq <= 0) {
    warnings.push({
      code: 'NEGATIVE_EQUITY',
      severity: 'warning',
      field: 'stockholders_equity',
      message:
        'Cảnh báo âm vốn chủ sở hữu (VCSH ≤ 0): Doanh nghiệp đang mất cân đối vốn nghiêm trọng.',
      related_fields: ['stockholders_equity'],
      actual: eq,
    });
  } else if (isNum(eq) && isNum(ta) && ta > 0 && eq / ta < 0.05) {
    warnings.push({
      code: 'THIN_EQUITY',
      severity: 'warning',
      field: 'stockholders_equity',
      message: 'Đệm vốn chủ sở hữu mỏng (< 5% Tổng tài sản), rủi ro đòn bẩy cao.',
      related_fields: ['stockholders_equity', 'total_assets'],
      actual: eq / ta,
    });
  }

  if (isNum(rev) && isNum(cogs) && isNum(gp)) {
    const expectedGp = rev - cogs;
    const tol = Math.max(1, 0.01 * Math.abs(rev));
    if (Math.abs(gp - expectedGp) > tol) {
      warnings.push({
        code: 'GROSS_PROFIT_MISMATCH',
        severity: 'warning',
        field: 'gross_profit',
        message: `Lợi nhuận gộp lệch trên 1% so với Doanh thu thuần - Giá vốn (${expectedGp.toLocaleString('vi-VN')}).`,
        related_fields: ['gross_profit', 'revenues', 'cost_of_goods_sold'],
        expected: expectedGp,
        actual: gp,
        discrepancy: gp - expectedGp,
      });
    }
  }

  if (isNum(ni) && ni > 0 && isNum(ocf) && ocf < 0) {
    warnings.push({
      code: 'PROFIT_WITH_NEGATIVE_OCF',
      severity: 'warning',
      field: 'operating_cash_flow',
      message:
        'Lợi nhuận sau thuế dương nhưng Lưu chuyển tiền từ hoạt động kinh doanh âm — cần lưu ý chất lượng lợi nhuận.',
      related_fields: ['net_income', 'operating_cash_flow'],
    });
  }

  return {
    is_balanced: errors.length === 0,
    errors,
    warnings,
  };
}

interface BalanceCheckAssistantProps {
  report: ValidationReport;
  onSelectField?: (field: string) => void;
}

export function BalanceCheckAssistant({
  report,
  onSelectField,
}: BalanceCheckAssistantProps) {
  const hasErrors = report.errors.length > 0;
  const hasWarnings = report.warnings.length > 0;

  return (
    <div
      className="surface p-4 space-y-3 text-xs"
      role={hasErrors ? 'alert' : 'status'}
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 font-semibold">
          {hasErrors ? (
            <>
              <AlertCircle
                className="h-4 w-4 text-[var(--risk-critical-fg)] shrink-0"
                aria-hidden="true"
              />
              <span className="text-[var(--risk-critical-fg)]">
                Trợ lý Cân đối Kế toán: Phát hiện {report.errors.length} lỗi cứng cần xử lý trước
                khi chốt
              </span>
            </>
          ) : (
            <>
              <CheckCircle2
                className="h-4 w-4 text-[var(--risk-low-fg)] shrink-0"
                aria-hidden="true"
              />
              <span className="text-[var(--risk-low-fg)]">
                Trợ lý Cân đối Kế toán: Đạt cân đối cấu trúc (có thể chốt báo cáo)
              </span>
            </>
          )}
        </div>
      </div>

      {hasErrors ? (
        <ul className="space-y-2">
          {report.errors.map((issue, idx) => (
            <li
              key={`${issue.code}-${issue.field}-${idx}`}
              className="p-2.5 rounded-[6px] bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)] flex flex-wrap items-start justify-between gap-2"
            >
              <div className="space-y-1">
                <div className="font-semibold">
                  Dòng lệch: {STATEMENT_FIELD_LABELS_VI[issue.field] ?? issue.field}
                </div>
                <div>{issue.message}</div>
                {issue.related_fields.length > 1 ? (
                  <div className="text-[11px] opacity-90">
                    Các chỉ tiêu liên quan:{' '}
                    {issue.related_fields
                      .map((f) => STATEMENT_FIELD_LABELS_VI[f] ?? f)
                      .join(' · ')}
                  </div>
                ) : null}
              </div>
              {onSelectField ? (
                <button
                  type="button"
                  onClick={() => onSelectField(issue.field)}
                  className="px-2 py-1 rounded bg-[var(--bg-surface)] text-[var(--risk-critical-fg)] border border-[var(--risk-critical-fg)]/30 text-[11px] font-medium cursor-pointer hover:opacity-90"
                >
                  Đi tới dòng lệch
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {hasWarnings ? (
        <ul className="space-y-1.5">
          {report.warnings.map((issue, idx) => (
            <li
              key={`${issue.code}-${issue.field}-${idx}`}
              className="p-2.5 rounded-[6px] bg-[var(--risk-medium-bg)] text-[var(--risk-medium-fg)] flex items-start gap-2"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <span className="font-semibold">
                  {STATEMENT_FIELD_LABELS_VI[issue.field] ?? issue.field}:{' '}
                </span>
                <span>{issue.message}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
