import React, { useEffect, useMemo, useRef, useState } from "react";
import { Save, RotateCcw, Wand2, Sparkles, Bot, RefreshCcw, Send } from "lucide-react";
import { RichEditor } from "./RichEditor";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";
import "../styles/novel-prose.css";

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

  // ── AI chat state ──
  const [aiChatInput, setAiChatInput] = useState("");
  // 初始为空数组：不再伪造"AI 已分析"的问候语（审计 P2-1）。
  // 真实结果由 editorAiReview 回填 / 用户提问后追加；空态由下方引导文案承接。
  const [aiChatMessages, setAiChatMessages] = useState<Array<{ role: "system" | "user"; text: string }>>([]);

  const sendAiMessage = () => {
    const text = aiChatInput.trim();
    if (!text) return;
    setAiChatMessages(prev => [...prev, { role: "user", text }]);
    setAiChatInput("");
    runEditorOp("polish"); // trigger AI operation; the result will feed back via editorAiReview
  };

  // ── Feed AI review into chat ──
  useEffect(() => {
    if (editorAiReview?.review?.issues?.length) {
      const msgs = editorAiReview.review.issues.map((issue: string) => `• ${issue}`).join("\n");
      setAiChatMessages(prev => [...prev, { role: "system", text: `七维审查结果：\n${msgs}` }]);
    }
  }, [editorAiReview?.review?.issues]);

  // ── Keyboard shortcut: Escape to exit fullscreen ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

  // NC-LIB-003: debounced autosave
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

  // Paginate the outline / version / offline-result lists.
  const chapterTreePager = usePagination({ items: chapterTree, pageSize: 10, mode: "client" });
  const versionsPager = usePagination({ items: versions, pageSize: 10, mode: "client" });
  const offlineResultsPager = usePagination({ items: offlineAiResults ?? [], pageSize: 10, mode: "client" });

  // ── Word count ──
  const wordCount = useMemo(() => {
    const text = editorText.replace(/<[^>]*>/g, "");
    return text.replace(/\s/g, "").length;
  }, [editorText]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-base)" }}>
      {/* ── Minimal toolbar ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border-subtle)", marginBottom: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{chapter ? chapter.title : "编辑器"}</span>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {chapter ? `字数 ${wordCount.toLocaleString()}` : ""}
            {dirty && <span style={{ color: "var(--warning)", marginLeft: 8 }}>未保存</span>}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="btn-sm btn-ghost" onClick={() => runEditorOp("continue")} style={{ gap: 4 }}>
            <Bot size={13} />续写
          </button>
          <button className="btn-sm btn-ghost" onClick={() => runEditorOp("polish")} style={{ gap: 4 }}>
            <Wand2 size={13} />润色
          </button>
          <button onClick={saveChapter} disabled={!chapter} className="btn-sm btn-primary" style={{ gap: 4 }}>
            <Save size={14} />保存
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
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>本地稿<textarea className="form-input" value={localConflictText} readOnly rows={8} style={{ marginTop: 4, background: "var(--bg-muted)", fontSize: 12 }} /></label>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>服务器稿<textarea className="form-input" value={serverText} readOnly rows={8} style={{ marginTop: 4, background: "var(--bg-muted)", fontSize: 12 }} /></label>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>合并稿<textarea className="form-input" value={mergeText} onChange={event => setMergeText(event.target.value)} rows={8} style={{ marginTop: 4, background: "var(--bg-muted)", fontSize: 12 }} /></label>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn-sm btn-ghost" onClick={() => { setEditorText(localConflictText); setConflictDismissed(true); }}>采用本地稿</button>
            <button className="btn-sm btn-ghost" onClick={() => { setEditorText(serverText); setConflictDismissed(true); }}>采用服务器稿</button>
            <button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={() => { setEditorText(mergeText); setConflictDismissed(true); }}>采用合并稿</button>
          </div>
        </div>
      ) : null}

      {/* ── 3-column editor layout (prototype) ── */}
      <div className="editor" style={{ flex: 1, minHeight: 0 }}>
        {/* LEFT: Chapter outline */}
        <div className="ed-side">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
              <path d="M3 3h18v18H3z"/><path d="M9 3v18M3 9h6"/>
            </svg>
            章节目录
          </div>
          {chapterTree.length > 0 ? (
            chapterTreePager.pageData.map(ch => (
              <div
                key={ch.id}
                className={`outline-item${chapter?.id === ch.id ? " active" : ""}`}
                onClick={() => selectChapter(ch.id)}
                style={chapter?.id === ch.id ? { color: "var(--primary-light)", background: "var(--primary-dim)" } : {}}
              >
                <span style={{ opacity: 0.5, fontSize: 11, minWidth: 24 }}>{ch.seq}.</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ch.title}</span>
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: "var(--text-3)", padding: "8px 10px" }}>
              暂无章节
            </div>
          )}
          <Pagination
            page={chapterTreePager.page}
            pageSize={chapterTreePager.pageSize}
            total={chapterTree.length}
            onPageChange={chapterTreePager.setPage}
            onPageSizeChange={chapterTreePager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />

          {/* Chapter selector dropdown (compact, for large lists) */}
          {chapters.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <select
                value={chapter?.id ?? ""}
                onChange={event => selectChapter(event.target.value)}
                aria-label="选择章节"
                className="form-input"
                style={{ height: 34, fontSize: 12 }}
              >
                {chapters.map((item, index) => (
                  <option key={item.id} value={item.id}>
                    {Number(item.meta?.seq || index + 1)}. {item.title}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* CENTER: Novel prose editor */}
        <div className="ed-main" style={{ padding: 0, display: "flex", flexDirection: "column" }}>
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
            hideAiPanel={true}
          />
        </div>

        {/* RIGHT: AI Assistant */}
        <div className="ed-aside" style={{ display: "flex", flexDirection: "column" }}>
          <div className="card-title" style={{ marginBottom: 12 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
              <rect x="3" y="11" width="18" height="10" rx="2"/>
              <circle cx="12" cy="5" r="2"/>
            </svg>
            AI 写作助手
          </div>

          {/* AI chat messages */}
          <div style={{ flex: 1, overflowY: "auto", marginBottom: 8 }}>
            {aiChatMessages.length === 0 ? (
              <div style={{ color: "var(--text-3)", fontSize: 13, lineHeight: 1.7, padding: "8px 4px" }}>
                向 AI 助手提问，或选中文本用浮动工具栏润色 / 续写。
              </div>
            ) : (
              aiChatMessages.map((msg, i) => (
                <div key={i} className={`ai-msg${msg.role === "user" ? " user" : ""}`}>
                  {msg.text}
                </div>
              ))
            )}

            {/* De-AI results display */}
            {deaiResult && (
              <div className="ai-msg" style={{ borderColor: "var(--primary)", background: "var(--primary-dim)" }}>
                <strong style={{ color: "var(--primary-light)" }}>去AI味完成</strong>
                <div style={{ marginTop: 4, fontSize: 12 }}>
                  原始: {deaiResult.original_score ?? "--"}分 → 最终: {deaiResult.final_score ?? "--"}分
                </div>
                {(deaiResult.layers || []).map((layer: any, i: number) => (
                  <div key={i} style={{ fontSize: 11, marginTop: 2, color: "var(--text-2)" }}>
                    {layer.label}: {layer.score_before} → {layer.score_after} ({layer.status === "pass" ? "✓" : "—"})
                  </div>
                ))}
              </div>
            )}

            {deaiLoading && (
              <div className="ai-msg" style={{ color: "var(--text-2)" }}>
                <RefreshCcw size={14} style={{ animation: "spin 1s linear infinite", marginRight: 8 }} />
                去AI味处理中…
              </div>
            )}
          </div>

          {/* AI prompt input */}
          <div className="ai-prompt" style={{ marginTop: "auto" }}>
            <input
              placeholder="向 AI 助手提问…"
              value={aiChatInput}
              onChange={e => setAiChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") sendAiMessage(); }}
            />
            <button className="btn-sm btn-primary" style={{ width: "auto", height: 38 }} onClick={sendAiMessage}>
              <Send size={14} /> 发送
            </button>
          </div>
        </div>
      </div>

      {/* ── Bottom: Version history ── */}
      {versions.length > 0 && (
        <div className="card" style={{ marginTop: 12, padding: "14px 18px" }}>
          <div className="card-title" style={{ marginBottom: 10 }}>
            版本历史
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {versionsPager.pageData.map(v => (
              <button key={v.id} onClick={() => restoreVersion(v.id)} className="btn-sm btn-ghost" style={{ fontSize: 12 }}>
                <RotateCcw size={12} /> {v.label}
                <small style={{ color: "var(--text-3)", marginLeft: 4 }}>{new Date(v.created_at).toLocaleString()}</small>
              </button>
            ))}
          </div>
          <Pagination
            page={versionsPager.page}
            pageSize={versionsPager.pageSize}
            total={versions.length}
            onPageChange={versionsPager.setPage}
            onPageSizeChange={versionsPager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
          {offlineAiResults?.length ? (
            <>
              <div className="card-title" style={{ marginTop: 12, marginBottom: 8 }}>离线 AI 结果</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {offlineResultsPager.pageData.map(result => (
                  <button key={result.id} onClick={() => applyOfflineAiResult?.(result.id, result.text)} className="btn-sm btn-ghost" style={{ fontSize: 12 }}>
                    应用 AI 结果
                    <small style={{ color: "var(--text-3)", marginLeft: 4, maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{result.text.slice(0, 36)}…</small>
                  </button>
                ))}
              </div>
              <Pagination
                page={offlineResultsPager.page}
                pageSize={offlineResultsPager.pageSize}
                total={offlineAiResults?.length ?? 0}
                onPageChange={offlineResultsPager.setPage}
                onPageSizeChange={offlineResultsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </>
          ) : null}
        </div>
      )}

      {/* ── Fullscreen overlay ── */}
      {isFullscreen && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 200,
          background: "var(--bg)", padding: 16,
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
            hideAiPanel={true}
          />
        </div>
      )}
    </div>
  );
}
