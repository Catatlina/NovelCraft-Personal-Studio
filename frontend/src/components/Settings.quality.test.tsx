import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Settings } from "./Settings";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  getApiKey: () => "",
  getApiUrl: () => "",
  getModel: () => "",
  setApiKey: vi.fn(),
  setApiUrl: vi.fn(),
  setModel: vi.fn(),
}));

const apiMock = vi.mocked(api);
const lexicon = {
  schema_version: "ai-flavor-lexicon-v2",
  version: 2,
  mode: "advisory" as const,
  hard_gate: false as const,
  source: "builtin",
  category_count: 1,
  phrase_count: 1,
  enabled_phrase_count: 1,
  usage_note: "候选信号，不是禁词表。",
  categories: [{
    key: "classic_description",
    label: "经典描写",
    description: "神态与心理表达候选",
    enabled: true,
    phrases: [{ phrase: "嘴角微扬", enabled: true, note: "复核堆叠" }],
  }],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AI 味词库设置", () => {
  it("展示来源与候选提示，并支持展开、添加和保存", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/api/v1/quality/ai-flavor-lexicon") return lexicon as never;
      if (path === "/api/v1/quality/ai-flavor-lexicon/reset") return lexicon as never;
      return lexicon as never;
    });

    render(<Settings />);
    fireEvent.click(screen.getByRole("button", { name: "质量规则" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "AI 味词库" })).toBeTruthy());
    expect(screen.getByText(/内置默认/, { exact: false })).toBeTruthy();
    expect(screen.getByText("候选信号，不是禁词表。", { exact: false })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "展开经典描写" }));
    const input = screen.getByRole("textbox", { name: "为经典描写添加词条" });
    fireEvent.change(input, { target: { value: "模板化描写" } });
    fireEvent.click(screen.getByRole("button", { name: "添加" }));
    expect(screen.getByDisplayValue("模板化描写")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "保存词库" }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/api/v1/quality/ai-flavor-lexicon",
      expect.objectContaining({ method: "PUT" }),
    ));
  });
});
