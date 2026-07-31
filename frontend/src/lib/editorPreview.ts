export function normalizeParagraphBreaks(text: string): string {
  // 0) 标点规范化：统一全角/半角混用
  let t = text
    .replace(/\r\n/g, "\n")
    .replace(/\.{3,}/g, "……")           // ... → ……
    .replace(/。。。/g, "……")             // 。。。→ ……
    .replace(/…{3}/g, "……")              // …… → ……（统一6点）
    .replace(/——{2,}/g, "——")             // 多余破折号合并
    .replace(/[""]/g, "「").replace(/[""]/g, "」")  // 引号统一
    .replace(/['']/g, "『").replace(/['']/g, "』");

  // 1) 把任意连续换行统一成标准段落分隔（空行）
  let normalized = t.replace(/\n+/g, "\n\n").trim();

  // 2) 兜底：若模型返回一整块无换行的文本，按网文风格切段：
  //    - 对话（「」包裹）必须独立成段
  //    - 每段 1-2 句，不超过 3 句或 80 字
  if (!normalized.includes("\n")) {
    // 先按对话边界拆分：「」包裹的内容独立成段
    const parts: string[] = [];
    const dialogRe = /「[^」]*」/g;
    let lastEnd = 0;
    let m: RegExpExecArray | null;
    while ((m = dialogRe.exec(normalized)) !== null) {
      if (m.index > lastEnd) {
        parts.push(normalized.slice(lastEnd, m.index));
      }
      parts.push(m[0]);
      lastEnd = m.index + m[0].length;
    }
    if (lastEnd < normalized.length) parts.push(normalized.slice(lastEnd));

    // 对每个非对话片段按句末标点切短段
    const grouped: string[] = [];
    for (const part of parts) {
      if (/^「/.test(part)) {
        grouped.push(part); // 对话独立成段
        continue;
      }
      const sentences = part
        .split(/(?<=[。！？!?])/)
        .map(s => s.trim())
        .filter(Boolean);
      let buf: string[] = [];
      for (const s of sentences) {
        buf.push(s);
        if (buf.length >= 2 || buf.join("").length > 80) {
          grouped.push(buf.join(""));
          buf = [];
        }
      }
      if (buf.length) grouped.push(buf.join(""));
    }
    normalized = grouped.filter(Boolean).join("\n\n");
  }

  // 3) 清理多余空行
  normalized = normalized.replace(/\n{3,}/g, "\n\n").trim();
  return normalized;
}

function safeReplace(source: string, search: string, replacement: string): string {
  if (!search) return replacement;
  // JavaScript String.replace 会把 replacement 里的 $ 当作特殊占位符（$&/$'/$`/$$），
  // 先把 replacement 里的 $ 转义成 $$，防止 AI 文本里的 $ 被吞掉或破坏段落结构。
  const escaped = replacement.replace(/\$/g, "$$$$");
  return source.replace(search, escaped);
}

export function buildAiEditPreview(
  sourceText: string,
  selectedText: string,
  proposedText: string,
  operation: string,
  hasExplicitSelection: boolean,
): string {
  const normalizedProposed = normalizeParagraphBreaks(proposedText);
  if (operation === "rewrite_chapter") return normalizedProposed;
  if (operation === "continue") {
    if (hasExplicitSelection && selectedText) {
      return safeReplace(sourceText, selectedText, `${selectedText}\n\n${normalizedProposed}`);
    }
    return `${sourceText}\n\n${normalizedProposed}`.trim();
  }
  return safeReplace(sourceText, selectedText, normalizedProposed);
}
