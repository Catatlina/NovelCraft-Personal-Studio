// 前端配置传递 — API Key / API URL / Model 通过 sessionStorage + HTTP Header 传到后端
const K_API_KEY = "nc_api_key";
const K_API_URL = "nc_api_url";
const K_MODEL = "nc_model";

/* Same-origin by default: Vite proxies in development and nginx proxies in production. */
const CONFIGURED_API_BASE = ((import.meta as any).env?.VITE_API_BASE as string | undefined)?.replace(/\/$/, "");
const API_BASE = CONFIGURED_API_BASE || "/api";
let refreshInFlight: Promise<boolean> | null = null;

export class ApiError extends Error {
  status: number;
  payload: unknown;
  constructor(status: number, payload: unknown) {
    super(`API request failed with status ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

export function getApiKey(): string { return sessionStorage.getItem(K_API_KEY) || ""; }
export function setApiKey(key: string) { sessionStorage.setItem(K_API_KEY, key); }
export function getApiUrl(): string { return sessionStorage.getItem(K_API_URL) || ""; }
export function setApiUrl(url: string) { sessionStorage.setItem(K_API_URL, url); }
export function getModel(): string { return sessionStorage.getItem(K_MODEL) || ""; }
export function setModel(m: string) { sessionStorage.setItem(K_MODEL, m); }

function getCookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split("; ").find(part => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function tryRefreshToken(): Promise<boolean> {
  if (!refreshInFlight) {
    const csrf = getCookie("csrf_token");
    refreshInFlight = fetch(`${API_BASE}/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : undefined,
    }).then(async response => {
      if (!response.ok) {
        sessionStorage.removeItem("nc_token");
        return false;
      }
      const body = await response.json();
      const token = body?.data?.access_token;
      if (!token) return false;
      sessionStorage.setItem("nc_token", token);
      return true;
    }).catch(() => {
      sessionStorage.removeItem("nc_token");
      return false;
    }).finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

/** Unified fetch — injects X-Api-Key, X-Api-Url, X-Model, Authorization headers + resolves API base */
export async function api<T = any>(url: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const headers: Record<string, string> = { ...(!isFormData ? { "Content-Type": "application/json" } : {}), ...(init?.headers as Record<string, string> || {}) };
  const key = getApiKey(); const apiUrl = getApiUrl(); const model = getModel();
  if (key) headers["X-Api-Key"] = key;
  if (apiUrl) headers["X-Api-Base-Url"] = apiUrl;
  if (model) headers["X-Model"] = model;
  const token = sessionStorage.getItem("nc_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const csrf = getCookie("csrf_token");
  if (csrf && !["GET", "HEAD", "OPTIONS"].includes((init?.method || "GET").toUpperCase())) {
    headers["X-CSRF-Token"] = csrf;
  }
  const fullUrl = url.startsWith("/api") ? API_BASE + url.slice(4) : url;
  let r = await fetch(fullUrl, { ...init, headers, credentials: "include" });
  const isAuthRequest = /\/auth\/(login|register|refresh)$/.test(url);
  if (r.status === 401 && token && !isAuthRequest && await tryRefreshToken()) {
    headers["Authorization"] = `Bearer ${sessionStorage.getItem("nc_token") || ""}`;
    r = await fetch(fullUrl, { ...init, headers, credentials: "include" });
  }
  const payload = await r.json();
  if (!r.ok) throw new ApiError(r.status, payload);
  return payload;
}

/** SSE streaming request — same auth headers as api(); onDelta fires per text
 *  chunk; resolves with the full text from the terminal {done,text} frame. */
export async function apiStream(
  url: string,
  init: RequestInit,
  onDelta: (delta: string) => void,
): Promise<{ text: string }> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as Record<string, string> || {}) };
  const key = getApiKey(); const apiUrl = getApiUrl(); const model = getModel();
  if (key) headers["X-Api-Key"] = key;
  if (apiUrl) headers["X-Api-Base-Url"] = apiUrl;
  if (model) headers["X-Model"] = model;
  const token = sessionStorage.getItem("nc_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const csrf = getCookie("csrf_token");
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const fullUrl = url.startsWith("/api") ? API_BASE + url.slice(4) : url;
  let response = await fetch(fullUrl, { ...init, headers, credentials: "include" });
  if (response.status === 401 && token && await tryRefreshToken()) {
    headers["Authorization"] = `Bearer ${sessionStorage.getItem("nc_token") || ""}`;
    response = await fetch(fullUrl, { ...init, headers, credentials: "include" });
  }
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, await response.json().catch(() => null));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalText: string | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      let payload: any;
      try { payload = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (payload.error) throw new ApiError(payload.code === "PENDING_BUDGET" ? 429 : 502, payload);
      if (payload.delta) onDelta(payload.delta);
      if (payload.done) finalText = payload.text ?? "";
    }
  }
  if (finalText === null) throw new ApiError(502, { error: "stream ended without done frame" });
  return { text: finalText };
}
