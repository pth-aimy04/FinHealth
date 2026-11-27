import { useMemo, useState } from 'react';
import { Calculator, CheckCircle2, Save } from 'lucide-react';
import type {
  AccountingStandard,
  AuditStatus,
  CurrencyCode,
  OrgStatement,
  OrgStatementInput,
  OrgStatementNumericFields,
  UnitScale,
  ValidationReport,
} from '@/types/api';
import {
  ACCOUNTING_STANDARD_LABELS,
  AUDIT_STATUS_LABELS,
} from '@/lib/format';
import {
  BalanceCheckAssistant,
  evaluateStatementBalance,
} from '@/components/statements/BalanceCheckAssistant';
import { Button, Panel, PanelHeader, cn } from '@/components/ui/Primitives';

type SectionTab = 'bs' | 'is' | 'cf';
type NumericKey = keyof OrgStatementNumericFields;

interface LineItemDef {
  field: NumericKey;
  label: string;
  codes: Record<'TT99_2025' | 'TT200_2014' | 'TT133_2016', string>;
  isParent?: boolean;
  isPerShare?: boolean;
  helper?: string;
}

const BS_LINES: LineItemDef[] = [
  {
    field: 'total_assets',
    label: 'Tổng cộng tài sản',
    codes: { TT99_2025: '270', TT200_2014: '270', TT133_2016: '270' },
    isParent: true,
    helper: 'Phải cân đối bằng Nợ phải trả (300) + Vốn chủ sở hữu (400).',
  },
  {
    field: 'current_assets',
    label: 'Tài sản ngắn hạn',
    codes: { TT99_2025: '100', TT200_2014: '100', TT133_2016: '100' },
    isParent: true,
  },
  {
    field: 'cash_and_equivalents',
    label: 'Tiền và các khoản tương đương tiền',
    codes: { TT99_2025: '110', TT200_2014: '110', TT133_2016: '110' },
  },
  {
    field: 'accounts_receivable',
    label: 'Các khoản phải thu ngắn hạn',
    codes: { TT99_2025: '130', TT200_2014: '130', TT133_2016: '130' },
  },
  {
    field: 'inventory',
    label: 'Hàng tồn kho',
    codes: { TT99_2025: '140', TT200_2014: '140', TT133_2016: '140' },
  },
  {
    field: 'total_liabilities',
    label: 'Nợ phải trả',
    codes: { TT99_2025: '300', TT200_2014: '300', TT133_2016: '300' },
    isParent: true,
  },
  {
    field: 'current_liabilities',
    label: 'Nợ ngắn hạn',
    codes: { TT99_2025: '310', TT200_2014: '310', TT133_2016: '310' },
    isParent: true,
  },
  {
    field: 'accounts_payable',
    label: 'Phải trả người bán ngắn hạn',
    codes: { TT99_2025: '311', TT200_2014: '311', TT133_2016: '311' },
  },
  {
    field: 'short_term_debt',
    label: 'Vay và nợ thuê tài chính ngắn hạn',
    codes: { TT99_2025: '320', TT200_2014: '320', TT133_2016: '316' },
  },
  {
    field: 'long_term_debt',
    label: 'Vay và nợ thuê tài chính dài hạn',
    codes: { TT99_2025: '338', TT200_2014: '338', TT133_2016: '336' },
  },
  {
    field: 'stockholders_equity',
    label: 'Vốn chủ sở hữu',
    codes: { TT99_2025: '400', TT200_2014: '400', TT133_2016: '400' },
    isParent: true,
  },
  {
    field: 'retained_earnings',
    label: 'Lợi nhuận sau thuế chưa phân phối',
    codes: { TT99_2025: '421', TT200_2014: '421', TT133_2016: '417' },
  },
];

