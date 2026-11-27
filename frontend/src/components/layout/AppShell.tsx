import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  Building2,
  ChevronDown,
  FileSpreadsheet,
  GitCompare,
  Globe2,
  LayoutDashboard,
  Menu,
  Moon,
  Search,
  Shield,
  Sun,
  UserCircle2,
  Users,
  X,
} from 'lucide-react';
import { api } from '@/lib/api';
import { ORG_ROLE_LABELS, formatPct, translateSector } from '@/lib/format';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/components/ui/Primitives';

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  adminOnly?: boolean;
  authOnly?: boolean;
  section: 'workspace' | 'market' | 'governance';
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Tổng quan', icon: LayoutDashboard, end: true, section: 'workspace' },
  { to: '/portfolio', label: 'Danh bạ Doanh nghiệp', icon: Building2, section: 'workspace' },
  { to: '/batch', label: 'Thẩm định Hàng loạt', icon: FileSpreadsheet, section: 'workspace' },
  { to: '/compare', label: 'So sánh Doanh nghiệp', icon: GitCompare, section: 'workspace' },
  { to: '/us-market', label: 'Thị trường Mỹ (SEC)', icon: Globe2, section: 'market' },
  { to: '/methodology', label: 'Phương pháp luận', icon: BookOpen, section: 'market' },
  {
    to: '/organization',
    label: 'Quản trị Tổ chức',
    icon: Users,
    authOnly: true,
    section: 'governance',
  },
  {
    to: '/admin',
    label: 'Quản trị Hệ thống',
    icon: Shield,
    adminOnly: true,
    section: 'governance',
  },
];

function BrandMark() {
  return (
    <svg
      viewBox="0 0 28 28"
      className="h-7 w-7 shrink-0"
      aria-hidden="true"
    >
      <rect
        x="1"
        y="1"
        width="26"
        height="26"
        rx="2"
        fill="#13294B"
        stroke="#E0A83B"
        strokeWidth="1.5"
      />
      <rect x="6" y="15" width="3.5" height="7" fill="#9FB6D4" />
      <rect x="12.25" y="10.5" width="3.5" height="11.5" fill="#F8FAFC" />
      <rect x="18.5" y="6.5" width="3.5" height="15.5" fill="#E0A83B" />
      <line x1="5" y1="22.5" x2="23" y2="22.5" stroke="#5A769C" strokeWidth="1" />
    </svg>
  );
}

