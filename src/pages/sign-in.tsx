import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { supabase } from "@/integrations/supabase/client";
import { AuthShell, AuthInput } from "@/components/auth-shell";

export function SignInPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    navigate("/app");
  }

  return (
    <AuthShell title="登入" subtitle="Sign in to your account">
      <title>登入 — Flight Price Notifier</title>
      <meta name="description" content="登入 Flight Price Notifier 帳戶。" />
      <form onSubmit={handleSubmit} className="space-y-4">
        <AuthInput
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
          required
        />
        <AuthInput
          id="password"
          label="密碼"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
          required
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85 disabled:opacity-60"
        >
          {loading ? "登入中…" : "登入 / Sign in"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        還沒有帳戶？{" "}
        <Link to="/sign-up" className="text-primary hover:underline">
          註冊 / Sign up
        </Link>
      </p>
    </AuthShell>
  );
}
