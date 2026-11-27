import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OrganizationPage } from '@/pages/OrganizationPage';
import { api } from '@/lib/api';

const mockUseAuth = vi.fn();

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

function renderOrgPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OrganizationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('OrganizationPage RBAC visibility', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'getOrganizationMembers').mockResolvedValue([
      {
        user_id: 1,
        email: 'admin@org.vn',
        display_name: 'Admin Org',
        job_title: 'CFO',
        role: 'org_admin',
        joined_at: '2026-01-01T00:00:00Z',
      },
      {
        user_id: 2,
        email: 'viewer@org.vn',
        display_name: 'Viewer Org',
        job_title: null,
        role: 'viewer',
        joined_at: '2026-01-02T00:00:00Z',
      },
    ]);
  });

  it('hides invite, role-change, member-removal, and audit controls from viewer role', async () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: 2,
        email: 'viewer@org.vn',
        display_name: 'Viewer Org',
        role: 'user',
        active: true,
        email_verified: true,
      },
      organizations: [
        {
          id: 10,
          name: 'Tổ chức Thử nghiệm',
          slug: 'org-test',
          is_personal: false,
          role: 'viewer',
          member_count: 2,
          is_active_workspace: true,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      activeOrg: {
        id: 10,
        name: 'Tổ chức Thử nghiệm',
        slug: 'org-test',
        is_personal: false,
        role: 'viewer',
        member_count: 2,
        is_active_workspace: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      switchOrg: vi.fn(),
      refreshOrganizations: vi.fn(),
    });

    renderOrgPage();

    await waitFor(() => expect(screen.getByText('Admin Org')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /Mời thành viên/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Gỡ/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Nhật ký kiểm toán tổ chức/i)).not.toBeInTheDocument();
  });
});
