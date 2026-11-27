import type { components } from "./schema";
export type Schema = components["schemas"];
export type Company = Schema["CompanySummarySchema"];
export type Analysis = Schema["CompanyFullAnalysisSchema"];
export type History = Schema["HistoricalMetricPointSchema"];
export type Prediction = Schema["PredictionDetailSchema"];
export type ManualInput = Schema["ManualStatementInputSchema"];
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
/** Retain HttpOnly sessions and cookie-bound CSRF on same-origin API calls. */
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const csrf =
    document.cookie
      .split("; ")
      .find((item) => item.startsWith("finhealth_csrf="))
      ?.split("=")[1] ?? "";
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": decodeURIComponent(csrf),
        ...options.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "Không kết nối được máy chủ. Kiểm tra kết nối và thử lại.",
      0,
    );
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data ? data.detail : null;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : response.status === 422
          ? "Dữ liệu chưa hợp lệ. Kiểm tra giá trị và định dạng các trường."
          : `Yêu cầu thất bại (${response.status}). Hãy thử lại.`,
      response.status,
    );
  }
  // Response types at call sites come from the backend-generated OpenAPI contracts.
  return data as T;
}
/** Submit a JSON mutation. */
export function mutate<T>(
  path: string,
  payload?: unknown,
  method = "POST",
): Promise<T> {
  return request<T>(path, {
    method,
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  });
}
export const filterKeys = [
  "q",
  "sector",
  "fiscal_year",
  "risk_level",
  "cluster_id",
  "min_roa",
  "max_debt_ratio",
  "min_current_ratio",
] as const;
/** Read bounded pages, filtering before client sorting and pagination. */
export async function companies(
  filters = new URLSearchParams(),
  signal?: AbortSignal,
): Promise<Company[]> {
  const rows: Company[] = [];
  for (let offset = 0; ; offset += 1000) {
    const params = new URLSearchParams();
    filterKeys.forEach((key) => {
      const value = filters.get(key);
      if (value) params.set(key, value);
    });
    params.set("limit", "1000");
    params.set("offset", String(offset));
    const page = await request<Company[]>(`/companies?${params}`, { signal });
    rows.push(...page);
    if (page.length < 1000) return rows;
  }
}
