# Competitive & Financial Domain Gap Audit | v1.1.0

This version updates the [v1.0.0 competitive audit](../v1.0.0/COMPETITIVE_AND_DOMAIN_AUDIT.md)
with the Stage 8 results. That report retains the commercial and open-source source
matrix. Stage 8 evaluates the local SEC cache, Parquet, SQLite, saved model and
running dashboard. See the [forensic audit](FORENSIC_AUDIT_REPORT.md) for numeric
verification and the [benchmark report](BENCHMARK_REPORT.md) for complete tables.

| Prior gap | Stage 8 status | Remaining exposure |
| --- | --- | --- |
| P0 concurrent filing targets | Zero non-forward pairs among 748 supervised rows | The target remains the next economic fiscal period with strict publication order. Fixed one-year legal PD needs a different outcome definition. |
| P0 ticker reuse | Excluded Parabolic Technologies by CIK 0001826011 across ingestion, ETL, training and active SQLite | Further ticker reuse and time-varying identifiers require a historical identity register. |
| P1 industrial scope and peer context | SIC 6000–6799 returns structured 422. Eight annual peer medians and percentile ranks with observed denominators are served. A cohort smaller than five issuers falls back to the industrial universe. | PCA and supervised features still use pooled ratios. Cohorts are broad SIC divisions and display ranks, with no sector adjustment learned by the model. |
| P1 Altman comparator | Applies manufacturing cutoff 1.81 and nonmanufacturing cutoff 1.10 | Book equity and operating income remain substitutes in the reference scores. |
| P1 calibration | Validation sigmoid improves Brier and log loss on the 80 test labels. SHAP remains additive in the raw margin. | Ten held-out positives and issuer selection limit precision. No adjudicated defaults or external calibration cohort. |
| P1 forecast persistence | ROA, EPS and OCF gain on both paired metrics. Liabilities/assets ties and ROE improves R² with higher MAE. | Strict five-target outperformance is still open. |
| Tier 1 credit ratios | Cash/current liabilities, operating income/interest, and FCF/total liabilities appear in the API and dashboard. | Capex is PP&E purchases. Interest includes the documented broader fallback when matched. A cash balance that includes restricted cash is retained with provenance but excluded from the ratio. Net debt/EBITDA and debt maturity are still unavailable. |
| Tier 1 memo and scenario | Printable credit memo and four bounded, read-only shocks recompute ratios, temporal features, Altman, PCA, forecast, score and contributions | The stress model holds interest and observed cash fixed, uses a 25% marginal tax assumption, moves financing and earnings through noncurrent assets, and applies the OCF shock independently. It lacks a cash flow and working capital bridge. |
| Verified insolvency outcomes | The release uses the existing cache and operational proxy | Chapter 7/11 event registry, delisting censoring and a verified external test remain open. |
| Quarterly / market updates | The active offline panel contains only 10-K reports | Quarterly deaccumulation, TTM, Merton and text fusion remain future work. |

| New ratio | Observed on annual panel | Observed on latest snapshot |
| --- | ---: | ---: |
| Cash ratio | 1,097 / 1,234 | 69 / 80 |
| Interest coverage | 745 / 1,234 | 15 / 80 |
| FCF / total liabilities | 683 / 1,234 | 50 / 80 |

Missing credit facts stay missing. Underwriting users should check observed cohort
counts before interpreting a percentile. AAPL has no matching latest interest fact.
Its memo shows missing coverage alongside its other reported credit ratios and the
source accession. Percentiles compare numerical ranks with midpoints for ties.

RapidRatings still supplies credit-specific industry analysis and public/private
coverage beyond the sample. Moody’s CreditEdge and Bloomberg DRSK offer multi-horizon
market-informed risk. Koyfin and Simply Wall St provide quarterly and TTM market
research workflows. EdgarTools covers statement stitching and dimensional XBRL.
The legal and other jurisdiction benchmarks and FinBERT discussed in the prior audit
remain separate validation and research tracks.
