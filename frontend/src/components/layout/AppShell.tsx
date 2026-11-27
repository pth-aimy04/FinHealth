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
  PanelLeftClose,
  PanelLeftOpen,
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
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Không gian Tổ chức',
    items: [
      { to: '/', label: 'Tổng quan', icon: LayoutDashboard, end: true },
      { to: '/portfolio', label: 'Danh bạ Doanh nghiệp', icon: Building2 },
      { to: '/batch', label: 'Thẩm định Hàng loạt', icon: FileSpreadsheet },
      { to: '/compare', label: 'So sánh Doanh nghiệp', icon: GitCompare },
    ],
  },
  {
    title: 'Thị trường & Minh bạch',
    items: [
      { to: '/us-market', label: 'Thị trường Mỹ (SEC)', icon: Globe2 },
      { to: '/methodology', label: 'Phương pháp luận', icon: BookOpen },
    ],
  },
  {
    title: 'Tổ chức & Quản trị',
    items: [
      { to: '/organization', label: 'Quản trị Tổ chức', icon: Users, authOnly: true },
      { to: '/admin', label: 'Quản trị Hệ thống', icon: Shield, adminOnly: true },
    ],
  },
];

export function AppShell() {
  const { theme, toggleTheme } = useTheme();
  const { user, isAdmin, organizations, activeOrg, switchOrg } = useAuth();
  const navigate = useNavigate();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [switchingOrg, setSwitchingOrg] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { data: orgCompanies } = useQuery({
    queryKey: ['org-companies', activeOrg?.id, 'quick-search'],
    queryFn: () => api.getOrgCompanies(),
    enabled: Boolean(user && activeOrg),
    staleTime: 60_000,
  });

  const { data: secUniverse } = useQuery({
    queryKey: ['companies', { limit: 200 }],
    queryFn: () => api.getCompanies({ limit: 200 }),
    staleTime: 120_000,
  });

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
        meta: 'Tổ chức',
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

  return (
    <div className="min-h-screen flex bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:px-3 focus:py-2 focus:rounded-[6px] focus:bg-[var(--accent-primary)] focus:text-[var(--accent-ink)] focus:text-xs"
      >
        Chuyển tới nội dung chính
      </a>

      {mobileOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/45 backdrop-blur-[1px] lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      {/* Left Navigation Rail */}
      <aside
        aria-label="Điều hướng chính"
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex flex-col bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] transition-all duration-200 lg:static',
          collapsed ? 'w-[68px]' : 'w-[256px]',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        )}
      >
        <div className="h-[56px] flex items-center justify-between px-4 border-b border-[var(--border-subtle)]">
          <Link
            to="/"
            className="flex items-center gap-2.5 min-w-0 text-[var(--text-primary)] no-underline"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] bg-[var(--accent-primary)] text-[var(--accent-ink)] font-mono text-xs font-bold shadow-xs">
              FH
            </span>
            {!collapsed ? (
              <div className="min-w-0">
                <div className="text-sm font-bold tracking-[-0.02em] leading-tight">FinHealth</div>
                <div className="text-[10px] text-[var(--text-muted)] leading-tight truncate">
                  Đánh giá Sức khỏe Tài chính
                </div>
              </div>
            ) : null}
          </Link>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1.5 rounded-[6px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            aria-label="Đóng thanh điều hướng"
          >
            <X className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className="hidden lg:inline-flex p-1.5 rounded-[6px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] cursor-pointer"
            aria-label={collapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Organization Workspace Switcher */}
        {user && activeOrg && !collapsed ? (
          <div className="px-3 py-2.5 border-b border-[var(--border-subtle)] bg-[var(--bg-subtle)]/50">
            <label
              htmlFor="org-workspace-switcher"
              className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1"
            >
              Không gian làm việc
            </label>
            <div className="relative">
              <select
                id="org-workspace-switcher"
                aria-label="Chuyển đổi tổ chức làm việc"
                value={activeOrg.id}
                disabled={switchingOrg}
                onChange={(e) => void handleOrgChange(Number(e.target.value))}
                className="w-full h-8 pl-2.5 pr-7 text-xs font-medium bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-strong)] rounded-[6px] appearance-none cursor-pointer focus:border-[var(--accent-primary)]"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-muted)]"
                aria-hidden="true"
              />
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
              <span className="truncate">{ORG_ROLE_LABELS[activeOrg.role]}</span>
              <Link
                to="/organization"
                onClick={() => setMobileOpen(false)}
                className="text-[var(--accent-primary)] hover:underline no-underline shrink-0"
              >
                Quản lý
              </Link>
            </div>
          </div>
        ) : null}

        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
          {NAV_GROUPS.map((group) => {
            const visibleItems = group.items.filter((item) => {
              if (item.adminOnly && !isAdmin) return false;
              if (item.authOnly && !user) return false;
              return true;
            });
            if (visibleItems.length === 0) return null;
            return (
              <div key={group.title} className="space-y-1">
                {!collapsed ? (
                  <div className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    {group.title}
                  </div>
                ) : null}
                {visibleItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      onClick={() => setMobileOpen(false)}
                      title={collapsed ? item.label : undefined}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-150 no-underline',
                          isActive
                            ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]',
                          collapsed && 'justify-center px-2',
                        )
                      }
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      {!collapsed ? <span className="truncate">{item.label}</span> : null}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="p-2.5 border-t border-[var(--border-subtle)]">
          <NavLink
            to="/account"
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-colors duration-150 no-underline',
                isActive
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]',
                collapsed && 'justify-center px-2',
              )
            }
          >
            <UserCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            {!collapsed ? (
              <div className="min-w-0">
                <div className="truncate leading-tight">
                  {user ? user.display_name : 'Đăng nhập / Tài khoản'}
                </div>
                {user?.job_title ? (
                  <div className="text-[11px] text-[var(--text-muted)] truncate leading-tight">
                    {user.job_title}
                  </div>
                ) : null}
              </div>
            ) : null}
          </NavLink>
        </div>
      </aside>

      {/* Main Column */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Sticky Top Command Bar */}
        <header className="sticky top-0 z-30 h-[56px] flex items-center justify-between gap-3 px-4 sm:px-6 bg-[var(--bg-surface)]/95 backdrop-blur-sm border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 -ml-1 rounded-[6px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              aria-label="Mở trình đơn điều hướng"
            >
              <Menu className="h-5 w-5" />
            </button>

            <form
              onSubmit={handleQuickSearch}
              className="relative flex-1 max-w-lg"
              role="search"
            >
              <Search
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-muted)]"
                aria-hidden="true"
              />
              <input
                ref={searchInputRef}
                type="search"
                value={searchQuery}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setTimeout(() => setSearchFocused(false), 160)}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm doanh nghiệp theo Tên, MST hoặc mã cổ phiếu (AAPL, MSFT)..."
                aria-label="Tìm nhanh doanh nghiệp theo tên, mã số thuế hoặc mã chứng khoán"
                className="w-full h-9 pl-9 pr-14 text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] border border-[var(--border-subtle)] rounded-[6px] focus:bg-[var(--bg-surface)] focus:border-[var(--accent-primary)] transition-colors"
              />
              <kbd className="hidden sm:inline-flex pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[4px]">
                Ctrl K
              </kbd>

              {searchFocused && searchSuggestions.length > 0 ? (
                <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 surface overflow-hidden divide-y divide-[var(--border-subtle)]">
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
                      className="w-full px-3.5 py-2.5 flex items-center justify-between gap-3 text-left text-xs hover:bg-[var(--bg-hover)] cursor-pointer bg-transparent border-0"
                    >
                      <div className="min-w-0 flex items-center gap-2.5">
                        <span className="font-mono font-bold text-[var(--accent-primary)] max-w-[92px] truncate shrink-0">
                          {item.badge}
                        </span>
                        <div className="min-w-0">
                          <div className="font-medium text-[var(--text-primary)] truncate">
                            {item.name}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)] truncate">
                            {item.subtitle}
                          </div>
                        </div>
                      </div>
                      <span className="num text-[11px] font-medium text-[var(--text-secondary)] shrink-0">
                        {item.meta}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </form>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {user && activeOrg ? (
              <Link
                to="/organization"
                className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-[6px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline"
                title={`Không gian làm việc: ${activeOrg.name} (${ORG_ROLE_LABELS[activeOrg.role]})`}
              >
                <Building2 className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
                <span className="max-w-[160px] truncate font-medium">{activeOrg.name}</span>
              </Link>
            ) : null}

            <button
              type="button"
              onClick={toggleTheme}
              className="h-9 w-9 inline-flex items-center justify-center rounded-[6px] border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
              aria-label={theme === 'light' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
              title={theme === 'light' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
            >
              {theme === 'light' ? (
                <Moon className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Sun className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </header>

        <main
          id="main-content"
          className="flex-1 p-4 sm:p-6 max-w-[1440px] w-full mx-auto animate-view"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
