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
});
