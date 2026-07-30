export function normalizeParagraphBreaks(text: string): string {
  // 1) 把任意连续换行统一成标准段落分隔（空行），避免后端/模型返回单换行时前端折叠成一段。
  let normalized = text.replace(/\r\n/g, "\n").replace(/\n+/g, "\n\n").trim();
  // 2) 兜底：若模型返回一整块无换行的文本（常见），按句末标点切成短段落（网文节奏，2-3 句/段）。
  //    与后端 _ensure_editor_paragraphs 保持一致，覆盖流式/离线等不经过后端的路径。
  if (!normalized.includes("\n")) {
    const sentences = normalized
      .split(/(?<=[。！？!?])/)
      .map(s => s.trim())
      .filter(Boolean);
    if (sentences.length > 1) {
      const grouped: string[] = [];
      let buf: string[] = [];
      for (const s of sentences) {
        buf.push(s);
        if (buf.length >= 3 || [...buf].join("").length > 90) {
          grouped.push(buf.join(""));
          buf = [];
        }
      }
      if (buf.length) grouped.push(buf.join(""));
      normalized = grouped.join("\n\n");
    }
  }
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
