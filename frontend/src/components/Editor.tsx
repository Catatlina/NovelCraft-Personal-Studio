import React, { useEffect, useMemo, useRef, useState } from "react";
import { Save, RotateCcw } from "lucide-react";
import { RichEditor } from "./RichEditor";
import "../styles/proto.css";

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
      <div className="card" style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, padding: "10px 16px", flexWrap: "wrap" }}>
        <select
          value={chapter?.id ?? ""}
          onChange={event => selectChapter(event.target.value)}
          disabled={!chapters.length}
          aria-label="选择章节"
          className="form-input"
          style={{ minWidth: 180, width: "auto", height: 34 }}
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
          className="form-input"
          style={{
            flex: 1, minWidth: 120, background: "transparent", border: "none",
            fontSize: 18, fontWeight: 600, color: "var(--text-1)", height: 34
          }}
        />
        <button onClick={saveChapter} disabled={!chapter} className="btn-sm btn-primary" style={{ width: "auto", padding: "0 14px" }}>
          <Save size={15} /> 保存
        </button>
        <small style={{ color: "var(--text-3)", fontSize: 12 }} data-testid="autosave-status">
          {dirty ? (<>未保存改动…</>) : autoSavedAt ? (<>已自动保存 {autoSavedAt}</>) : ""}
        </small>

        {/* View toggles */}
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          <button
            onClick={() => setFocusMode(!isFocusMode)}
            title="专注模式"
            className="btn-sm btn-ghost"
          >
            {isFocusMode ? "👁 专注中" : "📝 专注"}
          </button>
          <button
            onClick={() => setNightMode(!isNightMode)}
            title="夜间模式"
            className="btn-sm btn-ghost"
          >
            {isNightMode ? "☀️" : "🌙"}
          </button>
          <button
            onClick={() => setFullscreen(!isFullscreen)}
            title={isFullscreen ? "退出全屏" : "全屏"}
            className="btn-sm btn-ghost"
          >
            {isFullscreen ? "↙ 退出全屏" : "⛶ 全屏"}
          </button>
        </div>
      </div>

      {/* ── Stream preview ── */}
      {streamPreview ? (
        <div className="card" style={{ maxHeight: 160, overflowY: "auto", fontSize: 13, whiteSpace: "pre-wrap", marginBottom: 12, padding: 12 }}>
          <small style={{ color: "var(--cyan)" }}>AI 生成中…</small>
          <div style={{ marginTop: 4 }}>{streamPreview}</div>
        </div>
      ) : null}

      {/* ── Offline notice ── */}
      {(offlineNotice || offlineQueueCount) ? (
        <div className="badge orange" style={{ marginBottom: 12, padding: "8px 14px", fontSize: 12 }}>
          {offlineNotice || `离线队列 ${offlineQueueCount} 项`}
        </div>
      ) : null}

      {/* ── Conflict resolution ── */}
      {conflict && !conflictDismissed ? (
        <div className="card" style={{ marginBottom: 12 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--orange)", marginBottom: 12 }}>离线版本冲突</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>本地稿<textarea className="form-input" value={localConflictText} readOnly rows={8} style={{ marginTop: 4, background: "rgba(0,0,0,.25)", fontSize: 12 }} /></label>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>服务器稿<textarea className="form-input" value={serverText} readOnly rows={8} style={{ marginTop: 4, background: "rgba(0,0,0,.25)", fontSize: 12 }} /></label>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>合并稿<textarea className="form-input" value={mergeText} onChange={event => setMergeText(event.target.value)} rows={8} style={{ marginTop: 4, background: "rgba(0,0,0,.25)", fontSize: 12 }} /></label>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn-sm btn-ghost" onClick={() => { setEditorText(localConflictText); setConflictDismissed(true); }}>采用本地稿</button>
            <button className="btn-sm btn-ghost" onClick={() => { setEditorText(serverText); setConflictDismissed(true); }}>采用服务器稿</button>
            <button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={() => { setEditorText(mergeText); setConflictDismissed(true); }}>采用合并稿</button>
          </div>
        </div>
      ) : null}

      {/* ── Main editor area with chapter tree (left) + editor (center) + AI panel (right) ── */}
      <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0 }}>
        {/* ── Left: Chapter tree (hidden in focus mode) ── */}
        {!isFocusMode && chapters.length > 1 && (
          <div className="sidebar" style={{ width: 200 }}>
            <div className="card-title" style={{ padding: "4px 8px 8px", fontSize: 13 }}>
              章节目录
            </div>
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
      <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
        <div className="card-title" style={{ marginBottom: 10 }}>
          版本历史
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {versions.map(v => (
          <button key={v.id} onClick={() => restoreVersion(v.id)} className="btn-sm btn-ghost" style={{ fontSize: 12 }}>
            <RotateCcw size={12} /> {v.label}
            <small style={{ color: "var(--text-3)", marginLeft: 4 }}>{new Date(v.created_at).toLocaleString()}</small>
          </button>
        ))}
        </div>
        {offlineAiResults?.length ? (
          <>
            <div className="card-title" style={{ marginTop: 12, marginBottom: 8 }}>离线 AI 结果</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {offlineAiResults?.map(result => (
              <button key={result.id} onClick={() => applyOfflineAiResult?.(result.id, result.text)} className="btn-sm btn-ghost" style={{ fontSize: 12 }}>
                应用 AI 结果
                <small style={{ color: "var(--text-3)", marginLeft: 4, maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{result.text.slice(0, 36)}…</small>
              </button>
            ))}
            </div>
          </>
        ) : null}
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
