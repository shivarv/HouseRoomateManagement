const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001/api/v1";
const TOKEN_KEY = "roommate.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ msg, loc }, ...]
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

/** The server itself had a problem (no message of its own): say so plainly. */
function serverTrouble(status: number): string | null {
  if (status === 502 || status === 503 || status === 504) return "Roommates is waking up or busy. Try again in a moment.";
  if (status >= 500) return "Something went wrong on our side. Try again in a moment.";
  return null;
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    // The browser only says "Failed to fetch": offline, or the server is asleep or down.
    throw new ApiError(
      0,
      navigator.onLine
        ? "Couldn't connect to Roommates right now. It may be waking up, so try again in a moment."
        : "You're offline. Check your internet connection, then try again.",
    );
  }

  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(res.status, errorMessage(body, serverTrouble(res.status) ?? res.statusText));
  }
  return body as T;
}
