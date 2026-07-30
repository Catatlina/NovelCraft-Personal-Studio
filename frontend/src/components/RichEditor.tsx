import React, { useCallback, useState, useRef, useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Bold, Italic, Heading, List, Undo, Redo, Wand2, Sparkles, Bot, RefreshCcw } from "lucide-react";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSelection?: (s: string) => void;
  selection?: string;
  onAiOp?: (op: string, instruction?: string) => void;
  aiReview?: any;
  deaiResult?: any;
  deaiLoading?: boolean;
  deai?: (t: string) => void;
  autoSavedAt?: string;
  dirty?: boolean;
  hideAiPanel?: boolean;
  isFocusMode?: boolean;
  isFullscreen?: boolean;
  isNightMode?: boolean;
  onToggleFocusMode?: () => void;
  onToggleFullscreen?: () => void;
  onToggleNightMode?: () => void;
};

function toEditorHtml(value: string): string {
  if (!value) return "";
  if (value.trimStart().startsWith("<")) return value;
  return value
    .split(/\n{2,}/)
    .map(paragraph => `<p>${paragraph
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")}</p>`)
    .join("");
}

export function RichEditor({ value, onChange, onSelection, selection, onAiOp, aiReview, deaiResult, deaiLoading, deai, autoSavedAt, dirty, hideAiPanel, isFocusMode, isFullscreen, isNightMode, onToggleFocusMode, onToggleFullscreen, onToggleNightMode }: Props) {
  const [showAiBar, setShowAiBar] = useState(false);
  const [barPos, setBarPos] = useState({ x: 0, y: 0 });
  const lastEmittedValue = useRef(value);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: "开始创作..." }),
    ],
    content: toEditorHtml(value),
    onUpdate: ({ editor }) => {
      // App.tsx persists a TipTap-like text document. Feeding getHTML() into
      // that text field produced nested paragraph markup after reload.
      const text = editor.getText({ blockSeparator: "\n\n" });
      lastEmittedValue.current = text;
      onChange(text);
    },
    onSelectionUpdate: ({ editor }) => {
      const { from, to, empty } = editor.state.selection;
      if (!empty && from !== to) {
        const text = editor.state.doc.textBetween(from, to);
        onSelection?.(text);
        // Position the AI bar near selection
        const view = editor.view;
        const start = view.coordsAtPos(from);
        const end = view.coordsAtPos(to);
        setBarPos({ x: (start.left + end.right) / 2, y: start.top - 40 });
        setShowAiBar(true);
      } else {
        setShowAiBar(false);
      }
    },
  });

  useEffect(() => {
    // React StrictMode may reconnect passive effects after Tiptap has already
    // destroyed this editor instance. Calling getHTML() in that window reaches
    // a disposed ProseMirror schema and crashes the entire editor route.
    if (value === lastEmittedValue.current) return;
    if (editor && !editor.isDestroyed && value !== editor.getText({ blockSeparator: "\n\n" })) {
      editor.commands.setContent(toEditorHtml(value));
      lastEmittedValue.current = value;
    }
  }, [value, editor]);

  if (!editor) return <div>Loading editor...</div>;

  return (
    <div style={{ position: "relative" }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 4, padding: "4px 0", borderBottom: "1px solid var(--border-subtle)", marginBottom: 8 }}>
        <button onClick={() => editor.chain().focus().toggleBold().run()} className={editor.isActive("bold") ? "active" : ""}><Bold size={14} /></button>
        <button onClick={() => editor.chain().focus().toggleItalic().run()} className={editor.isActive("italic") ? "active" : ""}><Italic size={14} /></button>
        <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={editor.isActive("heading") ? "active" : ""}><Heading size={14} /></button>
        <button onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={14} /></button>
        <button onClick={() => editor.chain().focus().undo().run()}><Undo size={14} /></button>
        <button onClick={() => editor.chain().focus().redo().run()}><Redo size={14} /></button>
        <button onClick={() => onAiOp?.("rewrite_chapter")} title="整章重写"><RefreshCcw size={14} />整章重写</button>
      </div>

      {/* Editor area */}
      <EditorContent editor={editor} style={{ minHeight: 300, padding: "0 8px", fontSize: 15, lineHeight: 1.8 }} />

      {/* Floating AI bar on text selection */}
      {showAiBar && (
        <div style={{
          position: "absolute", left: barPos.x, top: barPos.y,
          transform: "translate(-50%, -100%)",
          display: "flex", gap: 4, padding: "4px 8px",
          background: "var(--surface-elevated)", borderRadius: 8,
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)", zIndex: 100,
        }}>
          <button onClick={() => onAiOp?.("polish")} style={{ fontSize: 12 }}><Wand2 size={12} /> 润色</button>
          <button onClick={() => onAiOp?.("rewrite")} style={{ fontSize: 12 }}><Sparkles size={12} /> 改写</button>
          <button onClick={() => onAiOp?.("deai")} style={{ fontSize: 12 }}><RefreshCcw size={12} /> 去AI味</button>
          <button onClick={() => onAiOp?.("continue")} style={{ fontSize: 12 }}><Bot size={12} /> 续写</button>
        </div>
      )}
    </div>
  );
}
