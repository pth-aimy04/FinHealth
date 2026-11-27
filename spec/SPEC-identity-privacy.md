# Spec: Identity, Organization Workspace, RBAC & Data Privacy (`identity-privacy`) — V1.0

> **Module ID:** `identity-privacy` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phạm vi nghiệp vụ:** M01 + Multi-Tenant Organization Workspace + RBAC + Tuân thủ Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 + Sửa toàn bộ lỗi xác thực/CORS hiện hữu trong repo.

---

## 1. Objective

Cung cấp tầng định danh, không gian làm việc tổ chức (Multi-Tenant Organization Workspace), phân quyền theo vai trò (RBAC) và bảo vệ quyền dữ liệu cá nhân đạt chuẩn Go-Live Production, làm nền tảng cô lập dữ liệu cho toàn bộ các module phía sau (`financial-data`, `risk-analytics`, `batch-and-reporting`).

### Yêu cầu nghiệp vụ cụ thể
1. **Hoàn thiện & sửa lỗi vòng đời tài khoản (Auth & OTP):**
   - Sửa lỗi 422 ở luồng xác thực email đăng ký trên frontend (`frontend/src/lib/api.ts:202-206` đang gửi thiếu `new_password` so với `VerifyOtpInput` ở `src/finhealth/api/schemas/accounts.py:52-57`). **Giữ nguyên invariant bảo mật của backend** (`test_verification_cannot_preserve_attacker_selected_password`: chủ hộp thư phải xác nhận `new_password` ở bước `POST /auth/verify-email` để chống tấn công pre-registration takeover), và sửa **frontend (`api.ts` + `AccountPage.tsx`)** gửi đủ `{ email, challenge, code, new_password }` (cho phép chủ hộp thư đặt hoặc xác nhận mật khẩu cuối cùng ngay tại bước nhập OTP).
   - Hoàn thiện giao diện đổi mật khẩu (qua OTP) và đổi email (qua OTP) trên `frontend/src/pages/AccountPage.tsx` (backend đã có sẵn tại `/auth/change-password`, `/auth/confirm-password-change`, `/auth/change-email`, `/auth/confirm-email`), đồng thời sửa lỗi controlled input tên hiển thị (`AccountPage.tsx:137`).
   - Bổ sung trường hồ sơ tổ chức/chức danh tùy chọn cho người dùng (`job_title`, tối đa 120 ký tự).
2. **Workspace Tổ chức (Organization) & RBAC (V1.0):**
   - Mọi dữ liệu riêng tư (`WatchlistItem`, `SavedScreener`, `SavedAnalysis`, và các bảng DN/BCTC ở module `financial-data`) được gắn theo **`organization_id`** thay vì chỉ `user_id`.
   - Khi người dùng xác thực đăng ký thành công, hệ thống **tự động tạo 1 Workspace mặc định** (ví dụ: `"Không gian của <display_name>"`, `is_personal = True`) và gán người dùng vai trò `org_admin` để khách hàng cá nhân dùng ngay không cần thao tác thừa.
   - Hỗ trợ **tạo Organization mới**, **chuyển đổi Workspace đang hoạt động** (active organization lưu trên server-side `UserSession.active_org_id`, không tin `org_id` từ client nếu chưa kiểm tra tư cách thành viên), và **quản lý thành viên** với 3 vai trò tường minh:
     - `org_admin`: Toàn quyền trong tổ chức (quản lý thông tin tổ chức, mời/xóa thành viên, đổi vai trò, quản lý toàn bộ dữ liệu DN/BCTC, xuất/xóa tổ chức).
     - `analyst`: Tạo/sửa/lưu nháp DN & BCTC, chạy chấm điểm/so sánh/batch/PDF, quản lý Watchlist/Screener chung của tổ chức; không được quản lý thành viên hoặc xóa tổ chức.
     - `viewer`: Chỉ xem hồ sơ DN, kết quả phân tích, báo cáo PDF và danh sách theo dõi của tổ chức; không được tạo/sửa/xóa dữ liệu.
   - Luồng **mời thành viên qua Email + Mã mời một lần (single-use expiring invite token, hiệu lực 72 giờ, lưu dạng SHA-256 hash)**: `org_admin` mời email kèm vai trò (`analyst` hoặc `viewer`, chỉ có thể nâng `org_admin` sau khi đã là thành viên hoặc mời trực tiếp với xác nhận); người nhận chấp nhận lời mời sau khi đăng nhập đúng email được mời.
   - Tách bạch hoàn toàn **System Role (`users.role`: `'user' | 'admin'`)** với **Organization Role (`organization_members.role`: `'org_admin' | 'analyst' | 'viewer'`)** — System Admin quản trị hạ tầng/tài khoản, **không tự động có quyền đọc dữ liệu BCTC riêng tư của tổ chức khách hàng**.
