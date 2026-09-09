import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { supabase } from "@/integrations/supabase/client";
import { AuthShell, AuthInput } from "@/components/auth-shell";

export function SignUpPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: window.location.origin },
    });
    if (error) {
      setLoading(false);
      setError(error.message);
      return;
    }
    navigate("/app");
  }

  return (
    <AuthShell title="建立帳戶" subtitle="Create your account">
      <title>註冊 — Flight Price Notifier</title>
      <meta name="description" content="建立 Flight Price Notifier 帳戶，開始追蹤機票價格。" />
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
          label="密碼（至少 6 碼）"
          type="password"
          autoComplete="new-password"
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
          {loading ? "建立中…" : "註冊 / Sign up"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        已有帳戶？{" "}
        <Link to="/sign-in" className="text-primary hover:underline">
          登入 / Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
