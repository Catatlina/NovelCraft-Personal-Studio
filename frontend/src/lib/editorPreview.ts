function normalizeParagraphBreaks(text: string): string {
  // 把任意连续换行统一成标准段落分隔（空行），避免后端/模型返回单换行时前端折叠成一段。
  return text.replace(/\n+/g, "\n\n").trim();
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
      return sourceText.replace(selectedText, `${selectedText}\n\n${normalizedProposed}`);
    }
    return `${sourceText}\n\n${normalizedProposed}`.trim();
  }
  return sourceText.replace(selectedText, normalizedProposed);
}