3. **Tuân thủ Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 (có hiệu lực 01/01/2026):**
   - **Quyền truy cập & trích xuất dữ liệu (Data Portability):** `GET /api/v1/auth/me/export` trả về gói JSON gồm hồ sơ cá nhân, danh sách tổ chức tham gia, lịch sử phiên và nhật ký hoạt động của chính người dùng.
   - **Quyền xóa tài khoản & xóa sạch dữ liệu (Right to Erasure / Purge):** `POST /api/v1/auth/delete-account` (yêu cầu mật khẩu hiện tại + OTP xác nhận qua email) thực hiện:
     - Thu hồi ngay lập tức toàn bộ phiên đăng nhập (`user_sessions`) và mã OTP (`account_action_tokens`, `email_verification_codes`, `account_action_codes`).
     - Nếu người dùng là `org_admin` duy nhất của một tổ chức còn thành viên khác → trả `409 Conflict` yêu cầu chuyển quyền `org_admin` hoặc giải tán tổ chức trước.
     - Xóa cứng (hard delete / cascade purge) toàn bộ workspace chỉ thuộc riêng người dùng đó cùng dữ liệu liên quan, xóa hồ sơ cá nhân hoặc ẩn danh hóa dấu vết tham chiếu trong `admin_audit_logs` (không lưu email/tên thật sau khi xóa).
   - **Nhật ký kiểm toán tổ chức (`organization_audit_logs`):** Ghi nhận append-only các hành động nhạy cảm (mời thành viên, đổi vai trò, gỡ thành viên, đổi tên tổ chức, xuất dữ liệu, yêu cầu xóa) — tuyệt đối không ghi mật khẩu, OTP, token hay số liệu BCTC.
4. **Sửa lỗi nền tảng bảo mật & CORS:**
   - Mở rộng cấu hình CORS tại `src/finhealth/api/main.py:81-87` bổ sung `PATCH` và `DELETE` vào `allow_methods` (chỉ bật `allow_credentials=True` khi `cors_allowed_origins` là danh sách origin tường minh, không chứa `"*"`).
   - Đảm bảo mọi route ghi dữ liệu riêng tư đều đi qua `require_user` (xác thực cookie + `X-CSRF-Token` + `Origin`) và dependency phân quyền tổ chức `require_org_role(...)`.

### Hợp đồng giao diện cung cấp cho các module phía sau (Boundary Contract)
Các module `financial-data`, `risk-analytics`, `batch-and-reporting` chỉ tương tác với `identity-privacy` qua các dependency/model sau:
- `OrgContext` (dataclass bất biến): `{ user: User, organization: Organization, org_role: Literal["org_admin", "analyst", "viewer"] }`
- Dependency FastAPI:
  - `require_org_context(min_role: Literal["viewer", "analyst", "org_admin"] = "viewer") -> OrgContext`
- Khóa ngoại chuẩn cho mọi bảng riêng tư ở module sau: `organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)`

---

## 2. Tech Stack

- **Backend:** Python 3.10+, FastAPI (`>=0.110.0`), Pydantic v2 (`>=2.6.0`), SQLAlchemy 2.0 (`>=2.0.28`), Alembic (`>=1.13.1`), `argon2-cffi` (`>=23.1.0`).
- **Database:** Tương thích đồng thời **SQLite**, **PostgreSQL** và **SQL Server (pyodbc)** (tuân thủ nguyên tắc single cascade path trên MSSQL như hiện có trong `src/finhealth/db/models.py`).
- **Frontend:** React 19, TypeScript 5.7, Vite 6.2, `@tanstack/react-query`, Tailwind CSS 4 (`frontend/`).

---

## 3. Commands

