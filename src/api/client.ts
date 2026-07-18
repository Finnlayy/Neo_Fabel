import {getIdToken} from "../auth/firebase";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type TokenProvider = () => Promise<string | null>;

let externalTokenProvider: TokenProvider | null = null;

export function setApiTokenProvider(provider: TokenProvider | null): void {
  externalTokenProvider = provider;
}

async function resolveToken(): Promise<string | null> {
  if (externalTokenProvider) return externalTokenProvider();
  return getIdToken();
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const token = await resolveToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && token) {
    const refreshed = await getIdToken(true);
    if (refreshed) {
      headers.set("Authorization", `Bearer ${refreshed}`);
      const retry = await fetch(path, { ...init, headers });
      return parseResponse<T>(retry);
    }
  }
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail ?? body;
    const code = detail?.code ?? "api_error";
    const message = detail?.message ?? `HTTP ${response.status}`;
    if (code === "auth_unconfigured") {
      throw new ApiError(response.status, "auth_unconfigured", message);
    }
    if (response.status === 401) {
      throw new ApiError(401, "session_expired", message);
    }
    throw new ApiError(response.status, code, message);
  }
  return body as T;
}
