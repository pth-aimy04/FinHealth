/** Optional sign-in and private workspace. Never gate the public financial dashboard. */
import { escapeHtml as esc } from "./charts.js";

let user = null;
let pending = null;
let initialized = false;
const $ = (id) => document.getElementById(id);
const cookie = () => decodeURIComponent(document.cookie.split("; ")
  .find((row) => row.startsWith("finhealth_csrf="))?.split("=")[1] ?? "");

export async function accountRequest(path, method = "GET", payload) {
  const response = await fetch(`/api/v1${path}`, {
    method, credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie() },
    ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) updateUser(null);
    const message = typeof data.detail === "string" ? data.detail
      : response.status === 422 ? "Kiểm tra dữ liệu. Mật khẩu mới cần ít nhất 12 ký tự."
      : `Không hoàn thành yêu cầu (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function updateUser(value) {
  user = value;
  if ($("account-open")) {
    $("account-open").textContent = user ? (user.display_name || user.email).trim().slice(0, 1).toUpperCase() : "Đăng nhập";
    $("account-open").classList.toggle("account-avatar", !!user);
    $("account-open").setAttribute("aria-label", user ? "Mở menu tài khoản" : "Đăng nhập");
    $("account-open").setAttribute("aria-expanded", "false");
    $("account-menu").hidden = true;
    $("account-register").hidden = !!user;
    $("account-menu-name").textContent = user?.display_name || "";
    $("account-menu-email").textContent = user?.email || "";
    $("account-menu-admin").hidden = user?.role !== "admin";
  }
  for (const element of document.querySelectorAll("[data-admin-only]")) {
    element.hidden = user?.role !== "admin";
  }
  if (user?.role !== "admin" && $("preview-admin-workspace")) {
    const content = $("account-content");
    const message = $("account-message");
    if (content?.parentElement === $("preview-admin-workspace")) {
      $("account-dialog").append(content, message);
      content.replaceChildren();
      message.textContent = "";
    }
    $("preview-admin-workspace").replaceChildren();
    if (location.hash === "#admin") location.hash = "screener";
  }
  window.dispatchEvent(new CustomEvent("finhealth:identity", { detail: user }));
}

export function currentUser() { return user; }

function showDialog(title, html) {
  const administrative = title.startsWith("Quản trị —") && !!$("preview-admin-workspace");
  const dialog = $("account-dialog");
  dialog.classList.remove("auth-dialog");
  const host = administrative ? $("preview-admin-workspace") : dialog;
  if (administrative) host.replaceChildren($("account-content"), $("account-message"));
  else host.append($("account-content"), $("account-message"));
  $("account-title").textContent = title;
  $("account-content").innerHTML = html;
  $("account-message").textContent = "";
  if (administrative) {
    dialog.close();
    if (location.hash !== "#admin") location.hash = "admin";
  } else if (!dialog.open) dialog.showModal();
}

function field(label, name, type = "text", required = true) {
  const password = type === "password";
  return `<label>${esc(label)}<input name="${name}" type="${type}" ${required ? "required" : ""}
    ${password ? 'maxlength="128"' : 'maxlength="254"'}
    autocomplete="${password ? (name === "current_password" || name === "password" ? "current-password" : "new-password") : name === "email" ? "email" : "off"}"></label>`;
}

function form(html, submit) {
  return `<form id="account-form" class="account-form">${html}<button type="submit">${submit}</button></form>`;
}

function bindForm(handler) {
  $("account-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.target.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await handler(Object.fromEntries(new FormData(event.target)));
    } catch (error) {
      $("account-message").textContent = error.message;
    } finally { button.disabled = false; }
  });
}

function matchingPassword(data, key) {
  if ((data[key] ?? "").length < 12) throw new Error("Mật khẩu cần ít nhất 12 ký tự.");
  if (data[key] !== data.confirm) throw new Error("Hai mật khẩu chưa khớp.");
  delete data.confirm;
}

export async function ensureUser(action) {
  try {
    updateUser(await accountRequest("/auth/me"));
    await action();
  } catch (error) {
    if (error.status !== 401) throw error;
    pending = action;
    openAuth("login");
  }
}

function openAuth(mode = "login") {
  const register = mode === "register", emailOnly = ["forgot-password", "resend-verification"].includes(mode);
  const fields = (register ? field("Họ và tên", "display_name") : "") + field("Email", "email", "email") +
    (!emailOnly ? field("Mật khẩu", "password", "password") : "") +
    (register ? field("Nhập lại mật khẩu", "confirm", "password") : "");
  const links = register
    ? '<span>Đã có tài khoản? <button type="button" data-auth="login">Đăng nhập</button></span>'
    : emailOnly
      ? '<span><button type="button" data-auth="login">Quay lại đăng nhập</button></span>'
      : '<span>Bạn chưa có tài khoản? <button type="button" data-auth="register">Đăng ký</button></span>' +
        '<span><button type="button" data-auth="forgot-password">Quên mật khẩu?</button></span>' +
        '<span><button type="button" data-auth="resend-verification">Gửi lại mã xác thực</button></span>';
  showDialog(register ? "Đăng ký tài khoản" : emailOnly ? "Khôi phục / xác thực tài khoản" : "Đăng nhập hệ thống",
    '<div class="auth-brand"><img src="/static/finhealth-logo.svg" alt=""><strong>FinHealth<span>.</span></strong></div>' +
    (emailOnly ? '<p>Nhập email để nhận mã xác thực.</p>' : "") +
    form(fields, emailOnly ? "Gửi mã OTP" : register ? "Đăng ký" : "Đăng nhập") +
    `<div class="auth-links">${links}</div>` +
    (register ? '<p class="auth-note">Sau khi đăng ký, nhập mã OTP được gửi đến email để xác thực tài khoản.</p>' : ""));
  $("account-dialog").classList.add("auth-dialog");
  for (const button of document.querySelectorAll("[data-auth]")) button.onclick = () => openAuth(button.dataset.auth);
  bindForm(async (data) => {
    if (register) matchingPassword(data, "password");
    const result = await accountRequest(`/auth/${mode}`, "POST", data);
    if (register || mode === "resend-verification") {
      openOtp(data.email, result.challenge, register ? data.password : null);
      return;
    }
    if (mode === "forgot-password") {
      openActionOtp("reset", data.email, result.challenge, null, () => accountRequest("/auth/forgot-password", "POST", data));
      return;
    }
    if (mode !== "login") {
      $("account-message").textContent = result.message + " Kiểm tra hộp thư và mục thư rác.";
      $("account-form").reset();
      return;
    }
    updateUser(result);
    $("account-dialog").close();
    const continuation = pending;
    pending = null;
    if (continuation) await continuation();
  });
}

function openOtp(email, initialChallenge, registrationPassword) {
  let challenge = initialChallenge;
  showDialog("Xác thực email bằng OTP", `<p>Mã gồm 6 chữ số đã được gửi tới <strong>${esc(email)}</strong> nếu tài khoản đủ điều kiện.</p>
    <p>Đọc email trên điện thoại rồi nhập mã tại đây. Không cần mở localhost trên điện thoại.
    Mã có hiệu lực 10 phút, tối đa 5 lần nhập sai. Gửi lại sẽ thay thế mã cũ.</p>` +
    form(`<label>Mã OTP<input name="code" type="text" inputmode="numeric" autocomplete="one-time-code"
      pattern="[0-9]{6}" minlength="6" maxlength="6" required autofocus></label>` +
      (!registrationPassword ? field("Mật khẩu bạn muốn dùng (ít nhất 12 ký tự)", "new_password", "password") +
       field("Nhập lại mật khẩu", "confirm", "password") : ""), "Xác thực đăng ký") +
    '<div class="account-actions"><button id="otp-resend" type="button">Gửi lại mã OTP</button><button id="otp-back" type="button">Đổi email / Đăng ký lại</button></div>');
  let resendAt = Date.now() + 60 * 1000;
  $("otp-resend").onclick = async () => {
    if (Date.now() < resendAt) {
      $("account-message").textContent = `Vui lòng đợi ${Math.ceil((resendAt - Date.now()) / 1000)} giây trước khi gửi lại.`;
      return;
    }
    const button = $("otp-resend");
    button.disabled = true;
    try {
      const result = await accountRequest("/auth/resend-verification", "POST", { email });
      challenge = result.challenge;
      resendAt = Date.now() + 60 * 1000;
      $("account-form").elements.code.value = "";
      $("account-message").textContent = "Đã yêu cầu gửi mã mới. Nhập mã trong email mới nhất.";
    } catch (error) { showError(error); }
    finally { button.disabled = false; }
  };
  $("otp-back").onclick = () => openAuth("register");
  bindForm(async (data) => {
    if (!registrationPassword) matchingPassword(data, "new_password");
    const result = await accountRequest("/auth/verify-email", "POST", {
      email, challenge, code: data.code.trim(), new_password: registrationPassword ?? data.new_password,
    });
    registrationPassword = null;
    openAuth("login");
    $("account-form").elements.email.value = email;
    $("account-message").textContent = result.message;
  });
}

function openActionOtp(purpose, email, initialChallenge, selectedPassword, resend) {
  let challenge = initialChallenge;
  let resendAt = Date.now() + 60000;
  const title = {reset: "Đặt lại mật khẩu", "change-password": "Đổi mật khẩu", "change-email": "Đổi email"}[purpose];
  const endpoint = {reset: "reset-password", "change-password": "confirm-password-change", "change-email": "confirm-email"}[purpose];
  showDialog(`${title} — Xác nhận OTP`, `<p>Kiểm tra mã 6 chữ số trong email <strong>${esc(email)}</strong> rồi nhập tại đây. Mã có hạn 10 phút, tối đa 5 lần nhập sai. Không cần mở liên kết trên điện thoại.</p>` +
    form('<label>Mã OTP<input name="code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required></label>' +
      (purpose === "reset" ? field("Mật khẩu mới", "new_password", "password") + field("Nhập lại mật khẩu", "confirm", "password") : ""), "Xác nhận OTP") +
    '<button id="action-resend" type="button">Gửi lại mã OTP</button>');
  $("action-resend").onclick = async () => {
    if (Date.now() < resendAt) {
      $("account-message").textContent = `Vui lòng đợi ${Math.ceil((resendAt - Date.now()) / 1000)} giây.`;
      return;
    }
    const button = $("action-resend"); button.disabled = true;
    try {
      const result = await resend(); challenge = result.challenge; resendAt = Date.now() + 60000;
      $("account-form").elements.code.value = "";
      $("account-message").textContent = "Đã yêu cầu gửi mã mới. Mã trước không còn dùng được.";
    } catch (error) { showError(error); }
    finally { button.disabled = false; }
  };
  bindForm(async (data) => {
    if (purpose === "reset") matchingPassword(data, "new_password");
    const payload = {email, challenge, code: data.code.trim()};
    if (purpose !== "change-email") payload.new_password = selectedPassword ?? data.new_password;
    const result = await accountRequest(`/auth/${endpoint}`, "POST", payload);
    selectedPassword = null;
    updateUser(null); openAuth("login");
    $("account-form").elements.email.value = email;
    $("account-message").textContent = result.message;
  });
}

function accountHome() {
  showDialog("Tài khoản của tôi", `<p>${esc(user.email)}</p><div class="account-actions">
    <button id="private-lists">Danh sách và kết quả đã lưu</button><button id="profile-edit">Sửa tên hiển thị</button>
    <button id="password-edit">Đổi mật khẩu</button><button id="email-edit">Đổi email</button>
    ${user.role === "admin" ? '<button id="admin-open">Quản trị hệ thống</button>' : ""}
    <button id="logout">Đăng xuất</button></div>`);
  $("private-lists").onclick = () => privateLists().catch(showError);
  $("profile-edit").onclick = () => {
    showDialog("Tên hiển thị", form(field("Tên mới", "display_name"), "Lưu"));
    $("account-form").elements.display_name.value = user.display_name;
    bindForm(async (data) => { updateUser(await accountRequest("/auth/profile", "PATCH", data)); accountHome(); });
  };
  $("password-edit").onclick = () => {
    showDialog("Đổi mật khẩu", form(field("Mật khẩu hiện tại", "current_password", "password") +
      field("Mật khẩu mới (ít nhất 12 ký tự)", "new_password", "password") +
      field("Nhập lại mật khẩu mới", "confirm", "password"), "Đổi mật khẩu"));
    bindForm(async (data) => {
      matchingPassword(data, "new_password");
      const result = await accountRequest("/auth/change-password", "POST", data);
      openActionOtp("change-password", user.email, result.challenge, data.new_password,
        () => accountRequest("/auth/change-password", "POST", data));
    });
  };
  $("email-edit").onclick = () => {
    showDialog("Đổi email", form(field("Email mới", "email", "email") +
      field("Mật khẩu hiện tại", "current_password", "password"), "Gửi xác thực email mới"));
    bindForm(async (data) => {
      const result = await accountRequest("/auth/change-email", "POST", data);
      openActionOtp("change-email", data.email, result.challenge, null,
        () => accountRequest("/auth/change-email", "POST", data));
    });
  };
  if ($("admin-open")) $("admin-open").onclick = () => adminHome().catch(showError);
  $("logout").onclick = confirmLogout;
}

function showError(error) { $("account-message").textContent = error.message; }

function confirmLogout() {
  showDialog("Đăng xuất", `<div class="logout-confirm"><p>Bạn có muốn đăng xuất khỏi FinHealth không?</p>
    <div class="logout-actions"><button id="logout-cancel" type="button">Hủy</button>
    <button id="logout-confirm" type="button">Đăng xuất</button></div></div>`);
  $("logout-cancel").onclick = () => $("account-dialog").close();
  $("logout-confirm").onclick = async () => {
    const button = $("logout-confirm");
    button.disabled = true;
    try { await accountRequest("/auth/logout", "POST"); updateUser(null); $("account-dialog").close(); }
    catch (error) { showError(error); }
    finally { button.disabled = false; }
  };
}

async function privateLists() {
  const [watch, filters, analyses] = await Promise.all([
    accountRequest("/me/watchlist"), accountRequest("/me/screeners"), accountRequest("/me/analyses"),
  ]);
  const rows = (items, type, title, empty) => `<section class="saved-group"><div class="saved-group-heading"><h3>${title}</h3><span>${items.length}</span></div>${items.length ? items.map((item) =>
    `<div class="account-list-row"><button class="saved-open" data-open="${type}" data-id="${item.id}">${esc(item.name ?? item.ticker ?? item.cik)}</button>
    <button class="saved-delete" data-delete="${type}" data-id="${item.id}" aria-label="Xóa ${esc(item.name ?? item.ticker ?? item.cik)}">Xóa</button></div>`).join("") : `<p class="saved-empty">${empty}</p>`}</section>`;
  showDialog("Dữ liệu đã lưu", `<p class="saved-intro">Truy cập nhanh các doanh nghiệp, bộ lọc và kết quả bạn đã lưu.</p><div class="saved-groups">` +
    rows(watch, "watchlist", "Doanh nghiệp theo dõi", "Bạn chưa theo dõi doanh nghiệp nào.") +
    rows(filters, "screeners", "Bộ lọc đã lưu", "Bạn chưa lưu bộ lọc nào.") +
    rows(analyses, "analyses", "Kết quả phân tích", "Bạn chưa lưu kết quả phân tích nào.") + "</div>");
  for (const button of document.querySelectorAll("[data-delete]")) button.onclick = async () => {
    try { await accountRequest(`/me/${button.dataset.delete}/${button.dataset.id}`, "DELETE"); await privateLists(); }
    catch (error) { showError(error); }
  };
  for (const button of document.querySelectorAll("[data-open]")) button.onclick = async () => {
    try {
      const id = Number(button.dataset.id), type = button.dataset.open;
      if (type === "analyses") {
        const item = await accountRequest(`/me/analyses/${id}`);
        showDialog(item.name, '<p>Kết quả được lưu tại thời điểm phân tích, kèm phiên bản mô hình.</p><pre id="saved-output"></pre>');
        $("saved-output").textContent = JSON.stringify(item, null, 2);
      } else {
        window.dispatchEvent(new CustomEvent(type === "watchlist" ? "finhealth:open-company" : "finhealth:apply-screener",
          { detail: (type === "watchlist" ? watch : filters).find((row) => row.id === id) }));
        $("account-dialog").close();
      }
    } catch (error) { showError(error); }
  };
}

const ADMIN_STATES = {
  queued: "Đang chờ", running: "Đang xử lý", processing: "Đang xử lý",
  succeeded: "Hoàn tất", failed: "Thất bại",
};

function adminState(value) {
  return ADMIN_STATES[value] ?? value ?? "Chưa có thông tin";
}

function adminDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString("vi-VN");
}

function requesterLabel(job) {
  if (job.requested_by == null) return '<span class="admin-requester-missing">Không có thông tin</span>';
  const name = String(job.requested_by_name ?? "").trim();
  const email = String(job.requested_by_email ?? "").trim();
  if (!name && !email) return `<span class="admin-requester-missing">Tài khoản #${esc(job.requested_by)}</span>`;
  return `<span class="admin-requester"><strong>${esc(name || email)}</strong>${name && email ? `<small>${esc(email)}</small>` : ""}<small>ID #${esc(job.requested_by)}</small></span>`;
}

