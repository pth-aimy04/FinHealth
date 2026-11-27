import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/context/ThemeContext';
import { AuthProvider } from '@/context/AuthContext';
import { AppShell } from '@/components/layout/AppShell';
import { OverviewPage } from '@/pages/OverviewPage';
import { ScreenerPage } from '@/pages/ScreenerPage';
import { CompanyDetailPage } from '@/pages/CompanyDetailPage';
import { ComparePage } from '@/pages/ComparePage';
import { ClusterMapPage } from '@/pages/ClusterMapPage';
import { StressLabPage } from '@/pages/StressLabPage';
import { ModelLabPage } from '@/pages/ModelLabPage';
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

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Vào thẳng Không gian Phân tích Tài chính ngay tại gốc '/' */}
              <Route path="/" element={<AppShell />}>
                <Route index element={<OverviewPage />} />
                <Route path="screener" element={<ScreenerPage />} />
                <Route path="companies/:identifier" element={<CompanyDetailPage />} />
                <Route path="compare" element={<ComparePage />} />
                <Route path="clusters" element={<ClusterMapPage />} />
                <Route path="stress" element={<StressLabPage />} />
                <Route path="models" element={<ModelLabPage />} />
                <Route path="workspace" element={<WorkspacePage />} />
                <Route path="account" element={<AccountPage />} />
                <Route path="admin" element={<AdminPage />} />
              </Route>
              {/* Giữ tương thích đường dẫn cũ /app/* chuyển hướng mượt về /* */}
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

import { useParams } from 'react-router-dom';
function LegacyCompanyRedirect() {
  const { identifier = '' } = useParams();
  return <Navigate to={`/companies/${encodeURIComponent(identifier)}`} replace />;
}

export default App;
