import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Review } from "./Review";

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("../lib/api", () => ({ api: mocks.api, ApiError: class extends Error {} }));
vi.mock("../v7/api/client", () => ({
  default: {
    getAiSmell: vi.fn().mockResolvedValue({ has_data: false }),
    getEmotionalArc: vi.fn().mockResolvedValue({ has_data: false }),
    getChapterCharacterStats: vi.fn().mockResolvedValue({ has_data: false }),
    getCharacterStats: vi.fn().mockResolvedValue({ has_data: false }),
  },
}));

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

  it("读取 V7 综合评分与 33 维审计证据，并区分模型评分和兼容折算", () => {
    render(
      <Review
        chapter={chapter}
        review={{
          canonical_engine: "v7",
          overall_score: 82,
          dimension_scores: { consistency: 90, pacing: 74 },
          audit_report: {
            count: 33,
            scored_count: 2,
            llm_scored_count: 1,
            coverage: 1 / 33,
            complete: false,
            source: "macro_projection",
            items: {
              conflict: { key: "conflict", group: "plot", label: "核心冲突", score: 88, source: "llm", evidence: "角色被迫做出选择" },
              causality: { key: "causality", group: "plot", label: "因果链", score: 74, source: "macro_projection" },
            },
          },
          final_continuity_audit: { continuity: { status: "continuous", narrative_flow: "承接上一章结尾" } },
        }}
      />,
    );

    expect(screen.getByText("82")).toBeTruthy();
    expect(screen.getByText("主分来自 V7 审阅器返回的 overall_score。")).toBeTruthy();
    expect(screen.getByText("2/33 项有分数")).toBeTruthy();
    expect(screen.getByText("兼容")).toBeTruthy();
    fireEvent.click(screen.getByText("情节与因果"));
    expect(screen.getByText(/模型逐项审计/)).toBeTruthy();
    expect(screen.getAllByText(/七维分数折算/).length).toBeGreaterThan(0);
  });

  it("没有模型分数时只按现有检查证据折算，不补造默认高分", () => {
    render(<Review chapter={{ ...chapter, id: undefined }} review={{ checks: { continuity: { status: "warning", issues: ["缺少桥接"] } } }} />);

    expect(screen.getByText("暂无综合评分")).toBeTruthy();
    expect(screen.getByText("V7 审阅尚未返回主分；其他指标不会被折算成综合分。")).toBeTruthy();
    expect(screen.getByText("需留意")).toBeTruthy();
  });
});
