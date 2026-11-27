import { createContext, useContext, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import type { OrgRole, OrganizationSummary, PublicUser } from '@/types/api';

interface AuthContextValue {
  user: PublicUser | null;
  isLoading: boolean;
  isAdmin: boolean;
  organizations: OrganizationSummary[];
  activeOrg: OrganizationSummary | null;
  activeOrgRole: OrgRole | null;
  isOrgsLoading: boolean;
  refreshAuth: () => Promise<void>;
  refreshOrganizations: () => Promise<void>;
  switchOrg: (organizationId: number) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        return await api.getMe();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return null;
        }
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });

  const user = data ?? null;

  const { data: organizationsData, isLoading: isOrgsLoading } = useQuery({
    queryKey: ['auth', 'organizations', user?.id],
    queryFn: async () => {
      try {
        return await api.getOrganizations();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return [];
        }
        throw error;
      }
    },
    enabled: Boolean(user),
    retry: false,
    staleTime: 30_000,
  });

  const organizations = user ? (organizationsData ?? []) : [];
  const activeOrg =
    organizations.find((org) => org.is_active_workspace) ?? organizations[0] ?? null;
  const activeOrgRole: OrgRole | null = activeOrg?.role ?? null;

  async function refreshAuth() {
    await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    await queryClient.invalidateQueries({ queryKey: ['auth', 'organizations'] });
  }

  async function refreshOrganizations() {
    await queryClient.invalidateQueries({ queryKey: ['auth', 'organizations'] });
  }

  async function switchOrg(organizationId: number) {
    await api.switchOrganization(organizationId);
    // Invalidate and clear all cached workspace/org queries to prevent cross-tenant display leaks
    queryClient.removeQueries({
      predicate: (query) => {
        const rootKey = query.queryKey[0];
        return rootKey !== 'auth' && rootKey !== 'health';
      },
    });
    await queryClient.invalidateQueries();
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      queryClient.setQueryData(['auth', 'me'], null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== 'auth',
      });
      queryClient.removeQueries({ queryKey: ['auth', 'organizations'] });
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAdmin: user?.role === 'admin',
        organizations,
        activeOrg,
        activeOrgRole,
        isOrgsLoading: Boolean(user) && isOrgsLoading,
        refreshAuth,
        refreshOrganizations,
        switchOrg,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
