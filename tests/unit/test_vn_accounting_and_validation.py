"""Unit tests for extended ratios, validator, VAS mapper, HTKK XML, Excel, and VN samples."""

import math
import zipfile
from io import BytesIO

import pytest
from sqlalchemy import func, select

from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.account_models import Organization
from finhealth.db.base import Base
from finhealth.db.org_models import OrgCompany, OrgFinancialStatement
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.accounting_validator import validate_financial_statement
from finhealth.etl.excel_templates import (
    MAX_EXCEL_UPLOAD_BYTES,
    generate_bctc_template_bytes,
    parse_bctc_excel_bytes,
)
from finhealth.etl.financial_ratios import compute_equity_guards, compute_statement_ratios
from finhealth.etl.htkk_xml_parser import MAX_HTKK_XML_BYTES, parse_htkk_xml_bytes
from finhealth.etl.vn_accounting_mapper import (
    SUPPORTED_VAS_REGIMES,
    map_vas_codes_to_normalized,
)
from finhealth.etl.vn_samples import get_vn_sample_definitions, seed_vn_sample_companies


def _healthy_statement() -> dict[str, float]:
    """Return a clean, balanced statement fixture for ratio and validator tests."""
    return {
        "total_assets": 1000.0,
        "current_assets": 500.0,
        "cash_and_equivalents": 150.0,
        "accounts_receivable": 120.0,
        "inventory": 180.0,
        "total_liabilities": 400.0,
        "current_liabilities": 200.0,
        "short_term_debt": 80.0,
        "long_term_debt": 150.0,
        "accounts_payable": 90.0,
        "stockholders_equity": 600.0,
        "retained_earnings": 250.0,
        "revenues": 1200.0,
        "cost_of_goods_sold": 780.0,
        "gross_profit": 420.0,
        "operating_expenses": 180.0,
        "operating_income": 240.0,
        "depreciation_amortization": 60.0,
        "interest_expense": 20.0,
        "net_income": 176.0,
        "operating_cash_flow": 220.0,
        "capex": 70.0,
    }


def test_extended_ratios_and_negative_thin_equity_guards() -> None:
    """Verify extended ratios, derived gross profit/EBITDA, and negative/thin equity policies."""
    stmt = _healthy_statement()
    ratios = compute_statement_ratios(stmt)

    assert ratios["gross_margin"] == pytest.approx(420.0 / 1200.0)
    assert ratios["quick_ratio"] == pytest.approx((500.0 - 180.0) / 200.0)
    assert ratios["dso"] == pytest.approx((120.0 / 1200.0) * 365.0)
    assert ratios["dio"] == pytest.approx((180.0 / 780.0) * 365.0)
    assert ratios["ebitda_margin"] == pytest.approx((240.0 + 60.0) / 1200.0)
    assert ratios["short_term_debt_share"] == pytest.approx(80.0 / 400.0)
    assert ratios["equity_to_assets"] == pytest.approx(0.6)
    assert ratios["is_negative_equity"] is False
    assert ratios["is_thin_equity"] is False

    # Missing gross_profit derives from revenues - COGS; missing inventory keeps quick_ratio None.
    partial = {k: v for k, v in stmt.items() if k not in ("gross_profit", "inventory")}
    partial_ratios = compute_statement_ratios(partial)
    assert partial_ratios["gross_margin"] == pytest.approx(420.0 / 1200.0)
    assert partial_ratios["quick_ratio"] is None

    # Negative equity case: equity = -50, assets = 1000
    neg_stmt = {**stmt, "stockholders_equity": -50.0, "total_liabilities": 1050.0}
    neg_ratios = compute_statement_ratios(neg_stmt)
    assert neg_ratios["is_negative_equity"] is True
    assert neg_ratios["is_thin_equity"] is False
    assert neg_ratios["equity_to_assets"] == pytest.approx(-0.05)
    assert neg_ratios["roe"] is None
    assert neg_ratios["debt_to_equity"] is None
    for val in neg_ratios.values():
        if isinstance(val, float):
            assert math.isfinite(val)

    # Thin equity case: 0 < equity/assets < 0.05
    thin_stmt = {**stmt, "stockholders_equity": 30.0, "total_liabilities": 970.0}
    thin_ratios = compute_statement_ratios(thin_stmt)
    assert thin_ratios["is_negative_equity"] is False
    assert thin_ratios["is_thin_equity"] is True
    assert thin_ratios["equity_to_assets"] == pytest.approx(0.03)
    assert thin_ratios["roe"] is None
    assert thin_ratios["debt_to_equity"] is None

    # Direct helper check with zero assets
    zero_guard = compute_equity_guards(0.0, -50.0)
    assert zero_guard["equity_to_assets"] is None
    assert zero_guard["is_negative_equity"] is True
    assert zero_guard["is_thin_equity"] is False


