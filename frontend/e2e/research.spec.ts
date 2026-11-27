import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
/** Log into the disposable browser database through the actual account form. */
async function login(page: Page, role = "user"): Promise<void> {
  await page.goto("/account");
  await page
    .getByLabel("Email *", { exact: true })
    .fill(`react-${role}@example.com`);
  await page
    .getByLabel("Mật khẩu *", { exact: true })
    .fill("FinHealth-browser-fixture-42!");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Tên hiển thị *")).toBeVisible();
  if (role === "user") {
    const cookies = await page.context().cookies();
    const csrf =
      cookies.find((cookie) => cookie.name === "finhealth_csrf")?.value ?? "";
    for (const collection of ["screeners", "analyses"]) {
      const response = await page.request.get(`/api/v1/me/${collection}`);
      const rows: { id: number; name: string }[] = await response.json();
      for (const row of rows.filter((item) => item.name.startsWith("E2E "))) {
        const deleted = await page.request.delete(
          `/api/v1/me/${collection}/${row.id}`,
          { headers: { "X-CSRF-Token": csrf } },
        );
        expect(deleted.status()).toBe(204);
      }
    }
  }
}
test("guest filters, deep links, comparison, report cutoff and authorization", async ({
  page,
}) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/screener?q=AAPL&sort=roa:desc");
  await expect(
    page.getByRole("link", { name: "AAPL", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "AAPL", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("AAPL");
  await page.getByRole("tab", { name: "Dự báo & TreeSHAP" }).click();
  await expect(
    page.getByRole("heading", { name: "TreeSHAP · đóng góp vào đầu ra gốc" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("tab", { name: "Dự báo & TreeSHAP" }),
  ).toHaveAttribute("data-state", "active");
  await page.goto("/compare?identifiers=AAPL,MSFT&common_fiscal_year=2024");
  await expect(
    page.getByRole("region", { name: "So sánh chỉ số nhóm doanh nghiệp" }),
  ).toBeVisible();
  await page.goto("/reports?identifier=AAPL&as_of=2024-12-31");
  await expect(page.getByLabel("Chọn phiên bản")).toBeVisible();
  await expect(
    page.getByText("Chỉ dùng số liệu công bố có sẵn tại mốc đã chọn."),
  ).toBeVisible();
  await page.goto("/reports?identifier=FPT");
  await expect(page.getByLabel("Chọn phiên bản")).toBeVisible();
  await page.goto("/admin");
  await expect(
    page.getByText("Chỉ quản trị viên được phép truy cập.", { exact: false }),
  ).toBeVisible();
  expect(failures).toEqual([]);
});
test("real cookie session, CSRF workspace writes and user authorization", async ({
  page,
}) => {
  await login(page);
  await page.goto("/screener?q=AAPL");
  await page.getByRole("button", { name: "Lưu bộ lọc", exact: true }).click();
  await page.getByLabel("Tên bộ lọc").fill("E2E Apple research");
  await page
    .getByRole("button", { name: "Lưu vào workspace", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.goto("/company/AAPL");
  await page.getByRole("button", { name: "Theo dõi", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đã theo dõi" })).toBeVisible();
  await page.goto("/workspace");
  await expect(
    page.getByRole("link", { name: "Phân tích", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Bộ lọc đã lưu", exact: true })
    .click();
  await expect(
    page.getByText("E2E Apple research", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("row")
    .filter({ hasText: "E2E Apple research" })
    .getByRole("button", { name: "Xóa", exact: true })
    .click();
  await page.getByRole("button", { name: "Xóa mục", exact: true }).click();
  await expect(
    page.getByText("E2E Apple research", { exact: true }),
  ).not.toBeVisible();
  await page.goto("/admin");
  await expect(
    page.getByText("Tài khoản hiện tại không có quyền quản trị.", {
      exact: false,
    }),
  ).toBeVisible();
  const protectedResponse = await page.request.get("/api/v1/admin/users");
  expect(protectedResponse.status()).toBe(403);
  const cookies = await page.context().cookies();
  expect(
    cookies.find((cookie) => cookie.name === "finhealth_session")?.httpOnly,
  ).toBe(true);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([
    "finhealth-theme",
  ]);
});
test("administrator read views and worker-disabled controls", async ({
  page,
}) => {
  await login(page, "admin");
  await page.goto("/admin");
  await page.getByRole("button", { name: "Người dùng", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Danh sách tài khoản" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Tác vụ SEC", exact: true }).click();
  await expect(
    page.getByText("Worker đang tắt. Không thể gửi tác vụ hàng đợi."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Audit", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Nhật ký kiểm toán", exact: true }),
  ).toBeVisible();
});
test("responsive themes, keyboard dialog and visual evidence", async ({
  page,
}) => {
  for (const theme of ["dark", "light"]) {
    await page.goto("/");
    await page.evaluate((value) => {
      localStorage.setItem("finhealth-theme", value);
      document.documentElement.dataset.theme = value;
    }, theme);
    await page.reload();
    for (const width of [375, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 960 });
      await expect(
        page.getByRole("heading", { name: "Toàn cảnh sức khỏe tài chính" }),
      ).toBeVisible();
      await expect(
        page
          .getByRole("region", { name: "Doanh nghiệp trong vũ trụ nghiên cứu" })
          .getByRole("link")
          .first(),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `../audit-reports/frontend/overview-${theme}-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "Mở điều hướng" }).click();
  await expect(
    page.getByRole("dialog", { name: "FinHealth · Điều hướng" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/screener");
  await expect(
    page.getByRole("heading", { name: "Sàng lọc doanh nghiệp" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../audit-reports/frontend/screener-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.setViewportSize({ width: 812, height: 375 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 720, height: 500 });
  // 1440px desktop at 200% browser zoom reflows to a 720 CSS-pixel layout viewport.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/company/AAPL");
  await expect(
    page.getByRole("tab", { name: "Tổng quan", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../audit-reports/frontend/company-desktop.png",
    fullPage: true,
  });
});

test("financial simulations, manual scoring, CSV portfolio and saved analysis", async ({
  page,
}) => {
  await page.goto("/company/AAPL?tab=stress");
  await page
    .getByRole("button", { name: "Chạy mô phỏng", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Đối chiếu thực tế và mô phỏng" }),
  ).toBeVisible();
  await login(page);
  const source = await page.request.get("/api/v1/companies/AAPL");
  const data = await source.json();
  const actual = data.history.at(-1);
  await page.goto("/prediction");
  await page.locator('[name="company_name"]').fill("E2E financial statement");
  await page.locator('[name="fiscal_year"]').fill(String(actual.fiscal_year));
  for (const key of [
    "total_assets",
    "total_liabilities",
    "current_assets",
    "current_liabilities",
    "stockholders_equity",
    "retained_earnings",
    "revenues",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "cash_and_equivalents",
    "interest_expense",
    "capex",
  ]) {
    if (actual[key] !== null && actual[key] !== undefined)
      await page.locator(`[name="${key}"]`).fill(String(actual[key]));
  }
  await page.getByRole("button", { name: "Chạy dự báo", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "TreeSHAP · đóng góp vào đầu ra gốc" }),
  ).toBeVisible({ timeout: 20_000 });
  await page.locator('[name="name"]').fill("E2E saved analysis");
  await page
    .getByRole("button", { name: "Lưu vào workspace", exact: true })
    .click();
  await expect(
    page.getByText("Đã lưu phân tích.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Danh mục hàng loạt", exact: true })
    .click();
  const csv = `company_name,fiscal_year,is_manufacturing,total_assets,total_liabilities\nPortfolio Company,${actual.fiscal_year},true,${actual.total_assets},${actual.total_liabilities}\n`;
  await page.getByLabel("Chọn file báo cáo CSV").setInputFiles({
    name: "portfolio.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Đánh giá file CSV" }).click();
  await expect(
    page.getByRole("heading", { name: "Kết quả danh mục" }),
  ).toBeVisible({ timeout: 20_000 });
  await page.goto("/workspace");
  await page
    .getByRole("button", { name: "Phân tích đã lưu", exact: true })
    .click();
  await expect(
    page.getByText("E2E saved analysis", { exact: true }),
  ).toBeVisible();
});

test("WCAG AA checks on both themes and dense data routes", async ({
  page,
}) => {
  test.setTimeout(180_000);
  for (const theme of ["dark", "light"]) {
    for (const route of [
      "/",
      "/screener?q=AAPL",
      "/company/AAPL",
      "/reports?identifier=AAPL",
      "/account",
      "/models",
    ]) {
      await page.goto(route);
      await page.evaluate((value) => {
        localStorage.setItem("finhealth-theme", value);
        document.documentElement.dataset.theme = value;
      }, theme);
      await expect(page.locator("main h1")).toBeVisible();
      await page.waitForTimeout(500);
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(
        result.violations.map((violation) => ({
          id: violation.id,
          nodes: violation.nodes.map((node) => node.target),
        })),
        `${route} ${theme}`,
      ).toEqual([]);
    }
  }
});
