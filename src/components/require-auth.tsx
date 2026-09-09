import { useEffect, useState } from "react";
import { Navigate, Outlet, useOutletContext } from "react-router";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";

export type AuthOutletContext = { user: User };

/**
 * Client-side auth guard (replaces the former `_authenticated` layout route).
 * Renders nothing while the session is being checked, redirects to /sign-in
 * when there is no user, otherwise renders the child route with the user in
 * outlet context.
 */
export function RequireAuth() {
  const [state, setState] = useState<
    { status: "loading" } | { status: "anon" } | { status: "authed"; user: User }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    supabase.auth.getUser().then(({ data, error }) => {
      if (cancelled) return;
      if (error || !data.user) setState({ status: "anon" });
      else setState({ status: "authed", user: data.user });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") return null;
  if (state.status === "anon") return <Navigate to="/sign-in" replace />;
  return <Outlet context={{ user: state.user } satisfies AuthOutletContext} />;
}

export function useAuthUser(): User {
  return useOutletContext<AuthOutletContext>().user;
}
