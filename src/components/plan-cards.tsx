import { useEffect, useState } from "react";
import { BellRing, Check, Loader2, TrendingDown } from "lucide-react";
import {
  listSubscriptions,
  saveSubscription,
  type PlanName,
  type Subscription,
} from "@/lib/flight-api";

type Plan = {
  planName: PlanName;
  title: string;
  subtitle: string;
  lowestHint: string;
};

/** Routes are hard-coded for v1 — the API only accepts these two plans. */
const PLANS: readonly Plan[] = [
  {
    planName: "tokyo",
    title: "台北 ✈ 東京",
    subtitle: "Taipei → Tokyo",
    lowestHint: "近期最低約 NT$9,325",
  },
  {
    planName: "seoul",
    title: "台北 ✈ 首爾",
    subtitle: "Taipei → Seoul",
    lowestHint: "近期最低約 NT$5,989",
  },
];

function formatTwd(value: number): string {
  return `NT$ ${value.toLocaleString("en-US")}`;
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function PlanCard({
  plan,
  email,
  initialSubscription,
}: {
  plan: Plan;
  email: string;
  initialSubscription: Subscription | null;
}) {
  const [subscription, setSubscription] = useState<Subscription | null>(initialSubscription);
  const [targetPrice, setTargetPrice] = useState(
    initialSubscription ? String(initialSubscription.target_price) : "",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subscribed = subscription !== null;
  const errorId = `${plan.planName}-error`;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsed = Number(targetPrice);
    if (!Number.isInteger(parsed) || parsed < 1) {
      setError("請輸入 1 以上的整數金額。Enter a whole number of at least 1.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const saved = await saveSubscription({
        email,
        plan_name: plan.planName,
        target_price: parsed,
      });
      setSubscription(saved);
      setTargetPrice(String(saved.target_price));
    } catch (caught) {
      setError(messageOf(caught, "儲存失敗，請稍後再試。Could not save, please try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="flex h-full flex-col rounded-2xl border border-border bg-card p-6 transition-colors hover:border-primary/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-card-foreground">{plan.title}</h2>
          <p className="mt-1 text-sm font-medium text-primary">{plan.subtitle}</p>
        </div>
        {subscribed && (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
            <Check className="h-3.5 w-3.5" aria-hidden />
            已訂閱 / Subscribed
          </span>
        )}
      </div>

      <p className="mt-3 flex items-center gap-1.5 text-sm text-muted-foreground">
        <TrendingDown className="h-4 w-4" aria-hidden />
        {plan.lowestHint}
      </p>

      {subscription && (
        <p className="mt-4 text-sm text-muted-foreground">
          目前目標價 / Current target{" "}
          <span className="font-semibold text-card-foreground">
            {formatTwd(subscription.target_price)}
          </span>
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-auto space-y-3 pt-5">
        <div className="space-y-1.5">
          <label
            htmlFor={`${plan.planName}-target`}
            className="text-sm font-medium text-card-foreground"
          >
            目標價 / Target price (TWD)
          </label>
          <input
            id={`${plan.planName}-target`}
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            required
            value={targetPrice}
            onChange={(event) => setTargetPrice(event.target.value)}
            placeholder="10000"
            aria-describedby={error ? errorId : undefined}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring"
          />
        </div>

        <button
          type="submit"
          disabled={saving}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              儲存中…
            </>
          ) : (
            <>
              <BellRing className="h-4 w-4" aria-hidden />
              {subscribed ? "更新目標價 / Update target" : "開始追蹤 / Start tracking"}
            </>
          )}
        </button>

        {error && (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </form>
    </article>
  );
}

export function PlanCards({ email }: { email: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ready"; subscriptions: Subscription[] }
    | { status: "error"; message: string }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    listSubscriptions(email)
      .then((subscriptions) => {
        if (!cancelled) setState({ status: "ready", subscriptions });
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: messageOf(caught, "無法載入訂閱狀態。Could not load your subscriptions."),
        });
      });

    return () => {
      cancelled = true;
    };
  }, [email]);

  if (state.status === "loading") {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        載入訂閱狀態中… / Loading your subscriptions…
      </p>
    );
  }

  if (state.status === "error") {
    return (
      <p role="alert" className="text-sm text-destructive">
        {state.message}
      </p>
    );
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2">
      {PLANS.map((plan) => (
        <PlanCard
          key={plan.planName}
          plan={plan}
          email={email}
          initialSubscription={
            state.subscriptions.find((s) => s.plan_name === plan.planName) ?? null
          }
        />
      ))}
    </div>
  );
}