def test_accounting_validator_detects_exact_errors_and_warnings() -> None:
    """Validator pinpoints structural errors and emits solvency warnings without blocking."""
    clean_report = validate_financial_statement(_healthy_statement())
    assert clean_report.is_balanced is True
    assert clean_report.errors == []
    assert clean_report.warnings == []

    # Within 0.5% tolerance passes
    within_tol = {**_healthy_statement(), "total_assets": 1004.0}
    assert validate_financial_statement(within_tol).is_balanced is True

    # Beyond 0.5% tolerance fails with exact field and discrepancy
    imbalanced = {**_healthy_statement(), "total_assets": 1050.0}
    rep = validate_financial_statement(imbalanced)
    assert rep.is_balanced is False
    assert any(
        err.code == "BALANCE_SHEET_IMBALANCE"
        and err.field == "total_assets"
        and err.discrepancy == pytest.approx(50.0)
        for err in rep.errors
    )

    # Structural sub-item violations
    broken = {
        **_healthy_statement(),
        "current_assets": 1200.0,
        "current_liabilities": 450.0,
        "cash_and_equivalents": 1300.0,
        "inventory": 1250.0,
        "accounts_receivable": 1210.0,
        "short_term_debt": 500.0,
    }
    broken_rep = validate_financial_statement(broken)
    error_fields = {err.field for err in broken_rep.errors}
    assert {
        "current_assets",
        "current_liabilities",
        "cash_and_equivalents",
        "inventory",
        "accounts_receivable",
        "short_term_debt",
    }.issubset(error_fields)

    # Long-term debt exceeding non-current liabilities (TL - CL = 200)
    lt_broken = {**_healthy_statement(), "long_term_debt": 250.0}
    lt_rep = validate_financial_statement(lt_broken)
    assert any(
        err.code == "LONG_TERM_DEBT_EXCEEDS_NONCURRENT_LIABILITIES"
        and err.field == "long_term_debt"
        and err.discrepancy == pytest.approx(50.0)
        for err in lt_rep.errors
    )

    # Warnings: negative equity (still balanced TA = TL + E), GP mismatch, profit with negative OCF
    warn_stmt = {
        **_healthy_statement(),
        "total_liabilities": 1050.0,
        "stockholders_equity": -50.0,
        "gross_profit": 350.0,
        "operating_cash_flow": -120.0,
    }
    warn_rep = validate_financial_statement(warn_stmt)
    assert warn_rep.is_balanced is True
    warn_codes = {w.code for w in warn_rep.warnings}
    assert {"NEGATIVE_EQUITY", "GROSS_PROFIT_MISMATCH", "PROFIT_NEGATIVE_OCF"}.issubset(warn_codes)


def test_vn_accounting_mapper_unifies_tt99_tt200_tt133() -> None:
    """TT99/2025, TT200/2014, and TT133/2016 codes normalize to identical fields."""
    tt200_norm = map_vas_codes_to_normalized(
        "TT200_2014",
        bs_codes={
            "100": 500,
            "110": 150,
            "130": 120,
            "140": 180,
            "270": 1000,
            "300": 400,
            "310": 200,
            "311": 90,
            "320": 80,
            "338": 150,
            "400": 600,
            "421": 250,
        },
        is_codes={
            "10": 1200,
            "11": 780,
            "20": 420,
            "23": 20,
            "25": 70,
            "26": 110,
            "30": 240,
            "60": 176,
        },
        cf_codes={"02": 60, "20": 220, "21": -70},
        unit_scale=1_000_000,
    )
    tt99_norm = map_vas_codes_to_normalized(
        "TT99_2025",
        bs_codes={
            "100": 500,
            "110": 150,
            "130": 120,
            "140": 180,
            "270": 1000,
            "300": 400,
            "310": 200,
            "311": 90,
            "320": 80,
            "338": 150,
            "400": 600,
            "421": 250,
        },
        is_codes={
            "10": 1200,
            "11": 780,
            "20": 420,
            "23": 20,
            "25": 70,
            "26": 110,
            "30": 240,
            "60": 176,
        },
        cf_codes={"02": 60, "20": 220, "21": -70},
        unit_scale=1_000_000,
    )
    tt133_norm = map_vas_codes_to_normalized(
        "TT133_2016",
        bs_codes={
            "100": 500,
            "110": 150,
            "130": 120,
            "140": 180,
            "270": 1000,
            "300": 400,
            "310": 200,
            "311": 90,
            "316": 80,
            "336": 150,
            "400": 600,
            "417": 250,
        },
        is_codes={
            "10": 1200,
            "11": 780,
            "20": 420,
            "23": 20,
            "24": 180,
            "30": 240,
            "60": 176,
        },
        cf_codes={"02": 60, "20": 220, "21": -70},
        unit_scale=1_000_000,
    )

    assert tt200_norm == tt99_norm == tt133_norm
    assert tt200_norm["operating_expenses"] == pytest.approx(180_000_000.0)
    assert tt200_norm["capex"] == pytest.approx(70_000_000.0)
    assert tt200_norm["ebitda"] == pytest.approx(300_000_000.0)
    assert tt200_norm["market_value_equity"] is None


