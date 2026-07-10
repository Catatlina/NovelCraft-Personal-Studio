// 前端配置传递 — API Key / API URL / Model 通过 sessionStorage + HTTP Header 传到后端
const K_API_KEY = "nc_api_key";
const K_API_URL = "nc_api_url";
const K_MODEL = "nc_model";

/* Vite dev server has proxy; production (npm build) needs absolute API URL */
const IS_DEV = typeof import.meta !== "undefined" && !!(import.meta as any).env?.DEV;
const API_BASE = IS_DEV ? "/api" : `${window.location.protocol}//${window.location.hostname}:8000/api`;

export function getApiKey(): string { return sessionStorage.getItem(K_API_KEY) || ""; }
export function setApiKey(key: string) { sessionStorage.setItem(K_API_KEY, key); }
export function getApiUrl(): string { return sessionStorage.getItem(K_API_URL) || ""; }
export function setApiUrl(url: string) { sessionStorage.setItem(K_API_URL, url); }
export function getModel(): string { return sessionStorage.getItem(K_MODEL) || ""; }
export function setModel(m: string) { sessionStorage.setItem(K_MODEL, m); }

/** Unified fetch — injects X-Api-Key, X-Api-Url, X-Model, Authorization headers + resolves API base */
export async function api<T = any>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as Record<string, string> || {}) };
  const key = getApiKey(); const apiUrl = getApiUrl(); const model = getModel();
  if (key) headers["X-Api-Key"] = key;
  if (apiUrl) headers["X-Api-Base-Url"] = apiUrl;
  if (model) headers["X-Model"] = model;
  const token = sessionStorage.getItem("nc_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const fullUrl = url.startsWith("/api") ? API_BASE + url.slice(4) : url;
  const r = await fetch(fullUrl, { ...init, headers });
  return r.json();
}
