import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Bookmark,
  Cpu,
  GitCompare,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  Search,
  Shield,
  SlidersHorizontal,
  Sun,
  Table2,
  UserCircle2,
  X,
} from 'lucide-react';
import { api } from '@/lib/api';
import { formatPct, translateSector } from '@/lib/format';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/components/ui/Primitives';

interface NavGroup {
  title: string;
  items: Array<{
    to: string;
    label: string;
    icon: typeof LayoutDashboard;
    end?: boolean;
    adminOnly?: boolean;
  }>;
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Phân tích Thị trường',
    items: [
      { to: '/', label: 'Tổng quan Thị trường', icon: LayoutDashboard, end: true },
      { to: '/screener', label: 'Sàng lọc Doanh nghiệp', icon: Table2 },
      { to: '/compare', label: 'So sánh Cùng ngành', icon: GitCompare },
      { to: '/clusters', label: 'Bản đồ Phân cụm PCA', icon: Radar },
    ],
  },
  {
    title: 'Quản trị Rủi ro & AI',
    items: [
      { to: '/stress', label: 'Mô phỏng Stress Test', icon: SlidersHorizontal },
      { to: '/models', label: 'Mô hình AI & Chấm điểm', icon: Cpu },
    ],
  },
  {
    title: 'Cá nhân & Hệ thống',
    items: [
      { to: '/workspace', label: 'Danh mục Cá nhân', icon: Bookmark },
      { to: '/admin', label: 'Quản trị Hệ thống', icon: Shield, adminOnly: true },
    ],
  },
];

