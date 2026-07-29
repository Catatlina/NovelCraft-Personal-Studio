import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Review } from "./Review";

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("../lib/api", () => ({ api: mocks.api, ApiError: class extends Error {} }));

const chapter = {
  id: "chapter-1",
  title: "第一章 夜雨",
  updated_at: "2026-07-29T10:00:00Z",
  body: { type: "doc", content: [{ type: "paragraph", text: "他是一个好人。" }] },
  meta: {
    repair_recommendation: { action: "repair_local", level: "sentence", reason: "文字问题" },
  },
};
const review = {
  score: 68,
  checks: { style: { status: "fail", issues: ["人物评价过于空泛"] } },
};

describe("审阅修复预览门禁", () => {
  beforeEach(() => mocks.api.mockReset());
  afterEach(() => cleanup());

  it("生成预览不会直接应用正文", async () => {
    const onApplied = vi.fn();
    mocks.api.mockResolvedValueOnce({
      action: "repair_local",
      base_updated_at: "2026-07-29T10:00:00+00:00",
      current_body: chapter.body,
      proposal: {
        action: "repair_local",
        proposed_body: { type: "doc", content: [{ type: "paragraph", text: "他是个愿意帮人的人。" }] },
        replacements: [{ anchor: "一个好人", replacement: "个愿意帮人的人" }],
      },
      signature: "a".repeat(64),
    });

    render(<Review chapter={chapter} review={review} onRepairApplied={onApplied} />);
    fireEvent.click(screen.getByRole("button", { name: /生成修复预览/ }));

    expect(await screen.findByText("修复预览 · 尚未应用")).toBeTruthy();
    expect(screen.getByText("他是个愿意帮人的人。")).toBeTruthy();
    expect(onApplied).not.toHaveBeenCalled();
    expect(mocks.api).toHaveBeenCalledTimes(1);
  });

  it("只有点击确认应用后才调用应用端点", async () => {
    const onApplied = vi.fn();
    mocks.api
      .mockResolvedValueOnce({
        action: "repair_local",
        base_updated_at: "2026-07-29T10:00:00+00:00",
        current_body: chapter.body,
        proposal: {
          action: "repair_local",
          proposed_body: { type: "doc", content: [{ type: "paragraph", text: "他是个愿意帮人的人。" }] },
          replacements: [{ anchor: "一个好人", replacement: "个愿意帮人的人" }],
        },
        signature: "a".repeat(64),
      })
      .mockResolvedValueOnce({
        body: { type: "doc", content: [{ type: "paragraph", text: "他是个愿意帮人的人。" }] },
        status: "needs_review",
        updated_at: "2026-07-29T10:01:00+00:00",
      });

    render(<Review chapter={chapter} review={review} onRepairApplied={onApplied} />);
    fireEvent.click(screen.getByRole("button", { name: /生成修复预览/ }));
    fireEvent.click(await screen.findByRole("button", { name: "确认应用" }));

    await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(2));
    expect(String(mocks.api.mock.calls[1][0])).toContain("/repair-apply");
    expect(onApplied).toHaveBeenCalledWith(expect.objectContaining({ status: "needs_review" }));
  });
});
