import { Link, useNavigate } from "react-router";
import { Plane, LogOut } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuthUser } from "@/components/require-auth";
import { PlanCards } from "@/components/plan-cards";

export function AppShellPage() {
  const navigate = useNavigate();
  const user = useAuthUser();

  async function handleSignOut() {
    await supabase.auth.signOut();
    navigate("/", { replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <title>Dashboard — Flight Price Notifier</title>
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
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

      <main className="flex-1 px-4 py-12 sm:px-6 sm:py-16">
        <div className="mx-auto w-full max-w-4xl">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">航線訂閱</h1>
          <p className="mt-3 text-muted-foreground">
            選擇航線、設定目標價，票價低於目標就寄 email 通知你。
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Pick a route and set a target price — we email you when the fare drops below it.
          </p>

          <div className="mt-8">
            {user.email ? (
              <PlanCards email={user.email} />
            ) : (
              <p role="alert" className="text-sm text-destructive">
                你的帳號沒有 email，無法建立訂閱。Your account has no email address.
              </p>
            )}
          </div>

          {user.email && (
            <p className="mt-6 text-sm text-muted-foreground">
              通知會寄到 / Alerts go to{" "}
              <span className="font-medium text-foreground">{user.email}</span>
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
