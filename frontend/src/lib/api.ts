export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

let csrfToken = "";
let onUnauthorized: (() => void) | null = null;

export const setCsrfToken = (token: string) => {
  csrfToken = token;
};
export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler;
};

/** FastAPI sends either a text message or a list of validation problems. Turn both into one sentence. */
function messageOf(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.filter((p) => p !== "body").join(" ");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return fallback;
}

async function request<T>(method: string, url: string, body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  let payload: BodyInit | undefined;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const response = await fetch(`/api${url}`, { method, headers, body: payload, credentials: "same-origin" });
  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      /* the body was not JSON */
    }
    if (response.status === 401 && !url.startsWith("/auth/login")) onUnauthorized?.();
    throw new ApiError(messageOf(parsed, `The request failed (${response.status}).`), response.status);
  }
  return (await response.json()) as T;
}

export const qs = (params: Record<string, string | number | boolean | null | undefined>): string => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()}` : "";
};

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  put: <T>(url: string, body: unknown = {}) => request<T>("PUT", url, body),
  patch: <T>(url: string, body: unknown = {}) => request<T>("PATCH", url, body),
  del: <T>(url: string) => request<T>("DELETE", url),
  upload: <T>(url: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>("POST", url, undefined, form);
  },
};

export const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : "Something went wrong.";