```powershell
# Backend lint, typecheck & tests (chạy từ thư mục gốc repo)
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src/finhealth
.\.venv\Scripts\pytest.exe -v
.\.venv\Scripts\pytest.exe -v tests/unit tests/integration -k "account or auth or org or workspace or security"

# Database migration
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe downgrade -1

# Frontend typecheck, unit tests & build
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

---

## 4. Project Structure

```text
migrations/versions/
  └── 0008_organizations_rbac_and_privacy.py   # Bảng organizations, organization_members,
                                               # organization_invites, organization_audit_logs;
                                               # thêm active_org_id vào user_sessions,
                                               # organization_id vào watchlist_items,
                                               # saved_screeners, saved_analyses + backfill dữ liệu cũ
src/finhealth/db/
  ├── account_models.py                        # Cập nhật User (job_title), UserSession (active_org_id),
  │                                            # thêm Organization, OrganizationMember,
  │                                            # OrganizationInvite, OrganizationAuditLog
  └── repositories.py                          # Giữ nguyên ranh giới, không trộn logic auth vào financial repo
src/finhealth/api/
  ├── security.py                              # Thêm OrgContext, resolve_org_context, require_org_role
  ├── main.py                                  # Sửa CORS allow_methods bổ sung PATCH, DELETE + mount organizations router
  ├── schemas/accounts.py                      # Giữ nguyên VerifyOtpInput (chống pre-registration); thêm Organization*, Invite*, Privacy* schemas
  └── routers/
      ├── accounts.py                          # Giữ invariant verify-email; tự tạo personal org khi verify; thêm export dữ liệu & xóa tài khoản (OTP)
      ├── organizations.py                     # CRUD tổ chức, chuyển active org, mời/chấp nhận/đổi vai trò/gỡ thành viên, audit log
      └── workspace.py                         # Chuyển phạm vi /me/* sang lọc theo OrgContext.organization.id + kiểm tra RBAC
frontend/src/
  ├── types/api.ts                             # Kiểu Organization, OrgMember, OrgInvite, OrgRole
  ├── lib/api.ts                               # Sửa verifyEmail; thêm changePassword, changeEmail, export/delete account, org APIs
  ├── context/AuthContext.tsx                  # Lưu activeOrg, danh sách organizations, hàm switchOrg
  ├── components/layout/AppShell.tsx           # Bộ chuyển Workspace (Org Switcher) trên thanh điều hướng
  └── pages/
      ├── AccountPage.tsx                      # Nối đủ Đổi mật khẩu, Đổi email, Xuất dữ liệu, Xóa tài khoản, sửa bug displayName
      └── OrganizationPage.tsx                 # Trang quản trị Workspace Tổ chức, thành viên, lời mời & nhật ký kiểm toán
tests/
  ├── unit/test_org_rbac_invariants.py         # Kiểm thử thuần ma trận quyền RBAC, không phụ thuộc DB/mạng
  └── integration/test_organizations_and_privacy.py  # Kiểm thử luồng đầy đủ: cô lập đa tổ chức, mời/đổi vai trò,
                                                     # chống IDOR, verify-email, xóa tài khoản purge sạch dữ liệu
```

---

## 5. Code Style

Tuân thủ chặt PEP 8 (`ruff` line-length 100), type annotation đầy đủ mọi tham số và giá trị trả về, docstring ngắn gọn một dòng, `StrictInput(extra="forbid")` trên mọi Pydantic request contract, và kiểm tra quyền phía server không bao giờ tin ID/role từ client.

### Mẫu chuẩn từ mã nguồn FinHealth (`src/finhealth/api/security.py`)
```python
from dataclasses import dataclass
from typing import Annotated, Callable, Literal

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.api.security import require_user
from finhealth.db.account_models import Organization, OrganizationMember, User

OrgRole = Literal["viewer", "analyst", "org_admin"]
_ROLE_RANK: dict[OrgRole, int] = {"viewer": 1, "analyst": 2, "org_admin": 3}


@dataclass(frozen=True)
class OrgContext:
    """Verified user identity paired with an authorized active organization scope."""

    user: User
    organization: Organization
    role: OrgRole


