import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";
import {
  NavLink,
  Outlet,
  Route,
  Routes,
  Link,
  useLocation,
  useNavigate,
  Navigate,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BellRing,
  ChartNoAxesCombined,
  ChevronRight,
  FileText,
  FolderHeart,
  LayoutDashboard,
  Menu,
  Moon,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  Users,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { request, type Schema } from "../lib/api/client";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import { QueryState } from "../components/shared";
import { useSession } from "./session";
const Overview = lazy(() => import("../features/overview"));
const Screener = lazy(() => import("../features/screener"));
const Company = lazy(() => import("../features/company"));
const Comparison = lazy(() => import("../features/comparison"));
const Reports = lazy(() => import("../features/reports"));
const Models = lazy(() => import("../features/models"));
const Prediction = lazy(() => import("../features/prediction"));
const Workspace = lazy(() => import("../features/workspace"));
const Accounts = lazy(() => import("../features/accounts"));
const Admin = lazy(() => import("../features/admin"));
const navigation = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard },
  { to: "/screener", label: "Sàng lọc doanh nghiệp", icon: Search },
  { to: "/compare", label: "So sánh doanh nghiệp", icon: Users },
  { to: "/reports", label: "Kho báo cáo", icon: FileText },
  { to: "/models", label: "Mô hình & phân cụm", icon: ChartNoAxesCombined },
  { to: "/prediction", label: "Dự báo tự nhập", icon: Activity },
];
/** Persistent research navigation with role-dependent administrative entry. */
function Navigation({ onNavigate }: { onNavigate?: () => void }): ReactElement {
  const { user } = useSession();
  return (
    <nav aria-label="Điều hướng chính">
      <p className="nav-label">PHÂN TÍCH & NGHIÊN CỨU</p>
      <div className="nav-links">
        {navigation.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <Icon size={18} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </div>
      <p className="nav-label mt-8">KHÔNG GIAN CÁ NHÂN</p>
      <div className="nav-links">
        <NavLink
          to="/workspace"
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          onClick={onNavigate}
        >
          <FolderHeart size={18} aria-hidden="true" />
          Workspace
        </NavLink>
        <NavLink
          to="/account"
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          onClick={onNavigate}
        >
          <Settings2 size={18} aria-hidden="true" />
          Tài khoản
        </NavLink>
        {user?.role === "admin" && (
          <NavLink
            to="/admin"
            onClick={onNavigate}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            <ShieldCheck size={18} aria-hidden="true" />
            Quản trị hệ thống
          </NavLink>
        )}
      </div>
    </nav>
  );
}
/** Responsive shell, theme persistence and accessible route focus. */
function Shell(): ReactElement {
  const [mobile, setMobile] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("finhealth-theme") === "light"
        ? "light"
        : "dark";
    } catch {
      return "dark";
    }
  });
  const { user } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const main = useRef<HTMLElement>(null);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => request<Schema["HealthCheckSchema"]>("/health"),
    staleTime: 60_000,
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("finhealth-theme", theme);
    } catch {
      /* Theme remains in memory when storage is unavailable. */
    }
  }, [theme]);
  useEffect(() => {
    main.current?.focus();
    window.scrollTo({ top: 0, behavior: "instant" });
    document.title = `FinHealth · ${navigation.find((item) => item.to === location.pathname)?.label ?? "Nghiên cứu doanh nghiệp"}`;
  }, [location.pathname]);
  const section =
    navigation.find((item) => item.to === location.pathname)?.label ??
    (location.pathname.startsWith("/company")
      ? "Phân tích doanh nghiệp"
      : location.pathname === "/workspace"
        ? "Workspace cá nhân"
        : location.pathname === "/admin"
          ? "Quản trị hệ thống"
          : "Tài khoản");
  return (
    <div className="shell">
      <a href="#main-content" className="skip-link">
        Đến nội dung chính
      </a>
      <aside className="sidebar">
        <div>
          <Link to="/" className="brand">
            <span className="brand-mark">
              <Activity size={22} aria-hidden="true" />
            </span>
            FinHealth<span className="text-primary">.</span>
          </Link>
          <p className="brand-sub">FINANCIAL INTELLIGENCE</p>
        </div>
        <Navigation />
        <div className="sidebar-bottom">
          <div className="small">
            <ShieldCheck
              size={15}
              className="inline mr-2 positive"
              aria-hidden="true"
            />
            Nghiên cứu từ dữ liệu nguồn
          </div>
          <p>
            SEC EDGAR · Báo cáo công bố
            <br />
            Mô hình theo thời gian
          </p>
          <a
            className="small source-link mt-4"
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
          >
            Tài liệu API
            <ArrowUpRight size={12} aria-hidden="true" />
          </a>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <Button
              className="mobile-menu"
              variant="ghost"
              size="icon"
              aria-label="Mở điều hướng"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} aria-hidden="true" />
            </Button>
            <span>Không gian nghiên cứu</span>
            <ChevronRight size={13} aria-hidden="true" />
            <span className="text-foreground">{section}</span>
          </div>
          <div className="topbar-actions">
            <form
              className="topbar-search"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                navigate(
                  `/screener?q=${encodeURIComponent(String(data.get("search")))}`,
                );
              }}
            >
              <label className="sr-only" htmlFor="global-search">
                Tìm doanh nghiệp
              </label>
              <input
                id="global-search"
                name="search"
                placeholder="Tìm doanh nghiệp…"
                required
              />
              <button className="sr-only" type="submit">
                Tìm
              </button>
            </form>
            <span className="topbar-status small muted">
              <span
                className="status-dot"
                style={{
                  background: health.data?.database_connected
                    ? "var(--positive)"
                    : "var(--warning)",
                }}
              />
              {health.data?.database_connected ? "Đã kết nối" : "Chưa kết nối"}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={
                theme === "dark" ? "Bật giao diện sáng" : "Bật giao diện tối"
              }
              onClick={() =>
                setTheme((value) => (value === "dark" ? "light" : "dark"))
              }
            >
              {theme === "dark" ? (
                <Sun size={18} aria-hidden="true" />
              ) : (
                <Moon size={18} aria-hidden="true" />
              )}
            </Button>
            <Button variant="ghost" size="icon" asChild>
              <Link to="/reports" aria-label="Báo cáo và cảnh báo dữ liệu">
                <BellRing size={18} aria-hidden="true" />
              </Link>
            </Button>
            <Link
              className="avatar"
              to="/account"
              aria-label={user ? `Tài khoản ${user.display_name}` : "Đăng nhập"}
            >
              {user ? (
                user.display_name.slice(0, 2).toUpperCase()
              ) : (
                <Users size={17} aria-hidden="true" />
              )}
            </Link>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} ref={main}>
          <Suspense fallback={<QueryState pending />}>
            <Outlet />
          </Suspense>
          <footer className="footer">
            <span>
              FinHealth · Corporate Financial Health & Credit Risk Analytics
            </span>
            <span>
              Chỉ phục vụ nghiên cứu ·{" "}
              {health.data?.active_model_version ?? "Chưa có mô hình"}
            </span>
          </footer>
        </main>
      </div>
      <Dialog
        open={mobile}
        onOpenChange={setMobile}
        title="FinHealth · Điều hướng"
      >
        <Navigation onNavigate={() => setMobile(false)} />
      </Dialog>
    </div>
  );
}
/** Deep-linkable application routes; legacy bookmarks enter the React account page. */
export default function App(): ReactElement {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Overview />} />
        <Route path="screener" element={<Screener />} />
        <Route path="company/:identifier" element={<Company />} />
        <Route path="compare" element={<Comparison />} />
        <Route path="reports" element={<Reports />} />
        <Route path="models" element={<Models />} />
        <Route path="prediction" element={<Prediction />} />
        <Route path="workspace" element={<Workspace />} />
        <Route path="account" element={<Accounts />} />
        <Route path="admin" element={<Admin />} />
        <Route
          path="account.html"
          element={<Navigate to="/account" replace />}
        />
        <Route
          path="*"
          element={
            <div className="state">
              <X aria-hidden="true" />
              <h1>Không tìm thấy trang</h1>
              <Link to="/">Về tổng quan</Link>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