const IS_LINES: LineItemDef[] = [
  {
    field: 'revenues',
    label: 'Doanh thu thuần về bán hàng và cung cấp dịch vụ',
    codes: { TT99_2025: '10', TT200_2014: '10', TT133_2016: '10' },
    isParent: true,
  },
  {
    field: 'cost_of_goods_sold',
    label: 'Giá vốn hàng bán',
    codes: { TT99_2025: '11', TT200_2014: '11', TT133_2016: '11' },
  },
  {
    field: 'gross_profit',
    label: 'Lợi nhuận gộp về bán hàng và cung cấp dịch vụ',
    codes: { TT99_2025: '20', TT200_2014: '20', TT133_2016: '20' },
    isParent: true,
    helper: 'Tự tính bằng Doanh thu thuần (10) - Giá vốn (11) khi bấm Tự cộng tổng.',
  },
  {
    field: 'operating_expenses',
    label: 'Chi phí hoạt động (Bán hàng + Quản lý doanh nghiệp)',
    codes: { TT99_2025: '25+26', TT200_2014: '25+26', TT133_2016: '24' },
  },
  {
    field: 'interest_expense',
    label: 'Chi phí lãi vay',
    codes: { TT99_2025: '23', TT200_2014: '23', TT133_2016: '23' },
  },
  {
    field: 'operating_income',
    label: 'Lợi nhuận thuần từ hoạt động kinh doanh',
    codes: { TT99_2025: '30', TT200_2014: '30', TT133_2016: '30' },
    isParent: true,
  },
  {
    field: 'net_income',
    label: 'Lợi nhuận sau thuế thu nhập doanh nghiệp',
    codes: { TT99_2025: '60', TT200_2014: '60', TT133_2016: '60' },
    isParent: true,
  },
  {
    field: 'eps_basic',
    label: 'Lãi cơ bản trên cổ phiếu (không nhân đơn vị)',
    codes: { TT99_2025: '70', TT200_2014: '70', TT133_2016: '—' },
    isPerShare: true,
  },
];

const CF_LINES: LineItemDef[] = [
  {
    field: 'depreciation_amortization',
    label: 'Khấu hao TSCĐ và bất động sản đầu tư',
    codes: { TT99_2025: '02', TT200_2014: '02', TT133_2016: '02' },
  },
  {
    field: 'ebitda',
    label: 'EBITDA (Tự tính = LN thuần HĐKD + Khấu hao)',
    codes: { TT99_2025: '—', TT200_2014: '—', TT133_2016: '—' },
    isParent: true,
  },
  {
    field: 'operating_cash_flow',
    label: 'Lưu chuyển tiền thuần từ hoạt động kinh doanh',
    codes: { TT99_2025: '20', TT200_2014: '20', TT133_2016: '20' },
    isParent: true,
  },
  {
    field: 'capex',
    label: 'Tiền chi mua sắm, xây dựng TSCĐ (CAPEX)',
    codes: { TT99_2025: '21', TT200_2014: '21', TT133_2016: '21' },
  },
  {
    field: 'market_value_equity',
    label: 'Vốn hóa thị trường (tùy chọn — chỉ dùng cho DN niêm yết)',
    codes: { TT99_2025: '—', TT200_2014: '—', TT133_2016: '—' },
  },
];

const ALL_LINES: Array<LineItemDef & { section: SectionTab }> = [
  ...BS_LINES.map((item) => ({ ...item, section: 'bs' as const })),
  ...IS_LINES.map((item) => ({ ...item, section: 'is' as const })),
  ...CF_LINES.map((item) => ({ ...item, section: 'cf' as const })),
];

const UNIT_OPTIONS: Array<{ scale: UnitScale; label: string }> = [
  { scale: 1, label: 'Đồng' },
  { scale: 1_000_000, label: 'Triệu đồng' },
  { scale: 1_000_000_000, label: 'Tỷ đồng' },
];

