import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AccountPage } from '@/pages/AccountPage';
import { api } from '@/lib/api';

const mockUseAuth = vi.fn();

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

function renderAccountPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountPage />
    </QueryClientProvider>,
  );
}

describe('AccountPage lifecycle and privacy flows', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('register -> verify OTP sends email, challenge, code, and new_password', async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      activeOrg: null,
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    });

    const registerSpy = vi.spyOn(api, 'register').mockResolvedValue({
      message: 'Mã OTP đã được gửi.',
      challenge: 'c'.repeat(32),
      expires_in: 600,
    });
    const verifySpy = vi.spyOn(api, 'verifyEmail').mockResolvedValue({
      message: 'Đã xác thực email. Bạn có thể đăng nhập.',
    });

    renderAccountPage();

    fireEvent.click(screen.getByRole('tab', { name: 'Đăng ký' }));
    fireEvent.change(screen.getByLabelText('Tên hiển thị'), { target: { value: 'Trần Minh' } });
    fireEvent.change(screen.getByLabelText('Email công việc'), {
      target: { value: 'minh@company.vn' },
    });
    fireEvent.change(screen.getByLabelText(/Mật khẩu \(tối thiểu 12 ký tự\)/i), {
      target: { value: 'SecurePass2026!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Gửi mã OTP xác thực Email/i }));

    await waitFor(() => expect(registerSpy).toHaveBeenCalled());

    const otpInput = await screen.findByLabelText(/Mã OTP 6 chữ số/i);
    const confirmPassInput = screen.getByLabelText(/Xác nhận mật khẩu đăng nhập/i);
    fireEvent.change(otpInput, { target: { value: '654321' } });
    fireEvent.change(confirmPassInput, { target: { value: 'FinalOwnerPass2026!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác thực Email' }));

    await waitFor(() =>
      expect(verifySpy).toHaveBeenCalledWith(
        'minh@company.vn',
        'c'.repeat(32),
        '654321',
        'FinalOwnerPass2026!',
      ),
    );
  });

  it('allows clearing and editing controlled displayName and exposes privacy controls when signed in', async () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: 7,
        email: 'cfo@minhan.vn',
        display_name: 'Lê Thị Hoa',
        job_title: 'CFO',
        role: 'user',
        active: true,
        email_verified: true,
      },
      activeOrg: {
        id: 1,
        name: 'Công ty Minh An',
        slug: 'minh-an',
        is_personal: false,
        role: 'org_admin',
        member_count: 3,
        is_active_workspace: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      refreshAuth: vi.fn(),
      logout: vi.fn(),
    });

    const updateProfileSpy = vi.spyOn(api, 'updateProfile').mockResolvedValue({
      id: 7,
      email: 'cfo@minhan.vn',
      display_name: 'Lê Hoa Mới',
      job_title: 'Giám đốc Tài chính',
      role: 'user',
      active: true,
      email_verified: true,
    });

    renderAccountPage();

    const nameInput = screen.getByLabelText('Tên hiển thị') as HTMLInputElement;
    expect(nameInput.value).toBe('Lê Thị Hoa');
    // Controlled input can be cleared cleanly (fixes legacy value={displayName || user.display_name} bug)
    fireEvent.change(nameInput, { target: { value: '' } });
    expect(nameInput.value).toBe('');
    fireEvent.change(nameInput, { target: { value: 'Lê Hoa Mới' } });
    fireEvent.change(screen.getByLabelText(/Chức danh/i), {
      target: { value: 'Giám đốc Tài chính' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Lưu thay đổi hồ sơ/i }));

    await waitFor(() =>
      expect(updateProfileSpy).toHaveBeenCalledWith('Lê Hoa Mới', 'Giám đốc Tài chính'),
    );

    expect(screen.getByText(/Đổi mật khẩu \(OTP\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Đổi địa chỉ Email \(OTP\)/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Xuất dữ liệu cá nhân/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Gửi OTP xóa tài khoản/i })).toBeInTheDocument();
  });
});
