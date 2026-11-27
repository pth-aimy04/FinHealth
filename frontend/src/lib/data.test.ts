import { describe, expect, it, vi } from "vitest";
import { ApiError, companies, mutate } from "./api/client";
import { metric, percent, number } from "./formatters";
import { parseCsv, serializeCsv } from "./csv";
import { trajectory } from "./series";
import { manualPayload } from "../features/prediction";
import { readSort } from "../features/screener";
import type { History } from "./api/client";
describe("financial presentation integrity", () => {
  it("reads quoted statement CSV and rejects malformed rows", () => {
    expect(
      parseCsv(
        'company_name,total_assets,total_liabilities\r\n"Issuer, Inc.",100,0\r\n',
      ),
    ).toEqual([
      {
        company_name: "Issuer, Inc.",
        total_assets: "100",
        total_liabilities: "0",
      },
    ]);
    expect(() => parseCsv('name,assets\n"Unclosed,100')).toThrow(
      "CSV có dấu nháy chưa đóng.",
    );
    expect(() => parseCsv("name,assets\nCompany,100,50")).toThrow(
      "Số cột không khớp",
    );
  });
  it("keeps absent, nonfinite and zero observations distinct", () => {
    expect(number(null)).toBe("—");
    expect(number(Infinity)).toBe("—");
    expect(percent(undefined)).toBe("—");
    expect(percent(0)).toBe("0%");
    expect(metric("roa", -0.125)).toBe("-12,5%");
  });
  it("breaks lines across missing fiscal years and missing facts", () => {
    const row = (fiscal_year: number, roa: number | null): History => ({
      fiscal_year,
      roa,
      negative_ocf_streak: 0,
      fiscal_period: "FY",
      form_type: "10-K",
      period_end_date: `${fiscal_year}-12-31`,
    });
    expect(
      trajectory(
        [row(2021, 0.1), row(2023, null), row(2024, 0.2)],
        null,
        "roa",
      ),
    ).toEqual({
      years: [2021, 2022, 2023, 2024],
      actual: [0.1, null, null, 0.2],
      forecast: [null, null, null, null],
    });
  });
  it("does not turn optional financial entries into zero", () => {
    const input = manualPayload({
      company_name: "Issuer",
      fiscal_year: "2025",
      total_assets: "100",
      total_liabilities: "0",
      is_manufacturing: "true",
      net_income: "",
    });
    expect(input.total_liabilities).toBe(0);
    expect(input.net_income).toBeNull();
    expect(input.current_assets).toBeNull();
  });
  it("exports signed numbers, escaped text, nulls and protected CIK/formulas", () => {
    expect(
      serializeCsv(
        ["cik", "name", "roa", "missing"],
        [{ cik: "0000123", name: "=SUM(1,2)", roa: -0.125, missing: null }],
      ),
    ).toBe("cik,name,roa,missing\r\n'0000123,\"'=SUM(1,2)\",-0.125,\r\n");
  });
  it("restores only supported multi-column sorts", () => {
    expect(readSort("roa:desc,ticker:asc,not_a_field:desc")).toEqual([
      { id: "roa", desc: true },
      { id: "ticker", desc: false },
    ]);
  });
});
describe("API security boundary", () => {
  it("sends same-origin cookies and the current CSRF cookie for mutations", async () => {
    document.cookie = "finhealth_csrf=test-csrf";
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));
    await mutate("/me/screeners", { name: "Quality", filters: {} });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/me/screeners",
      expect.objectContaining({
        credentials: "same-origin",
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "test-csrf" }),
      }),
    );
  });
  it("preserves authorization errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('{"detail":"Forbidden"}', { status: 403 }),
    );
    await expect(mutate("/admin/users/1", {}, "PATCH")).rejects.toEqual(
      new ApiError("Forbidden", 403),
    );
  });
  it("fetches every filtered API page rather than silently dropping the rest", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify(
            Array.from({ length: 1000 }, (_, i) => ({ cik: String(i) })),
          ),
        ),
      )
      .mockResolvedValueOnce(new Response('[{"cik":"1000"}]'));
    expect(
      await companies(new URLSearchParams("q=AAPL&sort=roa:desc")),
    ).toHaveLength(1001);
    expect(String(fetcher.mock.calls[1][0])).toContain("offset=1000");
    expect(String(fetcher.mock.calls[1][0])).not.toContain("sort=");
  });
});
