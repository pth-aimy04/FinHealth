/** DOM regression checks. Requires jsdom/esbuild in .venv/ui-tools and a local API. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM, VirtualConsole } = require("../../.venv/ui-tools/node_modules/jsdom");
const { buildSync } = require("../../.venv/ui-tools/node_modules/esbuild");
const root = path.resolve(__dirname, "../..");
const origin = process.env.FINHEALTH_PREVIEW_ORIGIN || "http://127.0.0.1:8000";
const primary = process.env.FINHEALTH_TEST_PRIMARY === "1";
const frontend = primary ? "frontend" : "frontend/preview";
const bundle = buildSync({
  entryPoints: [path.join(root, frontend, "js/app.js")],
  bundle: true, write: false, format: "iife", target: "es2022",
}).outputFiles[0].text;
const html = fs.readFileSync(path.join(root, frontend, "index.html"), "utf8");
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const reply = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json" },
});

/** Wait for observable asynchronous UI state with a bounded timeout. */
async function until(predicate, description) {
  const deadline = Date.now() + 30000;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error(`Timeout: ${description}`);
    await pause(30);
  }
}

/** Exercise the actual bundled controller in a DOM; mock authentication boundaries only. */
async function scenario(role) {
  const errors = [];
  let expired = false;
  let logoutCalls = 0;
  let signedInFixture = false;
  let downloads = 0;
  let manualPosts = 0;
  let requestCount = 0;
  const consoleBridge = new VirtualConsole();
  consoleBridge.on("jsdomError", (error) => errors.push(error.message));
  const dom = new JSDOM(html, {
    url: `${origin}${primary ? "/" : "/static/preview/index.html"}`,
    runScripts: "outside-only", pretendToBeVisual: true, virtualConsole: consoleBridge,
  });
  const w = dom.window;
  w.structuredClone = structuredClone;
  if (primary) {
    w.URL.createObjectURL = () => "blob:fixture";
    w.URL.revokeObjectURL = () => {};
    w.HTMLAnchorElement.prototype.click = function () { if (this.download) downloads++; };
  }
  w.matchMedia = () => ({ matches: false, addEventListener() {} });
  // jsdom does not implement native dialog APIs; keep actual controller/modal DOM intact.
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () {
    if (!this.open) return;
    this.open = false;
    setTimeout(() => this.dispatchEvent(new w.Event("close")), 0);
  };
  w.addEventListener("error", (event) => errors.push(event.message));
  w.fetch = async (input, options = {}) => {
    const url = new URL(input, origin);
    const endpoint = url.pathname.replace("/api/v1", "");
    const method = options.method || "GET";
    requestCount++;
    if (endpoint === "/auth/me") {
      return (role !== "guest" || signedInFixture) && !expired
        ? reply({ id: 999, email: "fixture@example.com", role: role === "guest" ? "user" : "admin", display_name: "Người dùng thử" })
        : reply({ detail: "Not authenticated" }, 401);
    }
    if (endpoint.startsWith("/admin/")) {
      if (expired) return reply({ detail: "Session expired" }, 401);
      if (primary && endpoint === "/admin/ingestion/123/events") return reply([
        { stage: "queued", message: '<img src=x onerror="alert(1)">', created_at: "2026-11-23T13:00:00Z" },
        { stage: "processing", message: "Đang xử lý dữ liệu", created_at: "2026-11-23T13:01:00Z" },
      ]);
      if (primary && endpoint === "/admin/ingestion/124/events") return reply([]);
      if (primary && endpoint === "/admin/ingestion/125/events") return reply({ detail: "Không thể tải lịch sử" }, 503);
      if (endpoint === "/admin/overview") return reply({
        worker_enabled: false, email_configured: false, last_success: null,
        counts: { queued: 2, running: 1, failed: 0 },
      });
      if (endpoint === "/admin/users") {
        if (role === "admin_list_error") return reply({ detail: "Không tải được tài khoản thử nghiệm" }, 503);
        return reply([{ id: 42, email: "account@example.com", role: "user", active: true }]);
      }
      if (endpoint === "/admin/audit") return reply([{ created_at: "2026-11-24T13:01:00Z", actor_id: 999, action: "ingestion.submit", target: "123", outcome: "success" }]);
      if (endpoint === "/admin/ingestion" && role === "admin_paging" && Number(url.searchParams.get("offset")) >= 50) {
        return reply([{ id: 456, identifier: "PAGE2", status: "queued", requested_at: "2026-11-23T13:00:00Z" }]);
      }
      if (endpoint === "/admin/ingestion") return reply([{
        id: 123, identifier: '<img src=x onerror="alert(1)">', status: "queued",
        requested_at: "2026-11-23T13:00:00Z", requested_by: 999,
        requested_by_name: '<img src=x onerror="alert(2)">', requested_by_email: "admin@example.com",
      }, ...(primary ? [
        { id: 124, identifier: "EMPTY", status: "succeeded", requested_at: "2026-11-23T13:00:00Z" },
        { id: 125, identifier: "FAIL", status: "failed", error_code: "FixtureError", requested_at: "2026-11-23T13:00:00Z" },
      ] : []), ...(role === "admin_paging" ? Array.from({ length: 48 }, (_, index) => ({
        id: 200 + index, identifier: `TEST${index}`, status: "queued", requested_at: "2026-11-23T13:00:00Z",
      })) : [])]);
      return reply([]);
    }
    if (endpoint === "/auth/register" && method === "POST") {
      return reply({ challenge: "fixture-challenge", message: "Nhập OTP" });
    }
    if (primary && endpoint === "/auth/login" && method === "POST") {
      signedInFixture = true;
      return reply({ id: 999, email: "fixture@example.com", role: "user", display_name: "Người dùng thử" });
    }
    if (primary && endpoint === "/models/predict-manual" && method === "POST") {
      manualPosts++;
      return reply({ detail: "Fixture model unavailable" }, 503);
    }
    if (primary && endpoint === "/auth/logout" && method === "POST") {
      logoutCalls++;
      expired = true;
      return new Response(null, { status: 204 });
    }
    if (primary && endpoint === "/me/watchlist") return reply([{ id: 12, name: "Apple", cik: "0000320193" }]);
    if (primary && endpoint === "/me/screeners") return reply([{ id: 13, name: "Theo dõi nợ", filters: {} }]);
    if (primary && endpoint === "/me/analyses") return reply([]);
    if (method !== "GET") throw new Error(`Mutation blocked by UI verification: ${method} ${endpoint}`);
    assert.equal(url.origin, origin);
    return fetch(url, options);
  };
  try {
    w.eval(bundle);
    const $ = (id) => w.document.getElementById(id);
    await until(() => $("company-overview").textContent.includes("Apple"), "real company analysis loaded")
      .catch((error) => { throw new Error(`${error.message}; notice: ${$("notice").textContent}; DOM errors: ${errors.join("; ")}`); });
    assert.ok(!$("notice").textContent.includes("Không khởi tạo"), $("notice").textContent);
    assert.ok(!$("notice").textContent.includes("Không tải"), $("notice").textContent);
    assert.ok($("screener-body").querySelectorAll("tr").length > 1);
    assert.equal($("account-dialog").open, false, "public browsing must not open login");
    for (const tab of ["company", "compare", "explain", "manual", "science", "screener"]) {
      $(`tab-${tab}`).click();
      assert.equal($(`panel-${tab}`).hidden, false);
      assert.equal($(`tab-${tab}`).getAttribute("aria-selected"), "true");
    }
    $("tab-manual").click();
    const objectives = [...$("manual-model-version").options];
    assert.deepEqual(objectives.map((option) => option.textContent), [
      "Cảnh báo sớm khó khăn tài chính", "Dự báo nguy cơ phá sản",
    ]);
    assert.equal(objectives[0].value, "v1.2.0");
    assert.equal(objectives[1].value, "kaggle-v1.2.0");
    if (primary) {
      const evaluationOptions = [...$("science-model-select").options];
      assert.deepEqual(evaluationOptions.map((option) => option.textContent), objectives.map((option) => option.textContent));
      assert.deepEqual(evaluationOptions.map((option) => option.value), objectives.map((option) => option.value));
    }
    assert.equal($("manual-fill-selected").textContent, "Nạp số liệu từ công ty đang chọn");
    $("manual-fill-selected").click();
    assert.match($("manual-form").elements.company_name.value, /AAPL/);
    const examples = w.document.querySelector(".manual-examples");
    assert.equal(examples.open, false);
    examples.open = true;
    examples.querySelector('[data-vn-preset="FPT"]').click();
    assert.match($("manual-form").elements.company_name.value, /FPT/);
    assert.match($("manual-status").textContent, /bấm Dự báo/);
    const batch = w.document.querySelector(".manual-batch");
    assert.equal(batch.open, false);
    batch.open = true;
    assert.ok($("batch-csv-input"));
    assert.ok($("download-batch-template"));
    $("screener-search").value = "AAPL";
    $("screener-search").dispatchEvent(new w.Event("input", { bubbles: true }));
    await until(() => $("screener-body").querySelectorAll("tr").length === 1, "search filters rows");
    assert.match($("screener-body").textContent, /AAPL/);
    $("reset-filters").click();
    await until(() => $("screener-body").querySelectorAll("tr").length > 1, "reset restores rows");
    $("preview-menu").click();
    assert.ok(w.document.body.classList.contains("fh-menu-open"));
    assert.equal(w.document.querySelector(".main-shell").inert, true);
    assert.equal($("preview-sidebar").inert, false);
    w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape" }));
    assert.equal($("preview-menu").getAttribute("aria-expanded"), "false");
    assert.equal(w.document.querySelector(".main-shell").inert, false);
    assert.equal($("preview-sidebar").inert, true);
    if (role === "guest") {
      assert.equal($("tab-admin").hidden, true);
      if (primary) {
        $("manual-form").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
        await until(() => $("account-dialog").open, "manual prediction requires login");
        assert.equal(manualPosts, 0);
        $("account-close").click();
      }
      $("follow-company").click();
      await until(() => $("account-dialog").open, "private action requests login");
      $("account-close").click();
      $("account-open").click();
      assert.equal($("account-title").textContent, "Đăng nhập hệ thống");
      if (primary) {
        assert.ok(w.document.querySelector('.auth-brand img[src="/static/finhealth-logo.svg"]'));
        assert.equal(w.document.querySelector(".sidebar-footer").hidden, true);
      }
      w.document.querySelector('[data-auth="register"]').click();
      assert.equal($("account-title").textContent, "Đăng ký tài khoản");
      assert.deepEqual([...$("account-form").querySelectorAll("input")].map((input) => input.name),
        ["display_name", "email", "password", "confirm"]);
      const fields = $("account-form").elements;
      fields.email.value = "fixture@example.com";
      fields.password.value = fields.confirm.value = "Fixture password 123!";
      fields.display_name.value = "Fixture";
      $("account-form").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
      await until(() => !!w.document.querySelector('input[autocomplete="one-time-code"]'), "registration shows OTP input");
      assert.match($("account-content").textContent, /Không cần mở localhost/);
      $("account-close").click();
      w.location.hash = "admin";
      await until(() => w.location.hash === "#screener", "guest admin hash is rejected");
      if (primary) {
        $("export-screener").click();
        await until(() => $("account-dialog").open, "CSV export requires login");
        assert.equal(downloads, 0);
        const fields = $("account-form").elements;
        fields.email.value = "fixture@example.com";
        fields.password.value = "Fixture password 123!";
        $("account-form").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
        await until(() => downloads === 1, "CSV export resumes after login");
      }
    } else {
      $("tab-admin").click();
      await until(() => !!$("admin-refresh"), "full-page administration renders");
      assert.equal($("account-dialog").open, false);
      assert.equal($("account-content").parentElement.id, "preview-admin-workspace");
      assert.equal($("preview-admin-workspace").querySelectorAll("img").length, 0, "job values must stay escaped");
      assert.match($("preview-admin-workspace").textContent, /<img src=x/);
      if (primary) {
        const requester = w.document.querySelector('[data-job-row="123"] .admin-requester');
        assert.match(requester.textContent, /admin@example.com/);
        assert.match(requester.textContent, /ID #999/);
        assert.equal(requester.querySelectorAll("img").length, 0, "requester name is escaped");
        assert.match(w.document.querySelector('[data-job-row="124"]').textContent, /Không có thông tin/);
      }
      assert.equal($("admin-train"), null, "training form is not present in administration");
      assert.ok($("admin-users-section"));
      assert.ok($("admin-audit-section"));
      if (role === "admin_list_error") {
        assert.match($("admin-users-section").textContent, /Không tải được tài khoản thử nghiệm/);
      } else {
        assert.match($("admin-users-section").textContent, /account@example.com/);
      }
      assert.match($("admin-audit-section").textContent, /ingestion\.submit/);
      if (primary) {
        const detailButton = w.document.querySelector('[data-events="123"]');
        detailButton.click();
        await until(() => w.document.querySelector(".admin-timeline"), "job events appear beside selected row");
        assert.equal(detailButton.getAttribute("aria-expanded"), "true");
        assert.match(w.document.querySelector(".admin-event-row").textContent, /Đang xử lý dữ liệu/);
        assert.equal(w.document.querySelector(".admin-event-row").querySelectorAll("img").length, 0);
        detailButton.click();
        assert.equal(w.document.querySelector(".admin-event-row"), null);
        w.document.querySelector('[data-events="124"]').click();
        await until(() => w.document.querySelector(".admin-event-row")?.textContent.includes("Chưa có sự kiện"), "empty event history is explained");
        w.document.querySelector('[data-events="125"]').click();
        await until(() => w.document.querySelector(".admin-event-row")?.textContent.includes("Không tải được chi tiết"), "event error is visible");
        assert.equal(w.document.querySelectorAll(".admin-event-row").length, 1);
        const jobNext = w.document.querySelector('[data-page="jobs"][data-direction="next"]');
        assert.equal(jobNext.disabled, role !== "admin_paging");
        if (role === "admin_paging") {
          jobNext.click();
          await until(() => $("account-content").textContent.includes("PAGE2"), "job history advances independently");
          assert.match($("admin-users-section").textContent, /account@example.com/);
          assert.match($("admin-audit-section").textContent, /ingestion\.submit/);
          assert.match($("admin-users-section").textContent, /Trang 1/);
          assert.match($("admin-audit-section").textContent, /Trang 1/);
          w.document.querySelector('[data-page="jobs"][data-direction="prev"]').click();
          await until(() => w.document.querySelector('[data-events="123"]'), "job history returns to first page");
        }
      }
      $("account-open").click();
      assert.equal($("account-menu").hidden, false);
      if (primary) {
        assert.equal(w.document.querySelector(".sidebar-footer").hidden, false);
        $("personal-open").click();
        await until(() => $("account-title").textContent === "Dữ liệu đã lưu", "saved data dialog loaded");
        assert.match($("account-content").textContent, /Apple/);
        assert.match($("account-content").textContent, /Theo dõi nợ/);
        assert.equal($("account-content").querySelectorAll("[data-delete]").length, 2);
        $("account-close").click();
        await until(() => $("account-content").parentElement.id === "preview-admin-workspace", "admin restored after saved data");
        $("account-open").click();
        $("account-menu-logout").click();
        assert.ok($("logout-confirm"));
        assert.equal(logoutCalls, 0);
        $("logout-cancel").click();
        assert.equal(logoutCalls, 0);
        await until(() => $("account-content").parentElement.id === "preview-admin-workspace", "admin restored after canceled logout");
        $("account-open").click();
      }
      assert.ok($("account-password"));
      assert.ok($("account-email"));
      $("account-password").click();
      assert.equal($("account-title").textContent, "Đổi mật khẩu");
      assert.ok($("account-form").elements.current_password);
      $("account-close").click();
      await until(() => $("account-content").parentElement.id === "preview-admin-workspace", "admin restored after password form");
      $("account-open").click();
      $("account-settings").click();
      assert.equal($("account-dialog").open, true);
      $("account-close").click();
      await until(() => $("account-content").parentElement.id === "preview-admin-workspace", "admin view restored after account dialog");
      if (role === "admin_logout") {
        $("account-open").click();
        $("account-menu-logout").click();
        $("logout-confirm").click();
        await until(() => logoutCalls === 1 && $("tab-admin").hidden, "confirmed logout removes admin access");
      } else {
        expired = true;
        $("admin-refresh").click();
        await until(() => $("tab-admin").hidden, "expired session removes admin access");
      }
      assert.equal($("preview-admin-workspace").textContent, "", "private data cleared on expiry");
    }
    assert.deepEqual(errors, [], "no uncaught DOM errors");
    console.log(`PASS ${role}: live financial API, navigation, filtering, responsive menu, ${role !== "guest" ? "admin view and account actions" : "optional login/registration OTP/admin rejection"}; ${requestCount} requests`);
  } finally {
    dom.window.close();
  }
}

(async () => {
  await scenario("guest");
  await scenario("admin");
  if (primary) await scenario("admin_logout");
  if (primary) await scenario("admin_paging");
  if (primary) await scenario("admin_list_error");
  console.log("DOM checks passed. Visual layout and real admin sign-in still require browser review.");
})().catch((error) => { console.error(error); process.exitCode = 1; });
