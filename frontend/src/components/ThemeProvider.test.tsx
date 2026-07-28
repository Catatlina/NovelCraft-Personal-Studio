import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider, useTheme } from "./ThemeProvider";

function ThemeProbe() {
  const { theme, preference, setTheme } = useTheme();
  return (
    <button type="button" onClick={() => setTheme("dark")}>
      {preference}:{theme}
    </button>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", vi.fn().mockImplementation(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("Starlume theme contract", () => {
  it("follows the system by default and persists a manual choice", () => {
    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);

    expect(screen.getByRole("button").textContent).toBe("system:light");
    expect(document.documentElement.dataset.theme).toBe("light");

    act(() => screen.getByRole("button").click());

    expect(screen.getByRole("button").textContent).toBe("dark:dark");
    expect(localStorage.getItem("starlume-theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
