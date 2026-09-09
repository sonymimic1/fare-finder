/**
 * Client for the flight-subscription API (API Gateway + Lambda).
 * Base URL is injected at build time by Vite (VITE_* prefix), same as the
 * Supabase client — resolved lazily so a missing value fails loudly at the
 * first call instead of at module import.
 */

export type PlanName = "tokyo" | "seoul";

export type SubscriptionStatus = "pending_payment" | "active" | "cancelled" | "expired";

export type Subscription = {
  email: string;
  route: string;
  plan_name: string;
  origin: string;
  destination: string;
  target_price: number;
  currency: string;
  created_at: string;
  updated_at: string;
  /** Absent on rows created before M2 — read it through `statusOf`. */
  subscription_status?: SubscriptionStatus;
  merchant_trade_no?: string;
  /** ISO UTC timestamp. */
  current_period_end?: string;
  /** Human-facing `YYYY-MM-DD` rendering of `current_period_end`. */
  current_period_end_date?: string;
};

/** M1 rows carry no status; the backend treats those as unpaid, so we do too. */
export function statusOf(subscription: Subscription): SubscriptionStatus {
  return subscription.subscription_status ?? "pending_payment";
}

export type SaveSubscriptionInput = {
  email: string;
  plan_name: PlanName;
  target_price: number;
};

/**
 * `POST /subscribe` answers in one of two shapes:
 * - `text/html` — an auto-submitting ECPay cashier form the browser must run
 *   (new subscription, finishing a `pending_payment` one, or resubscribing).
 * - `application/json` — the row was updated in place, no payment needed.
 */
export type SaveSubscriptionResult =
  { kind: "checkout"; html: string } | { kind: "updated"; subscription: Subscription };

export type CancelSubscriptionInput = {
  email: string;
  route: string;
};

function flightApiBaseUrl(): string {
  const url = import.meta.env["VITE_FLIGHT_API_URL"];

  if (!url) {
    const message = "Missing environment variable: VITE_FLIGHT_API_URL.";
    console.error(`[FlightApi] ${message}`);
    throw new Error(message);
  }

  return url.replace(/\/+$/, "");
}

function errorMessageFrom(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null) {
    const { error } = body as { error?: unknown };
    if (typeof error === "string" && error.length > 0) return error;
  }
  return `Request failed (HTTP ${status}).`;
}

async function parseJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    // Non-JSON body (e.g. an empty error response) — callers handle null.
    return null;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${flightApiBaseUrl()}${path}`, init);
  const body = await parseJsonBody(response);

  if (!response.ok) throw new Error(errorMessageFrom(body, response.status));

  return body as T;
}

function jsonPost(input: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  };
}

export async function listSubscriptions(email: string): Promise<Subscription[]> {
  const data = await requestJson<{ ok: boolean; email: string; subscriptions: Subscription[] }>(
    `/subscriptions?email=${encodeURIComponent(email)}`,
  );
  return data.subscriptions ?? [];
}

export async function saveSubscription(
  input: SaveSubscriptionInput,
): Promise<SaveSubscriptionResult> {
  const response = await fetch(`${flightApiBaseUrl()}/subscribe`, jsonPost(input));

  // The cashier form is HTML — never hand it to `response.json()`.
  if (response.ok && (response.headers.get("content-type") ?? "").includes("text/html")) {
    return { kind: "checkout", html: await response.text() };
  }

  const body = await parseJsonBody(response);
  if (!response.ok) throw new Error(errorMessageFrom(body, response.status));

  const { subscription } = (body ?? {}) as { subscription?: Subscription };
  if (!subscription) throw new Error("Unexpected response from /subscribe.");

  return { kind: "updated", subscription };
}

export async function cancelSubscription(input: CancelSubscriptionInput): Promise<Subscription> {
  const data = await requestJson<{ ok: boolean; subscription: Subscription }>(
    "/cancel",
    jsonPost(input),
  );
  return data.subscription;
}
