"""Multi-tenant organization workspace, membership RBAC, invites and audit endpoints."""

import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.api.schemas.accounts import (
    OrganizationCreateInput,
    OrganizationInviteAcceptInput,
    OrganizationInviteInput,
    OrganizationMemberRoleInput,
    OrganizationSwitchInput,
    OrganizationUpdateInput,
)
from finhealth.api.security import (
    ORG_ROLE_RANK,
    OrgRole,
    _coerce_org_role,
    _require_identity,
    aware_time,
    digest,
    request_limit,
    require_user,
)
from finhealth.core import mail
from finhealth.db.account_models import (
    Organization,
    OrganizationAuditLog,
    OrganizationInvite,
    OrganizationMember,
    User,
    UserSession,
)
from finhealth.db.base import utc_now

MAX_ORGS_PER_USER = 5
MAX_MEMBERS_PER_ORG = 50
INVITE_EXPIRY_HOURS = 72

router = APIRouter(prefix="/organizations", tags=["organizations"])
Db = Annotated[Session, Depends(get_db)]
IdentityPair = Annotated[tuple[User, UserSession], Depends(_require_identity)]
Actor = Annotated[User, Depends(require_user)]


def has_org_permission(role: OrgRole, min_role: OrgRole) -> bool:
    """Evaluate monotonic organization RBAC hierarchy: viewer < analyst < org_admin."""
    return ORG_ROLE_RANK[role] >= ORG_ROLE_RANK[min_role]


def can_modify_org_admin_membership(
    target_role: str,
    new_role: str | None,
    org_admin_count: int,
) -> bool:
    """Prevent demoting or removing the last org_admin of an organization."""
    if target_role != "org_admin":
        return True
    if new_role == "org_admin":
        return True
    return org_admin_count > 1


def generate_invite_token() -> tuple[str, str]:
    """Return a single-use opaque invitation token and its SHA-256 database digest."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, digest(raw_token)


def build_org_slug(name: str) -> str:
    """Create a collision-resistant ASCII slug bounded to 80 characters."""
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not base:
        base = "workspace"
    suffix = secrets.token_hex(4)
    return f"{base[:68]}-{suffix}"


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite naive timestamps to UTC-aware datetimes for comparison."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(
        timezone.utc
    )


def record_org_audit(
    db: Session,
    organization_id: int,
    actor_id: int | None,
    action: str,
    target: str,
    outcome: str = "succeeded",
) -> None:
    """Append a governance audit event without ever storing secrets, tokens or BCTC data."""
    db.add(
        OrganizationAuditLog(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action[:64],
            target=target[:120],
            outcome=outcome[:24],
        )
    )


def ensure_personal_organization(db: Session, user: User) -> Organization:
    """Return an existing default active organization or provision a personal workspace."""
    existing = db.scalar(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.active == true(),
        )
        .order_by(Organization.is_personal.desc(), Organization.id.asc())
    )
    if existing is not None:
        return existing

    name = f"Không gian của {user.display_name}".strip()[:120]
    org = Organization(
        name=name,
        slug=build_org_slug(name),
        is_personal=True,
        active=True,
        created_by=user.id,
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="org_admin"))
    record_org_audit(db, org.id, user.id, "org.personal_create", f"org:{org.id}")
    db.flush()
    return org


def _require_org_membership(
    db: Session,
    org_id: int,
    user_id: int,
    min_role: OrgRole = "viewer",
) -> tuple[Organization, OrganizationMember, OrgRole]:
    """Enforce membership (404 anti-IDOR for non-members) and minimum RBAC role (403)."""
    row = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Organization.id == org_id,
            OrganizationMember.user_id == user_id,
            Organization.active == true(),
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy tổ chức")
    organization, member = row
    role = _coerce_org_role(member.role)
    if not has_org_permission(role, min_role):
        raise HTTPException(403, "Vai trò hiện tại không đủ quyền thực hiện thao tác này")
    return organization, member, role


def _count_org_members(db: Session, org_id: int) -> int:
    """Count current members belonging to an organization."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == org_id)
        )
        or 0
    )


