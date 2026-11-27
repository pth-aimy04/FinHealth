/** Same-origin typed API client with CSRF cookie propagation and explicit error mapping. */

import type {
  AccountingStandard,
  AdminOverview,
  AuditEntry,
  BatchJobDetail,
  BatchJobSummary,
  BatchPredictionResponse,
  BusinessType,
  ClusterPoint,
  CompanyAssessmentView,
  CompanyComparisonResponse,
  CompanyFullAnalysis,
  CompanySummary,
  DashboardOverview,
  DataQuality,
  ForecastEvidence,
  HealthCheck,
  IngestionEvent,
  IngestionJob,
  ManualPredictionResponse,
  ManualStatementInput,
  ModelEvaluationResponse,
  ModelVersionSummary,
  OrgCompany,
  OrgCompanyCreateInput,
  OrgCompanyUpdateInput,
  OrgCompareResponseView,
  OrgRole,
  OrgStatement,
  OrgStatementInput,
  OrgStatementUpdateInput,
  OrganizationAuditEntry,
  OrganizationDetail,
  OrganizationInvite,
  OrganizationInviteAcceptResponse,
  OrganizationInviteCreated,
  OrganizationMember,
  OrganizationSummary,
  OrganizationSwitchResponse,
  PublicUser,
  RelationshipTag,
  ReportAlert,
  ReportResponse,
  SampleSeedResponse,
  SavedAnalysisSummary,
  SavedScreenerEntry,
  StressScenarioRequest,
  StressSimulationResponse,
  UnitScale,
  UserDataExport,
  WatchlistEntry,
} from '@/types/api';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  errorType?: string;
  detailPayload?: unknown;

  constructor(status: number, message: string, errorType?: string, detailPayload?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorType = errorType;
    this.detailPayload = detailPayload;
  }
}

export function getCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split('; ')
    .find((part) => part.startsWith('finhealth_csrf='));
  return match ? decodeURIComponent(match.split('=')[1] ?? '') : null;
}

function extractErrorMessage(body: unknown, status: number): { message: string; payload?: unknown } {
  if (body && typeof body === 'object' && 'detail' in body) {
    const rawDetail = (body as { detail: unknown }).detail;
    if (typeof rawDetail === 'string') {
      return { message: rawDetail };
    }
    if (rawDetail && typeof rawDetail === 'object' && 'message' in rawDetail) {
      return {
        message: String((rawDetail as { message: unknown }).message),
        payload: rawDetail,
      };
    }
    return { message: JSON.stringify(rawDetail), payload: rawDetail };
  }
  if (typeof body === 'string' && body.trim()) {
    return { message: body };
  }
  return { message: `Request failed with status ${status}` };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (options.body && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCsrfCookie();
    if (csrf) {
      headers.set('X-CSRF-Token', csrf);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: 'same-origin',
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  const body = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');

  if (!response.ok) {
    const { message, payload } = extractErrorMessage(body, response.status);
    const errorType =
      body && typeof body === 'object' && 'error_type' in body
        ? String((body as { error_type: unknown }).error_type)
        : undefined;
    throw new ApiError(response.status, message, errorType, payload);
  }

  return body as T;
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCsrfCookie();
    if (csrf) {
      headers.set('X-CSRF-Token', csrf);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: 'same-origin',
  });

  if (!response.ok) {
    const contentType = response.headers.get('content-type') ?? '';
    const body = contentType.includes('application/json')
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');
    const { message, payload } = extractErrorMessage(body, response.status);
    throw new ApiError(response.status, message, undefined, payload);
  }

  return response.blob();
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function buildQuery(
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      qs.set(key, String(value));
    }
  }
  const str = qs.toString();
  return str ? `?${str}` : '';
}

export interface CompanyQueryParams {
  limit?: number;
  offset?: number;
  q?: string;
  sector?: string;
  risk_level?: string;
  cluster_id?: number;
  fiscal_year?: number;
  min_roa?: number;
  max_debt_ratio?: number;
  min_current_ratio?: number;
}

