import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { LogOut, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button, Panel, PanelHeader, cn } from '@/components/ui/Primitives';

type AuthMode = 'login' | 'register' | 'reset';

export function AccountPage() {
  const { user, refreshAuth, logout } = useAuth();
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  const [challenge, setChallenge] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
    mutationFn: () => api.register(email, password, displayName),
    onSuccess: (res) => {
      setErrorMessage(null);
      setChallenge(res.challenge);
      setStatusMessage(res.message);
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Đăng ký thất bại.'),
  });

  const verifyMutation = useMutation({
    mutationFn: () => api.verifyEmail(email, challenge, otpCode, newPassword || password),
    onSuccess: (res) => {
      setErrorMessage(null);
      setStatusMessage(res.message);
      setMode('login');
      setChallenge('');
      setOtpCode('');
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Xác thực OTP thất bại.'),
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
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Đặt lại mật khẩu thất bại.'),
  });

  const profileMutation = useMutation({
    mutationFn: () => api.updateProfile(displayName),
    onSuccess: async () => {
      setErrorMessage(null);
      setStatusMessage('Đã cập nhật tên hiển thị.');
      await refreshAuth();
    },
    onError: (err) => setErrorMessage(err instanceof Error ? err.message : 'Cập nhật thất bại.'),
  });

  if (user) {
    return (
      <div className="max-w-xl space-y-5">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">Tài khoản & Phiên đăng nhập</h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Được bảo vệ bằng cookie phiên cùng nguồn có thể thu hồi và mã chống giả mạo CSRF.
          </p>
        </div>

        <Panel>
          <PanelHeader
            title="Thông tin Định danh"
            actions={
              <Button variant="danger" size="sm" onClick={() => void logout()}>
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                Đăng xuất
              </Button>
            }
          />
          <div className="p-4 space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="surface-subtle p-3">
                <div className="text-[var(--text-secondary)]">Email</div>
                <div className="mt-0.5 font-mono font-medium">{user.email}</div>
              </div>
              <div className="surface-subtle p-3">
                <div className="text-[var(--text-secondary)]">Vai trò & Trạng thái</div>
                <div className="mt-0.5 font-medium flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-[var(--risk-low-fg)]" />
                  <span className="uppercase">{user.role === 'admin' ? 'Quản trị viên' : 'Thành viên'}</span> · Đã xác thực
                </div>
              </div>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                profileMutation.mutate();
              }}
              className="space-y-2.5 pt-2 border-t border-[var(--border-subtle)]"
            >
              <label htmlFor="profile-name" className="block font-medium">
                Tên hiển thị
              </label>
              <div className="flex gap-2">
                <input
                  id="profile-name"
                  type="text"
                  required
                  value={displayName || user.display_name}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="flex-1 h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
                <Button type="submit" variant="primary" disabled={profileMutation.isPending}>
                  Lưu thay đổi
                </Button>
              </div>
              {statusMessage ? (
                <p className="text-[var(--risk-low-fg)]">{statusMessage}</p>
              ) : null}
              {errorMessage ? (
                <p role="alert" className="text-[var(--risk-critical-fg)]">{errorMessage}</p>
              ) : null}
            </form>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div>
        <h1 className="text-[1.375rem] font-semibold tracking-[-0.02em]">Tài khoản FinHealth</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">
          Đăng nhập để quản lý danh sách theo dõi, bộ lọc đã lưu và phân tích cá nhân.
        </p>
      </div>

      <Panel>
        <div className="flex border-b border-[var(--border-subtle)] text-xs">
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
              onClick={() => {
                setMode(t.id);
                setErrorMessage(null);
                setStatusMessage(null);
                setChallenge('');
              }}
              className={cn(
                'flex-1 py-2.5 font-medium border-b-2 cursor-pointer bg-transparent',
                mode === t.id
                  ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                  : 'border-transparent text-[var(--text-secondary)]',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="p-5 space-y-4 text-xs">
          {statusMessage ? (
            <div className="p-2.5 rounded-[4px] bg-[var(--risk-low-bg)] text-[var(--risk-low-fg)]">
              {statusMessage}
            </div>
          ) : null}
          {errorMessage ? (
            <div role="alert" className="p-2.5 rounded-[4px] bg-[var(--risk-critical-bg)] text-[var(--risk-critical-fg)]">
              {errorMessage}
            </div>
          ) : null}

          {mode === 'login' ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                loginMutation.mutate();
              }}
              className="space-y-3"
            >
              <div>
                <label htmlFor="auth-email" className="block font-medium mb-1">Email</label>
                <input
                  id="auth-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <div>
                <label htmlFor="auth-pass" className="block font-medium mb-1">Mật khẩu</label>
                <input
                  id="auth-pass"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={loginMutation.isPending}>
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
              className="space-y-3"
            >
              <div>
                <label htmlFor="reg-name" className="block font-medium mb-1">Tên hiển thị</label>
                <input
                  id="reg-name"
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <div>
                <label htmlFor="reg-email" className="block font-medium mb-1">Email</label>
                <input
                  id="reg-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <div>
                <label htmlFor="reg-pass" className="block font-medium mb-1">
                  Mật khẩu (tối thiểu 12 ký tự)
                </label>
                <input
                  id="reg-pass"
                  type="password"
                  required
                  minLength={12}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={registerMutation.isPending}>
                Gửi mã OTP xác thực Email
              </Button>
            </form>
          ) : null}

          {mode === 'register' && challenge ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                verifyMutation.mutate();
              }}
              className="space-y-3"
            >
              <div>
                <label htmlFor="otp-code" className="block font-medium mb-1">Mã OTP 6 chữ số trong Email</label>
                <input
                  id="otp-code"
                  type="text"
                  pattern="[0-9]{6}"
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="123456"
                  className="w-full h-9 px-3 font-mono bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={verifyMutation.isPending}>
                Xác thực Email
              </Button>
            </form>
          ) : null}

          {mode === 'reset' && !challenge ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                forgotMutation.mutate();
              }}
              className="space-y-3"
            >
              <div>
                <label htmlFor="rst-email" className="block font-medium mb-1">Email tài khoản</label>
                <input
                  id="rst-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={forgotMutation.isPending}>
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
              className="space-y-3"
            >
              <div>
                <label htmlFor="rst-code" className="block font-medium mb-1">Mã OTP 6 chữ số</label>
                <input
                  id="rst-code"
                  type="text"
                  pattern="[0-9]{6}"
                  required
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="w-full h-9 px-3 font-mono bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <div>
                <label htmlFor="rst-new" className="block font-medium mb-1">Mật khẩu mới (tối thiểu 12 ký tự)</label>
                <input
                  id="rst-new"
                  type="password"
                  required
                  minLength={12}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full h-9 px-3 bg-[var(--bg-canvas)] border border-[var(--border-strong)] rounded-[4px]"
                />
              </div>
              <Button type="submit" variant="primary" className="w-full" disabled={resetMutation.isPending}>
                Xác nhận Đổi mật khẩu
              </Button>
            </form>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}