def _count_org_admins(db: Session, org_id: int) -> int:
    """Count current org_admin members in an organization."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == "org_admin",
            )
        )
        or 0
    )


def _send_invite_email_if_configured(
    request: Request,
    recipient: str,
    org_name: str,
    role: OrgRole,
    raw_token: str,
) -> bool:
    """Deliver invitation email when SMTP is configured; never leak SMTP credentials."""
    settings = request.app.state.settings
    try:
        mail.require_mail_configuration(settings)
        mail.send_account_email(
            settings,
            recipient,
            f"FinHealth — Lời mời tham gia {org_name}",
            f"Bạn được mời tham gia không gian làm việc '{org_name}' với vai trò {role}.\n"
            f"Mã mời một lần (hiệu lực {INVITE_EXPIRY_HOURS} giờ): {raw_token}\n"
            "Đăng nhập đúng địa chỉ email này trong FinHealth và nhập mã mời để tham gia.",
        )
        return True
    except mail.EmailDeliveryError:
        return False


@router.get("")
def list_organizations(identity: IdentityPair, db: Db) -> list[dict[str, object]]:
    """List all active organizations the authenticated user belongs to."""
    user, session = identity
    rows = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.active == true(),
        )
        .order_by(Organization.is_personal.desc(), Organization.id.asc())
    ).all()
    if not rows:
        return []
    org_ids = [org.id for org, _ in rows]
    counts_rows = db.execute(
        select(OrganizationMember.organization_id, func.count())
        .where(OrganizationMember.organization_id.in_(org_ids))
        .group_by(OrganizationMember.organization_id)
    ).all()
    counts = {int(org_id): int(total) for org_id, total in counts_rows}
    active_org_id = session.active_org_id if session.active_org_id in org_ids else rows[0][0].id
    return [
        {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "is_personal": org.is_personal,
            "role": member.role,
            "member_count": counts.get(org.id, 1),
            "is_active_workspace": org.id == active_org_id,
            "created_at": aware_time(org.created_at),
        }
        for org, member in rows
    ]


@router.post("", status_code=201)
def create_organization(
    payload: OrganizationCreateInput,
    request: Request,
    identity: IdentityPair,
    db: Db,
) -> dict[str, object]:
    """Create a new organization workspace bounded to MAX_ORGS_PER_USER per creator."""
    user, session = identity
    request_limit(db, request, "org-create", 20)
    owned_count = int(
        db.scalar(
            select(func.count())
            .select_from(Organization)
            .where(
                Organization.created_by == user.id,
                Organization.active == true(),
            )
        )
        or 0
    )
    if owned_count >= MAX_ORGS_PER_USER:
        raise HTTPException(
            409,
            f"Mỗi tài khoản chỉ được tạo tối đa {MAX_ORGS_PER_USER} tổ chức hoạt động.",
        )

    org = Organization(
        name=payload.name,
        slug=build_org_slug(payload.name),
        is_personal=False,
        active=True,
        created_by=user.id,
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="org_admin"))
    session.active_org_id = org.id
    record_org_audit(db, org.id, user.id, "org.create", f"org:{org.id}")
    db.commit()
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "is_personal": org.is_personal,
        "role": "org_admin",
        "member_count": 1,
        "is_active_workspace": True,
        "created_at": aware_time(org.created_at),
    }


@router.post("/switch")
def switch_organization(
    payload: OrganizationSwitchInput,
    identity: IdentityPair,
    db: Db,
) -> dict[str, object]:
    """Persist the verified active organization server-side on the current UserSession."""
    user, session = identity
    row = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Organization.id == payload.organization_id,
            OrganizationMember.user_id == user.id,
            Organization.active == true(),
        )
    ).first()
    if row is None:
        raise HTTPException(403, "Bạn không có quyền truy cập không gian làm việc này")
    organization, member = row
    session.active_org_id = organization.id
    db.commit()
    return {
        "active_org_id": organization.id,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "is_personal": organization.is_personal,
            "role": member.role,
        },
    }


@router.post("/invites/accept")
def accept_invite(
    payload: OrganizationInviteAcceptInput,
    request: Request,
    identity: IdentityPair,
    db: Db,
) -> dict[str, object]:
    """Accept a single-use SHA-256 hashed invite token strictly matching the signed-in email."""
    user, _ = identity
    request_limit(db, request, "org-invite-accept", 20)
    token_hash = digest(payload.token)
    invite = db.scalar(
        select(OrganizationInvite).where(
            OrganizationInvite.token_hash == token_hash,
            OrganizationInvite.accepted_at.is_(None),
            OrganizationInvite.revoked_at.is_(None),
        )
    )
    if invite is None or not secrets.compare_digest(invite.token_hash, token_hash):
        raise HTTPException(400, "Lời mời không hợp lệ hoặc đã được sử dụng")

    if _as_utc(invite.expires_at) <= utc_now():
        raise HTTPException(400, "Lời mời đã hết hạn")

    if user.email.strip().lower() != invite.email.strip().lower():
        raise HTTPException(403, "Lời mời này không dành cho địa chỉ email của bạn")

    org = db.scalar(
        select(Organization).where(
            Organization.id == invite.organization_id,
            Organization.active == true(),
        )
    )
    if org is None:
        raise HTTPException(400, "Tổ chức không còn hoạt động")

    existing = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(409, "Bạn đã là thành viên của tổ chức này")

    if _count_org_members(db, org.id) >= MAX_MEMBERS_PER_ORG:
        raise HTTPException(
            409,
            f"Tổ chức đã đạt giới hạn tối đa {MAX_MEMBERS_PER_ORG} thành viên.",
        )

    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=invite.role))
    invite.accepted_at = utc_now()
    record_org_audit(db, org.id, user.id, "member.invite_accept", f"user:{user.id}:{invite.role}")
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Không thể chấp nhận lời mời lúc này") from error
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        "role": invite.role,
    }


@router.get("/{org_id}")
def get_organization(org_id: int, user: Actor, db: Db) -> dict[str, object]:
    """Return details for one organization only if the authenticated user is a member."""
    org, _, role = _require_org_membership(db, org_id, user.id, "viewer")
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "is_personal": org.is_personal,
        "role": role,
        "member_count": _count_org_members(db, org.id),
        "created_at": aware_time(org.created_at),
    }


@router.patch("/{org_id}")
def update_organization(
    org_id: int,
    payload: OrganizationUpdateInput,
    user: Actor,
    db: Db,
) -> dict[str, object]:
    """Rename an organization; restricted to org_admin members."""
    org, _, role = _require_org_membership(db, org_id, user.id, "org_admin")
    org.name = payload.name
    record_org_audit(db, org.id, user.id, "org.rename", f"org:{org.id}")
    db.commit()
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "is_personal": org.is_personal,
        "role": role,
        "member_count": _count_org_members(db, org.id),
        "created_at": aware_time(org.created_at),
    }


@router.get("/{org_id}/members")
def list_members(org_id: int, user: Actor, db: Db) -> list[dict[str, object]]:
    """List organization members; accessible to all members of that organization."""
    _require_org_membership(db, org_id, user.id, "viewer")
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.id.asc())
    ).all()
    return [
        {
            "user_id": member_user.id,
            "email": member_user.email,
            "display_name": member_user.display_name,
            "job_title": member_user.job_title,
            "role": member.role,
            "joined_at": aware_time(member.created_at),
        }
        for member, member_user in rows
    ]


@router.post("/{org_id}/invites", status_code=201)
def create_invite(
    org_id: int,
    payload: OrganizationInviteInput,
    request: Request,
    user: Actor,
    db: Db,
) -> dict[str, object]:
    """Issue a 72-hour single-use SHA-256 hashed invitation token; org_admin only."""
    request_limit(db, request, "org-invite-create", 30)
    org, _, _ = _require_org_membership(db, org_id, user.id, "org_admin")

    if _count_org_members(db, org.id) >= MAX_MEMBERS_PER_ORG:
        raise HTTPException(
            409,
            f"Tổ chức đã đạt giới hạn tối đa {MAX_MEMBERS_PER_ORG} thành viên.",
        )

    existing_member = db.scalar(
        select(OrganizationMember.id)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org.id,
            User.email == payload.email,
        )
    )
    if existing_member is not None:
        raise HTTPException(409, "Người dùng này đã là thành viên của tổ chức")

    now = utc_now()
    db.execute(
        update(OrganizationInvite)
        .where(
            OrganizationInvite.organization_id == org.id,
            OrganizationInvite.email == payload.email,
            OrganizationInvite.accepted_at.is_(None),
            OrganizationInvite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    raw_token, token_hash = generate_invite_token()
    expires_at = now + timedelta(hours=INVITE_EXPIRY_HOURS)
    invite = OrganizationInvite(
        organization_id=org.id,
        email=payload.email,
        role=payload.role,
        token_hash=token_hash,
        invited_by=user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.flush()
    record_org_audit(db, org.id, user.id, "member.invite", f"invite:{invite.id}:{payload.role}")
    db.commit()

    email_sent = _send_invite_email_if_configured(
        request, payload.email, org.name, payload.role, raw_token
    )
    return {
        "id": invite.id,
        "organization_id": org.id,
        "email": invite.email,
        "role": invite.role,
        "token": raw_token,
        "email_sent": email_sent,
        "expires_at": aware_time(invite.expires_at),
    }


@router.get("/{org_id}/invites")
def list_invites(org_id: int, user: Actor, db: Db) -> list[dict[str, object]]:
    """List pending unexpired invitations for an organization without exposing token hashes."""
    _require_org_membership(db, org_id, user.id, "org_admin")
    now = utc_now()
    rows = db.scalars(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.accepted_at.is_(None),
            OrganizationInvite.revoked_at.is_(None),
            OrganizationInvite.expires_at > now,
        )
        .order_by(OrganizationInvite.id.desc())
    ).all()
    return [
        {
            "id": inv.id,
            "organization_id": inv.organization_id,
            "email": inv.email,
            "role": inv.role,
            "invited_by": inv.invited_by,
            "expires_at": aware_time(inv.expires_at),
            "created_at": aware_time(inv.created_at),
        }
        for inv in rows
    ]


@router.delete("/{org_id}/invites/{invite_id}", status_code=204)
def revoke_invite(org_id: int, invite_id: int, user: Actor, db: Db) -> None:
    """Revoke a pending organization invitation; org_admin only."""
    _require_org_membership(db, org_id, user.id, "org_admin")
    invite = db.scalar(
        select(OrganizationInvite).where(
            OrganizationInvite.id == invite_id,
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.accepted_at.is_(None),
            OrganizationInvite.revoked_at.is_(None),
        )
    )
    if invite is None:
        raise HTTPException(404, "Không tìm thấy lời mời đang chờ")
    invite.revoked_at = utc_now()
    record_org_audit(db, org_id, user.id, "member.invite_revoke", f"invite:{invite.id}")
    db.commit()


@router.patch("/{org_id}/members/{member_user_id}")
def update_member_role(
    org_id: int,
    member_user_id: int,
    payload: OrganizationMemberRoleInput,
    user: Actor,
    db: Db,
) -> dict[str, object]:
    """Update a member's RBAC role while blocking demotion of the last org_admin."""
    _require_org_membership(db, org_id, user.id, "org_admin")
    target = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == member_user_id,
        )
    )
    if target is None:
        raise HTTPException(404, "Không tìm thấy thành viên trong tổ chức")

    admin_count = _count_org_admins(db, org_id)
    if not can_modify_org_admin_membership(target.role, payload.role, admin_count):
        raise HTTPException(409, "Không thể hạ cấp quản trị viên cuối cùng của tổ chức")

    target.role = payload.role
    record_org_audit(
        db,
        org_id,
        user.id,
        "member.role_change",
        f"user:{member_user_id}:{payload.role}",
    )
    db.commit()
    return {"user_id": target.user_id, "role": target.role}


