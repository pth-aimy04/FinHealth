import { expect, test } from "@playwright/test";
test("Vite proxy retains real login cookies and CSRF on workspace mutations", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:5174/account");
  await page
    .getByLabel("Email *", { exact: true })
    .fill("react-user@example.com");
  await page
    .getByLabel("Mật khẩu *", { exact: true })
    .fill("FinHealth-browser-fixture-42!");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByLabel("Tên hiển thị *")).toBeVisible();
  await page.goto("http://127.0.0.1:5174/screener?q=AAPL");
  await page.getByRole("button", { name: "Lưu bộ lọc", exact: true }).click();
  await page.getByLabel("Tên bộ lọc").fill("Vite proxy verification");
  await page
    .getByRole("button", { name: "Lưu vào workspace", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const response = await page.request.get(
    "http://127.0.0.1:5174/api/v1/me/screeners",
  );
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ name: "Vite proxy verification" }),
    ]),
  );
  await page.reload();
  await expect(
    page.getByRole("link", { name: "AAPL", exact: true }),
  ).toBeVisible();
});
