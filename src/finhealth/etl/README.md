The parser produces a latest-filing view, not a historical point-in-time dataset.
Annual fiscal years use the period-end calendar year; Q1 ending in calendar Q4
may use the adjacent filing-context fiscal year. Ambiguous fiscal calendars that
collide under the database natural key raise `EtlProcessingError` for explicit
resolution rather than silently overwriting periods.

Candidates are selected per accounting field by tag priority, quarter duration
preference, filing date, then accession. Annual flow facts with a start date must
span 330–380 days. Quarterly flows must span 70–110 days; only operating cash flow
may fall back to YTD. Its provenance records this basis. YTD cash flow is not
converted to single-quarter cash flow, and durations without a start are accepted
as requested. Do not compare mixed flow bases without additional normalization.

`field_provenance` retains each selected fact's tag, unit, currency, start/end,
filing date, and accession. Accounting identity fallbacks use consolidated equity
to calculate liabilities or adjust for separately tagged noncontrolling interests.
They preserve missing values when temporary equity precludes a simple identity or
the assets and known balance component come from different filings. If the
supported equity scope tags are absent, the identity explicitly assumes no
noncontrolling interests. Parquet stores provenance as a JSON string;
the current database schema stores only statement-level accession/date. Retain
the raw cache and Parquet provenance for auditing; this stage does not add a
fact-level provenance database table or restatement archive.

Ratios reject nonfinite and nonpositive denominators, with a 1e-9 near-zero
threshold. Stage 6.6 also requires equity/assets >=5% for equity-denominator ratios
when assets are positive and finite; accepted ROE is capped to [-3,3] and
debt/equity to [0,20]. Raw accounting values remain intact. This is a fixed domain
policy, not learned clipping on the test split. Missing values remain missing.

Other ratios use the original near-zero
threshold. Missing values remain missing. Manufacturing Altman calculations use
the requested 1.2/1.4/3.3/0.6/1.0 coefficients and **book** equity for X4. This is
a book-equity proxy, not the original market-equity model. Non-manufacturing uses
the specified Z'' coefficients. These are reference indices, not calibrated
bankruptcy probabilities. Unknown SICs follow the non-manufacturing branch.

Temporal features group by company and form. Despite their required *_yoy_delta
names, they calculate t minus the preceding observed period; quarterly data does
not use a four-quarter lag. Streaks count consecutive observations, without filling
missing calendar periods. Current latest-filing features must not be used for
historical prediction without publication-date and restatement controls.

Fit RatioWinsorizer only on the training split. It rejects empty training frames,
all-missing columns, and infinite training values; it never imputes missing data.
Transform preserves NaNs and clips against the stored bounds without refitting.

Database persistence uses a savepoint for the complete batch and leaves outer
commit/rollback to the caller. Stale statement batches cannot overwrite metrics
from newer filings. Parquet export stages and atomically replaces a single file.
Use `FinancialEtlPipeline(use_spark=True)` for optional Spark export; unavailable
Spark/Java startup falls back to pandas/PyArrow with an explicit warning. Spark
must be installed through `finhealth[spark]`; the default path requires no Java.
