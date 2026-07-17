import React, { useCallback, useState, useRef, useEffect, useMemo } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Bold, Italic, Heading, List, Undo, Redo,
  Wand2, Sparkles, Bot, RefreshCcw, Maximize, Minimize,
  Moon, Sun, Eye, EyeOff, Type, Gauge
} from "lucide-react";
import "../styles/novel-prose.css";
import "../styles/proto.css";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSelection?: (s: string) => void;
  selection?: string;
  onAiOp?: (op: string) => void;
  // AI panel data
  aiReview?: { review?: { score?: number; issues?: string[] }; next?: { next_title?: string; goals?: string[]; conflicts?: string[]; warnings?: string[] } } | null;
  deaiResult?: { original_score?: number; final_score?: number; layers?: Array<{ name: string; label: string; score_before: number; score_after: number; status: string }>; final_text?: string } | null;
  deaiLoading?: boolean;
  // Autosave status
  autoSavedAt?: string;
  dirty?: boolean;
  // State toggles
  isFullscreen?: boolean;
  isNightMode?: boolean;
  isFocusMode?: boolean;
  onToggleFullscreen?: () => void;
  onToggleNightMode?: () => void;
  onToggleFocusMode?: () => void;
};

export function RichEditor({
  value, onChange, onSelection, selection, onAiOp,
  aiReview, deaiResult, deaiLoading,
  autoSavedAt, dirty,
  isFullscreen, isNightMode, isFocusMode,
  onToggleFullscreen, onToggleNightMode, onToggleFocusMode,
}: Props) {
  const [showFloatBar, setShowFloatBar] = useState(false);
  const [barPos, setBarPos] = useState({ x: 0, y: 0 });
  const [aiTab, setAiTab] = useState<"review" | "deai" | "suggest">("review");
  const editorRef = useRef<HTMLDivElement>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: "开始创作，让故事自然流淌...",
      }),
    ],
    content: value || "",
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    onSelectionUpdate: ({ editor }) => {
      const { from, to, empty } = editor.state.selection;
      if (!empty && from !== to) {
        const text = editor.state.doc.textBetween(from, to);
        onSelection?.(text);
        const view = editor.view;
        const start = view.coordsAtPos(from);
        const end = view.coordsAtPos(to);
        setBarPos({
          x: (start.left + end.right) / 2,
          y: start.top - 8,
        });
        setShowFloatBar(true);
      } else {
        setShowFloatBar(false);
      }
    },
    editorProps: {
      attributes: {
        class: `novel-prose${isNightMode ? " night-mode" : ""}${isFocusMode ? " focus-mode" : ""}`,
      },
    },
  });

  // ── Auto-detect paragraphs for plain text without <p> tags ──
  const ensureParagraphs = useCallback((html: string): string => {
    if (!html) return "";
    // Already has paragraph/wrapper tags
    if (/<p[>\s]|<h[1-6]|<div|<li|<blockquote|<br\s*\/?\s*>/.test(html)) return html;
    // Has double newlines — split by paragraphs
    if (/\n\s*\n/.test(html)) {
      return html
        .split(/\n\s*\n/)
        .map((para) => para.trim())
        .filter(Boolean)
        .map((para) => `<p>${para}</p>`)
        .join("");
    }
    // Plain text — split by Chinese sentence delimiters
    const sentences = html.split(/(?<=[。！？；])\s*/).filter((s) => s.trim());
    if (sentences.length <= 1) return `<p>${html}</p>`;
    return sentences.map((s) => `<p>${s.trim()}</p>`).join("");
  }, []);

  // Sync value from outside
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      const pos = editor.state.selection.from;
      editor.commands.setContent(ensureParagraphs(value || ""));
      try {
        editor.commands.setTextSelection(pos);
      } catch { /* ignore */ }
    }
  }, [value, editor, ensureParagraphs]);

  // ── Stats ──
  const stats = useMemo(() => {
    const text = editor?.getText() || "";
    const chars = text.length;
    const words = chars > 0 ? text.replace(/\s/g, "").length : 0; // Chinese char count
    const readingTime = Math.max(1, Math.ceil(words / 400)); // ~400 chars/min
    const paragraphs = (value.match(/<p[^>]*>/g) || []).length || 1;
    return { chars, words, readingTime, paragraphs };
  }, [value, editor]);

  // ── Floating toolbar handlers ──
  const handleFloatOp = useCallback((op: string) => {
    onAiOp?.(op);
    setShowFloatBar(false);
  }, [onAiOp]);

  if (!editor) return <div style={{ padding: 20, color: "var(--text-muted)" }}>Loading editor...</div>;

  return (
    <div className="novel-editor-area" ref={editorRef}>
      {/* ── Toolbar ── */}
      <div className="novel-toolbar" style={{ background: "var(--bg-elev)", border: "1px solid var(--border)" }}>
        {/* Text formatting */}
        <button onClick={() => editor.chain().focus().toggleBold().run()} className={`icon-btn ${editor.isActive("bold") ? "active" : ""}`} title="加粗 (Ctrl+B)" style={{ width: 32, height: 32 }}>
          <Bold size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleItalic().run()} className={`icon-btn ${editor.isActive("italic") ? "active" : ""}`} title="斜体 (Ctrl+I)" style={{ width: 32, height: 32 }}>
          <Italic size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={`icon-btn ${editor.isActive("heading", { level: 2 }) ? "active" : ""}`} title="章节标题" style={{ width: 32, height: 32 }}>
          <Heading size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleBulletList().run()} className={`icon-btn ${editor.isActive("bulletList") ? "active" : ""}`} title="列表" style={{ width: 32, height: 32 }}>
          <List size={15} />
        </button>

        <div className="toolbar-divider" />

        {/* Undo/Redo */}
        <button onClick={() => editor.chain().focus().undo().run()} className="icon-btn" title="撤销" style={{ width: 32, height: 32 }}>
          <Undo size={15} />
        </button>
        <button onClick={() => editor.chain().focus().redo().run()} className="icon-btn" title="重做" style={{ width: 32, height: 32 }}>
          <Redo size={15} />
        </button>

        <div className="toolbar-divider" />

        {/* AI operations */}
        <button onClick={() => onAiOp?.("polish")} className="btn-sm btn-ghost" title="AI润色选中文本" style={{ gap: 4 }}>
          <Wand2 size={13} /> 润色
        </button>
        <button onClick={() => onAiOp?.("deai")} className="btn-sm btn-ghost" title="七层去AI味" style={{ gap: 4 }}>
          <RefreshCcw size={13} /> 去AI味
        </button>

        <div className="toolbar-spacer" />

        {/* View toggles */}
        <button onClick={onToggleFocusMode} className={`icon-btn ${isFocusMode ? "active" : ""}`} title="专注模式" style={{ width: 32, height: 32 }}>
          <EyeOff size={15} />
        </button>
        <button onClick={onToggleNightMode} className={`icon-btn ${isNightMode ? "active" : ""}`} title="夜间模式" style={{ width: 32, height: 32 }}>
          {isNightMode ? <Sun size={15} /> : <Moon size={15} />}
        </button>
        <button onClick={onToggleFullscreen} className="icon-btn" title={isFullscreen ? "退出全屏" : "全屏"} style={{ width: 32, height: 32 }}>
          {isFullscreen ? <Minimize size={15} /> : <Maximize size={15} />}
        </button>
      </div>

      {/* ── Floating selection toolbar ── */}
      {showFloatBar && (
        <div
          className="floating-toolbar"
          style={{
            left: barPos.x, top: barPos.y,
            background: "var(--bg-elev)", border: "1px solid var(--border)"
          }}
        >
          <button onClick={() => handleFloatOp("polish")} className="btn-sm btn-ghost">
            <Wand2 size={12} /> 润色
          </button>
          <button onClick={() => handleFloatOp("rewrite")} className="btn-sm btn-ghost">
            <Sparkles size={12} /> 改写
          </button>
          <button onClick={() => handleFloatOp("deai")} className="btn-sm btn-ghost">
            <RefreshCcw size={12} /> 去AI味
          </button>
          <button onClick={() => handleFloatOp("continue")} className="btn-sm btn-ghost">
            <Bot size={12} /> 续写
          </button>
        </div>
      )}

      {/* ── Right panel: AI Assistant ── */}
      <div style={{ display: "flex", gap: 12 }}>
        {/* ── Main editor area ── */}
        <div className="card" style={{ flex: 1, minWidth: 0, padding: 16 }}>
          <EditorContent editor={editor} style={{ minHeight: isFullscreen ? "calc(100vh - 180px)" : 420 }} />

          {/* ── Status bar ── */}
          <div className="novel-status-bar" style={{
            background: "transparent", border: "none", borderTop: "1px solid var(--border)",
            borderRadius: 0, marginTop: 12, marginBottom: 0, padding: "10px 0 0"
          }}>
            <span className="stat">
              <Type size={12} />
              <span className="stat-value">{stats.words.toLocaleString()}</span> 字
            </span>
            <span className="stat">
              <Gauge size={12} />
              <span className="stat-value">{stats.readingTime}</span> 分钟阅读
            </span>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>
              共 <span className="stat-value">{stats.paragraphs}</span> 段
            </span>
            <span style={{ flex: 1 }} />
            {dirty && <span className="stat stat-saving" style={{ color: "var(--orange)" }}>● 未保存</span>}
            {!dirty && autoSavedAt && <span className="stat stat-saved" style={{ color: "var(--green)" }}>已保存 {autoSavedAt}</span>}
          </div>
        </div>

        {/* ── AI Panel (Right sidebar) ── */}
        {!isFocusMode && (
          <div className="ai-panel card" style={{ width: 300, flexShrink: 0, padding: 0 }}>
            <div className="ai-panel-tabs" style={{ borderBottom: "1px solid var(--border)" }}>
              <button className={aiTab === "review" ? "active" : ""} onClick={() => setAiTab("review")}>
                审查
              </button>
              <button className={aiTab === "deai" ? "active" : ""} onClick={() => setAiTab("deai")}>
                去AI味
              </button>
              <button className={aiTab === "suggest" ? "active" : ""} onClick={() => setAiTab("suggest")}>
                建议
              </button>
            </div>
            <div className="ai-panel-content">
              {/* Tab: Review */}
              {aiTab === "review" && (
                <div>
                  <h4>七维评分</h4>
                  {aiReview?.review ? (
                    <>
                      <p style={{ fontSize: 28, fontWeight: 800, color: "var(--primary-light)" }}>
                        {aiReview.review.score ?? "--"}
                      </p>
                      <div style={{ fontSize: 12, marginTop: 8 }}>
                        {(aiReview.review.issues || []).map((issue, i) => (
                          <p key={i} style={{ marginBottom: 4, color: "var(--text-2)" }}>
                            • {issue}
                          </p>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="muted" style={{ fontSize: 12, color: "var(--text-3)" }}>点击"七维审查"获取AI评价</p>
                  )}
                  {aiReview?.next && (
                    <>
                      <h4 style={{ marginTop: 16 }}>下一章规划</h4>
                      <strong style={{ color: "var(--cyan)" }}>{aiReview.next.next_title || "下一章"}</strong>
                      {aiReview.next.goals && (
                        <div style={{ fontSize: 11, marginTop: 4 }}>
                          {aiReview.next.goals.map((g, i) => <p key={i}>🎯 {g}</p>)}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Tab: De-AI */}
              {aiTab === "deai" && (
                <div>
                  <h4>七层去AI味管线</h4>
                  {deaiLoading ? (
                    <div className="ai-loading">
                      <RefreshCcw size={14} style={{ animation: "spin 1s linear infinite" }} />
                      去AI味处理中...
                    </div>
                  ) : deaiResult ? (
                    <div>
                      <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
                        <span style={{ fontSize: 12, color: "var(--text-3)" }}>原始:</span>
                        <span className={`deai-score-badge ${deaiResult.original_score && deaiResult.original_score >= 60 ? "high-ai" : deaiResult.original_score && deaiResult.original_score >= 30 ? "medium-ai" : "low-ai"}`}>
                          {deaiResult.original_score ?? "--"}分
                        </span>
                        <span style={{ color: "var(--primary-light)" }}>→</span>
                        <span className={`deai-score-badge ${deaiResult.final_score && deaiResult.final_score >= 60 ? "high-ai" : deaiResult.final_score && deaiResult.final_score >= 30 ? "medium-ai" : "low-ai"}`}>
                          {deaiResult.final_score ?? "--"}分
                        </span>
                      </div>
                      {(deaiResult.layers || []).map((layer, i) => (
                        <div key={layer.name} className={`deai-layer ${layer.status}`}>
                          <div className="layer-num">{i + 1}</div>
                          <div className="layer-name">{layer.label}</div>
                          <div className="layer-score">
                            {layer.score_before} → {layer.score_after}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted" style={{ fontSize: 12, color: "var(--text-3)" }}>
                      点击"去AI味"按钮执行七层管线处理
                    </p>
                  )}
                </div>
              )}

              {/* Tab: Suggest */}
              {aiTab === "suggest" && (
                <div>
                  <h4>AI 写作建议</h4>
                  <div style={{ fontSize: 12, color: "var(--text-2)" }}>
                    <p>选中文本后使用浮动工具栏进行：</p>
                    <ul style={{ paddingLeft: 16, marginTop: 8, lineHeight: 1.8 }}>
                      <li><strong>润色</strong> — 优化文笔，保持原意</li>
                      <li><strong>改写</strong> — 换个方式表达</li>
                      <li><strong>去AI味</strong> — 七层管线处理</li>
                      <li><strong>续写</strong> — 从光标处继续</li>
                    </ul>
                    <button
                      onClick={() => onAiOp?.("deai")}
                      className="btn-sm btn-primary"
                      style={{ marginTop: 12, width: "100%", justifyContent: "center" }}
                    >
                      <RefreshCcw size={14} /> 整章去AI味
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
