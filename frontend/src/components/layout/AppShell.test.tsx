import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';

const mockUseAuth = vi.fn();

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('@/context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getOrgCompanies: vi.fn().mockResolvedValue([]),
      getCompanies: vi.fn().mockResolvedValue([]),
    },
  };
});

function renderAppShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<div>Overview Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AppShell navigation and workspace governance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hides Admin, ModelLab, and ClusterMap from normal users while showing both parallel spaces', () => {
    const switchOrg = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: 'analyst@finhealth.vn',
        display_name: 'Nguyễn Văn A',
        job_title: 'Chuyên viên Tín dụng',
        role: 'user',
        active: true,
        email_verified: true,
      },
      isLoading: false,
      isAdmin: false,
      organizations: [
        {
          id: 10,
          name: 'Không gian Minh An',
          slug: 'minh-an',
          is_personal: true,
          role: 'org_admin',
          member_count: 2,
          is_active_workspace: true,
          created_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 11,
          name: 'Phòng Rủi ro KHDN',
          slug: 'khdn',
          is_personal: false,
          role: 'analyst',
          member_count: 5,
          is_active_workspace: false,
          created_at: '2026-01-02T00:00:00Z',
        },
      ],
      activeOrg: {
        id: 10,
        name: 'Không gian Minh An',
        slug: 'minh-an',
        is_personal: true,
        role: 'org_admin',
        member_count: 2,
        is_active_workspace: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      activeOrgRole: 'org_admin',
      isOrgsLoading: false,
      refreshAuth: vi.fn(),
      refreshOrganizations: vi.fn(),
      switchOrg,
      logout: vi.fn(),
    });

    renderAppShell();

    expect(screen.getByText('Danh bạ Doanh nghiệp')).toBeInTheDocument();
    expect(screen.getByText('Thị trường Mỹ (SEC)')).toBeInTheDocument();
    expect(screen.getByText('Thẩm định Hàng loạt')).toBeInTheDocument();
    expect(screen.getByText('So sánh Doanh nghiệp')).toBeInTheDocument();
    expect(screen.getByText('Phương pháp luận')).toBeInTheDocument();

    // End-user navigation must never expose ML/Admin technical routes
    expect(screen.queryByText(/Quản trị Hệ thống/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ModelLab|Mô hình AI|Phân cụm PCA|Cluster/i)).not.toBeInTheDocument();

    // Org switcher works
    const switcher = screen.getByLabelText('Chuyển đổi tổ chức làm việc');
    fireEvent.change(switcher, { target: { value: '11' } });
    expect(switchOrg).toHaveBeenCalledWith(11);
  });

  it('shows Admin navigation only for system admins', () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: 99,
        email: 'admin@finhealth.vn',
        display_name: 'Admin',
        role: 'admin',
        active: true,
        email_verified: true,
      },
      isLoading: false,
      isAdmin: true,
      organizations: [],
      activeOrg: null,
      activeOrgRole: null,
      isOrgsLoading: false,
      refreshAuth: vi.fn(),
      refreshOrganizations: vi.fn(),
      switchOrg: vi.fn(),
      logout: vi.fn(),
    });

    renderAppShell();
    expect(screen.getByText('Quản trị Hệ thống')).toBeInTheDocument();
  });
});