export function AppShell() {
  const { theme, toggleTheme } = useTheme();
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    staleTime: 60_000,
    retry: 1,
  });

  const { data: universe } = useQuery({
    queryKey: ['companies', { limit: 200 }],
    queryFn: () => api.getCompanies({ limit: 200 }),
    staleTime: 120_000,
  });

  // Live ticker tape: top 4 highest distress + 4 flagship blue-chip issuers
  const tickerStrip = useMemo(() => {
    const list = universe ?? [];
    if (list.length === 0) return [];
    const byRisk = [...list]
      .filter((c) => typeof c.distress_probability === 'number')
      .sort((a, b) => (b.distress_probability ?? 0) - (a.distress_probability ?? 0));
    const topAlert = byRisk.slice(0, 4);
    const bluechips = ['AAPL', 'MSFT', 'NVDA', 'JNJ', 'AMZN']
      .map((t) => list.find((c) => c.ticker === t))
      .filter((c): c is NonNullable<typeof c> => Boolean(c))
      .slice(0, 4);
    const seen = new Set<string>();
    return [...topAlert, ...bluechips].filter((c) => {
      if (seen.has(c.cik)) return false;
      seen.add(c.cik);
      return true;
    });
  }, [universe]);

  const searchSuggestions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || !universe) return [];
    return universe
      .filter(
        (c) =>
          (c.ticker && c.ticker.toLowerCase().includes(q)) ||
          c.name.toLowerCase().includes(q) ||
          c.cik.includes(q),
      )
      .slice(0, 6);
  }, [searchQuery, universe]);

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

  function handleQuickSearch(event: React.FormEvent) {
    event.preventDefault();
    const cleaned = searchQuery.trim();
    if (!cleaned) return;
    if (searchSuggestions.length > 0) {
      const top = searchSuggestions[0];
      navigate(`/companies/${encodeURIComponent(top.ticker || top.cik)}`);
    } else if (/^[A-Za-z]{1,6}$/.test(cleaned) || /^\d{1,10}$/.test(cleaned)) {
      navigate(`/companies/${encodeURIComponent(cleaned.toUpperCase())}`);
    } else {
      navigate(`/screener?q=${encodeURIComponent(cleaned)}`);
    }
    setSearchQuery('');
    setSearchFocused(false);
    searchInputRef.current?.blur();
  }

  return (
    <div className="min-h-screen flex bg-[var(--bg-canvas)] text-[var(--text-primary)]">
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
          collapsed ? 'w-[68px]' : 'w-[248px]',
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
                  Phân tích Rủi ro Tài chính
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

        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
          {NAV_GROUPS.map((group) => {
            const visibleItems = group.items.filter((i) => !i.adminOnly || isAdmin);
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
              <span className="truncate">
                {user ? user.display_name : 'Đăng nhập / Tài khoản'}
              </span>
            ) : null}
          </NavLink>
        </div>
      </aside>

      {/* Main Column */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Live Market Risk Ticker Strip */}
        {tickerStrip.length > 0 ? (
          <div className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] px-4 py-1.5 overflow-x-auto">
            <div className="flex items-center gap-4 text-[11px] whitespace-nowrap max-w-[1440px] mx-auto">
              <span className="font-semibold text-[var(--text-muted)] uppercase tracking-wider shrink-0">
                Nhịp rủi ro SEC
              </span>
              {tickerStrip.map((item) => {
                const lvl = (item.risk_level ?? '').toUpperCase();
                const dotColor =
                  lvl === 'CRITICAL'
                    ? '#BE123C'
                    : lvl === 'HIGH'
                      ? '#EA580C'
                      : lvl === 'MEDIUM'
                        ? '#D97706'
                        : '#0D7A68';
                return (
                  <Link
                    key={item.cik}
                    to={`/companies/${encodeURIComponent(item.ticker || item.cik)}`}
                    className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[4px] hover:bg-[var(--bg-surface)] text-[var(--text-primary)] no-underline transition-colors"
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: dotColor }}
                    />
                    <span className="font-mono font-semibold">{item.ticker ?? item.cik}</span>
                    <span className="num text-[var(--text-secondary)]">
                      {formatPct(item.distress_probability)}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ) : null}

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
                placeholder="Tìm nhanh mã cổ phiếu (AAPL, MSFT, PLUG), tên công ty hoặc CIK..."
                aria-label="Tìm nhanh mã chứng khoán, tên công ty hoặc CIK"
                className="w-full h-9 pl-9 pr-14 text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] border border-[var(--border-subtle)] rounded-[6px] focus:bg-[var(--bg-surface)] focus:border-[var(--accent-primary)] transition-colors"
              />
              <kbd className="hidden sm:inline-flex pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-[4px]">
                Ctrl K
              </kbd>

              {/* Live Search Autocomplete Popover */}
              {searchFocused && searchSuggestions.length > 0 ? (
                <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 surface overflow-hidden divide-y divide-[var(--border-subtle)]">
                  {searchSuggestions.map((item) => (
                    <button
                      key={item.cik}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        navigate(`/companies/${encodeURIComponent(item.ticker || item.cik)}`);
                        setSearchQuery('');
                        setSearchFocused(false);
                      }}
                      className="w-full px-3.5 py-2.5 flex items-center justify-between gap-3 text-left text-xs hover:bg-[var(--bg-hover)] cursor-pointer bg-transparent border-0"
                    >
                      <div className="min-w-0 flex items-center gap-2.5">
                        <span className="font-mono font-bold text-[var(--accent-primary)] w-12 shrink-0">
                          {item.ticker ?? '—'}
                        </span>
                        <div className="min-w-0">
                          <div className="font-medium text-[var(--text-primary)] truncate">
                            {item.name}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)] truncate">
                            {translateSector(item.sector)}
                          </div>
                        </div>
                      </div>
                      <span className="num text-[11px] font-semibold text-[var(--text-secondary)] shrink-0">
                        {formatPct(item.distress_probability)}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </form>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <div
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-[6px] bg-[var(--bg-subtle)] border border-[var(--border-subtle)]"
              title={
                health
                  ? `Cơ sở dữ liệu: ${health.database_connected ? 'Trực tuyến' : 'Gián đoạn'} · Mô hình: ${health.active_model_version ?? 'Chưa có'}`
                  : 'Đang kiểm tra trạng thái hệ thống'
              }
            >
              <Activity
                className="h-3.5 w-3.5"
                style={{
                  color: health?.database_connected
                    ? 'var(--risk-low-fg)'
                    : 'var(--risk-medium-fg)',
                }}
                aria-hidden="true"
              />
              <span className="num font-medium text-[var(--text-secondary)]">
                {health?.active_model_version ?? 'API'}
              </span>
            </div>

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

        <main id="main-content" className="flex-1 p-4 sm:p-6 max-w-[1440px] w-full mx-auto animate-view">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
