import "server-only";

/**
 * Server-side API client.
 *
 * All data fetching happens in React Server Components, so the browser never
 * talks to FastAPI directly and there is no client bundle cost for the
 * analytics payloads. `ApiError` carries the status so pages can distinguish
 * "no data ingested yet" (503) from a genuine failure.
 */
const BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public path: string) {
    super(message);
    this.name = "ApiError";
  }
}

export type QueryValue = string | number | boolean | undefined | null | Array<string | number>;

export function buildQuery(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => sp.append(key, String(v)));
    else sp.append(key, String(value));
  }
  const q = sp.toString();
  return q ? `?${q}` : "";
}

export async function api<T>(
  path: string,
  params: Record<string, QueryValue> = {},
  init: RequestInit & { revalidate?: number } = {},
): Promise<T> {
  const { revalidate = 300, ...rest } = init;
  const url = `${BASE}${path}${buildQuery(params)}`;
  let res: Response;
  try {
    res = await fetch(url, { ...rest, next: { revalidate } });
  } catch (cause) {
    throw new ApiError(
      0,
      `Cannot reach the Stryk API at ${BASE}. Is the backend running?`,
      path,
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, String(detail), path);
  }
  return (await res.json()) as T;
}

/** Fetch that resolves to null on 404 instead of throwing. */
export async function apiOrNull<T>(
  path: string,
  params: Record<string, QueryValue> = {},
): Promise<T | null> {
  try {
    return await api<T>(path, params);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}
