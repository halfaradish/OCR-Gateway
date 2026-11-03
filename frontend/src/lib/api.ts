export interface ApiFieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: ApiFieldError[];

  constructor(status: number, code: string, message: string, fields: ApiFieldError[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export class SessionExpiredError extends Error {
  constructor() {
    super("登录已过期，请重新登录。");
    this.name = "SessionExpiredError";
  }
}

const DEFAULT_TIMEOUT_MS = 15_000;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export const sessionEvents = new EventTarget();

export function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const entry = part.trim();
    if (entry.startsWith(prefix)) {
      return decodeURIComponent(entry.slice(prefix.length));
    }
  }
  return null;
}

interface EnvelopeError {
  error?: { code?: string; message?: string; fields?: ApiFieldError[] };
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  timeoutMs?: number;
  skipAuthRedirect?: boolean;
  signal?: AbortSignal;
}

async function perform(path: string, options: RequestOptions): Promise<Response> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie("ocr_csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const onAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onAbort);

  try {
    return await fetch(path, {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timer);
    options.signal?.removeEventListener("abort", onAbort);
  }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await perform(path, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "TIMEOUT", "请求超时，请重试。");
    }
    throw new ApiError(0, "NETWORK_ERROR", "无法连接网关，请确认服务正在运行。");
  }

  if (response.status === 401 && !options.skipAuthRedirect) {
    sessionEvents.dispatchEvent(new Event("expired"));
    throw new SessionExpiredError();
  }

  const method = (options.method ?? "GET").toUpperCase();
  if (response.status === 403 && !SAFE_METHODS.has(method)) {
    // Stale CSRF cookie (another tab logged in): refresh it once, then retry the write.
    try {
      await fetch("/api/admin/me", { credentials: "same-origin" });
      response = await perform(path, options);
    } catch {
      throw new ApiError(0, "NETWORK_ERROR", "无法连接网关，请确认服务正在运行。");
    }
    if (response.status === 401 && !options.skipAuthRedirect) {
      sessionEvents.dispatchEvent(new Event("expired"));
      throw new SessionExpiredError();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const envelope = (payload ?? {}) as EnvelopeError;
    const detail = envelope.error;
    throw new ApiError(
      response.status,
      detail?.code ?? "HTTP_ERROR",
      detail?.message ?? "请求失败，请重试。",
      detail?.fields ?? [],
    );
  }

  return payload as T;
}