@pytest.mark.parametrize(
    ("form_code", "form_name", "expected_regime", "st_code", "lt_code", "re_code", "opex_xml"),
    [
        (
            "405",
            "BCTC TT200/2014/TT-BTC",
            "TT200_2014",
            "ct320",
            "ct338",
            "ct421",
            "<ct25>70000000</ct25><ct26>110000000</ct26>",
        ),
        (
            "406",
            "BCTC TT133/2016/TT-BTC",
            "TT133_2016",
            "ct316",
            "ct336",
            "ct417",
            "<ct24>180000000</ct24>",
        ),
        (
            "BCTC_TT99",
            "Báo cáo tài chính TT99/2025/TT-BTC",
            "TT99_2025",
            "ct320",
            "ct338",
            "ct421",
            "<ct25>70000000</ct25><ct26>110000000</ct26>",
        ),
    ],
)
def test_htkk_xml_parser_auto_detects_all_three_regimes(
    form_code: str,
    form_name: str,
    expected_regime: str,
    st_code: str,
    lt_code: str,
    re_code: str,
    opex_xml: str,
) -> None:
    """HTKK parser detects TT200/TT133/TT99, extracts MST/period, and normalizes all sections."""
    xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <HSoThueDTu>
      <HSoKhaiThue>
        <TTinChung>
          <TTinTKhaiThue>
            <TKhaiThue>
              <maTKhai>{form_code}</maTKhai>
              <tenTKhai>{form_name}</tenTKhai>
              <KyKKhaiThue>
                <kieuKy>Y</kieuKy>
                <kyKKhai>2025</kyKKhai>
                <kyKKhaiDenNgay>31/12/2025</kyKKhaiDenNgay>
              </KyKKhaiThue>
            </TKhaiThue>
            <NNT>
              <mst>0101234567</mst>
              <tenNNT>Công ty TNHH Thử Nghiệm</tenNNT>
            </NNT>
          </TTinTKhaiThue>
        </TTinChung>
        <CTieuTKhaiChinh>
          <CDKT>
            <ct100>500000000</ct100>
            <ct110>150000000</ct110>
            <ct130>120000000</ct130>
            <ct140>180000000</ct140>
            <ct270>1000000000</ct270>
            <ct300>400000000</ct300>
            <ct310>200000000</ct310>
            <ct311>90000000</ct311>
            <{st_code}>80000000</{st_code}>
            <{lt_code}>150000000</{lt_code}>
            <ct400>600000000</ct400>
            <{re_code}>250000000</{re_code}>
          </CDKT>
          <KQHDSXKD>
            <ct10>1200000000</ct10>
            <ct11>780000000</ct11>
            <ct20>420000000</ct20>
            <ct23>20000000</ct23>
            {opex_xml}
            <ct30>240000000</ct30>
            <ct60>176000000</ct60>
          </KQHDSXKD>
          <LCTT_GT>
            <ct02>60000000</ct02>
            <ct20>220000000</ct20>
            <ct21>(70000000)</ct21>
          </LCTT_GT>
        </CTieuTKhaiChinh>
      </HSoKhaiThue>
    </HSoThueDTu>
    """.encode()

    parsed = parse_htkk_xml_bytes(xml_payload)
    assert parsed.accounting_standard == expected_regime
    assert parsed.tax_code == "0101234567"
    assert parsed.fiscal_year == 2025
    assert parsed.fiscal_period == "FY"
    assert parsed.validation.is_balanced is True
    assert parsed.normalized_fields["total_assets"] == pytest.approx(1_000_000_000.0)
    assert parsed.normalized_fields["short_term_debt"] == pytest.approx(80_000_000.0)
    assert parsed.normalized_fields["operating_expenses"] == pytest.approx(180_000_000.0)
    assert parsed.normalized_fields["capex"] == pytest.approx(70_000_000.0)


def test_htkk_xml_parser_blocks_xxe_and_oversized_uploads() -> None:
    """Reject XXE DTD payloads, entity expansion bombs, and files exceeding 5 MB."""
    xxe_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <HSoThueDTu><CDKT><ct270>&xxe;</ct270></CDKT></HSoThueDTu>
    """
    with pytest.raises(EtlProcessingError, match="XXE"):
        parse_htkk_xml_bytes(xxe_payload)

    billion_laughs = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">
    ]>
    <HSoThueDTu><CDKT><ct270>&lol2;</ct270></CDKT></HSoThueDTu>
    """
    with pytest.raises(EtlProcessingError, match="XXE"):
        parse_htkk_xml_bytes(billion_laughs)

    oversized = b"x" * (MAX_HTKK_XML_BYTES + 1)
    with pytest.raises(EtlProcessingError, match="5 MB"):
        parse_htkk_xml_bytes(oversized)


@pytest.mark.parametrize("regime", SUPPORTED_VAS_REGIMES)
def test_excel_template_round_trip_all_three_regimes(regime: str) -> None:
    """Generate template -> prefill -> parse back with 100% numeric accuracy across all regimes."""
    base = {k: v * 1_000_000.0 for k, v in _healthy_statement().items()}
    xlsx_bytes = generate_bctc_template_bytes(
        regime,
        fiscal_year=2025,
        currency="VND",
        unit_scale=1_000_000,
        audit_status="audited_unqualified",
        prefill=base,
    )
    parsed = parse_bctc_excel_bytes(xlsx_bytes)
    assert parsed.accounting_standard == regime
    assert parsed.fiscal_year == 2025
    assert parsed.unit_scale == 1_000_000
    assert parsed.audit_status == "audited_unqualified"
    assert parsed.validation.is_balanced is True

    for field_name, expected in base.items():
        assert parsed.normalized_fields[field_name] == pytest.approx(expected), (
            f"Mismatch on {field_name} for {regime}"
        )


def test_excel_parser_blocks_oversized_non_zip_and_zip_bomb() -> None:
    """Reject files > 5 MB, corrupted non-ZIP files, and high-compression zip-bombs."""
    with pytest.raises(EtlProcessingError, match="5 MB"):
        parse_bctc_excel_bytes(b"0" * (MAX_EXCEL_UPLOAD_BYTES + 1))

    with pytest.raises(EtlProcessingError, match="xlsx"):
        parse_bctc_excel_bytes(b"not a zip archive")

    # Build a tiny compressed ZIP whose uncompressed payload is 30 MB of zeros (zip-bomb)
    bomb_buf = BytesIO()
    with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sheet1.xml", b"0" * (30 * 1024 * 1024))
    with pytest.raises(EtlProcessingError, match="giải nén|zip-bomb"):
        parse_bctc_excel_bytes(bomb_buf.getvalue())


def test_vn_samples_are_100_percent_balanced_and_idempotent() -> None:
    """All 3 Vietnamese sample companies pass validator with 0 hard errors and seed idempotently."""
    samples = get_vn_sample_definitions()
    assert len(samples) == 3

    for company in samples:
        assert len(company.statements) == 5
        years = [s.fiscal_year for s in company.statements]
        assert years == [2022, 2023, 2024, 2025, 2026]
        for stmt in company.statements:
            report = validate_financial_statement(stmt.fields_million_vnd)
            assert report.is_balanced is True, (
                f"{company.name} FY{stmt.fiscal_year} failed: {report.errors}"
            )
            assert report.errors == []

    # Idempotent database seeding test
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            org = Organization(name="Test Org", slug="test-org", is_personal=True)
            session.add(org)
            session.commit()

            first = seed_vn_sample_companies(session, org.id)
            assert first["created_companies"] == 3
            assert first["created_statements"] == 15

            second = seed_vn_sample_companies(session, org.id)
            assert second["created_companies"] == 0
            assert second["existing_companies"] == 3
            assert second["created_statements"] == 0

            assert session.scalar(select(func.count()).select_from(OrgCompany)) == 3
            assert session.scalar(select(func.count()).select_from(OrgFinancialStatement)) == 15
    finally:
        engine.dispose()
