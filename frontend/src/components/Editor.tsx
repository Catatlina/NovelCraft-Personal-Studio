import React, { useEffect, useMemo, useRef, useState } from "react";
import { Save, RotateCcw } from "lucide-react";
import { RichEditor } from "./RichEditor";

type Content = { id: string; title: string; body: { content?: { text?: string }[] }; meta: Record<string, unknown> };
type Version = { id: string; label: string; reason?: string; snapshot: Record<string, unknown>; created_at: string };

export function Editor({ chapter, chapters, selectChapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion, offlineNotice, offlineQueueCount, offlineAiResults, applyOfflineAiResult, streamPreview, editorAiReview, deaiResult, deaiLoading }: {
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
  // ── New: De-AI pipeline state ──
  deaiResult?: { original_score?: number; final_score?: number; layers?: Array<{ name: string; label: string; score_before: number; score_after: number; status: string }>; final_text?: string } | null;
  deaiLoading?: boolean;
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

  // ── UI state toggles ──
  const [isFullscreen, setFullscreen] = useState(false);
  const [isNightMode, setNightMode] = useState(false);
  const [isFocusMode, setFocusMode] = useState(false);

  // ── Keyboard shortcut: Escape to exit fullscreen ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

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

  // ── Chapter tree from chapters list ──
  const chapterTree = useMemo(() => {
    return chapters.map((ch, i) => ({
      id: ch.id,
      title: ch.title,
      seq: Number(ch.meta?.seq || i + 1),
    }));
  }, [chapters]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* ── Top bar: chapter select, title, save, view toggles ── */}
      <div style={{
        display: "flex", gap: 8, alignItems: "center", marginBottom: 8,
        padding: "8px 12px", background: "var(--nc-card, rgba(22,22,50,.7))",
        backdropFilter: "blur(12px)", borderRadius: 8, border: "1px solid rgba(255,107,53,.15)",
        flexWrap: "wrap"
      }}>
        <select
          value={chapter?.id ?? ""}
          onChange={event => selectChapter(event.target.value)}
          disabled={!chapters.length}
          aria-label="选择章节"
          style={{ minWidth: 180 }}
        >
          {chapters.map((item, index) => (
            <option key={item.id} value={item.id}>
              {Number(item.meta?.seq || index + 1)}. {item.title}
            </option>
          ))}
        </select>
        <input
          value={chapter?.title ?? ""}
          readOnly
          style={{
            flex: 1, minWidth: 120, background: "transparent", border: "none",
            fontSize: 18, fontWeight: 600, color: "var(--text-primary)"
          }}
        />
        <button onClick={saveChapter} disabled={!chapter} className="primary" style={{ padding: "6px 12px" }}>
          <Save size={15} /> 保存
        </button>
        <small className="muted" data-testid="autosave-status">
          {dirty ? (<>未保存改动…</>) : autoSavedAt ? (<>已自动保存 {autoSavedAt}</>) : ""}
        </small>

        {/* View toggles */}
        <div style={{ display: "flex", gap: 2, marginLeft: "auto" }}>
          <button
            onClick={() => setFocusMode(!isFocusMode)}
            title="专注模式"
            style={{ border: isFocusMode ? "1px solid var(--nc-accent)" : undefined, background: isFocusMode ? "rgba(0,229,255,.1)" : undefined }}
          >
            {isFocusMode ? "👁 专注中" : "📝 专注"}
          </button>
          <button
            onClick={() => setNightMode(!isNightMode)}
            title="夜间模式"
            style={{ border: isNightMode ? "1px solid var(--nc-accent)" : undefined }}
          >
            {isNightMode ? "☀️" : "🌙"}
          </button>
          <button
            onClick={() => setFullscreen(!isFullscreen)}
            title={isFullscreen ? "退出全屏" : "全屏"}
          >
            {isFullscreen ? "↙ 退出全屏" : "⛶ 全屏"}
          </button>
        </div>
      </div>

      {/* ── Stream preview ── */}
      {streamPreview ? (
        <div className="panel" style={{ maxHeight: 160, overflowY: "auto", fontSize: 13, whiteSpace: "pre-wrap", marginBottom: 8 }}>
          <small className="muted">AI 生成中…</small>
          <div>{streamPreview}</div>
        </div>
      ) : null}

      {/* ── Offline notice ── */}
      {(offlineNotice || offlineQueueCount) ? (
        <div className="pill pending" style={{ marginBottom: 8 }}>
          {offlineNotice || `离线队列 ${offlineQueueCount} 项`}
        </div>
      ) : null}

      {/* ── Conflict resolution ── */}
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

      {/* ── Main editor area with chapter tree (left) + editor (center) + AI panel (right) ── */}
      <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0 }}>
        {/* ── Left: Chapter tree (hidden in focus mode) ── */}
        {!isFocusMode && chapters.length > 1 && (
          <div style={{
            width: 200, flexShrink: 0, overflowY: "auto",
            background: "var(--nc-card, rgba(22,22,50,.7))",
            backdropFilter: "blur(12px)", borderRadius: 10,
            border: "1px solid rgba(0,229,255,.1)", padding: 8
          }}>
            <h2 style={{ fontSize: 13, padding: "0 12px 8px", color: "var(--text-muted)", margin: 0 }}>章节目录</h2>
            <div className="chapter-tree">
              {chapterTree.map(ch => (
                <button
                  key={ch.id}
                  className={`chapter-tree-item ${chapter?.id === ch.id ? "active" : ""}`}
                  onClick={() => selectChapter(ch.id)}
                >
                  <span className="chapter-seq">{ch.seq}</span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ch.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Center: RichEditor ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <RichEditor
            value={editorText}
            onChange={setEditorText}
            onSelection={setSelection}
            selection={selection}
            onAiOp={op => runEditorOp(op)}
            aiReview={editorAiReview ?? null}
            deaiResult={deaiResult ?? null}
            deaiLoading={deaiLoading ?? false}
            autoSavedAt={autoSavedAt}
            dirty={dirty}
            isFullscreen={isFullscreen}
            isNightMode={isNightMode}
            isFocusMode={isFocusMode}
            onToggleFullscreen={() => setFullscreen(!isFullscreen)}
            onToggleNightMode={() => setNightMode(!isNightMode)}
            onToggleFocusMode={() => setFocusMode(!isFocusMode)}
          />
        </div>
      </div>

      {/* ── Bottom: Version history ── */}
      <div className="panel versions" style={{ marginTop: 12 }}>
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

      {/* ── Fullscreen overlay ── */}
      {isFullscreen && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 200,
          background: "var(--nc-bg, #0a0a14)", padding: 16,
          display: "flex", flexDirection: "column"
        }}>
          <RichEditor
            value={editorText}
            onChange={setEditorText}
            onSelection={setSelection}
            selection={selection}
            onAiOp={(op: string) => runEditorOp(op)}
            aiReview={editorAiReview ?? null}
            deaiResult={deaiResult ?? null}
            deaiLoading={deaiLoading ?? false}
            autoSavedAt={autoSavedAt}
            dirty={dirty}
            isFullscreen={true}
            isNightMode={isNightMode}
            isFocusMode={false}
            onToggleFullscreen={() => setFullscreen(false)}
            onToggleNightMode={() => setNightMode(!isNightMode)}
            onToggleFocusMode={() => setFocusMode(!isFocusMode)}
          />
        </div>
      )}
    </div>
  );
}
