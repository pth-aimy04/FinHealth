import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { DataForm } from "./data-form";
import { Dialog } from "./ui/dialog";
it("retains credentials after a failed request and associates errors with labels", async () => {
  const submit = vi.fn().mockRejectedValue(new Error("Email chưa xác thực"));
  render(
    <DataForm
      fields={[
        { name: "email", label: "Email", type: "email", required: true },
        {
          name: "password",
          label: "Mật khẩu",
          type: "password",
          required: true,
          min: 12,
        },
      ]}
      submit="Đăng nhập"
      onSubmit={submit}
    />,
  );
  await userEvent.type(screen.getByLabelText(/Email/), "user@example.com");
  await userEvent.type(screen.getByLabelText(/Mật khẩu/), "long-password-42");
  await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Email chưa xác thực",
  );
  expect(screen.getByLabelText(/Email/)).toHaveValue("user@example.com");
  expect(screen.getByLabelText(/Mật khẩu/)).toHaveValue("long-password-42");
});
it("focuses the first invalid financial field and prevents malformed submissions", async () => {
  const submit = vi.fn();
  render(
    <DataForm
      fields={[
        {
          name: "assets",
          label: "Tổng tài sản",
          type: "number",
          required: true,
          min: 1,
        },
      ]}
      submit="Dự báo"
      onSubmit={submit}
    />,
  );
  fireEvent.submit(
    screen.getByRole("button", { name: "Dự báo" }).closest("form")!,
  );
  await waitFor(() =>
    expect(screen.getByLabelText(/Tổng tài sản/)).toHaveAttribute(
      "aria-invalid",
      "true",
    ),
  );
  expect(submit).not.toHaveBeenCalled();
});
it("provides an accessible dismissible dialog", async () => {
  const close = vi.fn();
  render(
    <Dialog open onOpenChange={close} title="Lưu nghiên cứu">
      <button>Hủy</button>
    </Dialog>,
  );
  expect(screen.getByRole("dialog", { name: "Lưu nghiên cứu" })).toBeVisible();
  await userEvent.keyboard("{Escape}");
  expect(close).toHaveBeenCalledWith(false);
});
