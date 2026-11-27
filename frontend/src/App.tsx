import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/context/ThemeContext';
import { AuthProvider } from '@/context/AuthContext';
import { AppShell } from '@/components/layout/AppShell';
import { OverviewPage } from '@/pages/OverviewPage';
import { PortfolioPage } from '@/pages/PortfolioPage';
import { OrgCompanyDetailPage } from '@/pages/OrgCompanyDetailPage';
import { BatchAssessmentPage } from '@/pages/BatchAssessmentPage';
import { ComparePage } from '@/pages/ComparePage';
import { UsMarketPage } from '@/pages/UsMarketPage';
import { CompanyDetailPage } from '@/pages/CompanyDetailPage';
import { StressLabPage } from '@/pages/StressLabPage';
import { MethodologyPage } from '@/pages/MethodologyPage';
import { OrganizationPage } from '@/pages/OrganizationPage';
import { WorkspacePage } from '@/pages/WorkspacePage';
import { AccountPage } from '@/pages/AccountPage';
import { AdminPage } from '@/pages/AdminPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function LegacyCompanyRedirect() {
  const { identifier = '' } = useParams();
  return <Navigate to={`/us-market/${encodeURIComponent(identifier)}`} replace />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<AppShell />}>
                <Route index element={<OverviewPage />} />
                <Route path="portfolio" element={<PortfolioPage />} />
                <Route path="portfolio/:id" element={<OrgCompanyDetailPage />} />
                <Route path="batch" element={<BatchAssessmentPage />} />
                <Route path="compare" element={<ComparePage />} />
                <Route path="us-market" element={<UsMarketPage />} />
                <Route path="us-market/:identifier" element={<CompanyDetailPage />} />
                <Route path="stress" element={<StressLabPage />} />
                <Route path="methodology" element={<MethodologyPage />} />
                <Route path="organization" element={<OrganizationPage />} />
                <Route path="workspace" element={<WorkspacePage />} />
                <Route path="account" element={<AccountPage />} />
                <Route path="admin" element={<AdminPage />} />
                <Route path="admin/*" element={<AdminPage />} />
              </Route>
              {/* Redirect tương thích ngược với URL cũ */}
              <Route path="/screener" element={<Navigate to="/us-market" replace />} />
              <Route path="/companies/:identifier" element={<LegacyCompanyRedirect />} />
              <Route path="/models" element={<Navigate to="/admin" replace />} />
              <Route path="/clusters" element={<Navigate to="/admin" replace />} />
              <Route path="/app" element={<Navigate to="/" replace />} />
              <Route path="/app/companies/:identifier" element={<LegacyCompanyRedirect />} />
              <Route path="/app/*" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
