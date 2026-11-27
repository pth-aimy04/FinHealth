"""Account lifecycle with one-use email OTPs, revocable sessions and Law 91/2025 privacy."""

import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.action_codes import consume_code, invalidate_codes, issue_code
from finhealth.api.dependencies import get_db
from finhealth.api.routers.organizations import ensure_personal_organization
from finhealth.api.schemas.accounts import (
    ActionCodeInput,
    ChangeEmailInput,
    ChangePasswordInput,
    DeleteAccountConfirmInput,
    DeleteAccountRequestInput,
    EmailInput,
    LoginInput,
    PasswordCodeInput,
    ProfileInput,
    RegisterInput,
    VerifyOtpInput,
)
from finhealth.api.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    aware_time,
    check_origin,
    consume_limit,
    digest,
    hash_password,
    optional_identity,
    public_user,
    request_limit,
    require_user,
    revoke_sessions,
    verify_password,
)
from finhealth.api.verification import OTP_MINUTES, confirm_code, create_code
from finhealth.core import mail
from finhealth.db.account_models import (
    AccountActionToken,
    AdminAuditLog,
    Organization,
    OrganizationAuditLog,
    OrganizationInvite,
    OrganizationMember,
    SavedAnalysis,
    SavedScreener,
    User,
    UserSession,
    WatchlistItem,
)
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.base import utc_now
from finhealth.db.batch_models import OrgBatchJob, OrgBatchJobRow
from finhealth.db.lineage_models import IngestionRun
from finhealth.db.org_models import OrgAssessment, OrgCompany, OrgFinancialStatement
from finhealth.db.verification_models import EmailVerificationCode

router = APIRouter(prefix="/auth", tags=["accounts"])
Db = Annotated[Session, Depends(get_db)]
Identity = Annotated[User, Depends(require_user)]


def _user_profile(user: User) -> dict[str, object]:
    """Return safe profile fields including optional job_title without secrets."""
    return {**public_user(user), "job_title": user.job_title}


def issue_verification(db: Session, request: Request, user: User | None, email: str) -> dict:
    """Deliver a registration code without putting a localhost link in the email."""
    if user is not None and user.active and not user.email_verified:
        challenge, code = create_code(db, user)
        send(
            request,
            email,
            "FinHealth — Mã OTP xác thực đăng ký",
            f"Mã OTP của bạn: {code}\nMã có hiệu lực {OTP_MINUTES} phút, chỉ dùng một lần.\n"
            "Nhập mã trên màn hình FinHealth đang đăng ký trên máy tính. "
            "Bạn không cần mở website trên điện thoại. Không chia sẻ mã cho người khác.",
        )
    else:
        challenge = secrets.token_urlsafe(32)
        send_without_action(request, email)
    return {
        "message": "Nếu email hợp lệ, mã OTP đã được gửi. Kiểm tra hộp thư và thư rác.",
        "challenge": challenge,
        "expires_in": OTP_MINUTES * 60,
    }


def mail_ready(request: Request) -> None:
    """Translate unavailable SMTP into an actionable service response."""
    try:
        mail.require_mail_configuration(request.app.state.settings)
    except mail.EmailDeliveryError as error:
        raise HTTPException(503, str(error)) from error


def send(request: Request, recipient: str, subject: str, body: str) -> None:
    """Wrap the external SMTP boundary without exposing provider credentials."""
    try:
        mail.send_account_email(request.app.state.settings, recipient, subject, body)
    except mail.EmailDeliveryError as error:
        raise HTTPException(503, str(error)) from error


def send_without_action(request: Request, recipient: str) -> None:
    """Use the same SMTP boundary for unknown and ineligible identities to limit timing leaks."""
    send(
        request,
        recipient,
        "FinHealth — Yêu cầu tài khoản",
        "Chúng tôi đã nhận yêu cầu tài khoản. Nếu bạn đã xác thực email, hãy đăng nhập "
        "hoặc dùng chức năng quên mật khẩu trong FinHealth. Nếu chưa có tài khoản, "
        "hãy đăng ký trong ứng dụng. Nếu không yêu cầu, hãy bỏ qua email.",
    )


def clear_cookies(response: Response, request: Request) -> None:
    """Expire browser session and CSRF cookies using their original attributes."""
    secure = request.app.state.settings.public_base_url.startswith("https://")
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=secure, samesite="strict")


