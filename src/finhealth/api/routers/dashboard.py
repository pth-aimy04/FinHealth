"""Read-only dashboard inventory derived from the connected database."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.db.models import Company, FinancialStatement

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview")
def dashboard_overview(db: Annotated[Session, Depends(get_db)]) -> dict[str, int]:
    """Return actual company and annual-statement counts for the dashboard header."""
    companies = select(func.count()).select_from(Company).scalar_subquery()
    annual = (
        select(func.count())
        .select_from(FinancialStatement)
        .where(FinancialStatement.form_type == "10-K")
        .scalar_subquery()
    )
    company_count, statement_count = db.execute(select(companies, annual)).one()
    return {"company_count": company_count, "annual_statement_count": statement_count}
