import { describe, expect, it } from 'vitest';
import {
  selectRefreshedChapter,
  shouldSyncEditorText,
  sortChapterItems,
} from './chapterRefresh';

const textOf = (body: unknown) => String((body as { text?: string })?.text || '');

describe('chapter refresh after a settled workflow', () => {
  it('sorts chapters by sequence without mutating the server response', () => {
    const items = [
      { id: '2', meta: { seq: 2 }, body: { text: '第二章' } },
      { id: '1', meta: { seq: 1 }, body: { text: '第一章' } },
    ];

    expect(sortChapterItems(items).map(item => item.id)).toEqual(['1', '2']);
    expect(items.map(item => item.id)).toEqual(['2', '1']);
  });

  it('keeps the selected chapter when the server refreshes its metadata', () => {
    const refreshed = [
      { id: '1', meta: { seq: 1 }, body: { text: '最新正文' } },
      { id: '2', meta: { seq: 2 }, body: { text: '第二章' } },
    ];

    expect(selectRefreshedChapter(refreshed, '1')?.body).toEqual({ text: '最新正文' });
    expect(selectRefreshedChapter(refreshed, 'missing')?.id).toBe('1');
  });

  it('does not overwrite unsaved editor text during a background refresh', () => {
    const previous = { id: '1', meta: { seq: 1 }, body: { text: '旧正文' } };
    const next = { id: '1', meta: { seq: 1 }, body: { text: '新正文' } };

    expect(shouldSyncEditorText(previous, '旧正文', next, textOf)).toBe(true);
    expect(shouldSyncEditorText(previous, '作者未保存修改', next, textOf)).toBe(false);
  });
});
