import { describe, expect, it } from "vitest";
import { buildAiEditPreview } from "./editorPreview";

describe("AI 编辑预览", () => {
  it("润色只生成候选正文，不修改输入原文", () => {
    const original = "第一段原文。\n\n第二段原文。";
    const next = buildAiEditPreview(original, "第一段原文。", "第一段润色稿。", "polish", true);

    expect(original).toBe("第一段原文。\n\n第二段原文。");
    expect(next).toBe("第一段润色稿。\n\n第二段原文。");
  });

  it("无选区续写只追加候选内容", () => {
    expect(buildAiEditPreview("现有正文", "现有正文", "下一段", "continue", false))
      .toBe("现有正文\n\n下一段");
  });

  it("整章重写候选不会混入旧正文", () => {
    expect(buildAiEditPreview("旧章", "旧章", "新章", "rewrite_chapter", false)).toBe("新章");
  });

  it("把模型返回的单换行归一化为段落分隔，避免应用到草稿后折叠成一段", () => {
    const proposed = "第一句。\n第二句。\n第三句。";
    const next = buildAiEditPreview("原文。", "原文。", proposed, "polish", true);
    expect(next).toBe("第一句。\n\n第二句。\n\n第三句。");
  });

  it("AI 文本中的 $ 不会被 String.replace 特殊解释而破坏结构", () => {
    const proposed = "价格是 $100。\n第二段。";
    const next = buildAiEditPreview("原文。", "原文。", proposed, "polish", true);
    expect(next).toBe("价格是 $100。\n\n第二段。");
  });

  it("模型返回一整块无换行的文本时按句切成短段落，避免应用后折叠成一段", () => {
    const proposed = "林晚星站在天台边。她低头瞅了瞅楼下的霓虹。心里突然冒出一个念头。命运这玩意儿是不是安排好了。她深吸一口气下了天台。第二天一早收到一条陌生短信。";
    const next = buildAiEditPreview("原文。", "原文。", proposed, "polish", true);
    // 至少被切成多段（含 \n\n），不再是单一大段
    expect(next.includes("\n\n")).toBe(true);
    expect(next.split("\n\n").length).toBeGreaterThanOrEqual(2);
  });
});
