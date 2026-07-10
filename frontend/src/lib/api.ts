// 前端配置传递 — API Key / API URL / Model 通过 sessionStorage + HTTP Header 传到后端
const K_API_KEY = "nc_api_key";
const K_API_URL = "nc_api_url";
const K_MODEL = "nc_model";

/* Vite dev server has proxy; production (npm build) needs absolute API URL */
const IS_DEV = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;
const API_BASE = IS_DEV ? "/api" : `${window.location.protocol}//${window.location.hostname}:8000/api`;
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
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as Record<string, string> || {}) };
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
