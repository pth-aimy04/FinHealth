import type { History, Prediction } from "./api/client";
/** Keep actual and forecast observations separate, including gaps between fiscal years. */
export function trajectory(
  history: History[],
  prediction: Prediction | null | undefined,
  key: "roa" | "roe" | "debt_ratio" | "ocf_ratio" | "eps",
): { years: number[]; actual: (number | null)[]; forecast: (number | null)[] } {
  const observed = history.map((row) => row.fiscal_year);
  if (!observed.length) return { years: [], actual: [], forecast: [] };
  const target = prediction?.target_fiscal_year;
  const last = Math.max(...observed);
  const years = Array.from(
    { length: Math.max(last, target ?? last) - Math.min(...observed) + 1 },
    (_, i) => Math.min(...observed) + i,
  );
  const actual = years.map(
    (year) => history.find((row) => row.fiscal_year === year)?.[key] ?? null,
  );
  const forecast = years.map((year) =>
    prediction && year === target
      ? (prediction[`pred_${key}`] ?? null)
      : year === last && target === last + 1
        ? (history.find((row) => row.fiscal_year === last)?.[key] ?? null)
        : null,
  );
  return { years, actual, forecast };
}

/** Adapt quarter labels and missing fiscal periods without aggregating observations. */
export function historySeries(
  history: History[],
  prediction: Prediction | null | undefined,
  field: "roa" | "roe" | "debt_ratio" | "ocf_ratio" | "eps",
): {
  years: (number | string)[];
  actual: (number | null)[];
  forecast: (number | null)[];
} {
  const quarters = history.filter((row) => /^Q[1-4]$/.test(row.fiscal_period));
  if (quarters.length) {
    const positions = quarters.map(
      (row) => row.fiscal_year * 4 + Number(row.fiscal_period[1]) - 1,
    );
    const indices = Array.from(
      { length: Math.max(...positions) - Math.min(...positions) + 1 },
      (_, i) => Math.min(...positions) + i,
    );
    return {
      years: indices.map(
        (index) => `Q${(index % 4) + 1} ${Math.floor(index / 4)}`,
      ),
      actual: indices.map(
        (index) =>
          quarters.find(
            (row) =>
              row.fiscal_year * 4 + Number(row.fiscal_period[1]) - 1 === index,
          )?.[field] ?? null,
      ),
      forecast: indices.map(() => null),
    };
  }
  return trajectory(history, prediction, field);
}
