/**
 * Client for the flight-subscription API (API Gateway + Lambda).
 * Base URL is injected at build time by Vite (VITE_* prefix), same as the
 * Supabase client — resolved lazily so a missing value fails loudly at the
 * first call instead of at module import.
 */

export type PlanName = "tokyo" | "seoul";

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
};

export type SaveSubscriptionInput = {
  email: string;
  plan_name: PlanName;
  target_price: number;
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

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${flightApiBaseUrl()}${path}`, init);

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body (e.g. an empty error response) — handled below.
  }

  if (!response.ok) throw new Error(errorMessageFrom(body, response.status));

  return body as T;
}

export async function listSubscriptions(email: string): Promise<Subscription[]> {
  const data = await requestJson<{ ok: boolean; email: string; subscriptions: Subscription[] }>(
    `/subscriptions?email=${encodeURIComponent(email)}`,
  );
  return data.subscriptions ?? [];
}

export async function saveSubscription(input: SaveSubscriptionInput): Promise<Subscription> {
  const data = await requestJson<{ ok: boolean; subscription: Subscription }>("/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  return data.subscription;
}