export interface OrgCompanyQueryParams {
  q?: string;
  relationship_tag?: RelationshipTag;
  business_type?: BusinessType;
  include_archived?: boolean;
}

export const api = {
  // Health & Overview
  getHealth: () => request<HealthCheck>('/health'),
  getOverview: () => request<DashboardOverview>('/dashboard/overview'),
  getDataQuality: () => request<DataQuality>('/data-quality'),

  // SEC US Market Companies & Analytics
  getCompanies: (params: CompanyQueryParams = {}) =>
    request<CompanySummary[]>(
      `/companies${buildQuery(params as Record<string, string | number | undefined>)}`,
    ),
  getCompany: (identifier: string, formType: '10-K' | '10-Q' = '10-K') =>
    request<CompanyFullAnalysis>(
      `/companies/${encodeURIComponent(identifier)}${buildQuery({ form_type: formType })}`,
    ),
  analyzeCompany: (identifier: string, forceRefresh = false) =>
    request<CompanyFullAnalysis>(
      `/companies/${encodeURIComponent(identifier)}/analyze${buildQuery({ force_refresh: forceRefresh })}`,
      { method: 'POST' },
    ),
  compareCompanies: (
    identifiers: string[],
    commonFiscalYearOrPolicy?: number | 'latest_annual' | 'common_fiscal_year' | null,
    commonFiscalYear?: number | null,
  ) => {
    const resolvedYear =
      typeof commonFiscalYearOrPolicy === 'number'
        ? commonFiscalYearOrPolicy
        : typeof commonFiscalYear === 'number'
          ? commonFiscalYear
          : undefined;
    return request<CompanyComparisonResponse>(
      `/companies/compare${buildQuery({
        identifiers: identifiers.join(','),
        common_fiscal_year: resolvedYear,
      })}`,
    );
  },
  getClusterMap: () => request<ClusterPoint[]>('/clusters/map'),
  simulateStress: (identifier: string, scenario: StressScenarioRequest) =>
    request<StressSimulationResponse>(
      `/companies/${encodeURIComponent(identifier)}/simulate`,
      {
        method: 'POST',
        body: JSON.stringify(scenario),
      },
    ),

  // Reports, Alerts & Forecast Evidence
  getReports: (identifier: string) =>
    request<ReportResponse>(`/reports/${encodeURIComponent(identifier)}`),
  getReportAlerts: (identifier: string) =>
    request<ReportAlert[]>(`/report-alerts/${encodeURIComponent(identifier)}`),
  getFilingForecasts: (filingId: number) =>
    request<ForecastEvidence[]>(`/filings/${filingId}/forecasts`),

  // ML Models (Admin / MLOps)
  getModelVersions: () => request<ModelVersionSummary[]>('/models/versions'),
  getModelEvaluation: (modelVersion?: string) =>
    request<ModelEvaluationResponse>(
      `/models/evaluation${buildQuery({ model_version: modelVersion })}`,
    ),
  predictManual: (payload: ManualStatementInput) =>
    request<ManualPredictionResponse>('/models/predict-manual', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  predictBatch: (items: ManualStatementInput[], modelVersion?: string) =>
    request<BatchPredictionResponse>('/models/predict-batch', {
      method: 'POST',
      body: JSON.stringify({
        items,
        ...(modelVersion ? { model_version: modelVersion } : {}),
      }),
    }),
  trainModel: (payload: {
    train_end_year: number;
    model_version: string;
    validation_end_year?: number | null;
    imbalance_strategy: 'class_weight' | 'smote';
  }) =>
    request<ModelEvaluationResponse>('/models/train', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Auth, Account Lifecycle & Law 91/2025 Privacy
  getMe: () => request<PublicUser>('/auth/me'),
  login: (email: string, password: string) =>
    request<PublicUser>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, display_name: string) =>
    request<{ message: string; challenge: string; expires_in: number }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),
  resendVerification: (email: string) =>
    request<{ message: string; challenge: string; expires_in: number }>(
      '/auth/resend-verification',
      {
        method: 'POST',
        body: JSON.stringify({ email }),
      },
    ),
  verifyEmail: (email: string, challenge: string, code: string, new_password: string) =>
    request<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code, new_password }),
    }),
  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),
  updateProfile: (display_name: string, job_title?: string | null) =>
    request<PublicUser>('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(
        job_title !== undefined ? { display_name, job_title } : { display_name },
      ),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; challenge: string; expires_in: number }>(
      '/auth/forgot-password',
      {
        method: 'POST',
        body: JSON.stringify({ email }),
      },
    ),
  resetPassword: (email: string, challenge: string, code: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code, new_password }),
    }),
  requestChangePassword: (current_password: string, new_password: string) =>
    request<{ message: string; challenge: string; expires_in: number }>(
      '/auth/change-password',
      {
        method: 'POST',
        body: JSON.stringify({ current_password, new_password }),
      },
    ),
  confirmPasswordChange: (
    email: string,
    challenge: string,
    code: string,
    new_password: string,
  ) =>
    request<{ message: string }>('/auth/confirm-password-change', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code, new_password }),
    }),
  requestChangeEmail: (current_password: string, email: string) =>
    request<{ message: string; challenge: string; expires_in: number }>(
      '/auth/change-email',
      {
        method: 'POST',
        body: JSON.stringify({ current_password, email }),
      },
    ),
  confirmEmailChange: (email: string, challenge: string, code: string) =>
    request<{ message: string }>('/auth/confirm-email', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code }),
    }),
  exportMyData: () => request<UserDataExport>('/auth/me/export'),
  requestDeleteAccount: (current_password: string) =>
    request<{ message: string; challenge: string; expires_in: number }>(
      '/auth/delete-account/request',
      {
        method: 'POST',
        body: JSON.stringify({ current_password }),
      },
    ),
  confirmDeleteAccount: (current_password: string, challenge: string, code: string) =>
    request<{ message: string }>('/auth/delete-account', {
      method: 'POST',
      body: JSON.stringify({ current_password, challenge, code }),
    }),

  // Organizations & RBAC
  getOrganizations: () => request<OrganizationSummary[]>('/organizations'),
  createOrganization: (name: string) =>
    request<OrganizationSummary>('/organizations', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  switchOrganization: (organization_id: number) =>
    request<OrganizationSwitchResponse>('/organizations/switch', {
      method: 'POST',
      body: JSON.stringify({ organization_id }),
    }),
  acceptOrganizationInvite: (token: string) =>
    request<OrganizationInviteAcceptResponse>('/organizations/invites/accept', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  getOrganization: (orgId: number) =>
    request<OrganizationDetail>(`/organizations/${orgId}`),
  updateOrganization: (orgId: number, name: string) =>
    request<OrganizationDetail>(`/organizations/${orgId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  getOrganizationMembers: (orgId: number) =>
    request<OrganizationMember[]>(`/organizations/${orgId}/members`),
  createOrganizationInvite: (orgId: number, email: string, role: OrgRole) =>
    request<OrganizationInviteCreated>(`/organizations/${orgId}/invites`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    }),
  getOrganizationInvites: (orgId: number) =>
    request<OrganizationInvite[]>(`/organizations/${orgId}/invites`),
  revokeOrganizationInvite: (orgId: number, inviteId: number) =>
    request<void>(`/organizations/${orgId}/invites/${inviteId}`, { method: 'DELETE' }),
  updateOrganizationMemberRole: (orgId: number, memberUserId: number, role: OrgRole) =>
    request<{ user_id: number; role: OrgRole }>(
      `/organizations/${orgId}/members/${memberUserId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      },
    ),
  removeOrganizationMember: (orgId: number, memberUserId: number) =>
    request<void>(`/organizations/${orgId}/members/${memberUserId}`, { method: 'DELETE' }),
  getOrganizationAuditLogs: (orgId: number, limit = 50, offset = 0) =>
    request<OrganizationAuditEntry[]>(
      `/organizations/${orgId}/audit${buildQuery({ limit, offset })}`,
    ),

  // Organization Companies & Multi-Standard Statements
  getOrgCompanies: (params: OrgCompanyQueryParams = {}) =>
    request<OrgCompany[]>(
      `/org/companies${buildQuery(params as Record<string, string | boolean | undefined>)}`,
    ),
  createOrgCompany: (payload: OrgCompanyCreateInput) =>
    request<OrgCompany>('/org/companies', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getOrgCompany: (companyId: number) =>
    request<OrgCompany>(`/org/companies/${companyId}`),
  updateOrgCompany: (companyId: number, payload: OrgCompanyUpdateInput) =>
    request<OrgCompany>(`/org/companies/${companyId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteOrgCompany: (companyId: number) =>
    request<void>(`/org/companies/${companyId}`, { method: 'DELETE' }),
  seedOrgSamples: () =>
    request<SampleSeedResponse>('/org/samples/seed', { method: 'POST' }),

  getOrgCompanyStatements: (companyId: number) =>
    request<OrgStatement[]>(`/org/companies/${companyId}/statements`),
  createOrUpsertOrgStatement: (companyId: number, payload: OrgStatementInput) =>
    request<OrgStatement>(`/org/companies/${companyId}/statements`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getOrgStatement: (companyId: number, statementId: number) =>
    request<OrgStatement>(`/org/companies/${companyId}/statements/${statementId}`),
  updateOrgStatement: (
    companyId: number,
    statementId: number,
    payload: OrgStatementUpdateInput,
  ) =>
    request<OrgStatement>(`/org/companies/${companyId}/statements/${statementId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  finalizeOrgStatement: (companyId: number, statementId: number) =>
    request<OrgStatement>(
      `/org/companies/${companyId}/statements/${statementId}/finalize`,
      { method: 'POST' },
    ),
  deleteOrgStatement: (companyId: number, statementId: number) =>
    request<void>(`/org/companies/${companyId}/statements/${statementId}`, {
      method: 'DELETE',
    }),
  importHtkkXmlStatement: (
    companyId: number,
    file: File,
    options: {
      fiscal_year?: number;
      unit_scale?: UnitScale;
      accounting_standard?: AccountingStandard;
    } = {},
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    if (options.fiscal_year !== undefined) {
      formData.append('fiscal_year', String(options.fiscal_year));
    }
    if (options.unit_scale !== undefined) {
      formData.append('unit_scale', String(options.unit_scale));
    }
    if (options.accounting_standard) {
      formData.append('accounting_standard', options.accounting_standard);
    }
    return request<OrgStatement>(`/org/companies/${companyId}/statements/import-xml`, {
      method: 'POST',
      body: formData,
    });
  },
  importExcelStatement: (
    companyId: number,
    file: File,
    options: {
      fiscal_year?: number;
      unit_scale?: UnitScale;
      accounting_standard?: AccountingStandard;
    } = {},
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    if (options.fiscal_year !== undefined) {
      formData.append('fiscal_year', String(options.fiscal_year));
    }
    if (options.unit_scale !== undefined) {
      formData.append('unit_scale', String(options.unit_scale));
    }
    if (options.accounting_standard) {
      formData.append('accounting_standard', options.accounting_standard);
    }
    return request<OrgStatement>(`/org/companies/${companyId}/statements/import-excel`, {
      method: 'POST',
      body: formData,
    });
  },
  downloadBctcTemplate: (
    standard: 'TT99_2025' | 'TT200_2014' | 'TT133_2016',
    fiscalYear = 2025,
    unitScale: UnitScale = 1_000_000,
  ) =>
    requestBlob(
      `/templates/bctc/${encodeURIComponent(standard)}${buildQuery({
        fiscal_year: fiscalYear,
        unit_scale: unitScale,
      })}`,
    ),

  // Organization Risk Analytics & Comparison
  getOrgCompanyAnalysis: (companyId: number, fiscalYear?: number) =>
    request<CompanyAssessmentView>(
      `/org/companies/${companyId}/analysis${buildQuery({ fiscal_year: fiscalYear })}`,
    ),
  recomputeOrgCompanyAnalysis: (companyId: number, fiscalYear?: number) =>
    request<CompanyAssessmentView>(
      `/org/companies/${companyId}/recompute${buildQuery({ fiscal_year: fiscalYear })}`,
      { method: 'POST' },
    ),
  compareOrgCompanies: (companyIds: number[], commonFiscalYear?: number | null) =>
    request<OrgCompareResponseView>(
      `/org/companies/compare${buildQuery({
        ids: companyIds.join(','),
        common_fiscal_year: commonFiscalYear ?? undefined,
      })}`,
    ),

  // Batch Assessment Jobs (S03) & PDF Export (M12)
  downloadBatchTemplate: () => requestBlob('/org/batch/template.xlsx'),
  createBatchJob: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<BatchJobSummary>('/org/batch/jobs', {
      method: 'POST',
      body: formData,
    });
  },
  getBatchJobs: () => request<BatchJobSummary[]>('/org/batch/jobs'),
  getBatchJobDetail: (jobId: number) =>
    request<BatchJobDetail>(`/org/batch/jobs/${jobId}`),
  downloadBatchExport: (jobId: number) =>
    requestBlob(`/org/batch/jobs/${jobId}/export.xlsx`),
  downloadOrgReportPdf: (companyId: number, fiscalYear?: number) =>
    requestBlob(
      `/org/companies/${companyId}/report.pdf${buildQuery({ fiscal_year: fiscalYear })}`,
    ),
  downloadSecReportPdf: (identifier: string) =>
    requestBlob(`/companies/${encodeURIComponent(identifier)}/report.pdf`),

  // Organization-scoped Saved Workspace
  getWatchlist: () => request<WatchlistEntry[]>('/me/watchlist'),
  followCompany: (cik: string) =>
    request<{ id: number }>(`/me/watchlist/${encodeURIComponent(cik)}`, {
      method: 'POST',
    }),
  getScreeners: () => request<SavedScreenerEntry[]>('/me/screeners'),
  saveScreener: (
    name: string,
    filters: Record<string, string | number | null | undefined>,
  ) =>
    request<{ id: number }>('/me/screeners', {
      method: 'POST',
      body: JSON.stringify({ name, filters }),
    }),
  getSavedAnalyses: () => request<SavedAnalysisSummary[]>('/me/analyses'),
  saveAnalysis: (name: string, inputs: ManualStatementInput) =>
    request<{ id: number }>('/me/analyses', {
      method: 'POST',
      body: JSON.stringify({ name, inputs }),
    }),
  deleteSavedItem: (
    collection: 'watchlist' | 'screeners' | 'analyses',
    itemId: number,
  ) => request<void>(`/me/${collection}/${itemId}`, { method: 'DELETE' }),

  // Admin & Ingestion
  getAdminOverview: () => request<AdminOverview>('/admin/overview'),
  getAdminUsers: (offset = 0, limit = 50) =>
    request<PublicUser[]>(`/admin/users${buildQuery({ offset, limit })}`),
  setUserActive: (userId: number, active: boolean) =>
    request<PublicUser>(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ active }),
    }),
  getAdminIngestion: (status?: string) =>
    request<IngestionJob[]>(`/admin/ingestion${buildQuery({ status })}`),
  getIngestionEvents: (runId: number) =>
    request<IngestionEvent[]>(`/admin/ingestion/${runId}/events`),
  submitIngestion: (identifier: string) =>
    request<IngestionJob>(`/ingestion/${encodeURIComponent(identifier)}`, {
      method: 'POST',
    }),
  retryIngestion: (jobId: number) =>
    request<IngestionJob>(`/ingestion/${jobId}/retry`, { method: 'POST' }),
  getAdminAudit: () => request<AuditEntry[]>('/admin/audit'),
};
