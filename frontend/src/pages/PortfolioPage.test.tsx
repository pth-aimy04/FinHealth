import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PortfolioPage } from '@/pages/PortfolioPage';
import { api } from '@/lib/api';

const mockUseAuth = vi.fn();

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

function renderPortfolioPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PortfolioPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioPage RBAC and FI exclusion indicator', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'getOrgCompanies').mockResolvedValue([
      {
        id: 1,
        organization_id: 10,
        name: 'Công ty CP Sản xuất Minh An',
        tax_code: '0101234567',
        ticker: null,
        sector_code: 'C',
        sector_name: 'Sản xuất công nghiệp',
        business_type: 'manufacturing',
        listing_status: 'unlisted',
        relationship_tag: 'customer',
        archived: false,
        is_sample: true,
        scoring_eligible: true,
        scoring_exclusion_reason: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
      {
        id: 2,
        organization_id: 10,
        name: 'Ngân hàng TMCP Mẫu',
        tax_code: '0109999999',
        ticker: 'MBB',
        sector_code: 'K',
        sector_name: 'Ngân hàng',
        business_type: 'financial_institution',
        listing_status: 'listed',
        relationship_tag: 'portfolio',
        archived: false,
        is_sample: false,
        scoring_eligible: false,
        scoring_exclusion_reason: 'Tổ chức tài chính không thuộc phạm vi chấm điểm.',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    ]);
  });

  it('hides create, seed, import, archive, and delete actions from viewer role', async () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: 2,
        email: 'viewer@org.vn',
        display_name: 'Viewer',
        role: 'user',
        active: true,
        email_verified: true,
      },
      activeOrg: {
        id: 10,
        name: 'Tổ chức A',
        slug: 'org-a',
        is_personal: false,
        role: 'viewer',
        member_count: 2,
        is_active_workspace: true,
        created_at: '2026-01-01T00:00:00Z',
      },
      activeOrgRole: 'viewer',
    });

    renderPortfolioPage();

    await waitFor(() =>
      expect(screen.getByText('Công ty CP Sản xuất Minh An')).toBeInTheDocument(),
    );
    expect(screen.getByText('Loại trừ (TCTC)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Thêm doanh nghiệp/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Nhập BCTC/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Nạp 3 DN mẫu/i })).not.toBeInTheDocument();
  });
});
