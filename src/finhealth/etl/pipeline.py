"""Latest-filing ETL composition, transactional repository writes, and Parquet export."""

import json
import logging
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.core.constants import EXCLUDED_INDUSTRIAL_CIKS, US_GAAP_TAG_FALLBACKS
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.lineage import archive_forecast, archive_statement
from finhealth.db.models import Company, FinancialStatement
from finhealth.db.repositories import (
    CompanyRepository,
    FinancialMetricRepository,
    FinancialStatementRepository,
    normalize_cik,
)
from finhealth.etl.feature_engineering import compute_temporal_features
from finhealth.etl.financial_ratios import CREDIT_RATIO_COLUMNS, compute_statement_ratios
from finhealth.etl.spark_session import create_spark_session
from finhealth.etl.xbrl_parser import SecXbrlParser
from finhealth.ingestion.schemas import (
    CompanyMetadata,
    is_financial_institution_sic,
    is_manufacturing_sic,
)

logger = logging.getLogger(__name__)
_METRICS = frozenset(
    {
        "roa",
        "roe",
        "eps",
        "debt_ratio",
        "debt_to_equity",
        "current_ratio",
        "operating_margin",
        "ocf_ratio",
        "working_capital_ratio",
        "retained_earnings_ratio",
        "ebit_to_assets",
        "asset_turnover",
        "altman_z_score",
        "altman_zone",
        "roa_yoy_delta",
        "roe_yoy_delta",
        "debt_ratio_yoy_delta",
        "ocf_ratio_yoy_delta",
        "negative_ocf_streak",
        *CREDIT_RATIO_COLUMNS,
    }
)


def require_industrial_company(cik: str, sic_code: str | int | None) -> None:
    """Reject registrants outside the scope of industrial financial models."""
    if is_financial_institution_sic(sic_code):
        raise EtlProcessingError(
            "Depository institutions, insurers, REITs and other SIC 6000–6799 registrants "
            "require specialized regulatory capital models rather than industrial "
            "working-capital and Altman Z models."
        )
    if cik in EXCLUDED_INDUSTRIAL_CIKS:
        raise EtlProcessingError(
            f"CIK {cik} is excluded from the industrial panel due to the PARA ticker "
            "collision and its SPAC predecessor history."
        )


