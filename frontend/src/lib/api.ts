// 前端传递 API Key 到后端 — 存入 sessionStorage，请求时带 X-Api-Key header

const KEY_STORE = "nc_deepseek_key";

/* Vite dev server has proxy; production (npm build) needs absolute API URL */
const IS_DEV = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;
const API_BASE = IS_DEV ? "/api" : `${window.location.protocol}//${window.location.hostname}:8000/api`;

export function getApiKey(): string {
  return sessionStorage.getItem(KEY_STORE) || "";
}

export function setApiKey(key: string) {
  sessionStorage.setItem(KEY_STORE, key);
}

export function clearApiKey() {
  sessionStorage.removeItem(KEY_STORE);
}

/** Wrap fetch to inject API Key + auth header + correct API base */
export async function api<T = any>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...((init?.headers as Record<string, string>) || {}) };
  const key = getApiKey();
  if (key) headers["X-Api-Key"] = key;
  const token = sessionStorage.getItem("nc_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const fullUrl = url.startsWith("/api") ? API_BASE + url.slice(4) : url;
  const r = await fetch(fullUrl, { ...init, headers });
  return r.json();
}
