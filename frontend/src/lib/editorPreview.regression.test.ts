import { describe, expect, it, vi } from "vitest";

/**
 * 回归测试：AI 建议应用后必须立即落库刷新 updated_at 基准，
 * 否则 3s debounce autosave 会用过期 base_updated_at 提交触发
 * offline_conflict 回滚（2026-08-01 1306484 修复）。
 *
 * 这里直接校验 App.tsx 源码中的关键调用契约（静态断言），
 * 以及 editorPreview 的替换语义（运行时断言）。
 */
import { buildAiEditPreview, normalizeParagraphBreaks } from "../lib/editorPreview";

describe("editorPreview 替换语义（回归）", () => {
  it("整章替换：rewrite_chapter 直接返回建议文本", () => {
    const out = buildAiEditPreview("旧正文", "旧正文", "新正文", "rewrite_chapter", false);
    expect(out).toBe("新正文");
  });

  it("选区替换：polish 只替换选中部分", () => {
    const source = "前面。\n\n被选中。\n\n后面。";
    const out = buildAiEditPreview(source, "被选中。", "新文本。", "polish", true);
    expect(out).toBe("前面。\n\n新文本。\n\n后面。");
    expect(out).not.toContain("被选中");
  });

  it("无选区时整章作为替换目标（审阅区按建议润色）", () => {
    const source = "整章内容第一段。\n\n第二段。";
    const out = buildAiEditPreview(source, source, "建议后的整章。", "polish", false);
    expect(out).toBe("建议后的整章。");
  });

  it("continue 追加到末尾", () => {
    const out = buildAiEditPreview("已有。", "", "续写。", "continue", false);
    expect(out).toBe("已有。\n\n续写。");
  });

  it("normalizeParagraphBreaks 不丢内容且统一段落", () => {
    const out = normalizeParagraphBreaks("段落一。\n\n\n段落二。");
    expect(out).toContain("段落一");
    expect(out).toContain("段落二");
    expect(out).not.toContain("\n\n\n");
  });
});

describe("applyPendingAiEdit 落库契约（静态断言）", () => {
  function readAppTsx(): string {
    // 直接从源码根读 App.tsx（相对本文件：src/lib → src → 项目根）
    const fs = require("fs");
    const path = require("path");
    const p = path.resolve(__dirname, "../App.tsx");
    return fs.readFileSync(p, "utf-8");
  }

  it("App.tsx 中 apply 后立即 saveChapter(pendingAiEdit.nextText)", () => {
    const src = readAppTsx();
    expect(src).toContain("saveChapter(pendingAiEdit.nextText)");
  });

  it("saveChapter 支持 textOverride 参数", () => {
    const src = readAppTsx();
    expect(src).toMatch(/saveChapter\(textOverride\?: string\)/);
  });
});
