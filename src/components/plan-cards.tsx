import { useEffect, useState } from "react";
import {
  BellRing,
  CalendarClock,
  Check,
  Clock,
  CreditCard,
  Loader2,
  RotateCcw,
  TrendingDown,
} from "lucide-react";
import {
  cancelSubscription,
  listSubscriptions,
  saveSubscription,
  statusOf,
  type PlanName,
  type Subscription,
  type SubscriptionStatus,
} from "@/lib/flight-api";

type Plan = {
  planName: PlanName;
  title: string;
  subtitle: string;
  lowestHint: string;
};

type IconComponent = typeof BellRing;

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

const MONTHLY_PRICE = "NT$300";

/**
 * Every state posts to the same `/subscribe` endpoint; only the wording
 * differs. Whether the answer is a cashier form or an in-place update is
 * decided by the backend's Content-Type, not by the button.
 */
const ACTION_BY_STATUS: Record<SubscriptionStatus, { label: string; Icon: IconComponent }> = {
  pending_payment: { label: `完成付款 / Pay ${MONTHLY_PRICE}`, Icon: CreditCard },
  active: { label: "更新目標價 / Update target", Icon: BellRing },
  cancelled: { label: "更新目標價 / Update target", Icon: BellRing },
  expired: { label: "重新訂閱 / Resubscribe", Icon: RotateCcw },
};

const NEW_SUBSCRIPTION_ACTION = { label: "開始追蹤 / Start tracking", Icon: BellRing };

function formatTwd(value: number): string {
  return `NT$ ${value.toLocaleString("en-US")}`;
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function badgeOf(subscription: Subscription): {
  text: string;
  className: string;
  Icon: IconComponent;
} {
  switch (statusOf(subscription)) {
    case "active":
      return {
        text: "已訂閱 (有效) / Active",
        className: "bg-primary/15 text-primary",
        Icon: Check,
      };
    case "cancelled": {
      const until = subscription.current_period_end_date;
      return {
        text: until
          ? `已取消 · 有效至 ${until} / Cancelled · valid until ${until}`
          : "已取消 / Cancelled",
        className: "bg-amber-500/15 text-amber-300",
        Icon: CalendarClock,
      };
    }
    case "expired":
      return {
        text: "已結束 / Expired",
        className: "bg-muted text-muted-foreground",
        Icon: Clock,
      };
    default:
      return {
        text: "未完成付款 / Payment pending",
        className: "bg-amber-500/15 text-amber-300",
        Icon: CreditCard,
      };
  }
}

/** Hands the document over to ECPay's auto-submitting cashier form. */
function goToCheckout(html: string): void {
  document.open();
  document.write(html);
  document.close();
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
  const [cancelling, setCancelling] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = subscription ? statusOf(subscription) : null;
  const action = status ? ACTION_BY_STATUS[status] : NEW_SUBSCRIPTION_ACTION;
  const badge = subscription ? badgeOf(subscription) : null;
  const busy = saving || cancelling;
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
    let leavingPage = false;
    try {
      const result = await saveSubscription({
        email,
        plan_name: plan.planName,
        target_price: parsed,
      });

      if (result.kind === "checkout") {
        // This replaces the whole document — keep the form disabled and let
        // the browser POST to ECPay.
        leavingPage = true;
        goToCheckout(result.html);
        return;
      }

      setSubscription(result.subscription);
      setTargetPrice(String(result.subscription.target_price));
    } catch (caught) {
      setError(messageOf(caught, "儲存失敗，請稍後再試。Could not save, please try again."));
    } finally {
      if (!leavingPage) setSaving(false);
    }
  }

  async function handleCancel() {
    if (!subscription) return;

    setCancelling(true);
    setError(null);
    try {
      const cancelled = await cancelSubscription({ email, route: subscription.route });
      setSubscription(cancelled);
      setTargetPrice(String(cancelled.target_price));
      setConfirmingCancel(false);
    } catch (caught) {
      setError(messageOf(caught, "取消失敗，請稍後再試。Could not cancel, please try again."));
    } finally {
      setCancelling(false);
    }
  }

  return (
    <article className="flex h-full flex-col rounded-2xl border border-border bg-card p-6 transition-colors hover:border-primary/40">
      <div>
        <h2 className="text-lg font-semibold text-card-foreground">{plan.title}</h2>
        <p className="mt-1 text-sm font-medium text-primary">{plan.subtitle}</p>
      </div>

      {badge && (
        <p
          className={`mt-3 inline-flex w-fit items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium ${badge.className}`}
        >
          <badge.Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {badge.text}
        </p>
      )}

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
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              處理中… / Working…
            </>
          ) : (
            <>
              <action.Icon className="h-4 w-4" aria-hidden />
              {action.label}
            </>
          )}
        </button>

        {status === "active" &&
          (confirmingCancel ? (
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm">
              <span className="text-muted-foreground">確定取消？/ Cancel it?</span>
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="font-medium text-destructive underline-offset-4 transition-colors hover:underline disabled:cursor-not-allowed disabled:opacity-60"
              >
                {cancelling ? "取消中… / Cancelling…" : "是 / Yes"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingCancel(false)}
                disabled={cancelling}
                className="font-medium text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline disabled:cursor-not-allowed disabled:opacity-60"
              >
                否 / No
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingCancel(true)}
              disabled={busy}
              className="w-full text-center text-sm text-muted-foreground underline-offset-4 transition-colors hover:text-destructive hover:underline disabled:cursor-not-allowed disabled:opacity-60"
            >
              取消訂閱 / Cancel subscription
            </button>
          ))}

        {error && (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </form>
    </article>
  );
}

function BillingNote() {
  return (
    <p className="mb-6 flex items-start gap-2 rounded-2xl border border-border bg-card p-4 text-sm">
      <CreditCard className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
      <span>
        <span className="text-card-foreground">
          月費 {MONTHLY_PRICE}，可隨時取消，取消後服務保留至當期結束。
        </span>
        <span className="mt-0.5 block text-muted-foreground">
          {MONTHLY_PRICE}/month. Cancel anytime — alerts keep running until the end of the current
          period.
        </span>
      </span>
    </p>
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

  return (
    <div>
      <BillingNote />

      {state.status === "loading" && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          載入訂閱狀態中… / Loading your subscriptions…
        </p>
      )}

      {state.status === "error" && (
        <p role="alert" className="text-sm text-destructive">
          {state.message}
        </p>
      )}

      {state.status === "ready" && (
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
      )}
    </div>
  );
}