function parseNumericInput(raw: string): number | null {
  const cleaned = raw.trim().replace(/\s+/g, '').replace(/,/g, '');
  if (!cleaned) return null;
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

function buildInitialDraftStrings(
  initialStatement: OrgStatement | null | undefined,
  unitScale: UnitScale,
): Record<NumericKey, string> {
  const map = {} as Record<NumericKey, string>;
  for (const item of ALL_LINES) {
    const rawVal = initialStatement?.[item.field];
    if (typeof rawVal === 'number' && Number.isFinite(rawVal)) {
      const displayVal = item.isPerShare ? rawVal : rawVal / unitScale;
      map[item.field] = String(Number(displayVal.toFixed(4)));
    } else {
      map[item.field] = '';
    }
  }
  return map;
}

export interface StatementEditorFormProps {
  initialStatement?: OrgStatement | null;
  defaultFiscalYear?: number;
  isSubmitting?: boolean;
  serverError?: string | null;
  serverValidation?: ValidationReport | null;
  onSubmit: (payload: OrgStatementInput) => Promise<void> | void;
  onCancel?: () => void;
}

export function StatementEditorForm({
  initialStatement,
  defaultFiscalYear = new Date().getFullYear() - 1,
  isSubmitting = false,
  serverError = null,
  serverValidation = null,
  onSubmit,
  onCancel,
}: StatementEditorFormProps) {
  const initialScale: UnitScale =
    initialStatement?.unit_scale === 1 ||
    initialStatement?.unit_scale === 1_000_000 ||
    initialStatement?.unit_scale === 1_000_000_000
      ? initialStatement.unit_scale
      : 1_000_000;

  const [activeTab, setActiveTab] = useState<SectionTab>('bs');
  const [fiscalYear, setFiscalYear] = useState<number>(
    initialStatement?.fiscal_year ?? defaultFiscalYear,
  );
  const [fiscalPeriod, setFiscalPeriod] = useState<string>(
    initialStatement?.fiscal_period ?? 'FY',
  );
  const [accountingStandard, setAccountingStandard] = useState<AccountingStandard>(
    (initialStatement?.accounting_standard as AccountingStandard) ?? 'TT99_2025',
  );
  const [currency, setCurrency] = useState<CurrencyCode>(
    (initialStatement?.currency as CurrencyCode) ?? 'VND',
  );
  const [unitScale, setUnitScale] = useState<UnitScale>(initialScale);
  const [auditStatus, setAuditStatus] = useState<AuditStatus>(
    (initialStatement?.audit_status as AuditStatus) ?? 'unaudited',
  );
  const [values, setValues] = useState<Record<NumericKey, string>>(() =>
    buildInitialDraftStrings(initialStatement, initialScale),
  );
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const parsedNumeric = useMemo<OrgStatementNumericFields>(() => {
    const out: OrgStatementNumericFields = {};
    for (const item of ALL_LINES) {
      out[item.field] = parseNumericInput(values[item.field] ?? '');
    }
    return out;
  }, [values]);

  const liveReport = useMemo<ValidationReport>(() => {
    const clientReport = evaluateStatementBalance(parsedNumeric);
    if (serverValidation && serverValidation.errors.length > 0 && clientReport.errors.length === 0) {
      return serverValidation;
    }
    return clientReport;
  }, [parsedNumeric, serverValidation]);

  const errorFieldSet = useMemo(() => {
    const set = new Set<string>();
    for (const issue of liveReport.errors) {
      set.add(issue.field);
      for (const rel of issue.related_fields) {
        set.add(rel);
      }
    }
    return set;
  }, [liveReport.errors]);

  function handleUnitScaleChange(nextScale: UnitScale) {
    if (nextScale === unitScale) return;
    const ratio = unitScale / nextScale;
    setValues((prev) => {
      const next = { ...prev };
      for (const item of ALL_LINES) {
        if (item.isPerShare) continue;
        const num = parseNumericInput(prev[item.field] ?? '');
        if (num !== null) {
          next[item.field] = String(Number((num * ratio).toFixed(4)));
        }
      }
      return next;
    });
    setUnitScale(nextScale);
  }

  function handleFieldChange(field: NumericKey, rawValue: string) {
    setValues((prev) => {
      const next = { ...prev, [field]: rawValue };
      if (field === 'revenues' || field === 'cost_of_goods_sold') {
        const rev = parseNumericInput(next.revenues ?? '');
        const cogs = parseNumericInput(next.cost_of_goods_sold ?? '');
        if (rev !== null && cogs !== null) {
          next.gross_profit = String(Number((rev - cogs).toFixed(4)));
        }
      }
      if (field === 'operating_income' || field === 'depreciation_amortization') {
        const ebit = parseNumericInput(next.operating_income ?? '');
        const da = parseNumericInput(next.depreciation_amortization ?? '');
        if (ebit !== null && da !== null) {
          next.ebitda = String(Number((ebit + da).toFixed(4)));
        }
      }
      if (
        (field === 'total_liabilities' || field === 'stockholders_equity') &&
        !prev.total_assets?.trim()
      ) {
        const tl = parseNumericInput(next.total_liabilities ?? '');
        const eq = parseNumericInput(next.stockholders_equity ?? '');
        if (tl !== null && eq !== null) {
          next.total_assets = String(Number((tl + eq).toFixed(4)));
        }
      }
      return next;
    });
  }

  function handleAutoSumParents() {
    setValues((prev) => {
      const next = { ...prev };
      const tl = parseNumericInput(prev.total_liabilities ?? '');
      const eq = parseNumericInput(prev.stockholders_equity ?? '');
      if (tl !== null && eq !== null) {
        next.total_assets = String(Number((tl + eq).toFixed(4)));
      }
      const cash = parseNumericInput(prev.cash_and_equivalents ?? '');
      const ar = parseNumericInput(prev.accounts_receivable ?? '');
      const inv = parseNumericInput(prev.inventory ?? '');
      if (!prev.current_assets?.trim() && (cash !== null || ar !== null || inv !== null)) {
        next.current_assets = String(
          Number(((cash ?? 0) + (ar ?? 0) + (inv ?? 0)).toFixed(4)),
        );
      }
      const rev = parseNumericInput(prev.revenues ?? '');
      const cogs = parseNumericInput(prev.cost_of_goods_sold ?? '');
      if (rev !== null && cogs !== null) {
        next.gross_profit = String(Number((rev - cogs).toFixed(4)));
      }
      const ebit = parseNumericInput(prev.operating_income ?? '');
      const da = parseNumericInput(prev.depreciation_amortization ?? '');
      if (ebit !== null && da !== null) {
        next.ebitda = String(Number((ebit + da).toFixed(4)));
      }
      return next;
    });
  }

  function handleJumpToField(field: string) {
    const match = ALL_LINES.find((line) => line.field === field);
    if (match) {
      setActiveTab(match.section);
      setFocusedField(field);
    }
  }

  async function submitWithStatus(status: 'draft' | 'finalized') {
    const payload: OrgStatementInput = {
      fiscal_year: fiscalYear,
      fiscal_period: fiscalPeriod,
      accounting_standard: accountingStandard,
      currency,
      unit_scale: unitScale,
      audit_status: auditStatus,
      status,
      ...parsedNumeric,
    };
    await onSubmit(payload);
  }

  const regimeKey: 'TT99_2025' | 'TT200_2014' | 'TT133_2016' =
    accountingStandard === 'TT200_2014' || accountingStandard === 'TT133_2016'
      ? accountingStandard
      : 'TT99_2025';

  const tabLines: Record<SectionTab, LineItemDef[]> = {
    bs: BS_LINES,
    is: IS_LINES,
    cf: CF_LINES,
  };

  const tabTitles: Record<SectionTab, string> = {
    bs:
      accountingStandard === 'TT200_2014'
        ? '1. Bảng cân đối kế toán (B01-DN)'
        : '1. Báo cáo tình hình tài chính',
    is: '2. Kết quả hoạt động kinh doanh',
    cf: '3. Lưu chuyển tiền tệ',
  };

  return (
    <div className="space-y-5">
      <Panel ruled className="overflow-hidden">
        <PanelHeader
          title={
            initialStatement
              ? `Chỉnh sửa BCTC kỳ ${initialStatement.fiscal_year} (${initialStatement.fiscal_period})`
              : 'Nhập Báo cáo Tài chính 3 phần (TT99 / TT200 / TT133)'
          }
          description="Lưu nháp bất kỳ lúc nào; hệ thống kiểm tra cân đối kế toán trước khi chốt chấm điểm."
          actions={
            <Button variant="secondary" size="sm" onClick={handleAutoSumParents}>
              <Calculator className="h-3.5 w-3.5" aria-hidden="true" />
              Tự cộng tổng chỉ tiêu cha
            </Button>
          }
        />

        {/* Metadata Controls Ribbon */}
        <div className="px-5 py-4 bg-[var(--bg-subtle)]/50 border-b border-[var(--border-subtle)] grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
          <div>
            <label htmlFor="stmt-fiscal-year" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Năm tài chính
            </label>
            <input
              id="stmt-fiscal-year"
              type="number"
              min={1990}
              max={2100}
              value={fiscalYear}
              onChange={(e) => setFiscalYear(Number(e.target.value))}
              className="field-control num"
            />
          </div>

          <div>
            <label htmlFor="stmt-fiscal-period" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Kỳ báo cáo
            </label>
            <select
              id="stmt-fiscal-period"
              value={fiscalPeriod}
              onChange={(e) => setFiscalPeriod(e.target.value)}
              className="field-control"
            >
              <option value="FY">Cả năm (FY)</option>
              <option value="H1">Bán niên (H1)</option>
              <option value="Q1">Quý 1 (Q1)</option>
              <option value="Q2">Quý 2 (Q2)</option>
              <option value="Q3">Quý 3 (Q3)</option>
              <option value="Q4">Quý 4 (Q4)</option>
            </select>
          </div>

          <div>
            <label htmlFor="stmt-standard" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Chế độ kế toán
            </label>
            <select
              id="stmt-standard"
              value={accountingStandard}
              onChange={(e) => setAccountingStandard(e.target.value as AccountingStandard)}
              className="field-control"
            >
              <option value="TT99_2025">{ACCOUNTING_STANDARD_LABELS.TT99_2025}</option>
              <option value="TT200_2014">{ACCOUNTING_STANDARD_LABELS.TT200_2014}</option>
              <option value="TT133_2016">{ACCOUNTING_STANDARD_LABELS.TT133_2016}</option>
              <option value="IFRS_USGAAP">{ACCOUNTING_STANDARD_LABELS.IFRS_USGAAP}</option>
            </select>
          </div>

          <div>
            <label htmlFor="stmt-currency" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Tiền tệ
            </label>
            <select
              id="stmt-currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
              className="field-control"
            >
              <option value="VND">VND (₫)</option>
              <option value="USD">USD ($)</option>
            </select>
          </div>

          <div>
            <label htmlFor="stmt-unit-scale" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Đơn vị nhập liệu
            </label>
            <select
              id="stmt-unit-scale"
              aria-label="Đơn vị nhập liệu"
              value={unitScale}
              onChange={(e) => handleUnitScaleChange(Number(e.target.value) as UnitScale)}
              className="field-control"
            >
              {UNIT_OPTIONS.map((opt) => (
                <option key={opt.scale} value={opt.scale}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="stmt-audit-status" className="block font-semibold text-[var(--text-secondary)] mb-1">
              Trạng thái kiểm toán
            </label>
            <select
              id="stmt-audit-status"
              value={auditStatus}
              onChange={(e) => setAuditStatus(e.target.value as AuditStatus)}
              className="field-control"
            >
              {Object.entries(AUDIT_STATUS_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 3 Section Tabs */}
        <div
          className="px-5 flex flex-wrap border-b border-[var(--border-strong)] bg-[var(--bg-header)] gap-1 text-xs"
          role="tablist"
          aria-label="Ba phần báo cáo tài chính"
        >
          {(['bs', 'is', 'cf'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-4 py-2.5 text-[13px] font-semibold border-b-2 -mb-px cursor-pointer bg-transparent transition-colors',
                activeTab === tab
                  ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
              )}
            >
              {tabTitles[tab]}
            </button>
          ))}
        </div>

        {/* Accounting Ledger Input Rows */}
        <div className="divide-y divide-[var(--border-subtle)] text-[13px]">
          {tabLines[activeTab].map((item) => {
            const isErrorField = errorFieldSet.has(item.field);
            const isHighlighted = focusedField === item.field;
            const code = item.codes[regimeKey];
            return (
              <div
                key={item.field}
                className={cn(
                  'py-2.5 px-5 grid grid-cols-1 sm:grid-cols-12 gap-3 items-center transition-colors',
                  item.isParent && !isErrorField && 'bg-[var(--bg-header)]/55',
                  isErrorField && 'bg-[var(--risk-critical-bg)]/60',
                  isHighlighted && 'ring-1 ring-inset ring-[var(--accent-primary)]',
                )}
              >
                <div className="sm:col-span-1 num text-xs font-bold text-[var(--text-muted)]">
                  {code}
                </div>
                <div className="sm:col-span-7">
                  <label
                    htmlFor={`field-${item.field}`}
                    className={cn(
                      'block',
                      item.isParent ? 'font-bold text-[var(--text-primary)]' : 'text-[var(--text-secondary)]',
                      isErrorField && 'text-[var(--risk-critical-fg)]',
                    )}
                  >
                    {item.label}
                  </label>
                  {item.helper ? (
                    <div className="text-[11px] text-[var(--text-muted)] mt-0.5">{item.helper}</div>
                  ) : null}
                </div>
                <div className="sm:col-span-4">
                  <input
                    id={`field-${item.field}`}
                    type="text"
                    inputMode="decimal"
                    aria-invalid={isErrorField}
                    value={values[item.field] ?? ''}
                    onChange={(e) => handleFieldChange(item.field, e.target.value)}
                    onFocus={() => setFocusedField(item.field)}
                    placeholder="Để trống nếu chưa có"
                    className={cn(
                      'field-control text-right font-mono',
                      isErrorField && '!border-[var(--risk-critical-fg)] !text-[var(--risk-critical-fg)]',
                    )}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {serverError ? (
          <div
            role="alert"
            className="mx-5 my-3 px-4 py-2.5 rounded-[3px] border border-[var(--risk-critical-border)] bg-[var(--risk-critical-bg)] text-xs font-semibold text-[var(--risk-critical-fg)]"
          >
            {serverError}
          </div>
        ) : null}

        <div className="px-5 py-3.5 bg-[var(--bg-header)] border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-end gap-2">
          {onCancel ? (
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={isSubmitting}>
              Hủy
            </Button>
          ) : null}
          <Button
            variant="secondary"
            size="sm"
            disabled={isSubmitting}
            onClick={() => void submitWithStatus('draft')}
          >
            <Save className="h-3.5 w-3.5" aria-hidden="true" />
            Lưu nháp
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={isSubmitting || !liveReport.is_balanced}
            onClick={() => void submitWithStatus('finalized')}
          >
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Chốt báo cáo & Chấm điểm
          </Button>
        </div>
      </Panel>

      <BalanceCheckAssistant report={liveReport} onSelectField={handleJumpToField} />
    </div>
  );
}
