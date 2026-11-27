"""Deterministic 100%-balanced Vietnamese sample company datasets and idempotent seeding."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.db.org_models import OrgCompany, OrgFinancialStatement
from finhealth.etl.accounting_validator import validate_financial_statement

MILLION_VND = 1_000_000


@dataclass(frozen=True)
class SampleStatementSpec:
    """One annual financial statement in a Vietnamese sample company time series."""

    fiscal_year: int
    accounting_standard: str
    audit_status: str
    fields_million_vnd: dict[str, float]


@dataclass(frozen=True)
class SampleCompanySpec:
    """Profile and multi-year statements for one Vietnamese sample company."""

    name: str
    tax_code: str
    ticker: str | None
    sector_code: str
    sector_name: str
    business_type: str
    listing_status: str
    relationship_tag: str
    statements: tuple[SampleStatementSpec, ...]


def _build_balanced_stmt(
    *,
    fiscal_year: int,
    total_assets: float,
    current_assets: float,
    cash: float,
    receivables: float,
    inventory: float,
    total_liabilities: float,
    current_liabilities: float,
    short_term_debt: float,
    long_term_debt: float,
    accounts_payable: float,
    retained_earnings: float,
    revenues: float,
    cogs: float,
    opex: float,
    da: float,
    interest_expense: float,
    net_income: float,
    ocf: float,
    capex: float,
    audit_status: str = "audited_unqualified",
) -> SampleStatementSpec:
    """Construct a guaranteed TA = TL + E statement in million VND."""
    equity = round(total_assets - total_liabilities, 2)
    gross_profit = round(revenues - cogs, 2)
    operating_income = round(gross_profit - opex, 2)
    ebitda = round(operating_income + da, 2)
    standard = "TT99_2025" if fiscal_year >= 2026 else "TT200_2014"
    return SampleStatementSpec(
        fiscal_year=fiscal_year,
        accounting_standard=standard,
        audit_status=audit_status,
        fields_million_vnd={
            "total_assets": total_assets,
            "current_assets": current_assets,
            "cash_and_equivalents": cash,
            "accounts_receivable": receivables,
            "inventory": inventory,
            "total_liabilities": total_liabilities,
            "current_liabilities": current_liabilities,
            "short_term_debt": short_term_debt,
            "long_term_debt": long_term_debt,
            "accounts_payable": accounts_payable,
            "stockholders_equity": equity,
            "retained_earnings": retained_earnings,
            "revenues": revenues,
            "cost_of_goods_sold": cogs,
            "gross_profit": gross_profit,
            "operating_expenses": opex,
            "operating_income": operating_income,
            "depreciation_amortization": da,
            "ebitda": ebitda,
            "interest_expense": interest_expense,
            "net_income": net_income,
            "operating_cash_flow": ocf,
            "capex": capex,
        },
    )


def get_vn_sample_definitions() -> tuple[SampleCompanySpec, ...]:
    """Return the 3 deterministic Vietnamese sample companies (FY2022-FY2026, 100% balanced)."""
    minh_an = SampleCompanySpec(
        name="Công ty CP Sản xuất Minh An (Mẫu — Vững mạnh)",
        tax_code="0109990001",
        ticker="MAN",
        sector_code="C25",
        sector_name="Sản xuất sản phẩm từ kim loại đúc sẵn",
        business_type="manufacturing",
        listing_status="unlisted",
        relationship_tag="own_company",
        statements=(
            _build_balanced_stmt(
                fiscal_year=2022,
                total_assets=420_000,
                current_assets=215_000,
                cash=68_000,
                receivables=64_000,
                inventory=72_000,
                total_liabilities=168_000,
                current_liabilities=96_000,
                short_term_debt=32_000,
                long_term_debt=54_000,
                accounts_payable=42_000,
                retained_earnings=98_000,
                revenues=510_000,
                cogs=362_000,
                opex=68_000,
                da=24_000,
                interest_expense=7_200,
                net_income=58_200,
                ocf=74_000,
                capex=28_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2023,
                total_assets=465_000,
                current_assets=242_000,
                cash=79_000,
                receivables=71_000,
                inventory=78_000,
                total_liabilities=176_000,
                current_liabilities=102_000,
                short_term_debt=30_000,
                long_term_debt=56_000,
                accounts_payable=46_000,
                retained_earnings=126_000,
                revenues=565_000,
                cogs=398_000,
                opex=74_000,
                da=26_000,
                interest_expense=6_900,
                net_income=68_800,
                ocf=86_500,
                capex=31_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2024,
                total_assets=520_000,
                current_assets=276_000,
                cash=94_000,
                receivables=78_000,
                inventory=84_000,
                total_liabilities=187_000,
                current_liabilities=110_000,
                short_term_debt=28_000,
                long_term_debt=58_000,
                accounts_payable=50_000,
                retained_earnings=162_000,
                revenues=630_000,
                cogs=441_000,
                opex=82_000,
                da=29_000,
                interest_expense=6_500,
                net_income=80_400,
                ocf=99_000,
                capex=34_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2025,
                total_assets=582_000,
                current_assets=314_000,
                cash=112_000,
                receivables=86_000,
                inventory=92_000,
                total_liabilities=198_000,
                current_liabilities=118_000,
                short_term_debt=26_000,
                long_term_debt=60_000,
                accounts_payable=54_000,
                retained_earnings=204_000,
                revenues=705_000,
                cogs=490_000,
                opex=91_000,
                da=32_000,
                interest_expense=6_100,
                net_income=94_300,
                ocf=115_000,
                capex=36_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2026,
                total_assets=648_000,
                current_assets=356_000,
                cash=132_000,
                receivables=94_000,
                inventory=100_000,
                total_liabilities=210_000,
                current_liabilities=126_000,
                short_term_debt=24_000,
                long_term_debt=62_000,
                accounts_payable=58_000,
                retained_earnings=252_000,
                revenues=785_000,
                cogs=542_000,
                opex=101_000,
                da=35_000,
                interest_expense=5_800,
                net_income=108_900,
                ocf=131_000,
                capex=39_000,
            ),
        ),
    )

    hoang_long = SampleCompanySpec(
        name="Công ty TNHH Thương mại Hoàng Long (Mẫu — Suy giảm ngầm)",
        tax_code="0309990002",
        ticker=None,
        sector_code="G46",
        sector_name="Bán buôn thương mại tổng hợp",
        business_type="trade_service",
        listing_status="unlisted",
        relationship_tag="customer",
        statements=(
            _build_balanced_stmt(
                fiscal_year=2022,
                total_assets=310_000,
                current_assets=225_000,
                cash=34_000,
                receivables=88_000,
                inventory=92_000,
                total_liabilities=192_000,
                current_liabilities=148_000,
                short_term_debt=72_000,
                long_term_debt=32_000,
                accounts_payable=62_000,
                retained_earnings=38_000,
                revenues=480_000,
                cogs=374_000,
                opex=74_000,
                da=9_500,
                interest_expense=9_200,
                net_income=18_200,
                ocf=19_500,
                capex=8_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2023,
                total_assets=355_000,
                current_assets=266_000,
                cash=26_000,
                receivables=114_000,
                inventory=115_000,
                total_liabilities=231_000,
                current_liabilities=184_000,
                short_term_debt=96_000,
                long_term_debt=35_000,
                accounts_payable=74_000,
                retained_earnings=44_000,
                revenues=525_000,
                cogs=420_000,
                opex=78_000,
                da=10_000,
                interest_expense=12_400,
                net_income=11_700,
                ocf=4_200,
                capex=9_000,
            ),
            _build_balanced_stmt(
                fiscal_year=2024,
                total_assets=402_000,
                current_assets=310_000,
                cash=19_000,
                receivables=142_000,
                inventory=138_000,
                total_liabilities=274_000,
                current_liabilities=224_000,
                short_term_debt=124_000,
                long_term_debt=38_000,
                accounts_payable=86_000,
                retained_earnings=48_000,
                revenues=562_000,
                cogs=464_000,
                opex=76_000,
                da=10_500,
                interest_expense=15_800,
                net_income=5_000,
                ocf=-14_500,
                capex=8_500,
                audit_status="audited_qualified",
            ),
            _build_balanced_stmt(
                fiscal_year=2025,
                total_assets=448_000,
                current_assets=352_000,
                cash=14_000,
                receivables=168_000,
                inventory=158_000,
                total_liabilities=318_000,
                current_liabilities=266_000,
                short_term_debt=152_000,
                long_term_debt=40_000,
                accounts_payable=98_000,
                retained_earnings=50_000,
                revenues=595_000,
                cogs=505_000,
                opex=72_000,
                da=11_000,
                interest_expense=18_600,
                net_income=2_400,
                ocf=-26_000,
                capex=7_500,
                audit_status="audited_qualified",
            ),
            _build_balanced_stmt(
                fiscal_year=2026,
                total_assets=486_000,
                current_assets=388_000,
                cash=11_000,
                receivables=188_000,
                inventory=176_000,
                total_liabilities=355_000,
                current_liabilities=302_000,
                short_term_debt=178_000,
                long_term_debt=41_000,
                accounts_payable=108_000,
                retained_earnings=51_000,
                revenues=618_000,
                cogs=536_000,
                opex=67_000,
                da=11_500,
                interest_expense=21_200,
                net_income=1_100,
                ocf=-34_000,
                capex=6_000,
                audit_status="unaudited",
            ),
        ),
    )

    dai_phat = SampleCompanySpec(
        name="Công ty CP Xây lắp Đại Phát (Mẫu — Nguy cơ khủng hoảng cao)",
        tax_code="0109990003",
        ticker="DPC",
        sector_code="F41",
        sector_name="Xây dựng công trình dân dụng và công nghiệp",
        business_type="manufacturing",
        listing_status="unlisted",
        relationship_tag="supplier",
        statements=(
            _build_balanced_stmt(
                fiscal_year=2022,
                total_assets=520_000,
                current_assets=310_000,
                cash=18_000,
                receivables=152_000,
                inventory=128_000,
                total_liabilities=435_000,
                current_liabilities=332_000,
                short_term_debt=198_000,
                long_term_debt=88_000,
                accounts_payable=112_000,
                retained_earnings=-15_000,
                revenues=390_000,
                cogs=354_000,
                opex=38_000,
                da=16_000,
                interest_expense=29_500,
                net_income=-31_500,
                ocf=-24_000,
                capex=12_000,
                audit_status="audited_qualified",
            ),
            _build_balanced_stmt(
                fiscal_year=2023,
                total_assets=492_000,
                current_assets=288_000,
                cash=12_000,
                receivables=144_000,
                inventory=122_000,
                total_liabilities=446_000,
                current_liabilities=354_000,
                short_term_debt=218_000,
                long_term_debt=80_000,
                accounts_payable=118_000,
                retained_earnings=-54_000,
                revenues=335_000,
                cogs=314_000,
                opex=34_000,
                da=15_000,
                interest_expense=31_800,
                net_income=-44_800,
                ocf=-36_000,
                capex=8_000,
                audit_status="audited_qualified",
            ),
            _build_balanced_stmt(
                fiscal_year=2024,
                total_assets=460_000,
                current_assets=264_000,
                cash=8_000,
                receivables=132_000,
                inventory=114_000,
                total_liabilities=452_000,
                current_liabilities=374_000,
                short_term_debt=236_000,
                long_term_debt=68_000,
                accounts_payable=124_000,
                retained_earnings=-92_000,
                revenues=285_000,
                cogs=275_000,
                opex=30_000,
                da=14_000,
                interest_expense=33_200,
                net_income=-53_200,
                ocf=-42_000,
                capex=5_000,
                audit_status="audited_adverse_disclaimer",
            ),
            _build_balanced_stmt(
                fiscal_year=2025,
                total_assets=432_000,
                current_assets=242_000,
                cash=5_500,
                receivables=121_000,
                inventory=106_000,
                total_liabilities=458_000,
                current_liabilities=392_000,
                short_term_debt=252_000,
                long_term_debt=56_000,
                accounts_payable=128_000,
                retained_earnings=-126_000,
                revenues=240_000,
                cogs=238_000,
                opex=27_000,
                da=13_000,
                interest_expense=34_500,
                net_income=-59_500,
                ocf=-48_000,
                capex=4_000,
                audit_status="audited_adverse_disclaimer",
            ),
            _build_balanced_stmt(
                fiscal_year=2026,
                total_assets=405_000,
                current_assets=222_000,
                cash=4_000,
                receivables=110_000,
                inventory=99_000,
                total_liabilities=465_000,
                current_liabilities=408_000,
                short_term_debt=268_000,
                long_term_debt=48_000,
                accounts_payable=130_000,
                retained_earnings=-160_000,
                revenues=205_000,
                cogs=208_000,
                opex=24_000,
                da=12_000,
                interest_expense=36_000,
                net_income=-63_000,
                ocf=-52_000,
                capex=3_000,
                audit_status="unaudited",
            ),
        ),
    )

    return (minh_an, hoang_long, dai_phat)


def seed_vn_sample_companies(
    db: Session,
    organization_id: int,
    *,
    created_by: int | None = None,
) -> dict[str, Any]:
    """Idempotently seed the 3 Vietnamese sample companies and their 5-year BCTC series."""
    created_companies = 0
    existing_companies = 0
    created_statements = 0
    company_summaries: list[dict[str, Any]] = []

    for spec in get_vn_sample_definitions():
        company = db.scalar(
            select(OrgCompany).where(
                OrgCompany.organization_id == organization_id,
                OrgCompany.tax_code == spec.tax_code,
            )
        )
        if company is None:
            company = OrgCompany(
                organization_id=organization_id,
                name=spec.name,
                tax_code=spec.tax_code,
                ticker=spec.ticker,
                sector_code=spec.sector_code,
                sector_name=spec.sector_name,
                business_type=spec.business_type,
                listing_status=spec.listing_status,
                relationship_tag=spec.relationship_tag,
                archived=False,
                is_sample=True,
            )
            db.add(company)
            db.flush()
            created_companies += 1
        else:
            existing_companies += 1

        for stmt_spec in spec.statements:
            existing_stmt = db.scalar(
                select(OrgFinancialStatement).where(
                    OrgFinancialStatement.organization_id == organization_id,
                    OrgFinancialStatement.org_company_id == company.id,
                    OrgFinancialStatement.fiscal_year == stmt_spec.fiscal_year,
                    OrgFinancialStatement.fiscal_period == "FY",
                )
            )
            if existing_stmt is not None:
                continue

            scaled_fields = {
                key: float(val) * float(MILLION_VND)
                for key, val in stmt_spec.fields_million_vnd.items()
            }
            report = validate_financial_statement(scaled_fields)
            stmt = OrgFinancialStatement(
                organization_id=organization_id,
                org_company_id=company.id,
                fiscal_year=stmt_spec.fiscal_year,
                fiscal_period="FY",
                period_end_date=date(stmt_spec.fiscal_year, 12, 31),
                accounting_standard=stmt_spec.accounting_standard,
                currency="VND",
                unit_scale=MILLION_VND,
                display_unit="MILLION_VND",
                audit_status=stmt_spec.audit_status,
                status="finalized",
                source_channel="sample",
                validation_summary=report.to_dict(),
                raw_source_meta={"seed_profile": spec.tax_code},
                created_by=created_by,
                **scaled_fields,
            )
            db.add(stmt)
            created_statements += 1

        company_summaries.append(
            {
                "id": company.id,
                "name": company.name,
                "tax_code": company.tax_code,
                "business_type": company.business_type,
                "is_sample": company.is_sample,
            }
        )

    db.commit()
    return {
        "created_companies": created_companies,
        "existing_companies": existing_companies,
        "created_statements": created_statements,
        "companies": company_summaries,
    }
