/** Same-origin typed API client with CSRF cookie propagation and explicit error mapping. */

import type {
  AdminOverview,
  AuditEntry,
  BatchPredictionResponse,
  ClusterPoint,
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
  PublicUser,
  ReportAlert,
  ReportResponse,
  SavedAnalysisSummary,
  SavedScreenerEntry,
  StressScenarioRequest,
  StressSimulationResponse,
  WatchlistEntry,
} from '@/types/api';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  errorType?: string;

  constructor(status: number, message: string, errorType?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorType = errorType;
  }
}

export function getCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split('; ')
    .find((part) => part.startsWith('finhealth_csrf='));
  return match ? decodeURIComponent(match.split('=')[1] ?? '') : null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) {
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
  const body = isJson ? await response.json().catch(() => null) : await response.text().catch(() => '');

  if (!response.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail)
        : typeof body === 'string' && body.trim()
          ? body
          : `Request failed with status ${response.status}`;
    const errorType =
      body && typeof body === 'object' && 'error_type' in body
        ? String(body.error_type)
        : undefined;
    throw new ApiError(response.status, detail, errorType);
  }

  return body as T;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
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

export const api = {
  // Health & Overview
  getHealth: () => request<HealthCheck>('/health'),
  getOverview: () => request<DashboardOverview>('/dashboard/overview'),
  getDataQuality: () => request<DataQuality>('/data-quality'),

  // Companies & Analytics
  getCompanies: (params: CompanyQueryParams = {}) =>
    request<CompanySummary[]>(`/companies${buildQuery(params as Record<string, string | number | undefined>)}`),
  getCompany: (identifier: string, formType: '10-K' | '10-Q' = '10-K') =>
    request<CompanyFullAnalysis>(`/companies/${encodeURIComponent(identifier)}${buildQuery({ form_type: formType })}`),
  analyzeCompany: (identifier: string, forceRefresh = false) =>
    request<CompanyFullAnalysis>(
      `/companies/${encodeURIComponent(identifier)}/analyze${buildQuery({ force_refresh: forceRefresh })}`,
      { method: 'POST' },
    ),
  compareCompanies: (
    identifiers: string[],
    periodPolicy: 'latest_annual' | 'common_fiscal_year' = 'latest_annual',
  ) =>
    request<CompanyComparisonResponse>(
      `/companies/compare${buildQuery({ identifiers: identifiers.join(','), period_policy: periodPolicy })}`,
    ),
  getClusterMap: () => request<ClusterPoint[]>('/clusters/map'),
  simulateStress: (identifier: string, scenario: StressScenarioRequest) =>
    request<StressSimulationResponse>(`/companies/${encodeURIComponent(identifier)}/simulate`, {
      method: 'POST',
      body: JSON.stringify(scenario),
    }),

  // Reports, Alerts & Forecast Evidence
  getReports: (identifier: string) =>
    request<ReportResponse>(`/reports/${encodeURIComponent(identifier)}`),
  getReportAlerts: (identifier: string) =>
    request<ReportAlert[]>(`/report-alerts/${encodeURIComponent(identifier)}`),
  getFilingForecasts: (filingId: number) =>
    request<ForecastEvidence[]>(`/filings/${filingId}/forecasts`),

  // ML Models
  getModelVersions: () => request<ModelVersionSummary[]>('/models/versions'),
  getModelEvaluation: (modelVersion?: string) =>
    request<ModelEvaluationResponse>(`/models/evaluation${buildQuery({ model_version: modelVersion })}`),
  predictManual: (payload: ManualStatementInput) =>
    request<ManualPredictionResponse>('/models/predict-manual', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  predictBatch: (items: ManualStatementInput[], modelVersion?: string) =>
    request<BatchPredictionResponse>('/models/predict-batch', {
      method: 'POST',
      body: JSON.stringify({ items, ...(modelVersion ? { model_version: modelVersion } : {}) }),
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

  // Auth & Accounts
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
  verifyEmail: (email: string, challenge: string, code: string) =>
    request<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code }),
    }),
  logout: () => request<{ message: string }>('/auth/logout', { method: 'POST' }),
  updateProfile: (display_name: string) =>
    request<PublicUser>('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify({ display_name }),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; challenge: string; expires_in: number }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (email: string, challenge: string, code: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, challenge, code, new_password }),
    }),

  // Personal Workspace
  getWatchlist: () => request<WatchlistEntry[]>('/me/watchlist'),
  followCompany: (cik: string) =>
    request<{ id: number }>(`/me/watchlist/${encodeURIComponent(cik)}`, { method: 'POST' }),
  getScreeners: () => request<SavedScreenerEntry[]>('/me/screeners'),
  saveScreener: (name: string, filters: Record<string, string | number | null | undefined>) =>
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
  deleteSavedItem: (collection: 'watchlist' | 'screeners' | 'analyses', itemId: number) =>
    request<void>(`/me/${collection}/${itemId}`, { method: 'DELETE' }),

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
    request<IngestionJob>(`/ingestion/${encodeURIComponent(identifier)}`, { method: 'POST' }),
  retryIngestion: (jobId: number) =>
    request<IngestionJob>(`/ingestion/${jobId}/retry`, { method: 'POST' }),
  getAdminAudit: () => request<AuditEntry[]>('/admin/audit'),
};
