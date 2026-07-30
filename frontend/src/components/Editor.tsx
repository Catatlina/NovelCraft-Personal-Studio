import React, { useEffect, useMemo, useRef, useState } from "react";
import { Check, FilePenLine, Save, RotateCcw, Wand2, Bot, RefreshCcw, X } from "lucide-react";
import { RichEditor } from "./RichEditor";
import { PacingCurve } from "./PacingCurve";
import { SceneBoard } from "./SceneBoard";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";
import "../styles/novel-prose.css";

type Content = { id: string; title: string; body: { content?: { text?: string }[] }; meta: Record<string, unknown>; parent_id?: string | null };
type Version = { id: string; label: string; reason?: string; snapshot: Record<string, unknown>; created_at: string };
type PendingAiEdit = { op: string; originalText: string; proposedText: string; nextText: string };

export function Editor({ chapter, chapters, selectChapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion, offlineNotice, offlineQueueCount, offlineAiResults, applyOfflineAiResult, streamPreview, editorAiReview, pendingAiEdit, applyPendingAiEdit, discardPendingAiEdit, deaiResult, deaiLoading, markLiked, projectId }: {
  chapter: Content | null; chapters: Content[]; selectChapter: (id: string) => void;
  editorText: string; setEditorText: (t: string) => void;
  selection: string; setSelection: (s: string) => void;
  saveChapter: () => void; runEditorOp: (op: string, instruction?: string) => void;
  versions: Version[]; restoreVersion: (id: string) => void;
  offlineNotice?: string; offlineQueueCount?: number;
  offlineAiResults?: Array<{ id: string; text: string }>;
  applyOfflineAiResult?: (id: string, text: string) => void;
  streamPreview?: string;
  editorAiReview?: { review?: any; next?: any } | null;
  pendingAiEdit?: PendingAiEdit | null;
  applyPendingAiEdit?: () => Promise<void>;
  discardPendingAiEdit?: () => void;
  deaiResult?: { original_score?: number; final_score?: number; layers?: Array<{ name: string; label: string; score_before: number; score_after: number; status: string }>; final_text?: string } | null;
  deaiLoading?: boolean;
  markLiked?: (text: string) => void;
  projectId?: string;
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

  if (!chapter) {
    return (
      <section className="editor-empty">
        <span><FilePenLine size={25} /></span>
        <p className="eyebrow">CHAPTER EDITOR</p>
        <h2>还没有可以编辑的章节。</h2>
        <p>先从创作向导生成首章，或在书库中打开一本已有章节的小说。这里不会创建一段假的示例正文。</p>
      </section>
    );
  }

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
        <div className="ai-stream-preview">
          <small><span className="spinner" /> AI 正在生成预览，正文尚未改变</small>
          <div style={{ marginTop: 4 }}>{streamPreview}</div>
        </div>
      ) : null}

      {pendingAiEdit ? (
        <section className="ai-edit-preview" aria-live="polite">
          <div className="ai-edit-preview-head">
            <div><p className="eyebrow">PREVIEW BEFORE APPLY</p><h3>AI 建议已生成，等待你的确认</h3></div>
            <span>{pendingAiEdit.op}</span>
          </div>
          <div className="ai-edit-compare">
            <label><span>原文</span><textarea readOnly value={pendingAiEdit.originalText || "（追加操作，无替换原文）"} /></label>
            <label><span>AI 建议</span><textarea readOnly value={pendingAiEdit.proposedText} /></label>
          </div>
          <p>应用后只会更新当前草稿，自动保存时会创建可恢复版本；放弃则原文保持不变。</p>
          <div className="ai-edit-preview-actions">
            <button type="button" onClick={discardPendingAiEdit}><X size={16} /> 放弃建议</button>
            <button type="button" className="primary" onClick={() => void applyPendingAiEdit?.()}><Check size={16} /> 应用到草稿</button>
          </div>
        </section>
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

          {/* V3 §11.2: pacing curve over persisted per-chapter rhythm scores */}
          {(chapter?.parent_id || chapters[0]?.parent_id) ? (
            <PacingCurve novelId={(chapter?.parent_id || chapters[0]?.parent_id) as string} />
          ) : null}

          {/* V3-P3-⑪: Scene Director 分镜面板 */}
          {chapter?.id ? (
            <SceneBoard chapterId={chapter.id} projectId={projectId || (chapter?.parent_id as string)} />
          ) : null}

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
            key={`${chapter?.id ?? "empty"}:${(chapter as any)?.updated_at ?? ""}`}
            value={editorText}
            onChange={setEditorText}
            onSelection={setSelection}
            selection={selection}
            onAiOp={(op, instruction) => runEditorOp(op, instruction)}
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

          <div style={{ flex: 1, overflowY: "auto", marginBottom: 8 }}>
            <p className="editor-ai-help">选中正文后可润色、改写或去 AI 味；续写与整章重写可直接运行。所有结果都会先进入预览，不会直接覆盖正文。</p>
            <div className="editor-ai-tools">
              <button type="button" onClick={() => runEditorOp("continue")}><Bot size={15} /><span><strong>续写本章</strong><small>沿当前正文继续</small></span></button>
              <button type="button" onClick={() => runEditorOp("rewrite_chapter")}><RefreshCcw size={15} /><span><strong>整章重写</strong><small>保留核心剧情</small></span></button>
              <button type="button" disabled={!selection.trim()} onClick={() => runEditorOp("polish")}><Wand2 size={15} /><span><strong>润色选区</strong><small>{selection.trim() ? `${selection.length} 字已选择` : "请先选择文字"}</small></span></button>
              <button type="button" disabled={!selection.trim()} onClick={() => runEditorOp("deai")}><RefreshCcw size={15} /><span><strong>去 AI 味</strong><small>{selection.trim() ? "处理已选文字" : "请先选择文字"}</small></span></button>
              <button type="button" disabled={!selection.trim()} onClick={() => markLiked?.(selection.trim())}><Check size={15} /><span><strong>标记喜欢</strong><small>{selection.trim() ? "记录为偏好表达" : "请先选择文字"}</small></span></button>
            </div>

            {editorAiReview?.review?.issues?.length ? (
              <div className="ai-msg">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <strong>本次建议的审阅问题</strong>
                  <span className="badge">评分：{editorAiReview.review.score ?? "--"}</span>
                </div>
                {editorAiReview.review.issues.map((issue: string, index: number) => (
                  <div key={`${issue}-${index}`} style={{ marginBottom: 8 }}>
                    <div>• {issue}</div>
                    <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                      <button type="button" className="btn-sm btn-ghost" onClick={() => runEditorOp("polish", issue)}>按此建议润色</button>
                      <button type="button" className="btn-sm btn-ghost" onClick={() => runEditorOp("rewrite", issue)}>按此建议改写</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

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
              <button key={v.id} data-version-id={v.id} onClick={() => restoreVersion(v.id)} className="btn-sm btn-ghost" style={{ fontSize: 12 }}>
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
            key={`${chapter?.id ?? "empty"}:${(chapter as any)?.updated_at ?? ""}:fullscreen`}
            value={editorText}
            onChange={setEditorText}
            onSelection={setSelection}
            selection={selection}
            onAiOp={(op: string, instruction?: string) => runEditorOp(op, instruction)}
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
