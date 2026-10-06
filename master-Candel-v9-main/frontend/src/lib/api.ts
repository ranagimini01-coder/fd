// Only the configured backend origin is used; secrets never enter this bundle.
const BASE = `${import.meta.env.VITE_BACKEND_URL || ''}/api`;
export const apiUrl = (path: string) => `${BASE}${path}`;

// Fields are declared, not constructor parameter properties: tsconfig sets
// erasableSyntaxOnly, which rejects `constructor(readonly status: number)`.
export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`request failed with ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type JsonBody = unknown;
type ApiHeaders = Record<string, string>;

async function request<T>(method: string, path: string, body?: JsonBody, extraHeaders?: ApiHeaders): Promise<T> {
  // Demo-session cookies are automatic; operator credentials are explicit and short-lived.
  const res = await fetch(apiUrl(path), {
    method,
    headers: body === undefined ? extraHeaders : { "Content-Type": "application/json", ...extraHeaders },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // FastAPI reports request-validation failures as 422 with a {detail: [...]} body.
  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(res.status, errBody);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: JsonBody, headers?: ApiHeaders) => request<T>("POST", path, body ?? null, headers);
export const apiPut = <T>(path: string, body?: JsonBody) => request<T>("PUT", path, body ?? null);
export const apiPatch = <T>(path: string, body?: JsonBody) =>
  request<T>("PATCH", path, body ?? null);
export const apiDelete = <T>(path: string) => request<T>("DELETE", path);

export function promptOperatorControlHeaders(): ApiHeaders | null {
  const key = window.prompt("Provider control key");
  return key ? { "X-Provider-Control-Key": key } : null;
}
