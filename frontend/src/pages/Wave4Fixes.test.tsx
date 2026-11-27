import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { mapPdToSingleHealthScore } from '@/pages/OverviewPage';
import { OrgStatementEditorPage } from '@/pages/OrgStatementEditorPage';

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'analyst@finhealth.vn',
      display_name: 'Analyst',
      role: 'user',
      active: true,
      email_verified: true,
    },
    activeOrg: {
      id: 1,
      name: 'Test Org',
      slug: 'test-org',
      is_personal: true,
      role: 'org_admin',
      member_count: 1,
      is_active_workspace: true,
      created_at: '2026-01-01T00:00:00Z',
    },
    activeOrgRole: 'org_admin',
    isLoading: false,
    isAdmin: false,
    organizations: [],
    isOrgsLoading: false,
    refreshAuth: vi.fn(),
    refreshOrganizations: vi.fn(),
    switchOrg: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getOrgCompany: vi.fn().mockResolvedValue({
        id: 1,
        organization_id: 1,
        name: 'Công ty CP Sản xuất Minh An',
        tax_code: '0109990001',
        ticker: 'MAN',
        sector_code: 'C25',
        sector_name: 'Sản xuất kim loại',
        business_type: 'manufacturing',
        listing_status: 'unlisted',
        relationship_tag: 'own_company',
        archived: false,
        is_sample: true,
        scoring_eligible: true,
        scoring_exclusion_reason: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }),
    },
  };
});

describe('Wave 4 Go-Live Regressions', () => {
  it('aligns mapPdToSingleHealthScore with backend 80/60/35 log-compressed scale', () => {
    expect(mapPdToSingleHealthScore(0)).toBe(100);
    expect(mapPdToSingleHealthScore(0.005)).toBe(90);
    expect(mapPdToSingleHealthScore(0.01)).toBe(80);
    expect(mapPdToSingleHealthScore(0.02)).toBe(70);
    expect(mapPdToSingleHealthScore(0.03)).toBe(60);
    expect(mapPdToSingleHealthScore(0.055)).toBe(47.5);
    expect(mapPdToSingleHealthScore(0.08)).toBe(35);
    // Log-compressed tail for CRITICAL (>=8%)
    const criticalScore = mapPdToSingleHealthScore(0.25);
    expect(criticalScore).not.toBeNull();
    expect(criticalScore!).toBeGreaterThan(10);
    expect(criticalScore!).toBeLessThan(25);
    expect(mapPdToSingleHealthScore(1)).toBe(0);
  });

  it('renders StatementEditorForm on /portfolio/:id/statements/new without redirecting away', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/portfolio/1/statements/new']}>
          <Routes>
            <Route path="/portfolio/:id/statements/new" element={<OrgStatementEditorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(/Nhập Báo cáo Tài chính 3 phần/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Quay lại hồ sơ Công ty CP Sản xuất Minh An/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Lưu nháp/i })).toBeInTheDocument();
  });
});
