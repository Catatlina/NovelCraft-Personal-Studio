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
      <div className="novel-toolbar">
        {/* Text formatting */}
        <button onClick={() => editor.chain().focus().toggleBold().run()} className={editor.isActive("bold") ? "active" : ""} title="加粗 (Ctrl+B)">
          <Bold size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleItalic().run()} className={editor.isActive("italic") ? "active" : ""} title="斜体 (Ctrl+I)">
          <Italic size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={editor.isActive("heading", { level: 2 }) ? "active" : ""} title="章节标题">
          <Heading size={15} />
        </button>
        <button onClick={() => editor.chain().focus().toggleBulletList().run()} className={editor.isActive("bulletList") ? "active" : ""} title="列表">
          <List size={15} />
        </button>

        <div className="toolbar-divider" />

        {/* Undo/Redo */}
        <button onClick={() => editor.chain().focus().undo().run()} title="撤销">
          <Undo size={15} />
        </button>
        <button onClick={() => editor.chain().focus().redo().run()} title="重做">
          <Redo size={15} />
        </button>

        <div className="toolbar-divider" />

        {/* AI operations */}
        <button onClick={() => onAiOp?.("polish")} title="AI润色选中文本" style={{ width: "auto", padding: "0 8px", gap: 4 }}>
          <Wand2 size={13} /> 润色
        </button>
        <button onClick={() => onAiOp?.("deai")} title="七层去AI味" style={{ width: "auto", padding: "0 8px", gap: 4 }}>
          <RefreshCcw size={13} /> 去AI味
        </button>

        <div className="toolbar-spacer" />

        {/* View toggles */}
        <button onClick={onToggleFocusMode} className={isFocusMode ? "active" : ""} title="专注模式">
          <EyeOff size={15} />
        </button>
        <button onClick={onToggleNightMode} className={isNightMode ? "active" : ""} title="夜间模式">
          {isNightMode ? <Sun size={15} /> : <Moon size={15} />}
        </button>
        <button onClick={onToggleFullscreen} title={isFullscreen ? "退出全屏" : "全屏"}>
          {isFullscreen ? <Minimize size={15} /> : <Maximize size={15} />}
        </button>
      </div>

      {/* ── Floating selection toolbar ── */}
      {showFloatBar && (
        <div
          className="floating-toolbar"
          style={{ left: barPos.x, top: barPos.y }}
        >
          <button onClick={() => handleFloatOp("polish")}>
            <Wand2 size={12} /> 润色
          </button>
          <button onClick={() => handleFloatOp("rewrite")}>
            <Sparkles size={12} /> 改写
          </button>
          <button onClick={() => handleFloatOp("deai")}>
            <RefreshCcw size={12} /> 去AI味
          </button>
          <button onClick={() => handleFloatOp("continue")}>
            <Bot size={12} /> 续写
          </button>
        </div>
      )}

      {/* ── Right panel: AI Assistant ── */}
      <div style={{ display: "flex", gap: 12 }}>
        {/* ── Main editor area ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <EditorContent editor={editor} style={{ minHeight: isFullscreen ? "calc(100vh - 180px)" : 420 }} />

          {/* ── Status bar ── */}
          <div className="novel-status-bar">
            <span className="stat">
              <Type size={12} />
              <span className="stat-value">{stats.words.toLocaleString()}</span> 字
            </span>
            <span className="stat">
              <Gauge size={12} />
              <span className="stat-value">{stats.readingTime}</span> 分钟阅读
            </span>
            <span className="stat">
              共 <span className="stat-value">{stats.paragraphs}</span> 段
            </span>
            <span style={{ flex: 1 }} />
            {dirty && <span className="stat stat-saving">● 未保存</span>}
            {!dirty && autoSavedAt && <span className="stat stat-saved">已保存 {autoSavedAt}</span>}
          </div>
        </div>

        {/* ── AI Panel (Right sidebar) ── */}
        {!isFocusMode && (
          <div className="ai-panel" style={{ width: 300, flexShrink: 0 }}>
            <div className="ai-panel-tabs">
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
                      <p style={{ fontSize: 28, fontWeight: 800, color: "var(--nc-primary)" }}>
                        {aiReview.review.score ?? "--"}
                      </p>
                      <div style={{ fontSize: 12, marginTop: 8 }}>
                        {(aiReview.review.issues || []).map((issue, i) => (
                          <p key={i} style={{ marginBottom: 4, color: "var(--text-secondary)" }}>
                            • {issue}
                          </p>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="muted" style={{ fontSize: 12 }}>点击"七维审查"获取AI评价</p>
                  )}
                  {aiReview?.next && (
                    <>
                      <h4 style={{ marginTop: 16 }}>下一章规划</h4>
                      <strong style={{ color: "var(--nc-accent)" }}>{aiReview.next.next_title || "下一章"}</strong>
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
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>原始:</span>
                        <span className={`deai-score-badge ${deaiResult.original_score && deaiResult.original_score >= 60 ? "high-ai" : deaiResult.original_score && deaiResult.original_score >= 30 ? "medium-ai" : "low-ai"}`}>
                          {deaiResult.original_score ?? "--"}分
                        </span>
                        <span style={{ color: "var(--nc-accent)" }}>→</span>
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
                    <p className="muted" style={{ fontSize: 12 }}>
                      点击"去AI味"按钮执行七层管线处理
                    </p>
                  )}
                </div>
              )}

              {/* Tab: Suggest */}
              {aiTab === "suggest" && (
                <div>
                  <h4>AI 写作建议</h4>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    <p>选中文本后使用浮动工具栏进行：</p>
                    <ul style={{ paddingLeft: 16, marginTop: 8, lineHeight: 1.8 }}>
                      <li><strong>润色</strong> — 优化文笔，保持原意</li>
                      <li><strong>改写</strong> — 换个方式表达</li>
                      <li><strong>去AI味</strong> — 七层管线处理</li>
                      <li><strong>续写</strong> — 从光标处继续</li>
                    </ul>
                    <button
                      onClick={() => onAiOp?.("deai")}
                      style={{
                        marginTop: 12, width: "100%", justifyContent: "center",
                        background: "rgba(255,107,53,0.1)", color: "var(--nc-primary)",
                        border: "1px solid rgba(255,107,53,0.2)"
                      }}
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
