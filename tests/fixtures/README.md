These are hand-curated contract fixtures, not verbatim API snapshots or training data.
The ticker and submissions files contain the fields needed by ingestion tests.
The companyfacts fixture preserves SEC object/namespace/concept/units/observation
structure and includes comparative FY 2022 and FY 2023 observations from the 2023
10-K, plus Q1 FY 2024 observations from the 2024 10-Q. `fy` and `fp` describe the
filing context (the comparative 2022 observations occur in the FY 2023 filing).
Money is in dollars and EPS is in USD/shares. Instant balance-sheet facts omit start.

Sources for amounts, period dates, and accessions:

- https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
- https://www.sec.gov/Archives/edgar/data/320193/000032019324000006/aapl-20231230.htm

The requested `Revenues` fixture concept holds reported net-sales amounts to test
that generic concept's JSON structure. It is a deliberate test-only substitution:
Apple uses `RevenueFromContractWithCustomerExcludingAssessedTax` in these filings.
Do not treat this fixture as evidence Apple filed `Revenues` for these periods, or
copy this substitution into ingestion or ETL. Labels/descriptions are abbreviated
fixture annotations, not assertions about official taxonomy documentation.