export function AppShell() {
  const { theme, toggleTheme } = useTheme();
  const { user, isAdmin, organizations, activeOrg, switchOrg } = useAuth();
  const navigate = useNavigate();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [switchingOrg, setSwitchingOrg] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { data: orgCompanies } = useQuery({
    queryKey: ['org', activeOrg?.id, 'companies', 'quick-search'],
    queryFn: () => api.getOrgCompanies(),
    enabled: Boolean(user && activeOrg),
    staleTime: 60_000,
  });

  const { data: secUniverse } = useQuery({
    queryKey: ['companies', { limit: 200 }],
    queryFn: () => api.getCompanies({ limit: 200 }),
    staleTime: 120_000,
  });

  const visibleNav = useMemo(
    () =>
      NAV_ITEMS.filter((item) => {
        if (item.adminOnly && !isAdmin) return false;
        if (item.authOnly && !user) return false;
        return true;
      }),
    [isAdmin, user],
  );

  const workspaceNav = visibleNav.filter((i) => i.section === 'workspace');
  const marketNav = visibleNav.filter((i) => i.section === 'market');
  const governanceNav = visibleNav.filter((i) => i.section === 'governance');

  const searchSuggestions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];

    const orgMatches = (orgCompanies ?? [])
      .filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.tax_code && c.tax_code.toLowerCase().includes(q)) ||
          (c.ticker && c.ticker.toLowerCase().includes(q)),
      )
      .slice(0, 4)
      .map((c) => ({
        key: `org-${c.id}`,
        badge: c.ticker ?? c.tax_code ?? 'DN',
        name: c.name,
        subtitle: c.sector_name ?? 'Danh bạ Tổ chức · VND',
        meta: 'Nội bộ (VND)',
        to: `/portfolio/${c.id}`,
      }));

    const secMatches = (secUniverse ?? [])
      .filter(
        (c) =>
          (c.ticker && c.ticker.toLowerCase().includes(q)) ||
          c.name.toLowerCase().includes(q) ||
          c.cik.includes(q),
      )
      .slice(0, 4)
      .map((c) => ({
        key: `sec-${c.cik}`,
        badge: c.ticker ?? c.cik,
        name: c.name,
        subtitle: `${translateSector(c.sector)} · SEC (USD)`,
        meta: formatPct(c.distress_probability),
        to: `/us-market/${encodeURIComponent(c.ticker || c.cik)}`,
      }));

    return [...orgMatches, ...secMatches].slice(0, 6);
  }, [searchQuery, orgCompanies, secUniverse]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === 'Escape') {
        setSearchFocused(false);
        setMobileOpen(false);
        searchInputRef.current?.blur();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  async function handleOrgChange(nextOrgId: number) {
    if (!nextOrgId || nextOrgId === activeOrg?.id) return;
    setSwitchingOrg(true);
    try {
      await switchOrg(nextOrgId);
    } finally {
      setSwitchingOrg(false);
    }
  }

  function handleQuickSearch(event: React.FormEvent) {
    event.preventDefault();
    const cleaned = searchQuery.trim();
    if (!cleaned) return;
    if (searchSuggestions.length > 0) {
      navigate(searchSuggestions[0].to);
    } else if (/^\d{10}(?:-\d{3})?$/.test(cleaned)) {
      navigate(`/portfolio?q=${encodeURIComponent(cleaned)}`);
    } else if (/^[A-Za-z]{1,6}$/.test(cleaned)) {
      navigate(`/us-market/${encodeURIComponent(cleaned.toUpperCase())}`);
    } else {
      navigate(`/portfolio?q=${encodeURIComponent(cleaned)}`);
    }
    setSearchQuery('');
    setSearchFocused(false);
    searchInputRef.current?.blur();
  }

  const userInitials = user?.display_name
    ? user.display_name
        .trim()
        .split(/\s+/)
        .slice(-2)
        .map((w) => w[0]?.toUpperCase() ?? '')
        .join('')
    : '';

  return (
    <div className="min-h-screen flex flex-col overflow-x-clip bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      {/* Two-Tier Institutional Capital Navy Masthead */}
      <header className="sticky top-0 z-40">
        {/* Tier 1: Brand, Command Search Omnibox, Workspace Switcher & Account */}
        <div className="bg-[var(--chrome-bg)] text-[var(--chrome-ink)] border-b border-[var(--chrome-border)]">
          <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-2.5 md:py-0 md:h-[56px] flex flex-wrap md:flex-nowrap items-center justify-between gap-x-3 gap-y-2">
            {/* Left: Mobile Trigger + Institutional Brand Wordmark */}
            <div className="order-1 flex items-center gap-2.5 sm:gap-3 shrink-0">
              <button
                type="button"
                onClick={() => setMobileOpen((prev) => !prev)}
                className="lg:hidden h-9 w-9 inline-flex items-center justify-center rounded-[3px] border border-[var(--chrome-border)] text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-[var(--chrome-surface)] cursor-pointer bg-transparent"
                aria-label={mobileOpen ? 'Đóng thanh điều hướng' : 'Mở trình đơn điều hướng'}
                aria-expanded={mobileOpen}
              >
                {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
              </button>

              <Link
                to="/"
                className="flex items-center gap-2.5 text-[var(--chrome-ink)] no-underline group"
              >
                <BrandMark />
                <div className="flex items-center gap-2.5">
                  <span className="font-editorial text-[19px] font-bold tracking-[-0.02em] leading-none text-white">
                    FinHealth
                  </span>
                  <span
                    className="hidden xl:inline-block h-4 w-px bg-[var(--chrome-border)]"
                    aria-hidden="true"
                  />
                  <span className="hidden xl:inline-block text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--chrome-ink-muted)] leading-none">
                    Phân tích Tín dụng & Tài chính
                  </span>
                </div>
              </Link>
            </div>

            {/* Center: Institutional Omnibox Search */}
            <form
              onSubmit={handleQuickSearch}
              className="order-3 md:order-2 relative w-full md:w-auto md:flex-1 min-w-0 md:max-w-xl"
              role="search"
            >
              <Search
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--chrome-ink-muted)]"
                aria-hidden="true"
              />
              <input
                ref={searchInputRef}
                type="search"
                value={searchQuery}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setTimeout(() => setSearchFocused(false), 160)}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm nhanh doanh nghiệp (Tên, MST, hoặc mã CK: AAPL, MSFT)..."
                aria-label="Tìm nhanh doanh nghiệp theo tên, mã số thuế hoặc mã chứng khoán"
                className="w-full h-9 pl-9 pr-3 sm:pr-14 text-[13px] bg-[var(--chrome-surface)] text-white placeholder:text-[var(--chrome-ink-muted)] border border-[var(--chrome-border)] rounded-[3px] focus:outline-none focus:border-[var(--chrome-accent)] transition-colors"
              />
              <kbd className="hidden sm:inline-flex pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-[var(--chrome-ink-secondary)] bg-[var(--chrome-bg)] border border-[var(--chrome-border)] rounded-[2px]">
                Ctrl K
              </kbd>

              {searchFocused && searchSuggestions.length > 0 ? (
                <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 surface-popover overflow-hidden divide-y divide-[var(--border-subtle)] text-[var(--text-primary)]">
                  {searchSuggestions.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        navigate(item.to);
                        setSearchQuery('');
                        setSearchFocused(false);
                      }}
                      className="w-full px-3.5 py-2.5 flex items-center justify-between gap-3 text-left text-[13px] hover:bg-[var(--bg-hover)] cursor-pointer bg-transparent border-0"
                    >
                      <div className="min-w-0 flex items-center gap-2.5">
                        <span className="font-mono text-xs font-semibold px-1.5 py-0.5 rounded-[2px] bg-[var(--accent-soft)] text-[var(--accent-primary)] border border-[var(--accent-border)] max-w-[104px] truncate shrink-0">
                          {item.badge}
                        </span>
                        <div className="min-w-0">
                          <div className="font-semibold text-[var(--text-primary)] truncate">
                            {item.name}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)] truncate">
                            {item.subtitle}
                          </div>
                        </div>
                      </div>
                      <span className="num text-xs font-semibold text-[var(--text-secondary)] shrink-0">
                        {item.meta}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </form>

            {/* Right: Org Switcher + Theme + Account */}
            <div className="order-2 md:order-3 flex items-center gap-2 shrink-0">
              {user && activeOrg ? (
                <div className="hidden md:flex items-center gap-1.5">
                  <div className="relative flex items-center">
                    <Building2
                      className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--chrome-accent)]"
                      aria-hidden="true"
                    />
                    <select
                      id="org-workspace-switcher"
                      aria-label="Chuyển đổi tổ chức làm việc"
                      value={activeOrg.id}
                      disabled={switchingOrg}
                      onChange={(e) => void handleOrgChange(Number(e.target.value))}
                      className="h-9 pl-8 pr-7 max-w-[200px] text-xs font-semibold bg-[var(--chrome-surface)] text-[var(--chrome-ink)] border border-[var(--chrome-border)] rounded-[3px] appearance-none cursor-pointer hover:bg-[var(--chrome-surface-hover)] focus:outline-none focus:border-[var(--chrome-accent)] truncate"
                    >
                      {organizations.map((org) => (
                        <option
                          key={org.id}
                          value={org.id}
                          className="bg-[#0B1A30] text-white"
                        >
                          {org.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-[var(--chrome-ink-muted)]"
                      aria-hidden="true"
                    />
                  </div>
                </div>
              ) : null}

              <button
                type="button"
                onClick={toggleTheme}
                className="h-9 w-9 inline-flex items-center justify-center rounded-[3px] border border-[var(--chrome-border)] bg-[var(--chrome-surface)] text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-[var(--chrome-surface-hover)] cursor-pointer transition-colors"
                aria-label={theme === 'light' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
                title={theme === 'light' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
              >
                {theme === 'light' ? (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                )}
              </button>

              <NavLink
                to="/account"
                className={({ isActive }) =>
                  cn(
                    'h-9 inline-flex items-center gap-2 px-2.5 rounded-[3px] border text-xs font-semibold no-underline transition-colors',
                    isActive
                      ? 'bg-[var(--chrome-surface-hover)] border-[var(--chrome-accent)] text-white'
                      : 'bg-[var(--chrome-surface)] border-[var(--chrome-border)] text-[var(--chrome-ink)] hover:bg-[var(--chrome-surface-hover)]',
                  )
                }
              >
                {user ? (
                  <>
                    <span className="h-5 w-5 rounded-[2px] bg-[var(--chrome-accent)] text-[#0B1A30] font-mono text-[10px] font-bold inline-flex items-center justify-center shrink-0">
                      {userInitials || 'U'}
                    </span>
                    <span className="hidden sm:inline max-w-[120px] truncate">
                      {user.display_name}
                    </span>
                  </>
                ) : (
                  <>
                    <UserCircle2 className="h-4 w-4 text-[var(--chrome-accent)] shrink-0" aria-hidden="true" />
                    <span className="hidden sm:inline">Đăng nhập / Tài khoản</span>
                  </>
                )}
              </NavLink>
            </div>
          </div>
        </div>

        {/* Tier 2: Horizontal Institutional Module Navigation Bar (Desktop) */}
        <div className="hidden lg:block bg-[var(--chrome-sub)] border-b border-[var(--chrome-border)]">
          <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-[42px] flex items-center justify-between gap-4">
            <nav aria-label="Điều hướng chính" className="flex items-center h-full gap-1">
              {workspaceNav.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        'h-full inline-flex items-center gap-1.5 px-3 text-[13px] font-medium no-underline border-b-2 transition-colors',
                        isActive
                          ? 'border-[var(--chrome-accent)] text-white bg-white/[0.06] font-semibold'
                          : 'border-transparent text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-white/[0.04]',
                      )
                    }
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 opacity-85" aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}

              <span
                className="mx-2 h-4 w-px bg-[var(--chrome-border)] shrink-0"
                aria-hidden="true"
              />

              {marketNav.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        'h-full inline-flex items-center gap-1.5 px-3 text-[13px] font-medium no-underline border-b-2 transition-colors',
                        isActive
                          ? 'border-[var(--chrome-accent)] text-white bg-white/[0.06] font-semibold'
                          : 'border-transparent text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-white/[0.04]',
                      )
                    }
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 opacity-85" aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            {governanceNav.length > 0 ? (
              <div className="flex items-center h-full gap-1">
                {governanceNav.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        cn(
                          'h-full inline-flex items-center gap-1.5 px-3 text-[13px] font-medium no-underline border-b-2 transition-colors',
                          isActive
                            ? 'border-[var(--chrome-accent)] text-white bg-white/[0.06] font-semibold'
                            : 'border-transparent text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-white/[0.04]',
                        )
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0 opacity-85" aria-hidden="true" />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/55"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside
            aria-label="Điều hướng di động"
            className="relative z-10 w-[290px] max-w-[85vw] h-full bg-[var(--chrome-bg)] text-[var(--chrome-ink)] border-r border-[var(--chrome-border)] flex flex-col"
          >
            <div className="h-[56px] px-4 flex items-center justify-between border-b border-[var(--chrome-border)]">
              <div className="flex items-center gap-2.5">
                <BrandMark />
                <span className="font-editorial text-lg font-bold text-white">FinHealth</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="h-9 w-9 inline-flex items-center justify-center rounded-[3px] text-[var(--chrome-ink-secondary)] hover:bg-[var(--chrome-surface)] bg-transparent border-0 cursor-pointer"
                aria-label="Đóng thanh điều hướng"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {user && activeOrg ? (
              <div className="p-4 border-b border-[var(--chrome-border)] bg-[var(--chrome-sub)] space-y-1.5">
                <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--chrome-ink-muted)]">
                  Tổ chức đang hoạt động
                </div>
                <select
                  aria-label="Chuyển đổi tổ chức trên di động"
                  value={activeOrg.id}
                  disabled={switchingOrg}
                  onChange={(e) => void handleOrgChange(Number(e.target.value))}
                  className="w-full h-10 px-3 text-xs font-semibold bg-[var(--chrome-surface)] text-white border border-[var(--chrome-border)] rounded-[3px]"
                >
                  {organizations.map((org) => (
                    <option key={org.id} value={org.id} className="bg-[#0B1A30] text-white">
                      {org.name}
                    </option>
                  ))}
                </select>
                <div className="text-[11px] text-[var(--chrome-ink-secondary)]">
                  Vai trò: {ORG_ROLE_LABELS[activeOrg.role]}
                </div>
              </div>
            ) : null}

            <nav className="flex-1 overflow-y-auto p-3 space-y-1">
              {visibleNav.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'min-h-[44px] flex items-center gap-3 px-3 py-2.5 rounded-[3px] text-sm font-medium no-underline transition-colors',
                        isActive
                          ? 'bg-[var(--chrome-surface)] text-white border-l-2 border-l-[var(--chrome-accent)] font-semibold'
                          : 'text-[var(--chrome-ink-secondary)] hover:text-white hover:bg-white/[0.05]',
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>

            <div className="p-3 border-t border-[var(--chrome-border)]">
              <Link
                to="/account"
                onClick={() => setMobileOpen(false)}
                className="min-h-[44px] flex items-center gap-2.5 px-3 py-2 rounded-[3px] bg-[var(--chrome-surface)] text-white text-sm font-medium no-underline"
              >
                <UserCircle2 className="h-4 w-4 text-[var(--chrome-accent)] shrink-0" />
                <div className="min-w-0">
                  <div className="truncate">{user ? user.display_name : 'Đăng nhập / Tài khoản'}</div>
                  {user?.job_title ? (
                    <div className="text-[11px] text-[var(--chrome-ink-muted)] truncate">
                      {user.job_title}
                    </div>
                  ) : null}
                </div>
              </Link>
            </div>
          </aside>
        </div>
      ) : null}

      {/* Full-Width Institutional Workspace Canvas */}
      <main
        id="main-content"
        className="flex-1 min-w-0 w-full max-w-[1440px] mx-auto px-4 sm:px-6 py-5 sm:py-6 animate-view"
      >
        <Outlet />
      </main>

      {/* Subtle Institutional Regulatory Footer */}
      <footer className="border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] mt-8">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--text-muted)]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-semibold text-[var(--text-secondary)]">FinHealth</span>
            <span>Chuẩn kế toán TT99/2025 · TT200 · TT133 & SEC EDGAR</span>
          </div>
          <div>
            Công cụ phân tích định lượng nội bộ — Không phải dịch vụ xếp hạng tín nhiệm theo Nghị định 88/2014/NĐ-CP.
          </div>
        </div>
      </footer>
    </div>
  );
}
