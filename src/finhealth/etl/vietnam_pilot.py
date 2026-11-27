"""Manually reconciled pilot disclosures, isolated from SEC model training."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.db.lineage import fingerprint
from finhealth.db.lineage_models import FilingVersion

ANNUAL = "https://bctn2025.fpt.com/wp-content/uploads/2026/04/BCTN-2025.pdf"
QUARTER = (
    "https://fpt.com/-/media/project/fpt-corporation/fpt/ir/information-disclosures/"
    "year-report/2025/april/20250422---fpt---bctc-hop-nhat-quy-1-nam-2025.pdf"
)
DISCLOSURES = "https://fpt.com/vi/nha-dau-tu/thong-tin-cong-bo"
HPG_ANNUAL = (
    "https://file.hoaphat.com.vn/hoaphat-com-vn/2026/04/"
    "20260327-hpg-bctc-hop-nhat-nam-2025-sau-kiem-toan.pdf"
)
HPG_DISCLOSURES = "https://www.hoaphat.com.vn/quan-he-co-dong/bao-cao-tai-chinh"
HPG_ANNUAL_2024 = (
    "https://file.hoaphat.com.vn/hoaphat-com-vn/2025/03/"
    "bao-cao-tai-chinh-hop-nhat-nam-2024-da-kiem-toan-1.pdf"
)
CONCEPTS = {
    "total_assets": ("B01-DN/HN", "270"),
    "total_liabilities": ("B01-DN/HN", "300"),
    "current_liabilities": ("B01-DN/HN", "310"),
    "revenues": ("B02-DN/HN", "10"),
    "net_income": ("B02-DN/HN", "60"),
    "parent_net_income": ("B02-DN/HN", "61"),
    "operating_cash_flow": ("B03-DN/HN", "20"),
}


def seed_vietnam_disclosures(session: Session) -> int:
    """Import exact VND integers checked against official consolidated reports."""
    observations = (
        (
            "FPT", "Công ty Cổ phần FPT", DISCLOSURES,
            "FY", date(2025, 12, 31), date(2026, 3, 19), ANNUAL,
            "audited_consolidated",
            (88141991634625, 44393950887086, 41524928721230,
             70112825100710, 11232339450734, 9376127629501, 10136043915911),
        ),
        (
            "FPT", "Công ty Cổ phần FPT", QUARTER,
            "Q1", date(2025, 3, 31), date(2025, 4, 22), QUARTER,
            "quarterly_consolidated",
            (73997673121789, 36101018424847, 33917117422503,
             16058140942460, 2595557480309, 2174301386525, -2506903722401),
        ),
        (
            "HPG", "Công ty Cổ phần Tập đoàn Hòa Phát", HPG_DISCLOSURES,
            "FY", date(2025, 12, 31), date(2026, 3, 27), HPG_ANNUAL,
            "audited_consolidated",
            (257899200817547, 126679189940972, 94186268324508,
             156116094618482, 15514931571606, 15453174006223, 17365859056591),
        ),
        (
            "HPG", "Công ty Cổ phần Tập đoàn Hòa Phát", HPG_DISCLOSURES + "?page=3",
            "FY", date(2024, 12, 31), date(2025, 3, 28), HPG_ANNUAL_2024,
            "audited_consolidated",
            (224489707553981, 109842249570282, 75225243262689,
             138855112131387, 12020023621271, 12021443836074, 6608320655215),
        ),
    )
    inserted = 0
    for ticker, name, disclosure, period, end, published, url, status, amounts in observations:
        values = dict(zip(CONCEPTS, amounts, strict=True))
        facts: dict[str, Any] = {
            "values": values,
            "accounting_framework": "VAS",
            "audit_status": status,
            "issuer_name": name,
            "provenance": {
                name: {
                    "form": form, "line": line, "unit": "VND", "currency": "VND",
                    "duration_basis": "period" if form != "B01-DN/HN" else "instant",
                    "filed": published.isoformat(), "end": end.isoformat(), "source_url": url,
                }
                for name, (form, line) in CONCEPTS.items()
            },
            "disclosure_url": disclosure,
            "ingestion_method": "manual_source_reconciliation",
        }
        identity = {
            "issuer_key": f"vn:{ticker}", "accession": f"{ticker}-{end.year}-{period}-{status}",
            "form_type": "VN-FY" if period == "FY" else "VN-Q",
            "fiscal_year": end.year, "fiscal_period": period, "period_end": end,
            "published_on": published, "scope": "consolidated",
        }
        digest = fingerprint({**identity, **facts})
        if session.scalar(select(FilingVersion.id).where(
            FilingVersion.issuer_key == identity["issuer_key"], FilingVersion.fingerprint == digest
        )) is None:
            session.add(FilingVersion(
                **identity, fingerprint=digest, source_url=url,
                capture_kind="verified_pilot", facts=facts,
            ))
            inserted += 1
    return inserted
