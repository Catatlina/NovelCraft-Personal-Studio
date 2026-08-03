import { describe, expect, it } from "vitest";
import { textValue } from "../App";

describe("结构化正文安全解析", () => {
  it("递归提取嵌套 TipTap 文本，不产生 object 字符串", () => {
    const value = {
      type: "doc",
      content: [
        { type: "paragraph", content: [{ type: "text", text: "真实第一段。" }] },
        { type: "paragraph", content: [{ type: "text", text: "真实第二段。" }] },
      ],
    };

    expect(textValue(value)).toBe("真实第一段。\n\n真实第二段。");
    expect(textValue({ broken: { nested: true } })).toBe("");
    expect(textValue(value)).not.toContain("[object Object]");
  });
});
