import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';

describe('api client V1.0 contracts', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('verifyEmail sends email, challenge, code, and new_password', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: 'Đã xác thực email.' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await api.verifyEmail('user@example.com', 'c'.repeat(32), '123456', 'StrongPass123!');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/verify-email');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({
      email: 'user@example.com',
      challenge: 'c'.repeat(32),
      code: '123456',
      new_password: 'StrongPass123!',
    });
  });

  it('compareCompanies sends common_fiscal_year and never sends period_policy', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ companies: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await api.compareCompanies(['AAPL', 'MSFT'], 2024);

    const [urlWithYear] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(urlWithYear).toContain('/api/v1/companies/compare?');
    expect(urlWithYear).toContain('identifiers=AAPL%2CMSFT');
    expect(urlWithYear).toContain('common_fiscal_year=2024');
    expect(urlWithYear).not.toContain('period_policy');

    await api.compareCompanies(['AAPL', 'MSFT']);
    const [urlLatest] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(urlLatest).toContain('identifiers=AAPL%2CMSFT');
    expect(urlLatest).not.toContain('common_fiscal_year');
    expect(urlLatest).not.toContain('period_policy');
  });

  it('compareOrgCompanies targets /api/v1/org/companies/compare with ids and common_fiscal_year', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ companies: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await api.compareOrgCompanies([11, 22], 2025);

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/org/companies/compare?ids=11%2C22&common_fiscal_year=2025');
  });
});