async function adminHome(pages = { jobs: 0, users: 0, audit: 0 }) {
  const results = await Promise.allSettled([
    accountRequest("/admin/overview"), accountRequest(`/admin/ingestion?offset=${pages.jobs}&limit=51`),
    accountRequest(`/admin/users?offset=${pages.users}&limit=51`),
    accountRequest(`/admin/audit?offset=${pages.audit}&limit=51`),
  ]);
  if (user?.role !== "admin") return;
  if (results[0].status === "rejected") throw results[0].reason;
  const overview = results[0].value;
  const loadList = (result) => result.status === "fulfilled"
    ? { rows: result.value.slice(0, 50), next: result.value.length > 50, error: null }
    : { rows: [], next: false, error: result.reason.message };
  const jobList = loadList(results[1]), userList = loadList(results[2]), auditList = loadList(results[3]);
  const jobs = jobList.rows, users = userList.rows, audit = auditList.rows;
  const listMessage = (list, empty) => `<p class="${list.error ? "admin-list-error" : "admin-empty"}" role="status">${esc(list.error ? `Không tải được dữ liệu: ${list.error}` : empty)}</p>`;
  const pager = (key, list) => `<div class="admin-pagination"><span>Trang ${Math.floor(pages[key] / 50) + 1}</span><div>
    <button type="button" class="admin-button" data-page="${key}" data-direction="prev" ${pages[key] === 0 ? "disabled" : ""}>Trang trước</button>
    <button type="button" class="admin-button" data-page="${key}" data-direction="next" ${!list.next ? "disabled" : ""}>Trang sau</button></div></div>`;
  showDialog("Quản trị — Cập nhật SQL Server", `<div class="admin-topline"><div><h2>Tình trạng vận hành</h2>
    <p>Theo dõi các yêu cầu cập nhật và tình trạng hệ thống.</p></div><button type="button" id="admin-refresh" class="admin-button">Làm mới</button></div>
    <div class="admin-status-line"><span>Cơ sở dữ liệu: <strong>Đã kết nối</strong></span>
    <span>Bộ xử lý: <strong>${overview.worker_enabled ? "Đang bật" : "Đang tắt"}</strong></span>
    <span>Email: <strong>${overview.email_configured ? "Đã cấu hình" : "Chưa cấu hình"}</strong></span>
    <span>Cập nhật thành công gần nhất: <strong>${esc(overview.last_success ? adminDate(overview.last_success) : "Chưa có")}</strong></span></div>
    <div class="admin-summary"><div><span>Đang chờ</span><strong>${overview.counts.queued ?? 0}</strong></div>
    <div><span>Đang xử lý</span><strong>${overview.counts.running ?? 0}</strong></div>
    <div><span>Thất bại</span><strong>${overview.counts.failed ?? 0}</strong></div></div>
    <section class="admin-section admin-update"><div class="admin-section-heading"><div><h3>Yêu cầu cập nhật</h3>
    <p>Nhập mã chứng khoán hoặc CIK; các mã cách nhau bằng dấu phẩy, tối đa 10 mã.</p></div></div>
    ${form(field("Mã doanh nghiệp", "identifiers"), "Gửi yêu cầu cập nhật")}
    <div id="admin-notice"></div></section>
    <section class="admin-section"><div class="admin-section-heading"><div><h3>Lịch sử cập nhật</h3>
    <p>Chọn Xem để xem thông tin và các bước xử lý của từng yêu cầu.</p></div></div>
    <div class="table-scroll"><table class="data-table admin-job-table"><thead><tr><th>Mã</th><th>Doanh nghiệp</th><th>Trạng thái</th><th>Người yêu cầu</th><th>Thời gian yêu cầu</th><th>Kết thúc</th><th>Thao tác</th></tr></thead><tbody>
    ${jobs.map((job) => `<tr data-job-row="${esc(job.id)}"><td>#${esc(job.id)}</td><td><strong>${esc(job.identifier)}</strong></td><td><span class="admin-job-status ${["queued", "running", "succeeded", "failed"].includes(job.status) ? job.status : "unknown"}">${esc(adminState(job.status))}</span></td>
    <td>${requesterLabel(job)}</td><td>${esc(adminDate(job.requested_at))}</td><td>${esc(adminDate(job.finished_at))}</td>
    <td><div class="admin-row-actions"><button type="button" class="admin-button" data-events="${esc(job.id)}" aria-expanded="false">Xem</button>${job.status === "failed" ? `<button type="button" class="admin-button" data-retry="${esc(job.id)}">Chạy lại</button>` : ""}</div></td></tr>`).join("") || `<tr><td colspan="7">${listMessage(jobList, "Chưa có tác vụ cập nhật ở trang này.")}</td></tr>`}
    </tbody></table></div>${pager("jobs", jobList)}</section>
    <section class="admin-section" id="admin-users-section"><div class="admin-section-heading"><div><h3>Quản lý tài khoản</h3><p>Danh sách tài khoản và trạng thái hoạt động.</p></div></div><p id="admin-user-message" class="admin-user-message" role="status" aria-live="polite"></p>
    ${users.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${users.map((item) => `<tr><td>${esc(item.email)}</td><td>${item.role === "admin" ? "Quản trị viên" : "Người dùng"}</td><td>${item.active ? "Hoạt động" : "Đã khóa"}</td><td>
      ${item.role !== "admin" ? `<button type="button" class="admin-button" data-user="${esc(item.id)}" data-active="${!item.active}">${item.active ? "Khóa" : "Mở khóa"}</button>` : "—"}</td></tr>`).join("")}</tbody></table></div>` : listMessage(userList, "Không có tài khoản ở trang này.")}${pager("users", userList)}</section>
    <section class="admin-section" id="admin-audit-section"><div class="admin-section-heading"><div><h3>Nhật ký quản trị</h3><p>Các thao tác vận hành đã được ghi nhận.</p></div></div>
    ${audit.length ? `<div class="table-scroll"><table class="data-table"><thead><tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Đối tượng</th><th>Kết quả</th></tr></thead><tbody>${audit.map((row) => `<tr><td>${esc(adminDate(row.created_at))}</td><td>#${esc(row.actor_id)}</td><td>${esc(row.action)}</td><td>${esc(row.target)}</td><td>${esc(row.outcome)}</td></tr>`).join("")}</tbody></table></div>` : listMessage(auditList, "Chưa có nhật ký ở trang này.")}${pager("audit", auditList)}</section>`);
  $("admin-notice").append($("account-message"));
  $("admin-refresh").onclick = () => adminHome(pages).catch(showError);
  for (const button of document.querySelectorAll("[data-page]")) button.onclick = () => {
    const key = button.dataset.page;
    const next = Math.max(0, pages[key] + (button.dataset.direction === "next" ? 50 : -50));
    adminHome({ ...pages, [key]: next }).catch(showError);
  };
  bindForm(async (data) => {
    const identifiers = [...new Set(data.identifiers.split(",").map((v) => v.trim()).filter(Boolean))];
    if (!identifiers.length || identifiers.length > 10) throw new Error("Nhập từ 1 đến 10 mã.");
    const results = await Promise.allSettled(identifiers.map((id) => accountRequest(`/ingestion/${encodeURIComponent(id)}`, "POST")));
    await adminHome(pages);
    $("account-message").textContent = results.map((result, i) => `${identifiers[i]}: ${result.status === "fulfilled" ? "đã xếp hàng" : result.reason.message}`).join("; ");
  });
  for (const button of document.querySelectorAll("[data-events]")) button.onclick = async () => {
    const row = button.closest("tr");
    const existing = row.nextElementSibling;
    if (existing?.classList.contains("admin-event-row")) {
      existing.remove();
      button.setAttribute("aria-expanded", "false");
      button.textContent = "Xem";
      return;
    }
    document.querySelectorAll(".admin-event-row").forEach((item) => item.remove());
    document.querySelectorAll("[data-events]").forEach((item) => { item.setAttribute("aria-expanded", "false"); item.textContent = "Xem"; });
    const job = jobs.find((item) => String(item.id) === button.dataset.events);
    const detail = document.createElement("tr");
    detail.className = "admin-event-row";
    detail.innerHTML = `<td colspan="7"><div class="admin-event-panel" role="status" aria-live="polite"><strong>Đang tải chi tiết yêu cầu #${esc(job.id)}…</strong></div></td>`;
    row.after(detail);
    button.setAttribute("aria-expanded", "true");
    button.textContent = "Đóng";
    try {
      const events = await accountRequest(`/admin/ingestion/${encodeURIComponent(button.dataset.events)}/events`);
      if (!detail.isConnected) return;
      const timeline = events.length ? `<ol class="admin-timeline">${events.map((event) =>
        `<li><strong>${esc(adminState(event.stage))}</strong><span>${esc(adminDate(event.created_at))}</span><p>${esc(event.message || "Không có mô tả.")}</p></li>`).join("")}</ol>`
        : '<p class="admin-empty">Chưa có sự kiện xử lý được ghi lại cho yêu cầu này.</p>';
      detail.querySelector(".admin-event-panel").innerHTML = `<div class="admin-event-title"><strong>Chi tiết yêu cầu #${esc(job.id)} · ${esc(job.identifier)}</strong><span>${esc(adminState(job.status))}</span></div>
        <div class="admin-event-meta"><span>Số lần thử: ${esc(job.attempts ?? 0)}</span><span>Bắt đầu: ${esc(adminDate(job.started_at))}</span>
        ${job.retry_of != null ? `<span>Chạy lại từ yêu cầu #${esc(job.retry_of)}</span>` : ""}</div>
        ${job.error_code ? `<p class="admin-event-error">Thông tin lỗi: ${esc(job.error_code)}</p>` : ""}${timeline}`;
    } catch (error) {
      if (detail.isConnected) detail.querySelector(".admin-event-panel").textContent = `Không tải được chi tiết: ${error.message}`;
    }
  };
  for (const button of document.querySelectorAll("[data-retry]")) button.onclick = async () => {
    try { await accountRequest(`/ingestion/${button.dataset.retry}/retry`, "POST"); await adminHome(pages); }
    catch (error) { showError(error); }
  };
  for (const button of document.querySelectorAll("[data-user]")) button.onclick = async () => {
    button.disabled = true;
    try {
      const active = button.dataset.active === "true";
      await accountRequest(`/admin/users/${button.dataset.user}`, "PATCH", { active });
      await adminHome(pages);
      if ($("admin-user-message")) {
        $("admin-user-message").classList.add("is-success");
        $("admin-user-message").textContent = active ? "Đã mở khóa tài khoản." : "Đã khóa tài khoản.";
      }
    } catch (error) {
      if ($("admin-user-message")) $("admin-user-message").textContent = `Không cập nhật được tài khoản: ${error.message}`;
      else showError(error);
    } finally { button.disabled = false; }
  };
}

export async function savePersonal(kind, payload) {
  await ensureUser(async () => {
    await accountRequest(`/me/${kind}`, "POST", payload);
    showDialog("Đã lưu", "<p>Bạn có thể xem lại trong Không gian cá nhân.</p>");
  });
}

export async function bindAccount() {
  if (initialized) return;
  const showAdministration = async (refresh = false) => {
    if (user?.role !== "admin") return;
    if (!refresh && $("account-content")?.parentElement === $("preview-admin-workspace")) return;
    try { await adminHome(); }
    catch (error) {
      if ($("account-content")?.parentElement === $("preview-admin-workspace")) showError(error);
      else $("preview-admin-workspace").textContent = error.message;
    }
  };
  window.addEventListener("finhealth:open-admin", () => showAdministration());
  $("preview-admin-load")?.addEventListener("click", () => ensureUser(() => showAdministration(true)).catch(showError));
  initialized = true;
  try { sessionStorage.removeItem("finhealth_admin_token"); }
  catch { /* Storage may be disabled; authentication uses cookies exclusively. */ }
  document.body.insertAdjacentHTML("beforeend", `<dialog id="account-dialog" class="account-dialog" aria-labelledby="account-title">
    <header class="account-dialog-header"><h2 id="account-title"></h2><button id="account-close" aria-label="Đóng">Đóng</button></header>
    <div id="account-content"></div><p id="account-message" role="status" aria-live="polite"></p></dialog>`);
  $("account-close").onclick = () => { pending = null; $("account-dialog").close(); };
  $("account-dialog").addEventListener("cancel", () => { pending = null; });
  $("account-dialog").addEventListener("close", () => {
    if (location.hash === "#admin") showAdministration();
  });
  const host = document.querySelector(".system-status") ?? $("account-page");
  host.insertAdjacentHTML("beforeend", `<div class="account-controls">
    <button id="account-open" type="button" aria-expanded="false" aria-controls="account-menu">Đăng nhập</button>
    <button id="account-register" type="button">Tạo tài khoản</button>
    <div id="account-menu" class="account-menu" hidden>
      <div class="account-menu-profile"><strong id="account-menu-name"></strong><span id="account-menu-email"></span></div>
      <button id="personal-open" type="button">Dữ liệu đã lưu<span>Doanh nghiệp, bộ lọc và kết quả phân tích</span></button>
      <button id="account-settings" type="button">Chỉnh sửa tên hiển thị</button>
      <button id="account-password" type="button">Đổi mật khẩu</button>
      <button id="account-email" type="button">Đổi email</button>
      <button id="account-menu-admin" type="button" hidden>Quản trị hệ thống<span>Cập nhật dữ liệu và tài khoản</span></button>
      <button id="account-menu-logout" type="button">Đăng xuất</button>
    </div></div>`);
  const closeMenu = () => { $("account-menu").hidden = true; $("account-open").setAttribute("aria-expanded", "false"); };
  $("account-open").onclick = () => {
    if (!user) { openAuth(); return; }
    const open = $("account-menu").hidden;
    $("account-menu").hidden = !open;
    $("account-open").setAttribute("aria-expanded", String(open));
  };
  $("account-register").onclick = () => openAuth("register");
  $("personal-open").onclick = () => { closeMenu(); ensureUser(privateLists).catch(showError); };
  const openSetting = (id) => { closeMenu(); accountHome(); $(id).click(); };
  $("account-settings").onclick = () => openSetting("profile-edit");
  $("account-password").onclick = () => openSetting("password-edit");
  $("account-email").onclick = () => openSetting("email-edit");
  $("account-menu-admin").onclick = () => { closeMenu(); adminHome().catch(showError); };
  $("account-menu-logout").onclick = () => { closeMenu(); confirmLogout(); };
  document.addEventListener("click", (event) => { if (!event.target.closest(".account-controls")) closeMenu(); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("account-menu").hidden) { closeMenu(); $("account-open").focus(); }
  });
  try { updateUser(await accountRequest("/auth/me")); }
  catch (error) { if (error.status !== 401) console.warn("Không tải được trạng thái tài khoản."); }
  if ($("account-page")) {
    history.replaceState(null, "", location.pathname);
    showDialog("Xác thực bằng OTP", "<p>FinHealth hiện dùng mã OTP cho mọi yêu cầu xác thực. Trở về ứng dụng, chọn đăng ký, quên mật khẩu hoặc đổi email để nhận mã mới.</p><a href='/'>Trở về FinHealth</a>");
  }
}
