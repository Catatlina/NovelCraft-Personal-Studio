import { describe, expect, it } from "vitest";
import { formatLiveReviewScore } from "./Editor";

describe("实时审阅评分字段", () => {
  it("优先读取 V7 overall_score，避免有效审阅显示为 --", () => {
    expect(formatLiveReviewScore({ overall_score: 78 })).toBe("78");
  });

  it("兼容旧 score 和字符串数值", () => {
    expect(formatLiveReviewScore({ score: 81.5 })).toBe("81.5");
    expect(formatLiveReviewScore({ overall_score: "82" })).toBe("82");
  });

  it("没有评分时才显示占位符", () => {
    expect(formatLiveReviewScore({ issues: ["需要补强节奏"] })).toBe("--");
  });
});