def require_org_role(min_role: OrgRole = "viewer") -> Callable[..., OrgContext]:
    """Enforce server-verified organization membership and minimum RBAC privilege."""

    def _dependency(
        request: Request,
        user: Annotated[User, Depends(require_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> OrgContext:
        org_id = _resolve_active_org_id(request, user, db)
        row = db.execute(
            select(Organization, OrganizationMember)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Organization.id == org_id,
                OrganizationMember.user_id == user.id,
                Organization.active.is_(True),
            )
        ).first()
        if row is None:
            raise HTTPException(403, "Bạn không có quyền truy cập không gian làm việc này")
        organization, member = row
        role: OrgRole = member.role  # type: ignore[assignment]
        if _ROLE_RANK[role] < _ROLE_RANK[min_role]:
            raise HTTPException(403, "Vai trò hiện tại không đủ quyền thực hiện thao tác này")
        return OrgContext(user=user, organization=organization, role=role)

    return _dependency
```

---

## 6. Testing Strategy

- **Framework:** `pytest` (backend unit & integration, offline 100% — mock ranh giới SMTP duy nhất, không gọi mạng thật), `vitest` + `@testing-library/react` (frontend).
- **Unit tests (`tests/unit/test_org_rbac_invariants.py`):**
  - Xác minh bảng phân quyền `viewer < analyst < org_admin` trên toàn bộ ma trận hành động.
  - Xác minh không thể hạ cấp hoặc xóa `org_admin` cuối cùng của tổ chức.
  - Xác minh băm token lời mời (không lưu plaintext), giới hạn độ dài/ký tự tên tổ chức, từ chối trường lạ (`extra="forbid"`).
- **Integration tests (`tests/integration/test_organizations_and_privacy.py`):**
  - **Sửa bug đăng ký (giữ invariant bảo mật):** `POST /auth/register` → `POST /auth/verify-email` (gửi đủ `{email, challenge, code, new_password}` từ frontend) trả 200 → đăng nhập bằng `new_password` thành công và tự động có 1 Organization mặc định với vai trò `org_admin`; đồng thời `test_verification_cannot_preserve_attacker_selected_password` vẫn xanh 100%.
  - **Cô lập Multi-Tenant (chống IDOR):** User A ở Org 1 tạo `SavedAnalysis`/`SavedScreener`/`WatchlistItem`; User B ở Org 2 gọi `GET/DELETE` bằng đúng `item_id` của Org 1 bắt buộc nhận `404` (không lộ sự tồn tại).
  - **Luồng RBAC tổ chức:** `org_admin` mời User B làm `viewer` → User B xem được dữ liệu Org 1 nhưng nhận `403` khi gọi `POST`/`DELETE` → `org_admin` nâng User B lên `analyst` → User B tạo/xóa được mục trong Org 1 nhưng vẫn nhận `403` khi mời/gỡ thành viên.
  - **Chống chiếm đoạt lời mời:** User C có email khác email được mời thử chấp nhận mã mời của User B → bắt buộc nhận `403`.
  - **Luồng đổi mật khẩu/đổi email & xóa tài khoản (Luật 91/2025):**
    - `GET /auth/me/export` trả đầy đủ hồ sơ của chính user và không chứa dữ liệu user khác.
    - `POST /auth/delete-account` chặn `409` nếu là `org_admin` duy nhất của tổ chức còn thành viên khác; khi hợp lệ thì thu hồi phiên, xóa sạch bản ghi cá nhân/workspace riêng và các cookie cũ lập tức trả `401`.
  - **CORS & Migration:** Xác minh preflight `OPTIONS` chấp nhận `PATCH` và `DELETE` cho origin hợp lệ; xác minh `alembic upgrade head` backfill an toàn cho tài khoản hiện có (mỗi user cũ nhận 1 default org chứa lại dữ liệu `/me/*` cũ của họ).
- **Frontend tests (`frontend/src/`):** Test `AccountPage` (form đăng ký + verify OTP không lỗi, đổi mật khẩu/email, xóa tài khoản) và `OrganizationPage` (ẩn nút quản trị thành viên với `viewer`/`analyst`).

---

## 7. Boundaries

- **Always:**
  - Chạy đủ `ruff check .`, `mypy src/finhealth`, `pytest -v` và `npm --prefix frontend run typecheck && npm --prefix frontend test && npm --prefix frontend run build` trước khi hoàn tất triển khai.
  - Hash mọi mã OTP, session token, CSRF token và mã mời tổ chức trước khi lưu DB; dùng so sánh thời gian hằng số (`secrets.compare_digest`).
  - Bảo đảm mọi truy vấn dữ liệu riêng tư đều lọc theo `organization_id == ctx.organization.id` phía server.
  - Bảo đảm migration `0008` tương thích cả SQLite, PostgreSQL và SQL Server (chú ý quy tắc cascade duy nhất của MSSQL).
- **Ask first:**
  - Thay đổi thời hạn mặc định của phiên đăng nhập, OTP hoặc mã mời tổ chức.
  - Thêm bất kỳ thư viện ngoài mới nào vào `pyproject.toml` hoặc `frontend/package.json`.
  - Thay đổi cấu trúc bảng `users` làm phá vỡ tương thích ngược với snapshot seed hiện tại.
- **Never:**
  - Không bao giờ tin `organization_id` hoặc `role` gửi từ client payload/query để quyết định quyền mà không xác minh trong `organization_members`.
  - Không bao giờ ghi mật khẩu, hash mật khẩu, mã OTP, token mời, hoặc số liệu BCTC vào log hay bảng `admin_audit_logs` / `organization_audit_logs`.
  - Không triển khai Google OAuth trong bản V1.0 (đã đưa vào Deferred V2.0+).
  - Không cấp quyền cho System `admin` đọc lén dữ liệu BCTC riêng tư của tổ chức khách hàng qua `/api/v1/admin/*`.

---

## 8. Success Criteria

1. Người dùng mới hoàn tất luồng **Đăng ký → Xác thực OTP → Đăng nhập** trên UI React thật (không còn lỗi 422 ở `/auth/verify-email`) và tự động sở hữu Workspace mặc định với vai trò `org_admin`.
2. Trên cùng một Workspace Tổ chức: `org_admin` mời được đồng nghiệp qua email, phân quyền `analyst` / `viewer`, cả nhóm nhìn thấy chung danh mục Watchlist, Saved Screeners và Saved Analyses; `viewer` bị chặn 100% thao tác ghi (`403`); thành viên khác tổ chức bị cô lập tuyệt đối (`403`/`404`).
3. Luồng **Đổi mật khẩu (OTP)**, **Đổi email (OTP)**, **Xuất dữ liệu cá nhân (JSON)** và **Xóa tài khoản & dữ liệu (OTP)** hoạt động đầy đủ từ UI đến DB; sau khi xóa tài khoản, toàn bộ phiên cũ trả `401` và không còn email/dữ liệu riêng sót lại trong các bảng dữ liệu cá nhân.
4. Preflight CORS cho phép `GET, POST, PATCH, DELETE, OPTIONS` trên origin cấu hình hợp lệ; toàn bộ migration `alembic upgrade head` chạy sạch trên SQLite và không làm mất dữ liệu workspace hiện có.
5. `ruff check .`, `mypy src/finhealth`, `pytest -v`, `frontend` typecheck/test/build đều xanh 100%.

---

## 9. Out of Scope (Deferred)

- **Đăng nhập Google OAuth / SSO SAML (M01 mở rộng):** Trì hoãn sang V2.0+ vì Email công việc + Argon2id + OTP đã đáp ứng đầy đủ bảo mật B2B.
- **Xác thực 2 lớp bằng ứng dụng TOTP (Google Authenticator):** Trì hoãn sang V1.1/V2.0.
- **Phân quyền chi tiết cấp thư mục/từng doanh nghiệp con (ABAC):** V1.0 dừng ở 3 vai trò cấp tổ chức (`org_admin`, `analyst`, `viewer`) để giữ đơn giản và dễ kiểm toán.
- **Tích hợp thanh toán / gói cước theo số lượng ghế (Billing / Seats):** Chưa nằm trong phạm vi kỹ thuật V1.0 (chỉ đặt giới hạn cứng mặc định chống lạm dụng, ví dụ tối đa 50 thành viên/tổ chức, tối đa 5 tổ chức do 1 user tạo).

---

## 10. Quyết định Đã Chốt (Resolved Defaults for Implementation)

1. **Giới hạn chống lạm dụng V1.0:** Tối đa **50 thành viên/tổ chức**, tối đa **5 tổ chức do 1 tài khoản tạo**, mã mời hết hạn sau **72 giờ** (cấu hình được qua hằng số `core/constants.py`).
2. **Xóa tài khoản & `admin_audit_logs` (Luật 91/2025/QH15):** Chọn **Phương án A** — migration `0008` chuyển `admin_audit_logs.actor_id` sang `nullable=True` với `ON DELETE SET NULL` (tương thích SQLite/PostgreSQL/SQL Server) để xóa cứng hoàn toàn bản ghi `users` (0% PII tồn dư) mà vẫn bảo toàn tính append-only của nhật ký kiểm toán hệ thống.
3. **Thứ tự triển khai:** Thực thi song song theo từng đợt (Wave) định nghĩa trong `tasks/plan.md` và `tasks/todo.md`.
