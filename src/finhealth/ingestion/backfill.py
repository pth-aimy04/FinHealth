"""Replay trusted SEC cache data without contacting the upstream API."""

import argparse
import json

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from finhealth.core.config import get_settings
from finhealth.core.exceptions import FinHealthError
from finhealth.db.base import utc_now
from finhealth.db.lineage_models import IngestionRun
from finhealth.db.models import Company
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.etl.vietnam_pilot import seed_vietnam_disclosures
from finhealth.ingestion.schemas import CompanyMetadata, sec_report_dates


def main() -> int:
    """Backfill cached quarters or seed the independently sourced Vietnam pilot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vietnam-pilot", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        if args.vietnam_pilot:
            with factory.begin() as session:
                count = seed_vietnam_disclosures(session)
            print(f"Vietnam pilot observations inserted: {count}")
            return 0
        with factory() as session:
            companies = session.scalars(select(Company).order_by(Company.cik)).all()
            for company in companies:
                session.expunge(company)
        pipeline = FinancialEtlPipeline()
        failures: list[str] = []
        for company in companies:
            with factory.begin() as session:
                started = IngestionRun(identifier=company.cik, status="running", attempts=1)
                session.add(started)
                session.flush()
                run_id = started.id
            try:
                path = settings.raw_sec_path / "companyfacts" / f"CIK{company.cik}.json"
                payload = json.loads(path.read_bytes())
                submissions = path.parent.parent / "submissions" / path.name
                filings = json.loads(submissions.read_bytes())
                report_dates = sec_report_dates(filings, "10-Q")
                metadata = CompanyMetadata(
                    cik=company.cik, name=company.name, ticker=company.ticker,
                    sic_code=company.sic_code, sector=company.sector,
                    quarter_report_dates=report_dates,
                    amendment_report_dates=sec_report_dates(filings, "10-K/A", "10-Q/A"),
                )
                rows = pipeline.process_company_facts_payload(
                    company.cik, payload, company.sic_code, exclude_ambiguous=True,
                    quarter_report_dates=report_dates or {},
                )
                quarters = [row for row in rows if row["form_type"] == "10-Q"]
                with factory.begin() as session:
                    if quarters:
                        pipeline.persist_to_database(session, metadata, quarters)
                    amendments = pipeline.archive_amendments(session, metadata, payload)
                    run = session.get(IngestionRun, run_id)
                    assert run is not None
                    run.status = "succeeded"
                    run.company_cik = company.cik
                    run.finished_at = utc_now()
                print(f"{company.ticker}: {len(quarters)} cached quarterly observations, "
                      f"{amendments} amendment observations")
            except (
                OSError, AttributeError, KeyError, TypeError, ValueError,
                FinHealthError, SQLAlchemyError,
            ) as error:
                with factory.begin() as session:
                    run = session.get(IngestionRun, run_id)
                    assert run is not None
                    run.status = "failed"
                    run.error_code = type(error).__name__
                    run.finished_at = utc_now()
                failures.append(company.cik)
        if failures:
            print(f"Failed CIKs: {', '.join(failures)}")
        return int(bool(failures))
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