@router.delete("/{org_id}/members/{member_user_id}", status_code=204)
def remove_member(org_id: int, member_user_id: int, user: Actor, db: Db) -> None:
    """Remove a member (org_admin or self-leave) while blocking removal of the last org_admin."""
    org, _, role = _require_org_membership(db, org_id, user.id, "viewer")
    if member_user_id != user.id and not has_org_permission(role, "org_admin"):
        raise HTTPException(403, "Vai trò hiện tại không đủ quyền thực hiện thao tác này")

    target = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == member_user_id,
        )
    )
    if target is None:
        raise HTTPException(404, "Không tìm thấy thành viên trong tổ chức")

    if org.is_personal and member_user_id == org.created_by:
        raise HTTPException(409, "Không thể gỡ chủ sở hữu khỏi không gian cá nhân")

    admin_count = _count_org_admins(db, org_id)
    if not can_modify_org_admin_membership(target.role, None, admin_count):
        raise HTTPException(409, "Không thể gỡ quản trị viên cuối cùng của tổ chức")

    db.delete(target)
    record_org_audit(db, org_id, user.id, "member.remove", f"user:{member_user_id}")
    db.commit()


@router.get("/{org_id}/audit")
def list_audit_logs(
    org_id: int,
    user: Actor,
    db: Db,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    """Return append-only organization governance audit logs; org_admin only."""
    _require_org_membership(db, org_id, user.id, "org_admin")
    rows = db.scalars(
        select(OrganizationAuditLog)
        .where(OrganizationAuditLog.organization_id == org_id)
        .order_by(OrganizationAuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "actor_id": row.actor_id,
            "action": row.action,
            "target": row.target,
            "outcome": row.outcome,
            "created_at": aware_time(row.created_at),
        }
        for row in rows
    ]
