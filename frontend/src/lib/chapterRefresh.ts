export type RefreshableChapter = {
  id: string;
  meta?: Record<string, unknown>;
  body: unknown;
};

export function sortChapterItems<T extends RefreshableChapter>(items: T[]): T[] {
  return [...items].sort((a, b) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
}

export function selectRefreshedChapter<T extends RefreshableChapter>(
  items: T[],
  currentChapterId?: string,
): T | null {
  return items.find(item => item.id === currentChapterId) ?? items[0] ?? null;
}

export function shouldSyncEditorText<T extends RefreshableChapter>(
  previousChapter: T | null,
  currentEditorText: string,
  nextChapter: T | null,
  textOf: (body: unknown) => string,
): boolean {
  if (!nextChapter) return previousChapter === null;
  if (!previousChapter || previousChapter.id !== nextChapter.id) return true;
  // A settled workflow may refresh the same row with a new canonical review
  // and body. Preserve an author's unsaved edits, but replace text when the
  // editor still mirrors the previous persisted chapter.
  return currentEditorText === textOf(previousChapter.body);
}
