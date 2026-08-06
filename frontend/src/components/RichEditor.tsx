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
  aiBusy?: boolean;
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

export function RichEditor({ value, onChange, onSelection, selection, onAiOp, aiReview, deaiResult, deaiLoading, deai, autoSavedAt, dirty, hideAiPanel, isFocusMode, isFullscreen, isNightMode, onToggleFocusMode, onToggleFullscreen, onToggleNightMode, aiBusy }: Props) {
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

  const emitEditorText = useCallback((domTarget?: EventTarget | null) => {
    if (!editor || editor.isDestroyed) return;
    const stateText = editor.getText({ blockSeparator: "\n\n" });
    // A contenteditable can receive an input from browser automation, IME, or
    // mobile composition before ProseMirror has reconciled its internal state.
    // Prefer the document state, but fall back to the actual DOM text so Save
    // never persists an empty document while the user can visibly see text.
    const domText = domTarget instanceof HTMLElement
      ? (domTarget.innerText || domTarget.textContent || "")
      : "";
    const text = stateText || domText;
    lastEmittedValue.current = text;
    onChange(text);
  }, [editor, onChange]);

  useEffect(() => {
    // React StrictMode may reconnect passive effects after Tiptap has already
    // destroyed this editor instance. Calling getHTML() in that window reaches
    // a disposed ProseMirror schema and crashes the entire editor route.
    if (!editor || editor.isDestroyed) return;
    const currentText = editor.getText({ blockSeparator: "\n\n" });
    if (value === currentText) {
      lastEmittedValue.current = value;
      return;
    }
    editor.commands.setContent(toEditorHtml(value));
    lastEmittedValue.current = value;
  }, [value, editor]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.setEditable(!aiBusy);
  }, [editor, aiBusy]);

  if (!editor) return <div>Loading editor...</div>;

  return (
    <div style={{ position: "relative" }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 4, padding: "4px 0", borderBottom: "1px solid var(--border-subtle)", marginBottom: 8 }}>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().toggleBold().run()} className={editor.isActive("bold") ? "active" : ""}><Bold size={14} /></button>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().toggleItalic().run()} className={editor.isActive("italic") ? "active" : ""}><Italic size={14} /></button>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={editor.isActive("heading") ? "active" : ""}><Heading size={14} /></button>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={14} /></button>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().undo().run()}><Undo size={14} /></button>
        <button disabled={aiBusy} onClick={() => editor.chain().focus().redo().run()}><Redo size={14} /></button>
        <button disabled={aiBusy} onClick={() => onAiOp?.("rewrite_chapter")} title="整章重写"><RefreshCcw size={14} />整章重写</button>
      </div>

      {/* Editor area */}
      <EditorContent
        editor={editor}
        onInput={event => emitEditorText(event.target)}
        onBlur={event => emitEditorText(event.target)}
        style={{ minHeight: 300, padding: "0 8px", fontSize: 15, lineHeight: 1.8 }}
      />

      {/* Floating AI bar on text selection */}
      {showAiBar && (
        <div style={{
          position: "absolute", left: barPos.x, top: barPos.y,
          transform: "translate(-50%, -100%)",
          display: "flex", gap: 4, padding: "4px 8px",
          background: "var(--surface-elevated)", borderRadius: 8,
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)", zIndex: 100,
        }}>
          <button disabled={aiBusy} onClick={() => onAiOp?.("polish")} style={{ fontSize: 12 }}><Wand2 size={12} /> 润色</button>
          <button disabled={aiBusy} onClick={() => onAiOp?.("rewrite")} style={{ fontSize: 12 }}><Sparkles size={12} /> 改写</button>
          <button disabled={aiBusy} onClick={() => onAiOp?.("deai")} style={{ fontSize: 12 }}><RefreshCcw size={12} /> 去AI味</button>
          <button disabled={aiBusy} onClick={() => onAiOp?.("continue")} style={{ fontSize: 12 }}><Bot size={12} /> 续写</button>
        </div>
      )}
    </div>
  );
}
