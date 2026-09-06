import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Plane, LogOut, Construction } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

export const Route = createFileRoute("/_authenticated/app")({
  component: AppShellPage,
});

function AppShellPage() {
  const navigate = useNavigate();
  const { user } = Route.useRouteContext();

  async function handleSignOut() {
    await supabase.auth.signOut();
    navigate({ to: "/", replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link
            to="/"
            className="flex items-center gap-2 font-semibold tracking-tight"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Plane className="h-4 w-4" aria-hidden />
            </span>
            Flight Price Notifier
          </Link>
          <button
            onClick={handleSignOut}
            className="inline-flex items-center gap-2 rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Sign Out
          </button>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-16 sm:px-6">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
            <Construction className="h-7 w-7" aria-hidden />
          </div>
          <h1 className="mt-6 text-2xl font-semibold tracking-tight">
            Hi {user.email}
          </h1>
          <p className="mt-4 text-muted-foreground">
            你的航線追蹤儀表板即將上線 —
            下一個里程碑會加上訂閱航線的功能。
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Your dashboard is coming soon. Route-subscription will be added in
            the next milestone.
          </p>
        </div>
      </main>
    </div>
  );
}
