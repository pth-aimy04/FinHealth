import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import type { OrgStatementInput, OrgStatementUpdateInput, ValidationReport } from '@/types/api';
import { StatementEditorForm } from '@/components/statements/StatementEditorForm';
import { ErrorState, Skeleton } from '@/components/ui/Primitives';

function extractServerValidation(err: unknown): ValidationReport | null {
  if (!(err instanceof ApiError)) return null;
  const payload = err.detailPayload;
  if (payload && typeof payload === 'object' && 'validation' in payload) {
    const val = (payload as { validation?: unknown }).validation;
    if (val && typeof val === 'object' && 'is_balanced' in val) {
      return val as ValidationReport;
    }
  }
  return null;
}

export function OrgStatementEditorPage() {
  const { id = '', statementId } = useParams();
  const companyId = Number(id);
  const parsedStatementId = statementId ? Number(statementId) : null;
  const isEditMode = parsedStatementId !== null && Number.isInteger(parsedStatementId) && parsedStatementId > 0;
  const isValidCompanyId = Number.isInteger(companyId) && companyId > 0;

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeOrg } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverValidation, setServerValidation] = useState<ValidationReport | null>(null);

  const companyQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'company', companyId],
    queryFn: () => api.getOrgCompany(companyId),
    enabled: isValidCompanyId,
  });

  const statementQuery = useQuery({
    queryKey: ['org', activeOrg?.id, 'statement', companyId, parsedStatementId],
    queryFn: () => api.getOrgStatement(companyId, parsedStatementId as number),
    enabled: isValidCompanyId && isEditMode,
  });

  const saveMutation = useMutation({
    mutationFn: async (payload: OrgStatementInput) => {
      if (isEditMode && parsedStatementId !== null) {
        const updatePayload: OrgStatementUpdateInput = {
          period_end_date: payload.period_end_date,
          accounting_standard: payload.accounting_standard,
          currency: payload.currency,
          unit_scale: payload.unit_scale,
          display_unit: payload.display_unit,
          audit_status: payload.audit_status,
          status: payload.status,
          total_assets: payload.total_assets,
          current_assets: payload.current_assets,
          cash_and_equivalents: payload.cash_and_equivalents,
          accounts_receivable: payload.accounts_receivable,
          inventory: payload.inventory,
          total_liabilities: payload.total_liabilities,
          current_liabilities: payload.current_liabilities,
          short_term_debt: payload.short_term_debt,
          long_term_debt: payload.long_term_debt,
          accounts_payable: payload.accounts_payable,
          stockholders_equity: payload.stockholders_equity,
          retained_earnings: payload.retained_earnings,
          revenues: payload.revenues,
          cost_of_goods_sold: payload.cost_of_goods_sold,
          gross_profit: payload.gross_profit,
          operating_expenses: payload.operating_expenses,
          operating_income: payload.operating_income,
          depreciation_amortization: payload.depreciation_amortization,
          ebitda: payload.ebitda,
          interest_expense: payload.interest_expense,
          net_income: payload.net_income,
          operating_cash_flow: payload.operating_cash_flow,
          capex: payload.capex,
          market_value_equity: payload.market_value_equity,
          eps_basic: payload.eps_basic,
          eps_diluted: payload.eps_diluted,
        };
        return api.updateOrgStatement(companyId, parsedStatementId, updatePayload);
      }
      return api.createOrUpsertOrgStatement(companyId, payload);
    },
    onSuccess: async (saved) => {
      setServerError(null);
      setServerValidation(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'statements', companyId] }),
        queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'analysis', companyId] }),
        queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] }),
      ]);
      const nextTab = saved.status === 'finalized' ? 'overview' : 'statements';
      navigate(`/portfolio/${companyId}?tab=${nextTab}`);
    },
    onError: (err) => {
      setServerError(err instanceof Error ? err.message : 'Không thể lưu báo cáo tài chính.');
      setServerValidation(extractServerValidation(err));
    },
  });

  if (!isValidCompanyId) {
    return (
      <ErrorState
        title="Mã doanh nghiệp không hợp lệ"
        message="Vui lòng chọn doanh nghiệp từ Danh bạ Doanh nghiệp của tổ chức."
      />
    );
  }

  if (companyQuery.isLoading || (isEditMode && statementQuery.isLoading)) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  if (companyQuery.isError || !companyQuery.data) {
    return (
      <ErrorState
        title="Không tìm thấy doanh nghiệp"
        message={
          companyQuery.error instanceof Error
            ? companyQuery.error.message
            : 'Doanh nghiệp không tồn tại trong không gian làm việc hiện tại.'
        }
      />
    );
  }

  if (isEditMode && (statementQuery.isError || !statementQuery.data)) {
    return (
      <ErrorState
        title="Không tìm thấy kỳ BCTC cần chỉnh sửa"
        message={
          statementQuery.error instanceof Error
            ? statementQuery.error.message
            : 'Kỳ báo cáo tài chính không tồn tại hoặc đã bị xóa.'
        }
      />
    );
  }

  return (
    <div className="space-y-4 animate-view">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/portfolio/${companyId}?tab=statements`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--accent-primary)] no-underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Quay lại hồ sơ {companyQuery.data.name}
        </Link>
      </div>

      <StatementEditorForm
        initialStatement={isEditMode ? statementQuery.data : null}
        isSubmitting={saveMutation.isPending}
        serverError={serverError}
        serverValidation={serverValidation}
        onSubmit={async (payload) => {
          await saveMutation.mutateAsync(payload);
        }}
        onCancel={() => navigate(`/portfolio/${companyId}?tab=statements`)}
      />
    </div>
  );
}
