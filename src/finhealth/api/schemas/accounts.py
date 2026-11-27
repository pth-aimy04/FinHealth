"""Strict account contracts, without client-controlled roles or session identifiers."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finhealth.api.schemas.models import CompanyScreeningFilters, ManualStatementInputSchema

OrgRoleLiteral = Literal["viewer", "analyst", "org_admin"]
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


class StrictInput(BaseModel):
    """Reject unexpected fields rather than accepting privilege escalation input."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class EmailInput(StrictInput):
    """Normalize an ASCII email into a stable identity key."""

    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        """Reject control characters, ambiguous addresses and non-ASCII SMTP addresses."""
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", value):
            raise ValueError("Provide a valid email address")
        return value


class LoginInput(EmailInput):
    """Login accepts existing passwords without changing their whitespace."""

    password: str = Field(min_length=1, max_length=128)


class RegisterInput(LoginInput):
    """A registration can request only a normal user account."""

    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        """Require a visible display name."""
        if not value.strip():
            raise ValueError("Display name cannot be blank")
        return value.strip()


class VerifyOtpInput(EmailInput):
    """A six-digit mailbox code bound to a browser challenge and an owner-chosen password."""

    challenge: str = Field(min_length=32, max_length=128)
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=12, max_length=128)


class ActionCodeInput(EmailInput):
    """Confirm a purpose-specific OTP on the same screen where it was requested."""

    challenge: str = Field(min_length=32, max_length=128)
    code: str = Field(pattern=r"^[0-9]{6}$")


class PasswordCodeInput(ActionCodeInput):
    """Choose a new password only after verifying the mailbox OTP."""

    new_password: str = Field(min_length=12, max_length=128)


class ChangePasswordInput(StrictInput):
    """An authenticated password change requires the current credential."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ProfileInput(StrictInput):
    """Display name and optional job title may change without re-verifying email ownership."""

    display_name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")
    job_title: str | None = Field(default=None, max_length=120)

    @field_validator("job_title")
    @classmethod
    def clean_job_title(cls, value: str | None) -> str | None:
        """Normalize optional job title and reject control characters."""
        if value is None:
            return None
        if _CONTROL_CHARS_RE.search(value):
            raise ValueError("Job title contains invalid control characters")
        cleaned = value.strip()
        return cleaned if cleaned else None


class ChangeEmailInput(EmailInput):
    """Require the current credential before issuing an email-change token."""

    current_password: str = Field(min_length=1, max_length=128)


class ScreenerInput(StrictInput):
    """Store only filters accepted by the public screening service."""

    name: str = Field(min_length=1, max_length=120)
    filters: CompanyScreeningFilters


class AnalysisInput(StrictInput):
    """Recompute saved output on the server, never trust a client prediction."""

    name: str = Field(min_length=1, max_length=120)
    inputs: ManualStatementInputSchema


class AccountStatusInput(StrictInput):
    """Administrative account status changes cannot modify roles."""

    active: bool


class DeleteAccountRequestInput(StrictInput):
    """Require the current password before sending an account-deletion OTP."""

    current_password: str = Field(min_length=1, max_length=128)


class DeleteAccountConfirmInput(StrictInput):
    """Require both the current password and a fresh mailbox OTP to erase an account."""

    current_password: str = Field(min_length=1, max_length=128)
    challenge: str = Field(min_length=32, max_length=128)
    code: str = Field(pattern=r"^[0-9]{6}$")


def _clean_org_name(value: str) -> str:
    """Validate and trim an organization workspace name."""
    if _CONTROL_CHARS_RE.search(value):
        raise ValueError("Organization name contains invalid control characters")
    cleaned = value.strip()
    if len(cleaned) < 2:
        raise ValueError("Organization name must contain at least 2 visible characters")
    return cleaned


class OrganizationCreateInput(StrictInput):
    """Create a new multi-tenant organization workspace."""

    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Enforce visible length and reject control characters."""
        return _clean_org_name(value)


class OrganizationUpdateInput(StrictInput):
    """Rename an existing organization workspace."""

    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Enforce visible length and reject control characters."""
        return _clean_org_name(value)


class OrganizationSwitchInput(StrictInput):
    """Switch the server-side active organization stored on the current session."""

    organization_id: int = Field(gt=0)


class OrganizationInviteInput(EmailInput):
    """Invite a colleague by email with an explicit organization RBAC role."""

    role: OrgRoleLiteral = "viewer"


class OrganizationInviteAcceptInput(StrictInput):
    """Accept a single-use expiring organization invitation token."""

    token: str = Field(min_length=16, max_length=256)

    @field_validator("token")
    @classmethod
    def clean_token(cls, value: str) -> str:
        """Strip outer whitespace and reject blank tokens."""
        cleaned = value.strip()
        if len(cleaned) < 16:
            raise ValueError("Invalid invitation token")
        return cleaned


class OrganizationMemberRoleInput(StrictInput):
    """Assign an explicit RBAC role to an existing organization member."""

    role: OrgRoleLiteral
