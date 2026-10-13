export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: unknown }) => typeof item?.msg === "string" ? item.msg : "Invalid input").join("; ")
      : "Something went wrong. Please try again.";
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export type PublicUser = {
  id: string;
  full_name: string;
  username: string;
  email: string;
  phone: string | null;
  email_verified: boolean;
  delivery_id?: string | null;
  delivery_status?: string | null;
  verification_expires_at?: string | null;
};

export type SessionSummary = {
  id: string;
  device_type: string | null;
  browser: string | null;
  operating_system: string | null;
  ip_address: string | null;
  created_at: string;
  last_active_at: string;
  expires_at: string;
  status: string;
  current: boolean;
};

export type SecurityEvent = {
  id: string;
  event_type: string;
  ip_address: string | null;
  created_at: string;
};
