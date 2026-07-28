import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceDashboard } from "./WorkspaceDashboard";

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("小说首页真实状态", () => {
  it("用真实书库响应渲染小说数据", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      code: 0,
      message: "ok",
      data: [{
        id: "book-1",
        title: "潮汐之外",
        status: "draft",
        meta: { target_words: 100000 },
        total_words: 25000,
        chapter_count: 12,
        created_at: "2026-07-01T00:00:00Z",
        updated_at: "2026-07-28T00:00:00Z",
      }],
    }), { status: 200, headers: { "Content-Type": "application/json" } })));

    render(<WorkspaceDashboard projectId="project-1" onNavigate={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("潮汐之外")).toBeTruthy());
    expect(screen.getByText("12 章 · 25,000 字")).toBeTruthy();
    expect(screen.getByLabelText("目标字数完成 25%")).toBeTruthy();
  });

  it("请求失败时显示可操作错误，而不是伪造数据", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("service unavailable")));

    render(<WorkspaceDashboard projectId="project-1" onNavigate={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("书库暂时无法加载")).toBeTruthy());
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
  });
});
