import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  CheckCircle2,
  Download,
  KeyRound,
  LogOut,
  Mail,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { api, triggerBlobDownload } from '@/lib/api';
import { ORG_ROLE_LABELS } from '@/lib/format';
import { useAuth } from '@/context/AuthContext';
import { Button, PageHeader, Panel, PanelHeader, cn } from '@/components/ui/Primitives';

type AuthMode = 'login' | 'register' | 'reset';

export function AccountPage() {
  const { user, activeOrg, refreshAuth, logout } = useAuth();

  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [registerName, setRegisterName] = useState('');
  const [challenge, setChallenge] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const [profileName, setProfileName] = useState('');
  const [jobTitle, setJobTitle] = useState('');

  const [cpCurrentPassword, setCpCurrentPassword] = useState('');
  const [cpNewPassword, setCpNewPassword] = useState('');
  const [cpChallenge, setCpChallenge] = useState('');
  const [cpOtpCode, setCpOtpCode] = useState('');

  const [ceCurrentPassword, setCeCurrentPassword] = useState('');
  const [ceNewEmail, setCeNewEmail] = useState('');
  const [ceChallenge, setCeChallenge] = useState('');
  const [ceOtpCode, setCeOtpCode] = useState('');

  const [delPassword, setDelPassword] = useState('');
  const [delChallenge, setDelChallenge] = useState('');
  const [delOtpCode, setDelOtpCode] = useState('');

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setProfileName(user.display_name);
      setJobTitle(user.job_title ?? '');
    }
  }, [user]);

  const loginMutation = useMutation({
    mutationFn: () => api.login(email, password),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đăng nhập thành công.');
      await refreshAuth();
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Đăng nhập thất bại.'),
  });

  const registerMutation = useMutation({
    mutationFn: () => api.register(email, password, registerName),
    onSuccess: (res) => {
      setErrorMessage(null);
      setChallenge(res.challenge);
      setNewPassword(password);
      setStatusMessage(res.message);
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Đăng ký thất bại.'),
  });

  const resendMutation = useMutation({
    mutationFn: () => api.resendVerification(email),
    onSuccess: (res) => {
      setErrorMessage(null);
      setChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Gửi lại mã thất bại.'),
  });

  const verifyMutation = useMutation({
    mutationFn: () => api.verifyEmail(email, challenge, otpCode, newPassword),
    onSuccess: (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setMode('login');
      setChallenge('');
      setOtpCode('');
      setPassword(newPassword);
      setNewPassword('');
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Xác thực OTP thất bại.'),
  });

  const forgotMutation = useMutation({
    mutationFn: () => api.forgotPassword(email),
    onSuccess: (res) => {
      setErrorMessage(null);
      setChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Gửi yêu cầu thất bại.'),
  });

  const resetMutation = useMutation({
    mutationFn: () => api.resetPassword(email, challenge, otpCode, newPassword),
    onSuccess: (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setMode('login');
      setChallenge('');
      setOtpCode('');
      setNewPassword('');
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Đặt lại mật khẩu thất bại.'),
  });

  const profileMutation = useMutation({
    mutationFn: () => api.updateProfile(profileName.trim(), jobTitle.trim() || null),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã cập nhật hồ sơ cá nhân.');
      await refreshAuth();
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Cập nhật thất bại.'),
  });

  const requestChangePassMutation = useMutation({
    mutationFn: () => api.requestChangePassword(cpCurrentPassword, cpNewPassword),
    onSuccess: (res) => {
      setErrorMessage(null);
      setCpChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể gửi mã OTP đổi mật khẩu.'),
  });

  const confirmChangePassMutation = useMutation({
    mutationFn: () =>
      api.confirmPasswordChange(user!.email, cpChallenge, cpOtpCode, cpNewPassword),
    onSuccess: async (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setCpCurrentPassword('');
      setCpNewPassword('');
      setCpChallenge('');
      setCpOtpCode('');
      await refreshAuth();
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Xác nhận đổi mật khẩu thất bại.'),
  });

  const requestChangeEmailMutation = useMutation({
    mutationFn: () => api.requestChangeEmail(ceCurrentPassword, ceNewEmail),
    onSuccess: (res) => {
      setErrorMessage(null);
      setCeChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể gửi mã OTP đổi email.'),
  });

  const confirmChangeEmailMutation = useMutation({
    mutationFn: () => api.confirmEmailChange(ceNewEmail, ceChallenge, ceOtpCode),
    onSuccess: async (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setCeCurrentPassword('');
      setCeNewEmail('');
      setCeChallenge('');
      setCeOtpCode('');
      await refreshAuth();
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Xác nhận đổi email thất bại.'),
  });

  const exportDataMutation = useMutation({
    mutationFn: () => api.exportMyData(),
    onSuccess: (data) => {
      setErrorMessage(null);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json;charset=utf-8',
      });
      const dateStr = new Date().toISOString().slice(0, 10);
      triggerBlobDownload(blob, `finhealth-personal-data-${dateStr}.json`);
      setStatusMessage('Đã xuất gói dữ liệu cá nhân (JSON) theo Luật 91/2025/QH15.');
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể xuất dữ liệu cá nhân.'),
  });

  const requestDeleteMutation = useMutation({
    mutationFn: () => api.requestDeleteAccount(delPassword),
    onSuccess: (res) => {
      setErrorMessage(null);
      setDelChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Không thể gửi mã OTP xóa tài khoản.'),
  });

  const confirmDeleteMutation = useMutation({
    mutationFn: () => api.confirmDeleteAccount(delPassword, delChallenge, delOtpCode),
    onSuccess: async (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setDelPassword('');
      setDelChallenge('');
      setDelOtpCode('');
      await refreshAuth();
    },
    onError: (err) =>
      setErrorMessage(err instanceof Error ? err.message : 'Xóa tài khoản thất bại.'),
  });

  if (user) {
    return (
      <div className="max-w-4xl space-y-5 animate-view">
        <PageHeader
          title="Tài khoản & Bảo mật"
          description="Quản lý hồ sơ cá nhân, xác thực OTP đổi mật khẩu/email và quyền dữ liệu cá nhân theo Luật 91/2025/QH15."
          actions={
            <Button variant="danger" size="sm" onClick={() => void logout()}>
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              Đăng xuất
            </Button>
          }
        />

        {statusMessage ? (
          <div
            role="status"
            className="px-4 py-2.5 rounded-[3px] border border-[var(--risk-low-border)] text-xs font-semibold bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]"
          >
            {statusMessage}
          </div>
        ) : null}
        {errorMessage ? (
          <div
            role="alert"
            className="px-4 py-2.5 rounded-[3px] border border-[var(--risk-critical-border)] text-xs font-semibold bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)]"
          >
            {errorMessage}
          </div>
        ) : null}

        {/* Profile Identity Ledger */}
        <Panel ruled className="overflow-hidden">
          <PanelHeader title="Thông tin Định danh & Hồ sơ" />
          <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[var(--border-subtle)] bg-[var(--bg-header)]/50 border-b border-[var(--border-subtle)] text-xs">
            <div className="p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                Email đăng nhập
              </div>
              <div className="mt-1 font-mono font-semibold text-[var(--text-primary)] truncate">
                {user.email}
              </div>
            </div>
            <div className="p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                Tài khoản hệ thống
              </div>
              <div className="mt-1 font-semibold flex items-center gap-1.5 text-[var(--text-primary)]">
                <ShieldCheck className="h-3.5 w-3.5 text-[var(--risk-low-fg)]" aria-hidden="true" />
                <span>{user.role === 'admin' ? 'Quản trị hệ thống' : 'Thành viên'}</span> · Đã xác thực
              </div>
            </div>
            <div className="p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--text-muted)]">
                Không gian hiện tại
              </div>
              <div className="mt-1 font-semibold text-[var(--text-primary)] truncate">
                {activeOrg
                  ? `${activeOrg.name} (${ORG_ROLE_LABELS[activeOrg.role]})`
                  : 'Chưa chọn tổ chức'}
              </div>
            </div>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              profileMutation.mutate();
            }}
            className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs"
          >
            <div>
              <label htmlFor="profile-name" className="block font-semibold text-[var(--text-secondary)] mb-1">
                Tên hiển thị
              </label>
              <input
                id="profile-name"
                type="text"
                required
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                className="field-control"
              />
            </div>
            <div>
              <label htmlFor="profile-job-title" className="block font-semibold text-[var(--text-secondary)] mb-1">
                Chức danh / Bộ phận (tùy chọn)
              </label>
              <input
                id="profile-job-title"
                type="text"
                maxLength={120}
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="VD: Giám đốc Tài chính, Chuyên viên Tín dụng"
                className="field-control"
              />
            </div>
            <div className="sm:col-span-2 flex justify-end">
              <Button type="submit" variant="primary" size="sm" disabled={profileMutation.isPending}>
                {profileMutation.isPending ? 'Đang lưu...' : 'Lưu thay đổi hồ sơ'}
              </Button>
            </div>
          </form>
        </Panel>

        {/* Change Password & Change Email */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Đổi mật khẩu (OTP)"
              description="Yêu cầu mật khẩu hiện tại và mã OTP gửi qua email."
            />
            <div className="p-5 text-xs space-y-3">
              {!cpChallenge ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    requestChangePassMutation.mutate();
                  }}
                  className="space-y-3"
                >
                  <div>
                    <label htmlFor="cp-current" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mật khẩu hiện tại
                    </label>
                    <input
                      id="cp-current"
                      type="password"
                      required
                      value={cpCurrentPassword}
                      onChange={(e) => setCpCurrentPassword(e.target.value)}
                      className="field-control"
                    />
                  </div>
                  <div>
                    <label htmlFor="cp-new" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mật khẩu mới (tối thiểu 12 ký tự)
                    </label>
                    <input
                      id="cp-new"
                      type="password"
                      required
                      minLength={12}
                      value={cpNewPassword}
                      onChange={(e) => setCpNewPassword(e.target.value)}
                      className="field-control"
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="secondary"
                    size="sm"
                    disabled={requestChangePassMutation.isPending}
                  >
                    <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                    Gửi mã OTP đổi mật khẩu
                  </Button>
                </form>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    confirmChangePassMutation.mutate();
                  }}
                  className="space-y-3"
                >
                  <div>
                    <label htmlFor="cp-otp" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mã OTP 6 chữ số trong email hiện tại
                    </label>
                    <input
                      id="cp-otp"
                      type="text"
                      pattern="[0-9]{6}"
                      required
                      value={cpOtpCode}
                      onChange={(e) => setCpOtpCode(e.target.value)}
                      placeholder="123456"
                      className="field-control font-mono"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={confirmChangePassMutation.isPending}
                    >
                      Xác nhận đổi mật khẩu
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCpChallenge('');
                        setCpOtpCode('');
                      }}
                    >
                      Hủy
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <PanelHeader
              title="Đổi địa chỉ Email (OTP)"
              description="Mã OTP xác thực sẽ được gửi tới địa chỉ email mới."
            />
            <div className="p-5 text-xs space-y-3">
              {!ceChallenge ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    requestChangeEmailMutation.mutate();
                  }}
                  className="space-y-3"
                >
                  <div>
                    <label htmlFor="ce-current" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mật khẩu hiện tại
                    </label>
                    <input
                      id="ce-current"
                      type="password"
                      required
                      value={ceCurrentPassword}
                      onChange={(e) => setCeCurrentPassword(e.target.value)}
                      className="field-control"
                    />
                  </div>
                  <div>
                    <label htmlFor="ce-new-email" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Địa chỉ Email mới
                    </label>
                    <input
                      id="ce-new-email"
                      type="email"
                      required
                      value={ceNewEmail}
                      onChange={(e) => setCeNewEmail(e.target.value)}
                      className="field-control"
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="secondary"
                    size="sm"
                    disabled={requestChangeEmailMutation.isPending}
                  >
                    <Mail className="h-3.5 w-3.5" aria-hidden="true" />
                    Gửi mã OTP tới email mới
                  </Button>
                </form>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    confirmChangeEmailMutation.mutate();
                  }}
                  className="space-y-3"
                >
                  <div>
                    <label htmlFor="ce-otp" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mã OTP 6 chữ số gửi tới {ceNewEmail}
                    </label>
                    <input
                      id="ce-otp"
                      type="text"
                      pattern="[0-9]{6}"
                      required
                      value={ceOtpCode}
                      onChange={(e) => setCeOtpCode(e.target.value)}
                      placeholder="123456"
                      className="field-control font-mono"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={confirmChangeEmailMutation.isPending}
                    >
                      Xác nhận đổi Email
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCeChallenge('');
                        setCeOtpCode('');
                      }}
                    >
                      Hủy
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </Panel>
        </div>

        {/* Law 91/2025/QH15 Personal Data Rights */}
        <Panel className="overflow-hidden">
          <PanelHeader
            title="Quyền dữ liệu cá nhân (Luật 91/2025/QH15)"
            description="Trích xuất bản sao dữ liệu cá nhân hoặc yêu cầu xóa vĩnh viễn tài khoản."
          />
          <div className="p-5 space-y-5 text-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[var(--border-subtle)]">
              <div>
                <div className="font-bold text-[13px] text-[var(--text-primary)]">
                  Xuất dữ liệu cá nhân (JSON)
                </div>
                <p className="text-[var(--text-secondary)] mt-0.5 m-0">
                  Tải về hồ sơ tài khoản, danh sách tổ chức tham gia, lịch sử phiên và hoạt động của
                  riêng bạn.
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => exportDataMutation.mutate()}
                disabled={exportDataMutation.isPending}
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {exportDataMutation.isPending ? 'Đang xuất...' : 'Xuất dữ liệu cá nhân'}
              </Button>
            </div>

            <div className="space-y-3">
              <div>
                <div className="font-bold text-[13px] text-[var(--risk-critical-fg)]">
                  Xóa vĩnh viễn tài khoản & dữ liệu cá nhân
                </div>
                <p className="text-[var(--text-secondary)] mt-0.5 m-0">
                  Thao tác không thể hoàn tác. Toàn bộ phiên đăng nhập và không gian cá nhân sẽ bị
                  xóa sạch. Nếu bạn là quản trị viên duy nhất của tổ chức còn thành viên khác, hãy
                  chuyển quyền quản trị trước.
                </p>
              </div>

              {!delChallenge ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    requestDeleteMutation.mutate();
                  }}
                  className="flex flex-col sm:flex-row gap-2 sm:items-end"
                >
                  <div className="flex-1">
                    <label htmlFor="del-password" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Nhập mật khẩu hiện tại để nhận OTP xóa tài khoản
                    </label>
                    <input
                      id="del-password"
                      type="password"
                      required
                      value={delPassword}
                      onChange={(e) => setDelPassword(e.target.value)}
                      className="field-control"
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="danger"
                    size="sm"
                    disabled={requestDeleteMutation.isPending}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Gửi OTP xóa tài khoản
                  </Button>
                </form>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    confirmDeleteMutation.mutate();
                  }}
                  className="flex flex-col sm:flex-row gap-2 sm:items-end"
                >
                  <div className="flex-1">
                    <label htmlFor="del-otp" className="block font-semibold text-[var(--text-secondary)] mb-1">
                      Mã OTP 6 chữ số xác nhận xóa vĩnh viễn
                    </label>
                    <input
                      id="del-otp"
                      type="text"
                      pattern="[0-9]{6}"
                      required
                      value={delOtpCode}
                      onChange={(e) => setDelOtpCode(e.target.value)}
                      placeholder="123456"
                      className="field-control font-mono"
                    />
                  </div>
                  <Button
                    type="submit"
                    variant="danger"
                    size="sm"
                    disabled={confirmDeleteMutation.isPending}
                  >
                    Xác nhận xóa vĩnh viễn
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setDelChallenge('');
                      setDelOtpCode('');
                    }}
                  >
                    Hủy
                  </Button>
                </form>
              )}
            </div>
          </div>
        </Panel>
      </div>
    );
  }

  /* Unauthenticated Institutional Split Access Panel */
  return (
    <div className="max-w-4xl mx-auto py-4 animate-view">
      <div className="surface-ruled overflow-hidden grid grid-cols-1 md:grid-cols-12">
        {/* Left: Capital Navy Institutional Briefing */}
        <div className="md:col-span-5 bg-[var(--chrome-bg)] text-[var(--chrome-ink)] p-6 sm:p-8 flex flex-col justify-between gap-6">
          <div className="space-y-3">
            <h1 className="font-editorial text-2xl font-bold text-white leading-tight m-0">
              Tài khoản FinHealth
            </h1>
            <p className="text-[13px] text-[var(--chrome-ink-secondary)] leading-relaxed m-0">
              Cổng truy cập không gian làm việc tổ chức dành cho Phòng Thẩm định Tín dụng, CFO và
              Chuyên viên Phân tích Tài chính.
            </p>
          </div>

          <ul className="space-y-2.5 text-xs text-[var(--chrome-ink-secondary)] list-none p-0 m-0">
            {[
              'Cô lập tuyệt đối danh bạ & BCTC theo từng tổ chức',
              'Hỗ trợ TT99/2025, TT200/2014, TT133/2016 & XML HTKK',
              'Chấm điểm nguy cơ khủng hoảng 12T & xuất báo cáo PDF A4',
              'Tuân thủ Luật 91/2025/QH15 & Nghị định 88/2014/NĐ-CP',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--chrome-accent)] shrink-0 mt-0.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Right: Authentication Form */}
        <div className="md:col-span-7 bg-[var(--bg-surface)] flex flex-col">
          <div className="flex border-b border-[var(--border-strong)] bg-[var(--bg-header)] text-xs" role="tablist">
            {(
              [
                { id: 'login', label: 'Đăng nhập' },
                { id: 'register', label: 'Đăng ký' },
                { id: 'reset', label: 'Quên mật khẩu' },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={mode === t.id}
                onClick={() => {
                  setMode(t.id);
                  setErrorMessage(null);
                  setStatusMessage(null);
                  setChallenge('');
                  setOtpCode('');
                }}
                className={cn(
                  'flex-1 py-3 font-semibold border-b-2 -mb-px cursor-pointer bg-transparent transition-colors',
                  mode === t.id
                    ? 'border-[var(--accent-primary)] text-[var(--accent-primary)] bg-[var(--bg-surface)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="p-6 sm:p-8 space-y-4 text-xs flex-1">
            {statusMessage ? (
              <div
                role="status"
                className="p-3 rounded-[3px] border border-[var(--risk-low-border)] bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)] font-semibold"
              >
                {statusMessage}
              </div>
            ) : null}
            {errorMessage ? (
              <div
                role="alert"
                className="p-3 rounded-[3px] border border-[var(--risk-critical-border)] bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)] font-semibold"
              >
                {errorMessage}
              </div>
            ) : null}

            {mode === 'login' ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  loginMutation.mutate();
                }}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="auth-email" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Email
                  </label>
                  <input
                    id="auth-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="field-control"
                  />
                </div>
                <div>
                  <label htmlFor="auth-pass" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Mật khẩu
                  </label>
                  <input
                    id="auth-pass"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="field-control"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={loginMutation.isPending}
                >
                  {loginMutation.isPending ? 'Đang đăng nhập...' : 'Đăng nhập'}
                </Button>
              </form>
            ) : null}

            {mode === 'register' && !challenge ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  registerMutation.mutate();
                }}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="reg-name" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Tên hiển thị
                  </label>
                  <input
                    id="reg-name"
                    type="text"
                    required
                    value={registerName}
                    onChange={(e) => setRegisterName(e.target.value)}
                    className="field-control"
                  />
                </div>
                <div>
                  <label htmlFor="reg-email" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Email công việc
                  </label>
                  <input
                    id="reg-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="field-control"
                  />
                </div>
                <div>
                  <label htmlFor="reg-pass" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Mật khẩu (tối thiểu 12 ký tự)
                  </label>
                  <input
                    id="reg-pass"
                    type="password"
                    required
                    minLength={12}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="field-control"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={registerMutation.isPending}
                >
                  {registerMutation.isPending ? 'Đang gửi OTP...' : 'Gửi mã OTP xác thực Email'}
                </Button>
              </form>
            ) : null}

            {mode === 'register' && challenge ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  verifyMutation.mutate();
                }}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="otp-code" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Mã OTP 6 chữ số trong Email
                  </label>
                  <input
                    id="otp-code"
                    type="text"
                    pattern="[0-9]{6}"
                    required
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="123456"
                    className="field-control font-mono"
                  />
                </div>
                <div>
                  <label htmlFor="verify-new-pass" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Xác nhận mật khẩu đăng nhập (tối thiểu 12 ký tự)
                  </label>
                  <input
                    id="verify-new-pass"
                    type="password"
                    required
                    minLength={12}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="field-control"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={verifyMutation.isPending}
                >
                  {verifyMutation.isPending ? 'Đang xác thực...' : 'Xác thực Email'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => resendMutation.mutate()}
                  disabled={resendMutation.isPending}
                >
                  Gửi lại mã OTP
                </Button>
              </form>
            ) : null}

            {mode === 'reset' && !challenge ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  forgotMutation.mutate();
                }}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="rst-email" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Email tài khoản
                  </label>
                  <input
                    id="rst-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="field-control"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={forgotMutation.isPending}
                >
                  Gửi mã OTP đặt lại mật khẩu
                </Button>
              </form>
            ) : null}

            {mode === 'reset' && challenge ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  resetMutation.mutate();
                }}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="rst-code" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Mã OTP 6 chữ số
                  </label>
                  <input
                    id="rst-code"
                    type="text"
                    pattern="[0-9]{6}"
                    required
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    className="field-control font-mono"
                  />
                </div>
                <div>
                  <label htmlFor="rst-new" className="block font-semibold text-[var(--text-secondary)] mb-1">
                    Mật khẩu mới (tối thiểu 12 ký tự)
                  </label>
                  <input
                    id="rst-new"
                    type="password"
                    required
                    minLength={12}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="field-control"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  disabled={resetMutation.isPending}
                >
                  Xác nhận Đặt lại mật khẩu
                </Button>
              </form>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
