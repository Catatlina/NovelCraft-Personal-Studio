import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Settings } from "./Settings";
import pkg from "../../package.json";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  getApiKey: () => "",
  getApiUrl: () => "",
  getModel: () => "",
  setApiKey: vi.fn(),
  setApiUrl: vi.fn(),
  setModel: vi.fn(),
}));

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

describe("设置页版本 badge", () => {
  it("在设置页底部展示来自 package.json 的构建版本", () => {
    render(<Settings />);

    const badge = screen.getByTestId("app-version-badge");
    expect(badge.className).toContain("badge");
    expect(badge.textContent).toBe(`v${pkg.version}`);
  });

  it("版本号与 package.json 保持一致（不为空、不为占位符）", () => {
    render(<Settings />);

    const badge = screen.getByTestId("app-version-badge");
    const text = badge.textContent ?? "";
    expect(text.startsWith("v")).toBe(true);
    expect(text.length).toBeGreaterThan(1);
    expect(text).not.toMatch(/unknown|placeholder|todo/i);
  });
});