@router.post("/register", status_code=202)
def register(payload: RegisterInput, request: Request, db: Db) -> dict:
    """Register an unverified normal user and require real email delivery."""
    check_origin(request)
    request_limit(db, request, "register", 5)
    mail_ready(request)
    consume_limit(db, "account-email", payload.email, 3)
    consume_limit(db, "verification-send", payload.email, 1, seconds=60)
    user = db.scalar(select(User).where(User.email == payload.email))
    encoded = hash_password(payload.password)
    if user is None:
        user = User(email=payload.email, password_hash=encoded, display_name=payload.display_name)
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.email == payload.email))
    result = issue_verification(db, request, user, payload.email)
    db.commit()
    return result


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response, db: Db) -> dict[str, object]:
    """Authenticate a verified account and rotate to fresh session and CSRF secrets."""
    check_origin(request)
    request_limit(db, request, "login", 20)
    consume_limit(db, "login-account", payload.email, 10)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        # Match the dominant password verification cost for unknown identities.
        hash_password(payload.password)
        raise HTTPException(401, "Email hoặc mật khẩu không đúng, hoặc tài khoản chưa khả dụng")
    valid = verify_password(user.password_hash, payload.password)
    if not valid or not user.active or not user.email_verified:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng, hoặc tài khoản chưa khả dụng")
    old = optional_identity(request, db)
    if old:
        old[1].revoked_at = utc_now()
    default_org = ensure_personal_organization(db, user)
    raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    settings = request.app.state.settings
    db.add(
        UserSession(
            user_id=user.id,
            active_org_id=default_org.id,
            token_hash=digest(raw),
            csrf_hash=digest(csrf),
            credential_stamp=user.password_hash,
            expires_at=utc_now() + timedelta(hours=settings.session_hours),
        )
    )
    db.commit()
    for name, value, http_only in ((SESSION_COOKIE, raw, True), (CSRF_COOKIE, csrf, False)):
        response.set_cookie(
            name,
            value,
            max_age=settings.session_hours * 3600,
            httponly=http_only,
            secure=settings.public_base_url.startswith("https://"),
            samesite="strict",
            path="/",
        )
    return _user_profile(user)


@router.get("/me")
def me(user: Identity) -> dict[str, object]:
    """Return the signed-in profile without exposing session secrets."""
    return _user_profile(user)


@router.get("/me/export")
def export_my_data(user: Identity, db: Db) -> dict[str, object]:
    """Export only the authenticated user's own personal data (Law 91/2025/QH15 portability)."""
    org_rows = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.id.asc())
    ).all()
    sessions = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.id.desc())
    ).all()
    watchlist_items = db.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.id.desc())
    ).all()
    screeners = db.scalars(
        select(SavedScreener)
        .where(SavedScreener.user_id == user.id)
        .order_by(SavedScreener.id.desc())
    ).all()
    analyses = db.scalars(
        select(SavedAnalysis)
        .where(SavedAnalysis.user_id == user.id)
        .order_by(SavedAnalysis.id.desc())
    ).all()
    org_audits = db.scalars(
        select(OrganizationAuditLog)
        .where(OrganizationAuditLog.actor_id == user.id)
        .order_by(OrganizationAuditLog.id.desc())
    ).all()
    admin_audits = db.scalars(
        select(AdminAuditLog)
        .where(AdminAuditLog.actor_id == user.id)
        .order_by(AdminAuditLog.id.desc())
    ).all()

    return {
        "exported_at": utc_now().isoformat(),
        "profile": {
            **_user_profile(user),
            "created_at": aware_time(user.created_at),
            "updated_at": aware_time(user.updated_at),
        },
        "organizations": [
            {
                "organization_id": org.id,
                "name": org.name,
                "slug": org.slug,
                "is_personal": org.is_personal,
                "role": member.role,
                "joined_at": aware_time(member.created_at),
            }
            for org, member in org_rows
        ],
        "sessions": [
            {
                "id": sess.id,
                "active_org_id": sess.active_org_id,
                "created_at": aware_time(sess.created_at),
                "expires_at": aware_time(sess.expires_at),
                "revoked_at": aware_time(sess.revoked_at) if sess.revoked_at else None,
            }
            for sess in sessions
        ],
        "workspace": {
            "watchlist": [
                {
                    "id": item.id,
                    "organization_id": item.organization_id,
                    "company_id": item.company_id,
                    "created_at": aware_time(item.created_at),
                }
                for item in watchlist_items
            ],
            "screeners": [
                {
                    "id": item.id,
                    "organization_id": item.organization_id,
                    "name": item.name,
                    "filters": item.filters,
                }
                for item in screeners
            ],
            "analyses": [
                {
                    "id": item.id,
                    "organization_id": item.organization_id,
                    "name": item.name,
                    "model_version": item.model_version,
                    "created_at": aware_time(item.created_at),
                }
                for item in analyses
            ],
        },
        "activity_logs": {
            "organization_audit_logs": [
                {
                    "id": log.id,
                    "organization_id": log.organization_id,
                    "action": log.action,
                    "target": log.target,
                    "outcome": log.outcome,
                    "created_at": aware_time(log.created_at),
                }
                for log in org_audits
            ],
            "admin_audit_logs": [
                {
                    "id": log.id,
                    "action": log.action,
                    "target": log.target,
                    "outcome": log.outcome,
                    "created_at": aware_time(log.created_at),
                }
                for log in admin_audits
            ],
        },
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Db, user: Identity) -> dict[str, str]:
    """Revoke the presented session on the server, not just its browser cookie."""
    identity = optional_identity(request, db)
    if identity:
        identity[1].revoked_at = utc_now()
    db.commit()
    clear_cookies(response, request)
    return {"message": "Đã đăng xuất"}


