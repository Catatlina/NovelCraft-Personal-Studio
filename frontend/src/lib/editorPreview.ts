export function buildAiEditPreview(
  sourceText: string,
  selectedText: string,
  proposedText: string,
  operation: string,
  hasExplicitSelection: boolean,
): string {
  if (operation === "rewrite_chapter") return proposedText;
  if (operation === "continue") {
    if (hasExplicitSelection && selectedText) {
      return sourceText.replace(selectedText, `${selectedText}\n\n${proposedText}`);
    }
    return `${sourceText}\n\n${proposedText}`.trim();
  }
  return sourceText.replace(selectedText, proposedText);
}
