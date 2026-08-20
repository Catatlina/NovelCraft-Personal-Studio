import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { EditorAiChat } from "./EditorAiChat";

vi.mock("../lib/api", () => ({ api: vi.fn() }));

afterEach(cleanup);

beforeEach(() => {
  vi.mocked(api).mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.includes("/sessions/current")) return null as never;
    if (path === "/api/v1/authoring/sessions" && init?.method === "POST") return { id: "session-1", messages: [] } as never;
    return {} as never;
  });
});

describe("编辑器 AI 修改会话", () => {
  it("可以直接输入意见并按当前选区提交", async () => {
    const onRequestEdit = vi.fn();
    render(
      <EditorAiChat
        chapterId="chapter-1"
        selection="沈夜按住门把手。"
        onRequestEdit={onRequestEdit}
      />,
    );

    const input = screen.getByRole("textbox", { name: "输入修改意见" });
    fireEvent.change(input, { target: { value: "写得更紧张一点，保留动作事实" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(onRequestEdit).toHaveBeenCalledWith("写得更紧张一点，保留动作事实", "沈夜按住门把手。"));
    expect(screen.getByText("写得更紧张一点，保留动作事实")).toBeTruthy();
    expect(screen.getByText("写得更紧张一点，保留动作事实")).toBeTruthy();
  });

  it("没有选区时明确提示会修改整章，并支持带入审阅意见", async () => {
    const onRequestEdit = vi.fn();
    render(
      <EditorAiChat
        chapterId="chapter-1"
        selection=""
        suggestions={["章末缺少可见的下一步压力"]}
        onRequestEdit={onRequestEdit}
      />,
    );

    expect(screen.getByText("整章正文")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "章末缺少可见的下一步压力" }));
    const input = screen.getByRole("textbox", { name: "输入修改意见" });
    expect((input as HTMLTextAreaElement).value).toContain("请根据这条审阅意见修改");
    fireEvent.click(screen.getByRole("button", { name: "生成修改" }));

    await waitFor(() => expect(onRequestEdit).toHaveBeenCalledWith(
      "请根据这条审阅意见修改：章末缺少可见的下一步压力",
      "",
    ));
  });
});