@router.patch("/profile")
def profile(payload: ProfileInput, user: Identity, db: Db) -> dict[str, object]:
    """Update only the authenticated owner's display name and optional job title."""
    user.display_name = payload.display_name.strip()
    if "job_title" in payload.model_fields_set:
        user.job_title = payload.job_title
    db.commit()
    return _user_profile(user)


def deliver_action_code(
    db: Session,
    request: Request,
    user: User | None,
    purpose: str,
    recipient: str,
) -> dict[str, object]:
    """Send an OTP rather than an account action URL; keep public eligibility responses generic."""
    if user and user.active and user.email_verified:
        challenge, code = issue_code(db, user, purpose, recipient)
        labels = {
            "reset": "đặt lại mật khẩu",
            "change-password": "đổi mật khẩu",
            "change-email": "đổi email",
            "delete-account": "xóa tài khoản",
        }
        send(
            request,
            recipient,
            f"FinHealth — Mã OTP {labels[purpose]}",
            f"Mã OTP của bạn: {code}\nMục đích: {labels[purpose]}.\n"
            f"Mã có hiệu lực {OTP_MINUTES} phút, chỉ dùng một lần.\n"
            "Nhập mã tại màn hình FinHealth trên máy tính. Không cần mở liên kết "
            "trên điện thoại. Không chia sẻ mã cho bất kỳ ai.",
        )
    else:
        challenge = secrets.token_urlsafe(32)
        send_without_action(request, recipient)
    return {
        "message": "Nếu tài khoản hợp lệ, mã OTP đã được gửi qua email.",
        "challenge": challenge,
        "expires_in": OTP_MINUTES * 60,
    }


def finish_password(
    request: Request,
    response: Response,
    db: Session,
    user: User,
    password: str,
) -> dict[str, str]:
    """Persist a confirmed password and invalidate all outstanding recovery credentials."""
    user.password_hash = hash_password(password)
    revoke_sessions(db, user.id)
    invalidate_codes(db, user.id)
    send(
        request,
        user.email,
        "FinHealth — Mật khẩu đã được cập nhật",
        f"Yêu cầu cập nhật mật khẩu được xác nhận lúc {utc_now().isoformat()}. "
        "Nếu không phải bạn, hãy liên hệ quản trị viên. Email không chứa mật khẩu.",
    )
    db.commit()
    clear_cookies(response, request)
    return {"message": "Đã cập nhật mật khẩu. Vui lòng đăng nhập lại."}


@router.post("/change-password", status_code=202)
def change_password(
    payload: ChangePasswordInput,
    request: Request,
    user: Identity,
    db: Db,
) -> dict[str, object]:
    """Require the current password and mailbox OTP before changing credentials."""
    request_limit(db, request, "change-password", 5)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    mail_ready(request)
    consume_limit(db, "account-email", user.email, 3)
    consume_limit(db, "change-password-send", user.email, 1, seconds=60)
    result = deliver_action_code(db, request, user, "change-password", user.email)
    db.commit()
    return result


@router.post("/confirm-password-change")
def confirm_password_change(
    payload: PasswordCodeInput,
    request: Request,
    response: Response,
    user: Identity,
    db: Db,
) -> dict[str, str]:
    """Confirm OTP only for the authenticated account and the password-change purpose."""
    request_limit(db, request, "confirm-password-change", 10)
    mail_ready(request)
    owner, _ = consume_code(
        db, payload.email, payload.challenge, payload.code, "change-password", user.id
    )
    return finish_password(request, response, db, owner, payload.new_password)


