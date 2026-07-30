export function normalizeParagraphBreaks(text: string): string {
  // 把任意连续换行统一成标准段落分隔（空行），避免后端/模型返回单换行时前端折叠成一段。
  return text.replace(/\n+/g, "\n\n").trim();
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
