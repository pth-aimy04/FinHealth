import { useState, type ReactElement } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ShieldCheck, LockKeyhole, FolderHeart } from "lucide-react";
import { mutate } from "../lib/api/client";
import { useSession } from "../app/session";
import { PageTitle, Panel, QueryState } from "../components/shared";
import { Button } from "../components/ui/button";
import { DataForm, type Field } from "../components/data-form";
const email: Field = {
  name: "email",
  label: "Email",
  type: "email",
  required: true,
  max: 254,
};
const password: Field = {
  name: "password",
  label: "Mật khẩu",
  type: "password",
  required: true,
  max: 128,
};
const newPassword: Field = {
  name: "new_password",
  label: "Mật khẩu mới",
  type: "password",
  required: true,
  min: 12,
  max: 128,
  hint: "Ít nhất 12 ký tự. Cho phép dán và dùng trình quản lý mật khẩu.",
};
const currentPassword: Field = {
  name: "current_password",
  label: "Mật khẩu hiện tại",
  type: "password",
  required: true,
  max: 128,
};
type Challenge = { email: string; challenge: string; purpose: string };
/** Email OTP lifecycle with in-memory challenges and revocable backend cookies. */
export default function Accounts(): ReactElement {
  const { user, pending, error, refresh, logout } = useSession();
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") ?? (user ? "profile" : "login");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [notice, setNotice] = useState("");
  const [logoutError, setLogoutError] = useState<Error | null>(null);
  const switchMode = (value: string): void => {
    setChallenge(null);
    setNotice("");
    setParams({ mode: value });
  };
  const start = async (
    path: string,
    values: Record<string, string>,
    purpose: string,
  ): Promise<string> => {
    const result = await mutate<{ challenge: string; message: string }>(
      `/auth/${path}`,
      values,
    );
    setChallenge({
      email: values.email ?? user?.email ?? "",
      challenge: result.challenge,
      purpose,
    });
    return result.message;
  };
  const headings: Record<string, string> = {
    login: "Chào mừng trở lại",
    register: "Tạo tài khoản nghiên cứu",
    forgot: "Khôi phục mật khẩu",
    resend: "Gửi lại mã xác thực",
    profile: "Hồ sơ cá nhân",
    password: "Đổi mật khẩu",
    email: "Đổi địa chỉ email",
  };
  const fields: Record<string, Field[]> = {
    login: [email, password],
    register: [
      { name: "display_name", label: "Tên hiển thị", required: true, max: 120 },
      email,
      { ...password, min: 12, hint: "Tối thiểu 12 ký tự" },
    ],
    forgot: [email],
    resend: [email],
    profile: [
      { name: "display_name", label: "Tên hiển thị", required: true, max: 120 },
    ],
    password: [currentPassword, newPassword],
    email: [email, currentPassword],
  };
  return (
    <>
      <PageTitle
        title={user ? "Tài khoản & bảo mật" : "Tài khoản FinHealth"}
        description="Nghiên cứu công khai không cần đăng nhập. Đăng nhập để lưu bộ lọc, theo dõi và quản lý phân tích của bạn."
      />
      <QueryState pending={pending} error={error} retry={refresh} />
      {user && (
        <div className="account-tabs">
          <Button
            variant={mode === "profile" ? "default" : "outline"}
            onClick={() => switchMode("profile")}
          >
            Hồ sơ
          </Button>
          <Button variant="outline" onClick={() => switchMode("password")}>
            Đổi mật khẩu
          </Button>
          <Button variant="outline" onClick={() => switchMode("email")}>
            Đổi email
          </Button>
          <Button
            variant="ghost"
            onClick={() => void logout().catch(setLogoutError)}
          >
            Đăng xuất
          </Button>
          <Button variant="outline" asChild>
            <Link to="/workspace">Workspace</Link>
          </Button>
        </div>
      )}
      <QueryState error={logoutError} />
      <div className="auth-layout">
        <div className="auth-story">
          <ShieldCheck size={36} className="positive" aria-hidden="true" />
          <h2>
            Một không gian riêng.
            <br />
            Góc nhìn tài chính rõ ràng.
          </h2>
          <p>
            Lưu những gì bạn quan tâm và tiếp tục nghiên cứu từ bất kỳ phiên làm
            việc nào.
          </p>
          <div className="notice">
            <FolderHeart className="inline mr-2" size={18} aria-hidden="true" />
            Watchlist, bộ lọc và phân tích theo tài khoản.
          </div>
          <div className="notice">
            <LockKeyhole className="inline mr-2" size={18} aria-hidden="true" />
            Xác minh email bằng OTP. Phiên đăng nhập do máy chủ quản lý.
          </div>
        </div>
        <Panel
          title={
            challenge ? "Xác nhận mã OTP" : (headings[mode] ?? headings.login)
          }
          note={
            challenge
              ? `Mã 6 chữ số gửi tới ${challenge.email} · có hiệu lực 10 phút`
              : (user?.email ??
                "Thông tin đăng nhập được gửi qua kết nối cùng nguồn")
          }
        >
          <div className="panel-body">
            {notice && (
              <p role="status" className="notice">
                {notice}
              </p>
            )}
            {challenge ? (
              <>
                <DataForm
                  key={`otp-${challenge.challenge}`}
                  compact
                  fields={[
                    {
                      name: "code",
                      label: "Mã OTP",
                      required: true,
                      pattern: /^[0-9]{6}$/,
                      max: 6,
                      hint: "Nhập mã từ email; không cần mở liên kết.",
                    },
                    ...(challenge.purpose === "email" ? [] : [newPassword]),
                  ]}
                  submit="Xác nhận OTP"
                  onSubmit={async (values) => {
                    const endpoint = {
                      register: "verify-email",
                      resend: "verify-email",
                      forgot: "reset-password",
                      password: "confirm-password-change",
                      email: "confirm-email",
                    }[challenge.purpose];
                    const result = await mutate<{ message: string }>(
                      `/auth/${endpoint}`,
                      {
                        ...values,
                        email: challenge.email,
                        challenge: challenge.challenge,
                      },
                    );
                    setChallenge(null);
                    setNotice(result.message);
                    setParams({ mode: "login" });
                    await refresh();
                  }}
                />
                <Button
                  variant="ghost"
                  className="mt-4"
                  onClick={() => setChallenge(null)}
                >
                  Quay lại / yêu cầu mã mới
                </Button>
              </>
            ) : (
              <DataForm
                key={`${mode}-${user?.id ?? "guest"}`}
                compact
                fields={fields[mode] ?? fields.login}
                defaults={
                  mode === "profile" && user
                    ? { display_name: user.display_name }
                    : {}
                }
                submit={
                  mode === "login"
                    ? "Đăng nhập"
                    : mode === "profile"
                      ? "Lưu hồ sơ"
                      : "Gửi mã OTP"
                }
                onSubmit={async (values) => {
                  if (mode === "login") {
                    await mutate("/auth/login", values);
                    await refresh();
                    setParams({ mode: "profile" });
                    return "Đã đăng nhập.";
                  }
                  if (mode === "profile") {
                    await mutate("/auth/profile", values, "PATCH");
                    await refresh();
                    return "Đã lưu hồ sơ.";
                  }
                  const endpoint: Record<string, string> = {
                    register: "register",
                    forgot: "forgot-password",
                    resend: "resend-verification",
                    password: "change-password",
                    email: "change-email",
                  };
                  return start(endpoint[mode] ?? "login", values, mode);
                }}
              />
            )}
            {!user && (
              <div className="auth-links">
                {[
                  ["login", "Đăng nhập"],
                  ["register", "Đăng ký"],
                  ["forgot", "Quên mật khẩu"],
                  ["resend", "Gửi lại xác thực"],
                ]
                  .filter(([value]) => value !== mode)
                  .map(([value, text]) => (
                    <Button
                      key={value}
                      variant="ghost"
                      onClick={() => switchMode(value)}
                    >
                      {text}
                    </Button>
                  ))}
              </div>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
