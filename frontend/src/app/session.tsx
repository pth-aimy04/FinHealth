import {
  createContext,
  useContext,
  type ReactElement,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, request, mutate } from "../lib/api/client";
const userSchema = z.object({
  id: z.number(),
  email: z.string(),
  display_name: z.string(),
  role: z.string(),
  active: z.boolean(),
  email_verified: z.boolean(),
});
export type User = z.infer<typeof userSchema>;
const Session = createContext<{
  user: User | null;
  pending: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
} | null>(null);
/** Keep identity in Query memory; no browser session token storage. */
export function SessionProvider({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      try {
        return userSchema.parse(await request<unknown>("/auth/me"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
  const refresh = async (): Promise<void> => {
    await client.invalidateQueries({ queryKey: ["session"] });
  };
  const logout = async (): Promise<void> => {
    await mutate("/auth/logout");
    client.clear();
    await refresh();
  };
  return (
    <Session.Provider
      value={{
        user: session.data ?? null,
        pending: session.isPending,
        error: session.error,
        refresh,
        logout,
      }}
    >
      {children}
    </Session.Provider>
  );
}
/** Read the current verified account. */
export function useSession(): NonNullable<React.ContextType<typeof Session>> {
  const value = useContext(Session);
  if (!value) throw new Error("SessionProvider is required");
  return value;
}