@router.post("/forgot-password", status_code=202)
def forgot(payload: EmailInput, request: Request, db: Db) -> dict[str, object]:
    """Issue recovery OTPs without disclosing whether an account exists."""
    check_origin(request)
    request_limit(db, request, "forgot-password", 5)
    consume_limit(db, "account-email", payload.email, 3)
    consume_limit(db, "reset-send", payload.email, 1, seconds=60)
    mail_ready(request)
    user = db.scalar(select(User).where(User.email == payload.email))
    result = deliver_action_code(db, request, user, "reset", payload.email)
    db.commit()
    return result


@router.post("/resend-verification", status_code=202)
def resend(payload: EmailInput, request: Request, db: Db) -> dict:
    """Resend an OTP with per-address and per-peer quotas; replace the previous code."""
    check_origin(request)
    request_limit(db, request, "resend", 5)
    consume_limit(db, "account-email", payload.email, 3)
    consume_limit(db, "verification-send", payload.email, 1, seconds=60)
    mail_ready(request)
    user = db.scalar(select(User).where(User.email == payload.email))
    result = issue_verification(db, request, user, payload.email)
    db.commit()
    return result


@router.post("/verify-email")
def verify_email(payload: VerifyOtpInput, request: Request, db: Db) -> dict[str, str]:
    """Verify mailbox ownership, preserve owner-chosen password, and create personal org."""
    check_origin(request)
    request_limit(db, request, "verify", 20)
    consume_limit(db, "verify-account", payload.email, 10)
    confirm_code(db, payload.email, payload.challenge, payload.code, payload.new_password)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        ensure_personal_organization(db, user)
        db.commit()
    return {"message": "Đã xác thực email. Bạn có thể đăng nhập."}


@router.post("/reset-password")
def reset(
    payload: PasswordCodeInput,
    request: Request,
    response: Response,
    db: Db,
) -> dict[str, str]:
    """Recover a password using an expiring single-use email OTP, never a URL token."""
    check_origin(request)
    request_limit(db, request, "reset", 10)
    consume_limit(db, "reset-account", payload.email, 10)
    mail_ready(request)
    user, _ = consume_code(db, payload.email, payload.challenge, payload.code, "reset")
    return finish_password(request, response, db, user, payload.new_password)


@router.post("/change-email", status_code=202)
def change_email(payload: ChangeEmailInput, request: Request, user: Identity, db: Db) -> dict:
    """Require a current credential, then send the replacement mailbox an OTP."""
    request_limit(db, request, "change-email", 3)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    mail_ready(request)
    consume_limit(db, "account-email", payload.email, 3)
    consume_limit(db, "change-email-send", str(user.id), 1, seconds=60)
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(400, "Không thể sử dụng địa chỉ email này")
    result = deliver_action_code(db, request, user, "change-email", payload.email)
    db.commit()
    return result


@router.post("/confirm-email")
def confirm_email(
    payload: ActionCodeInput,
    request: Request,
    response: Response,
    user: Identity,
    db: Db,
) -> dict:
    """Apply the OTP-bound mailbox only for the account that requested its replacement."""
    request_limit(db, request, "confirm-email", 10)
    mail_ready(request)
    owner, record = consume_code(
        db, payload.email, payload.challenge, payload.code, "change-email", user.id
    )
    send(
        request,
        owner.email,
        "FinHealth — Địa chỉ email được cập nhật",
        "Yêu cầu đổi email đã được xác nhận bằng OTP. Nếu không phải bạn, liên hệ quản trị viên.",
    )
    owner.email = record.recipient
    revoke_sessions(db, owner.id)
    invalidate_codes(db, owner.id)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(400, "Không thể sử dụng địa chỉ email này") from error
    clear_cookies(response, request)
    return {"message": "Đã đổi email. Vui lòng đăng nhập lại."}


@router.post("/delete-account/request", status_code=202)
def request_delete_account(
    payload: DeleteAccountRequestInput,
    request: Request,
    user: Identity,
    db: Db,
) -> dict[str, object]:
    """Verify current password and email a one-time OTP before permanent account erasure."""
    request_limit(db, request, "delete-account-request", 5)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    mail_ready(request)
    consume_limit(db, "account-email", user.email, 3)
    consume_limit(db, "delete-account-send", user.email, 1, seconds=60)
    result = deliver_action_code(db, request, user, "delete-account", user.email)
    db.commit()
    return result