class FinancialEtlPipeline:
    """Compose pure normalization and features without fitting any learned preprocessing."""

    def __init__(self, use_spark: bool = False) -> None:
        """Select optional Spark export; PyArrow remains the Java-free fallback."""
        self.use_spark = use_spark

    def process_company_facts_payload(
        self,
        cik: str,
        payload: dict[str, Any],
        sic_code: str | None = None,
        *,
        exclude_ambiguous: bool = False,
        quarter_report_dates: dict[str, date] | None = None,
    ) -> list[dict[str, Any]]:
        """Normalize one company and enrich periods with ratios and grouped trajectories."""
        normalized = normalize_cik(cik)
        require_industrial_company(normalized, sic_code)
        if normalize_cik(payload.get("cik")) != normalized:
            raise EtlProcessingError("Payload CIK does not match the requested company")
        manufacturing = is_manufacturing_sic(sic_code)
        rows: list[dict[str, Any]] = []
        for record in SecXbrlParser().parse(
            payload, exclude_ambiguous=exclude_ambiguous, quarter_report_dates=quarter_report_dates
        ):
            row = record.model_dump()
            row.update(compute_statement_ratios(row, manufacturing))
            rows.append(row)
        return compute_temporal_features(rows)

    def persist_to_database(
        self, session: Session, metadata: CompanyMetadata, enriched_records: list[dict[str, Any]]
    ) -> Company:
        """Upsert the complete batch in a savepoint; caller owns the outer commit."""
        require_industrial_company(metadata.cik, metadata.sic_code)
        with session.begin_nested():
            companies = CompanyRepository(session)
            statements = FinancialStatementRepository(session)
            metrics = FinancialMetricRepository(session)
            company = companies.upsert_company(
                metadata.cik, metadata.name, metadata.ticker, metadata.sic_code, metadata.sector
            )
            periods = {
                row["accession_number"]: (row["fiscal_year"], row["fiscal_period"])
                for row in enriched_records if row["form_type"] == "10-Q"
            }
            self.quarantine_comparative_quarters(session, company.id, metadata, periods)
            for row in enriched_records:
                if normalize_cik(row["cik"]) != metadata.cik:
                    raise EtlProcessingError("Cannot persist records from another company")
                statement = statements.upsert_statement(
                    company.id,
                    row["accession_number"],
                    row["form_type"],
                    row["fiscal_year"],
                    row["fiscal_period"],
                    row["period_end_date"],
                    row["filed_date"],
                    {field: row.get(field) for field in US_GAAP_TAG_FALLBACKS},
                    provenance=row.get("field_provenance"),
                    record_provenance=True,
                    verified_quarter=(metadata.quarter_report_dates or {}).get(
                        row["accession_number"]
                    ) == row["period_end_date"],
                )
                if row["filed_date"] < statement.filed_date:
                    continue
                metrics.upsert_metric(
                    statement.id,
                    company.id,
                    statement.fiscal_year,
                    statement.fiscal_period,
                    {field: row.get(field) for field in _METRICS},
                )
        return company

    def quarantine_comparative_quarters(
        self, session: Session, company_id: int, metadata: CompanyMetadata,
        expected_periods: dict[str, tuple[int, str]] | None = None,
    ) -> int:
        """Archive and remove serving rows contradicted by the accession's report date."""
        report_dates = metadata.quarter_report_dates or {}
        if not report_dates:
            return 0
        rows = session.scalars(select(FinancialStatement).where(
            FinancialStatement.company_id == company_id,
            FinancialStatement.form_type == "10-Q",
            FinancialStatement.accession_number.in_(report_dates),
        )).all()
        periods = expected_periods or {}
        rejected = [row for row in rows if (
            report_dates[row.accession_number] != row.period_end_date
            or (row.accession_number in periods and periods[row.accession_number]
                != (row.fiscal_year, row.fiscal_period))
        )]
        for row in rejected:
            version = archive_statement(session, metadata.cik, row, "rejected_comparative")
            for forecast in row.predictions:
                archive_forecast(session, version, forecast)
            session.delete(row)
        session.flush()
        return len(rejected)

    def archive_amendments(
        self, session: Session, metadata: CompanyMetadata, payload: dict[str, Any],
    ) -> int:
        """Archive validated amendment facts without altering the first-filed model panel."""
        records = SecXbrlParser().amendments(payload, metadata.amendment_report_dates or {})
        for row in records:
            statement = FinancialStatement(**row.model_dump(exclude={"cik"}))
            archive_statement(session, metadata.cik, statement, "sec_amendment")
        return len(records)

    def export_to_parquet(self, records: list[dict[str, Any]], output_path: Path) -> Path:
        """Atomically export one Parquet file; provenance is a lossless JSON string column."""
        if not records:
            raise EtlProcessingError("Cannot export an empty dataset")
        rows = [
            {**row, "field_provenance": json.dumps(row.get("field_provenance", {}), sort_keys=True)}
            for row in records
        ]
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix="finhealth-", dir=output_path.parent) as staging:
                temporary = Path(staging) / "output.parquet"
                if self.use_spark:
                    try:
                        self._export_spark(rows, Path(staging) / "spark", temporary)
                    except EtlProcessingError as error:
                        logger.warning("Spark unavailable; exporting with PyArrow: %s", error)
                if not temporary.exists():
                    pd.DataFrame(rows).to_parquet(temporary, engine="pyarrow", index=False)
                temporary.replace(output_path)
        except (OSError, ValueError, TypeError, ImportError) as error:
            raise EtlProcessingError(f"Cannot export Parquet dataset: {output_path}") from error
        return output_path

    def _export_spark(self, rows: list[dict[str, Any]], staging: Path, target: Path) -> None:
        """Use Spark to write a single staged part with an explicit nullable field schema."""
        spark = create_spark_session()
        try:
            from pyspark.sql.types import (
                DateType,
                DoubleType,
                IntegerType,
                StringType,
                StructField,
                StructType,
            )

            date_fields = {"period_end_date", "filed_date"}
            int_fields = {"fiscal_year", "negative_ocf_streak"}
            string_fields = {
                "cik",
                "accession_number",
                "form_type",
                "fiscal_period",
                "altman_zone",
                "field_provenance",
            }
            schema = StructType(
                [
                    StructField(
                        key,
                        DateType()
                        if key in date_fields
                        else IntegerType()
                        if key in int_fields
                        else StringType()
                        if key in string_fields
                        else DoubleType(),
                        True,
                    )
                    for key in rows[0]
                ]
            )
            spark.createDataFrame(rows, schema=schema).coalesce(1).write.mode("overwrite").parquet(
                str(staging)
            )
            parts = list(staging.glob("part-*.parquet"))
            if len(parts) != 1:
                raise EtlProcessingError("Spark did not produce exactly one Parquet part")
            parts[0].replace(target)
        except Exception as error:
            raise EtlProcessingError("Spark Parquet export failed") from error
        finally:
            spark.stop()
