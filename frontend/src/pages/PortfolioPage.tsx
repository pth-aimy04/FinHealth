import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Archive,
  Building2,
  Database,
  ExternalLink,
  Plus,
  Search,
  Trash2,
  Upload,
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  BUSINESS_TYPE_LABELS,
  RELATIONSHIP_TAG_LABELS,
  RISK_TIER_META,
  formatDate,
  formatScore,
} from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import type {
  BusinessType,
  ListingStatus,
  OrgCompany,
  OrgCompanyCreateInput,
  RelationshipTag,
} from '@/types/api';
import { ImportStatementModal } from '@/components/statements/ImportStatementModal';
import {
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  Panel,
  PanelHeader,
  TableSkeleton,
} from '@/components/ui/Primitives';

export function PortfolioPage() {
  const queryClient = useQueryClient();
  const { user, activeOrg, activeOrgRole } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [queryText, setQueryText] = useState(searchParams.get('q') ?? '');
  const [relationshipFilter, setRelationshipFilter] = useState<RelationshipTag | ''>('');
  const [businessTypeFilter, setBusinessTypeFilter] = useState<BusinessType | ''>('');
  const [includeArchived, setIncludeArchived] = useState(false);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formTaxCode, setFormTaxCode] = useState('');
  const [formTicker, setFormTicker] = useState('');
  const [formSectorName, setFormSectorName] = useState('');
  const [formBusinessType, setFormBusinessType] = useState<BusinessType>('manufacturing');
  const [formListingStatus, setFormListingStatus] = useState<ListingStatus>('unlisted');
  const [formRelationship, setFormRelationship] = useState<RelationshipTag>('customer');

  const [importTarget, setImportTarget] = useState<OrgCompany | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canEdit = activeOrgRole === 'analyst' || activeOrgRole === 'org_admin';
  const canDelete = activeOrgRole === 'org_admin';

  const companiesQuery = useQuery({
    queryKey: [
      'org',
      activeOrg?.id,
      'companies',
      {
        q: queryText.trim(),
        relationship_tag: relationshipFilter || undefined,
        business_type: businessTypeFilter || undefined,
        include_archived: includeArchived,
      },
    ],
    queryFn: () =>
      api.getOrgCompanies({
        q: queryText.trim() || undefined,
        relationship_tag: relationshipFilter || undefined,
        business_type: businessTypeFilter || undefined,
        include_archived: includeArchived,
      }),
    enabled: Boolean(user && activeOrg),
  });

  const createMutation = useMutation({
    mutationFn: (payload: OrgCompanyCreateInput) => api.createOrgCompany(payload),
    onSuccess: async (created) => {
      setErrorMessage(null);
      setStatusMessage(`Đã thêm doanh nghiệp "${created.name}" vào danh bạ tổ chức.`);
      setShowCreateForm(false);
      setFormName('');
      setFormTaxCode('');
      setFormTicker('');
      setFormSectorName('');
      await queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể tạo hồ sơ doanh nghiệp.'),
  });

  const seedSamplesMutation = useMutation({
    mutationFn: () => api.seedOrgSamples(),
    onSuccess: async (res) => {
      setErrorMessage(null);
      setStatusMessage(
        `Đã khởi tạo ${res.created_companies} doanh nghiệp mẫu VN mới (${res.created_statements} kỳ BCTC).`,
      );
      await queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể nạp doanh nghiệp mẫu.'),
  });

  const archiveMutation = useMutation({
    mutationFn: ({ id, archived }: { id: number; archived: boolean }) =>
      api.updateOrgCompany(id, { archived }),
    onSuccess: async () => {
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể cập nhật trạng thái lưu trữ.'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteOrgCompany(id),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã xóa vĩnh viễn hồ sơ doanh nghiệp.');
      await queryClient.invalidateQueries({ queryKey: ['org', activeOrg?.id, 'companies'] });
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể xóa doanh nghiệp.'),
  });

  if (!user) {
    return (
      <Panel ruled>
        <EmptyState
          title="Đăng nhập để quản lý Danh bạ Doanh nghiệp"
          description="Lưu trữ hồ sơ khách hàng, nhà cung cấp, nhập BCTC chuẩn TT99/TT200/TT133 và đánh giá sức khỏe tài chính nội bộ."
          action={
            <Link to="/account" className="no-underline">
              <Button variant="primary">Đăng nhập / Đăng ký</Button>
            </Link>
          }
        />
      </Panel>
    );
  }

  const companies = companiesQuery.data ?? [];

  return (
    <div className="space-y-5 animate-view">
      <PageHeader
        title="Danh bạ Doanh nghiệp Tổ chức"
        description={`Không gian: ${activeOrg?.name ?? '—'} · Quản lý hồ sơ đối tác & khách hàng nội bộ (VND/USD), cô lập tuyệt đối theo tổ chức.`}
        actions={
          canEdit ? (
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => seedSamplesMutation.mutate()}
                disabled={seedSamplesMutation.isPending}
              >
                <Database className="h-3.5 w-3.5" aria-hidden="true" />
                Nạp 3 DN mẫu VN
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setShowCreateForm((v) => !v)}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Thêm doanh nghiệp
              </Button>
            </>
          ) : undefined
        }
      />

      {statusMessage ? (
        <div
          role="status"
          className="px-4 py-2.5 rounded-[3px] border text-xs font-semibold"
          style={{
            backgroundColor: 'var(--risk-low-bg)',
            color: 'var(--risk-low-fg)',
            borderColor: 'var(--risk-low-border)',
          }}
        >
          {statusMessage}
        </div>
      ) : null}
      {errorMessage ? (
        <div
          role="alert"
          className="px-4 py-2.5 rounded-[3px] border text-xs font-semibold"
          style={{
            backgroundColor: 'var(--risk-critical-bg)',
            color: 'var(--risk-critical-fg)',
            borderColor: 'var(--risk-critical-border)',
          }}
        >
          {errorMessage}
        </div>
      ) : null}

      {/* Inline Create Company Drawer Panel */}
      {canEdit && showCreateForm ? (
        <Panel ruled>
          <PanelHeader
            title="Thêm hồ sơ Doanh nghiệp mới"
            description="Nhập thông tin pháp lý cơ bản (Tên, MST, loại hình) để bắt đầu nhập BCTC và thẩm định."
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate({
                name: formName.trim(),
                tax_code: formTaxCode.trim() || null,
                ticker: formTicker.trim() || null,
                sector_name: formSectorName.trim() || null,
                business_type: formBusinessType,
                listing_status: formListingStatus,
                relationship_tag: formRelationship,
              });
            }}
            className="p-5 space-y-4 text-xs"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <label htmlFor="co-name" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Tên doanh nghiệp *
                </label>
                <input
                  id="co-name"
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="VD: Công ty Cổ phần Sản xuất Minh An"
                  className="field-control"
                />
              </div>

              <div>
                <label htmlFor="co-tax-code" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Mã số thuế (MST 10 hoặc 13 số)
                </label>
                <input
                  id="co-tax-code"
                  type="text"
                  value={formTaxCode}
                  onChange={(e) => setFormTaxCode(e.target.value)}
                  placeholder="0101234567"
                  className="field-control font-mono"
                />
              </div>

              <div>
                <label htmlFor="co-ticker" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Mã chứng khoán (nếu có)
                </label>
                <input
                  id="co-ticker"
                  type="text"
                  value={formTicker}
                  onChange={(e) => setFormTicker(e.target.value)}
                  placeholder="VD: HPG, VNM"
                  className="field-control font-mono uppercase"
                />
              </div>

              <div>
                <label htmlFor="co-sector" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Ngành nghề kinh doanh
                </label>
                <input
                  id="co-sector"
                  type="text"
                  value={formSectorName}
                  onChange={(e) => setFormSectorName(e.target.value)}
                  placeholder="VD: Sản xuất cơ khí, Thương mại vật liệu"
                  className="field-control"
                />
              </div>

              <div>
                <label htmlFor="co-relationship" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Mối quan hệ
                </label>
                <select
                  id="co-relationship"
                  value={formRelationship}
                  onChange={(e) => setFormRelationship(e.target.value as RelationshipTag)}
                  className="field-control"
                >
                  {Object.entries(RELATIONSHIP_TAG_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="co-business-type" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Loại hình doanh nghiệp
                </label>
                <select
                  id="co-business-type"
                  value={formBusinessType}
                  onChange={(e) => setFormBusinessType(e.target.value as BusinessType)}
                  className="field-control"
                >
                  {Object.entries(BUSINESS_TYPE_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="co-listing" className="block font-semibold text-[var(--text-secondary)] mb-1">
                  Trạng thái niêm yết
                </label>
                <select
                  id="co-listing"
                  value={formListingStatus}
                  onChange={(e) => setFormListingStatus(e.target.value as ListingStatus)}
                  className="field-control"
                >
                  <option value="unlisted">Chưa niêm yết (Doanh nghiệp tư nhân / TNHH)</option>
                  <option value="listed">Đã niêm yết (HOSE / HNX / UPCoM)</option>
                </select>
              </div>
            </div>

            {formBusinessType === 'financial_institution' ? (
              <div
                role="alert"
                className="p-3 rounded-[3px] border border-[var(--risk-medium-border)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium-fg)] flex items-start gap-2"
              >
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <strong>Lưu ý phạm vi loại trừ Tổ chức tài chính (TCTC):</strong> Ngân hàng, Bảo
                  hiểm, Chứng khoán và Quỹ đầu tư vẫn được lưu hồ sơ nhưng không áp dụng chấm điểm
                  Altman Z và mô hình rủi ro phi tài chính.
                </div>
              </div>
            ) : null}

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-subtle)]">
              <Button variant="ghost" size="sm" onClick={() => setShowCreateForm(false)}>
                Hủy
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Đang lưu...' : 'Lưu doanh nghiệp'}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {/* Unified Directory Ledger Panel with Docked Filter Toolbar (Zero Double-Box Separation) */}
      <Panel ruled className="overflow-hidden">
        <PanelHeader
          title={`Danh sách Doanh nghiệp (${companies.length})`}
          description="Bấm vào tên doanh nghiệp để xem đánh giá 5 trụ cột, Điểm Tựa/Điểm Nghẽn, lịch sử đa kỳ và nhập BCTC."
        />

        {/* Docked Filter Bar */}
        <div className="px-4 sm:px-5 py-3 bg-[var(--bg-subtle)]/55 border-b border-[var(--border-subtle)] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3 text-xs items-center">
          <div className="lg:col-span-5 relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-muted)]"
              aria-hidden="true"
            />
            <input
              type="search"
              aria-label="Tìm theo tên doanh nghiệp, mã số thuế hoặc mã chứng khoán"
              value={queryText}
              onChange={(e) => {
                setQueryText(e.target.value);
                const next = new URLSearchParams(searchParams);
                if (e.target.value.trim()) next.set('q', e.target.value);
                else next.delete('q');
                setSearchParams(next, { replace: true });
              }}
              placeholder="Tìm theo Tên doanh nghiệp, MST hoặc Mã CK..."
              className="field-control !pl-9"
            />
          </div>

          <div className="lg:col-span-3">
            <select
              aria-label="Lọc theo thẻ quan hệ"
              value={relationshipFilter}
              onChange={(e) => setRelationshipFilter(e.target.value as RelationshipTag | '')}
              className="field-control"
            >
              <option value="">Tất cả mối quan hệ</option>
              {Object.entries(RELATIONSHIP_TAG_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="lg:col-span-2">
            <select
              aria-label="Lọc theo loại hình doanh nghiệp"
              value={businessTypeFilter}
              onChange={(e) => setBusinessTypeFilter(e.target.value as BusinessType | '')}
              className="field-control"
            >
              <option value="">Tất cả loại hình</option>
              {Object.entries(BUSINESS_TYPE_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <label className="lg:col-span-2 inline-flex items-center gap-2 cursor-pointer text-[var(--text-secondary)] font-medium">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
              className="accent-[var(--accent-primary)]"
            />
            <span>Hiện đã lưu trữ</span>
          </label>
        </div>

        {companiesQuery.isLoading ? (
          <TableSkeleton rows={5} />
        ) : companiesQuery.isError ? (
          <div className="p-4">
            <ErrorState
              message={
                companiesQuery.error instanceof Error
                  ? companiesQuery.error.message
                  : 'Không thể tải danh bạ doanh nghiệp.'
              }
              onRetry={() => void companiesQuery.refetch()}
            />
          </div>
        ) : companies.length === 0 ? (
          <EmptyState
            title="Chưa có doanh nghiệp nào trong danh bạ"
            description="Thêm doanh nghiệp mới hoặc nạp ngay 3 hồ sơ doanh nghiệp mẫu Việt Nam để trải nghiệm phân tích đầy đủ."
            action={
              canEdit ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => seedSamplesMutation.mutate()}
                    disabled={seedSamplesMutation.isPending}
                  >
                    <Database className="h-3.5 w-3.5" aria-hidden="true" />
                    Nạp 3 doanh nghiệp mẫu VN
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowCreateForm(true)}
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    Tạo doanh nghiệp đầu tiên
                  </Button>
                </div>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Doanh nghiệp</th>
                  <th>MST / Mã CK</th>
                  <th>Quan hệ & Loại hình</th>
                  <th>Sức khỏe / Phạm vi</th>
                  <th>Cập nhật</th>
                  <th className="text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <tr key={company.id}>
                    <td>
                      <Link
                        to={`/portfolio/${company.id}`}
                        className="font-semibold text-[var(--text-primary)] hover:text-[var(--accent-primary)] no-underline inline-flex items-center gap-1.5 flex-wrap"
                      >
                        <Building2
                          className="h-3.5 w-3.5 text-[var(--accent-primary)] shrink-0"
                          aria-hidden="true"
                        />
                        <span>{company.name}</span>
                        {company.is_sample ? (
                          <span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.04em] rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)]">
                            Mẫu
                          </span>
                        ) : null}
                        {company.archived ? (
                          <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded-[2px] bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                            Lưu trữ
                          </span>
                        ) : null}
                      </Link>
                      {company.sector_name ? (
                        <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
                          {company.sector_name}
                        </div>
                      ) : null}
                    </td>
                    <td className="num text-[var(--text-secondary)]">
                      <div>{company.tax_code ?? '—'}</div>
                      {company.ticker ? (
                        <div className="text-[11px] text-[var(--accent-primary)] font-bold">
                          {company.ticker}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <div className="font-medium text-[var(--text-primary)]">
                        {RELATIONSHIP_TAG_LABELS[company.relationship_tag] ??
                          company.relationship_tag}
                      </div>
                      <div className="text-[11px] text-[var(--text-muted)]">
                        {BUSINESS_TYPE_LABELS[company.business_type] ?? company.business_type}
                      </div>
                    </td>
                    <td>
                      {!company.scoring_eligible ? (
                        <span
                          title={company.scoring_exclusion_reason ?? undefined}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[2px] border border-[var(--risk-medium-border)] text-[11px] font-semibold bg-[var(--risk-medium-bg)] text-[var(--risk-medium-fg)]"
                        >
                          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                          Loại trừ (TCTC)
                        </span>
                      ) : company.latest_risk_tier && RISK_TIER_META[company.latest_risk_tier] ? (
                        <div className="flex items-center gap-2">
                          <span className="num font-bold text-[var(--text-primary)]">
                            {formatScore(company.latest_health_score, 1)}
                          </span>
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-[2px] border text-[11px] font-semibold"
                            style={{
                              color: RISK_TIER_META[company.latest_risk_tier].fg,
                              backgroundColor: RISK_TIER_META[company.latest_risk_tier].bg,
                              borderColor: 'currentColor',
                            }}
                          >
                            {RISK_TIER_META[company.latest_risk_tier].label}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-[2px] border border-[var(--risk-low-border)] text-[11px] font-semibold bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]">
                          Đủ điều kiện chấm điểm
                        </span>
                      )}
                    </td>
                    <td className="num text-[var(--text-secondary)]">
                      {formatDate(company.updated_at)}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1.5">
                        <Link to={`/portfolio/${company.id}`} className="no-underline">
                          <Button variant="secondary" size="sm">
                            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                            Hồ sơ
                          </Button>
                        </Link>
                        {canEdit ? (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="Nhập XML HTKK / Excel"
                              onClick={() => setImportTarget(company)}
                            >
                              <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                              Nhập BCTC
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              title={company.archived ? 'Khôi phục' : 'Lưu trữ'}
                              aria-label={
                                company.archived
                                  ? `Khôi phục ${company.name}`
                                  : `Lưu trữ ${company.name}`
                              }
                              onClick={() =>
                                archiveMutation.mutate({
                                  id: company.id,
                                  archived: !company.archived,
                                })
                              }
                            >
                              <Archive className="h-3.5 w-3.5" aria-hidden="true" />
                            </Button>
                          </>
                        ) : null}
                        {canDelete ? (
                          <Button
                            variant="danger"
                            size="sm"
                            aria-label={`Xóa vĩnh viễn ${company.name}`}
                            onClick={() => deleteMutation.mutate(company.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {importTarget ? (
        <ImportStatementModal
          companyId={importTarget.id}
          companyName={importTarget.name}
          open={Boolean(importTarget)}
          onClose={() => setImportTarget(null)}
          onImported={() => {
            void queryClient.invalidateQueries({
              queryKey: ['org', activeOrg?.id, 'statements', importTarget.id],
            });
            void queryClient.invalidateQueries({
              queryKey: ['org', activeOrg?.id, 'analysis', importTarget.id],
            });
            void queryClient.invalidateQueries({
              queryKey: ['org', activeOrg?.id, 'companies'],
            });
          }}
        />
      ) : null}
    </div>
  );
}