@router.post("/delete-account")
def delete_account(
    payload: DeleteAccountConfirmInput,
    request: Request,
    response: Response,
    user: Identity,
    db: Db,
) -> dict[str, str]:
    """Erase PII and solo workspaces under Law 91/2025/QH15 after password + OTP confirmation."""
    request_limit(db, request, "delete-account", 10)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")

    consume_code(db, user.email, payload.challenge, payload.code, "delete-account", user.id)

    memberships = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.active == true(),
        )
    ).all()

    solo_org_ids: list[int] = []
    for org, member in memberships:
        total_members = int(
            db.scalar(
                select(func.count())
                .select_from(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
            )
            or 0
        )
        if member.role == "org_admin" and total_members > 1:
            admin_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(OrganizationMember)
                    .where(
                        OrganizationMember.organization_id == org.id,
                        OrganizationMember.role == "org_admin",
                    )
                )
                or 0
            )
            if admin_count <= 1:
                db.rollback()
                raise HTTPException(
                    409,
                    "Bạn là quản trị viên duy nhất của tổ chức còn thành viên khác. "
                    "Vui lòng chuyển quyền quản trị trước khi xóa tài khoản.",
                )
        if total_members <= 1:
            solo_org_ids.append(org.id)

    user_id = user.id
    revoke_sessions(db, user_id)

    # Anonymize append-only audit and shared reference pointers while preserving audit history.
    db.execute(
        update(AdminAuditLog).where(AdminAuditLog.actor_id == user_id).values(actor_id=None)
    )
    db.execute(
        update(OrganizationAuditLog)
        .where(OrganizationAuditLog.actor_id == user_id)
        .values(actor_id=None)
    )
    db.execute(
        update(OrganizationInvite)
        .where(OrganizationInvite.invited_by == user_id)
        .values(invited_by=None)
    )
    db.execute(
        update(Organization).where(Organization.created_by == user_id).values(created_by=None)
    )
    db.execute(
        update(OrgFinancialStatement)
        .where(OrgFinancialStatement.created_by == user_id)
        .values(created_by=None)
    )
    db.execute(
        update(OrgBatchJob).where(OrgBatchJob.created_by == user_id).values(created_by=None)
    )
    db.execute(
        update(IngestionRun).where(IngestionRun.requested_by == user_id).values(requested_by=None)
    )

    # Purge sessions, OTPs, and personal saved workspace records.
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    db.execute(delete(EmailVerificationCode).where(EmailVerificationCode.user_id == user_id))
    db.execute(delete(AccountActionCode).where(AccountActionCode.user_id == user_id))
    db.execute(delete(AccountActionToken).where(AccountActionToken.user_id == user_id))
    db.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id))
    db.execute(delete(SavedScreener).where(SavedScreener.user_id == user_id))
    db.execute(delete(SavedAnalysis).where(SavedAnalysis.user_id == user_id))

    # Purge solo/personal organizations and their private data regardless of FK cascade pragmas.
    if solo_org_ids:
        db.execute(delete(WatchlistItem).where(WatchlistItem.organization_id.in_(solo_org_ids)))
        db.execute(delete(SavedScreener).where(SavedScreener.organization_id.in_(solo_org_ids)))
        db.execute(delete(SavedAnalysis).where(SavedAnalysis.organization_id.in_(solo_org_ids)))
        db.execute(delete(OrgBatchJobRow).where(OrgBatchJobRow.organization_id.in_(solo_org_ids)))
        db.execute(delete(OrgBatchJob).where(OrgBatchJob.organization_id.in_(solo_org_ids)))
        db.execute(delete(OrgAssessment).where(OrgAssessment.organization_id.in_(solo_org_ids)))
        db.execute(
            delete(OrgFinancialStatement).where(
                OrgFinancialStatement.organization_id.in_(solo_org_ids)
            )
        )
        db.execute(delete(OrgCompany).where(OrgCompany.organization_id.in_(solo_org_ids)))
        db.execute(
            delete(OrganizationInvite).where(
                OrganizationInvite.organization_id.in_(solo_org_ids)
            )
        )
        db.execute(
            delete(OrganizationAuditLog).where(
                OrganizationAuditLog.organization_id.in_(solo_org_ids)
            )
        )
        db.execute(
            delete(OrganizationMember).where(
                OrganizationMember.organization_id.in_(solo_org_ids)
            )
        )
        db.execute(delete(Organization).where(Organization.id.in_(solo_org_ids)))

    db.execute(delete(OrganizationMember).where(OrganizationMember.user_id == user_id))
    db.delete(user)
    db.commit()
    clear_cookies(response, request)
    return {"message": "Tài khoản và dữ liệu cá nhân đã được xóa vĩnh viễn."}
