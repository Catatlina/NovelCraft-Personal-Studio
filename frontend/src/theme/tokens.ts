/**
 * theme/tokens.ts — TypeScript mirror of design/tokens.css (doc12).
 *
 * The authoritative values live in CSS (tokens.css). This module is a
 * convenience for inline styles / JS logic that needs a token value at runtime
 * without hard-coding a color. Prefer `cssVar()` to read the *currently active*
 * theme value from the DOM so light/dark always resolve correctly.
 */

/** Static snapshot of the dark-theme palette (mirrors tokens.css). */
export const tokens = {
  brand: {
    50: "#EEF0FE",
    100: "#D9DEF9",
    300: "#838DEB",
    500: "#5B66DB",
    600: "#444FCB",
    700: "#373FA8",
    foreground: "#FFFFFF",
  },
  bg: {
    base: "#14161C",
    subtle: "#1C1F26",
    muted: "#252932",
    elevated: "#2C313B",
  },
  border: {
    subtle: "#363C47",
    strong: "#49515F",
  },
  text: {
    primary: "#E8EAF0",
    secondary: "#A6ABBA",
    muted: "#797F8E",
  },
  success: "#31B572",
  warning: "#F2A93B",
  danger: "#DE4B5E",
  info: "#2E9BD6",
  radius: {
    sm: "4px",
    md: "6px",
    lg: "10px",
    xl: "14px",
    full: "9999px",
  },
  space: {
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    6: "24px",
    8: "32px",
  },
  shadow: {
    sm: "0 1px 2px hsl(0 0% 0% / 0.4)",
    md: "0 4px 12px hsl(0 0% 0% / 0.45)",
    lg: "0 12px 32px hsl(0 0% 0% / 0.55)",
    focus: "0 0 0 2px var(--brand-500)",
  },
  z: {
    floating: 100,
    overlay: 200,
    modal: 300,
    popover: 400,
    toast: 500,
    tooltip: 600,
  },
  duration: {
    fast: "120ms",
    base: "180ms",
    slow: "260ms",
  },
} as const;

/**
 * Read a CSS custom property's current value from :root (respects the active
 * theme). Returns "" when running outside the browser / token undefined.
 */
export function cssVar(name: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") return "";
  const value = getComputedStyle(document.documentElement).getPropertyValue(name);
  return value ? value.trim() : "";
}

export type ThemeName = "dark" | "light";
export const THEME_STORAGE_KEY = "nc-theme";
