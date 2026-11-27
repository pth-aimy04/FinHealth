"""Offline unit tests for organization RBAC, admin-retention, token and schema invariants."""

import pytest
from pydantic import ValidationError

from finhealth.api.routers.organizations import (
    INVITE_EXPIRY_HOURS,
    MAX_MEMBERS_PER_ORG,
    MAX_ORGS_PER_USER,
    build_org_slug,
    can_modify_org_admin_membership,
    generate_invite_token,
    has_org_permission,
)
from finhealth.api.schemas.accounts import (
    DeleteAccountConfirmInput,
    OrganizationCreateInput,
    OrganizationInviteAcceptInput,
    OrganizationInviteInput,
    OrganizationMemberRoleInput,
    OrganizationSwitchInput,
    OrganizationUpdateInput,
    ProfileInput,
    VerifyOtpInput,
)
from finhealth.api.security import ORG_ROLE_RANK, OrgRole, digest


def test_rbac_permission_matrix() -> None:
    """Verify monotonic viewer < analyst < org_admin privilege hierarchy."""
    roles: tuple[OrgRole, ...] = ("viewer", "analyst", "org_admin")
    assert ORG_ROLE_RANK["viewer"] < ORG_ROLE_RANK["analyst"] < ORG_ROLE_RANK["org_admin"]

    expected = {
        ("viewer", "viewer"): True,
        ("viewer", "analyst"): False,
        ("viewer", "org_admin"): False,
        ("analyst", "viewer"): True,
        ("analyst", "analyst"): True,
        ("analyst", "org_admin"): False,
        ("org_admin", "viewer"): True,
        ("org_admin", "analyst"): True,
        ("org_admin", "org_admin"): True,
    }
    for actor_role in roles:
        for min_role in roles:
            assert has_org_permission(actor_role, min_role) is expected[(actor_role, min_role)]


def test_last_org_admin_cannot_be_demoted_or_removed() -> None:
    """Block demotion or removal of the sole remaining org_admin while allowing safe changes."""
    assert can_modify_org_admin_membership("org_admin", "analyst", org_admin_count=1) is False
    assert can_modify_org_admin_membership("org_admin", "viewer", org_admin_count=1) is False
    assert can_modify_org_admin_membership("org_admin", None, org_admin_count=1) is False
    assert can_modify_org_admin_membership("org_admin", "org_admin", org_admin_count=1) is True

    assert can_modify_org_admin_membership("org_admin", "analyst", org_admin_count=2) is True
    assert can_modify_org_admin_membership("org_admin", None, org_admin_count=2) is True

    for non_admin in ("analyst", "viewer"):
        assert can_modify_org_admin_membership(non_admin, "viewer", org_admin_count=1) is True
        assert can_modify_org_admin_membership(non_admin, None, org_admin_count=1) is True


def test_invite_token_hashing_and_constants() -> None:
    """Invite tokens are high-entropy and persisted strictly as SHA-256 digests."""
    assert MAX_ORGS_PER_USER == 5
    assert MAX_MEMBERS_PER_ORG == 50
    assert INVITE_EXPIRY_HOURS == 72

    raw_a, hash_a = generate_invite_token()
    raw_b, hash_b = generate_invite_token()
    assert raw_a != raw_b
    assert hash_a != hash_b
    assert raw_a != hash_a
    assert len(hash_a) == 64
    assert hash_a == digest(raw_a)


def test_build_org_slug_handles_vietnamese_and_long_names() -> None:
    """Organization slugs are always ASCII, non-empty, unique and bounded to 80 chars."""
    slug_vn = build_org_slug("Công ty TNHH Sản xuất Minh An & Cộng sự")
    assert slug_vn.isascii()
    assert len(slug_vn) <= 80
    assert "minh-an" in slug_vn

    slug_long = build_org_slug("A" * 200)
    assert len(slug_long) <= 80

    slug_symbols = build_org_slug("!!!###$$$")
    assert slug_symbols.startswith("workspace-")


def test_organization_and_privacy_schemas_reject_extra_fields_and_invalid_inputs() -> None:
    """StrictInput(extra='forbid') blocks privilege injection and malformed values."""
    created = OrganizationCreateInput(name="  Công ty CP Minh An  ")
    assert created.name == "Công ty CP Minh An"

    with pytest.raises(ValidationError):
        OrganizationCreateInput(name="Minh An", is_personal=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        OrganizationCreateInput(name=" A ")
    with pytest.raises(ValidationError):
        OrganizationCreateInput(name="Bad\x00Org")

    with pytest.raises(ValidationError):
        OrganizationUpdateInput(name="Valid", role="org_admin")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        OrganizationSwitchInput(organization_id=0)
    with pytest.raises(ValidationError):
        OrganizationSwitchInput(organization_id=1, role="org_admin")  # type: ignore[call-arg]

    invite = OrganizationInviteInput(email="  Analyst@Example.COM ", role="analyst")
    assert invite.email == "analyst@example.com"
    assert invite.role == "analyst"

    with pytest.raises(ValidationError):
        OrganizationInviteInput(email="a@example.com", role="admin")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        OrganizationInviteInput(email="a@example.com", organization_id=1)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        OrganizationInviteAcceptInput(token="short")
    with pytest.raises(ValidationError):
        OrganizationInviteAcceptInput(token="a" * 32, role="org_admin")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        OrganizationMemberRoleInput(role="superadmin")  # type: ignore[arg-type]

    profile = ProfileInput(display_name="Nguyễn Văn A", job_title="  Trưởng phòng Tín dụng  ")
    assert profile.job_title == "Trưởng phòng Tín dụng"
    profile_blank_title = ProfileInput(display_name="Nguyễn Văn A", job_title="   ")
    assert profile_blank_title.job_title is None
    with pytest.raises(ValidationError):
        ProfileInput(display_name="Nguyễn Văn A", job_title="Bad\nTitle")
    with pytest.raises(ValidationError):
        ProfileInput(display_name="Nguyễn Văn A", role="admin")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        VerifyOtpInput(email="a@example.com", challenge="c" * 32, code="123456")  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        DeleteAccountConfirmInput(
            current_password="Password-1234!",
            challenge="c" * 32,
            code="123456",
            user_id=99,  # type: ignore[call-arg]
        )
