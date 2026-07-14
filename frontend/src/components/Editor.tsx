import React, { useEffect, useMemo, useRef, useState } from "react";
import { Save, RotateCcw } from "lucide-react";
import { RichEditor } from "./RichEditor";

type Content = { id: string; title: string; body: { content?: { text?: string }[] }; meta: Record<string, unknown> };
type Version = { id: string; label: string; reason?: string; snapshot: Record<string, unknown>; created_at: string };

export function Editor({ chapter, chapters, selectChapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion, offlineNotice, offlineQueueCount, offlineAiResults, applyOfflineAiResult, streamPreview, editorAiReview }: {
  chapter: Content | null; chapters: Content[]; selectChapter: (id: string) => void;
  editorText: string; setEditorText: (t: string) => void;
  selection: string; setSelection: (s: string) => void;
  saveChapter: () => void; runEditorOp: (op: string) => void;
  versions: Version[]; restoreVersion: (id: string) => void;
  offlineNotice?: string; offlineQueueCount?: number;
  offlineAiResults?: Array<{ id: string; text: string }>;
  applyOfflineAiResult?: (id: string, text: string) => void;
  streamPreview?: string;
  editorAiReview?: { review?: any; next?: any } | null;
}) {
  const conflict = versions.find(version => version.label === "offline_conflict" && version.reason === "offline_conflict");
  const docText = (body: any) => body?.content?.map((item: any) => item?.text || "").join("\n\n") || "";
  const localConflictText = useMemo(() => docText((conflict?.snapshot as any)?.body), [conflict?.id]);
  const serverText = useMemo(() => docText(chapter?.body), [chapter?.id, (chapter as any)?.updated_at]);
  const [mergeText, setMergeText] = useState("");
  const [conflictDismissed, setConflictDismissed] = useState(false);
  useEffect(() => {
    setMergeText(localConflictText || editorText);
    setConflictDismissed(false);
  }, [conflict?.id]);

  // NC-LIB-003: debounced autosave — 3s after the last edit, only when the draft
  // actually differs from the persisted chapter. Conflict resolution pauses it.
  const saveRef = useRef(saveChapter);
  saveRef.current = saveChapter;
  const [autoSavedAt, setAutoSavedAt] = useState("");
  const dirty = !!chapter && editorText !== serverText;
  useEffect(() => {
    if (!chapter || !dirty) return;
    if (conflict && !conflictDismissed) return;
    const timer = setTimeout(() => {
      saveRef.current();
      setAutoSavedAt(new Date().toLocaleTimeString());
    }, 3000);
    return () => clearTimeout(timer);
  }, [editorText, chapter?.id, dirty, conflict?.id, conflictDismissed]);

  return (
    <div className="editor-grid">
      <div className="panel">
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <select value={chapter?.id ?? ""} onChange={event => selectChapter(event.target.value)} disabled={!chapters.length} aria-label="选择章节">
            {chapters.map((item, index) => <option key={item.id} value={item.id}>{Number(item.meta?.seq || index + 1)}. {item.title}</option>)}
          </select>
          <input value={chapter?.title ?? ""} readOnly style={{ flex: 1, background: "transparent", border: "none", fontSize: 18, fontWeight: 600 }} />
          <button onClick={saveChapter} disabled={!chapter}><Save size={16} />保存</button>
          <small className="muted" data-testid="autosave-status">{dirty ? "未保存改动…" : autoSavedAt ? `已自动保存 ${autoSavedAt}` : ""}</small>
        </div>
        {streamPreview ? (
          <div className="panel" style={{ maxHeight: 160, overflowY: "auto", fontSize: 13, whiteSpace: "pre-wrap" }}>
            <small className="muted">AI 生成中…</small>
            <div>{streamPreview}</div>
          </div>
        ) : null}
        {(offlineNotice || offlineQueueCount) ? (
          <div className="pill pending" style={{ marginBottom: 8 }}>
            {offlineNotice || `离线队列 ${offlineQueueCount} 项`}
          </div>
        ) : null}
        {conflict && !conflictDismissed ? (
          <div className="panel" style={{ marginBottom: 12 }}>
            <h2>离线版本冲突</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <label>本地稿<textarea value={localConflictText} readOnly rows={8} /></label>
              <label>服务器稿<textarea value={serverText} readOnly rows={8} /></label>
              <label>合并稿<textarea value={mergeText} onChange={event => setMergeText(event.target.value)} rows={8} /></label>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button onClick={() => { setEditorText(localConflictText); setConflictDismissed(true); }}>采用本地稿</button>
              <button onClick={() => { setEditorText(serverText); setConflictDismissed(true); }}>采用服务器稿</button>
              <button className="primary" onClick={() => { setEditorText(mergeText); setConflictDismissed(true); }}>采用合并稿</button>
            </div>
          </div>
        ) : null}
        <RichEditor value={editorText} onChange={setEditorText} onSelection={setSelection} onAiOp={op => runEditorOp(op)} />
        {editorAiReview?.review || editorAiReview?.next ? (
          <div className="editor-review-panel">
            {editorAiReview.review && <section>
              <h2>七维评分</h2>
              <strong>{editorAiReview.review.score ?? "未评分"}</strong>
              <p>{(editorAiReview.review.issues || []).join("；") || "暂无具体问题"}</p>
            </section>}
            {editorAiReview.next && <section>
              <h2>下一章规划</h2>
              <strong>{editorAiReview.next.next_title || "下一章"}</strong>
              <p>{[...(editorAiReview.next.goals || []), ...(editorAiReview.next.conflicts || []), ...(editorAiReview.next.warnings || [])].join("；")}</p>
            </section>}
          </div>
        ) : null}
      </div>
      <div className="panel versions">
        <h2>版本历史</h2>
        {versions.map(v => (
          <button key={v.id} onClick={() => restoreVersion(v.id)}>
            <RotateCcw size={14} />{v.label}
            <small>{new Date(v.created_at).toLocaleString()}</small>
          </button>
        ))}
        {offlineAiResults?.length ? <h2>离线 AI 结果</h2> : null}
        {offlineAiResults?.map(result => (
          <button key={result.id} onClick={() => applyOfflineAiResult?.(result.id, result.text)}>
            应用 AI 结果
            <small>{result.text.slice(0, 36)}…</small>
          </button>
        ))}
      </div>
    </div>
  );
}
