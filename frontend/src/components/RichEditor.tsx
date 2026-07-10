import React, { useRef, useState, useEffect } from "react";
import { Bold, Italic, Heading, Undo, Wand2, Bot, Sparkles } from "lucide-react";

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSelection?: (text: string) => void;
  onAiOp?: (op: "polish" | "rewrite" | "continue") => void;
};

export function RichEditor({ value, onChange, onSelection, onAiOp }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [selBar, setSelBar] = useState<{ x: number; y: number; text: string } | null>(null);

  useEffect(() => {
    function handleSel() {
      const sel = window.getSelection();
      const text = sel?.toString().trim();
      if (text && text.length > 0) {
        const range = sel!.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        setSelBar({ x: rect.left + rect.width / 2, y: rect.top - 40, text });
        onSelection?.(text);
      } else {
        setSelBar(null);
      }
    }
    document.addEventListener("selectionchange", handleSel);
    return () => document.removeEventListener("selectionchange", handleSel);
  }, [onSelection]);

  function exec(cmd: string, val?: string) {
    document.execCommand(cmd, false, val);
    ref.current?.focus();
    if (ref.current) onChange(ref.current.innerHTML);
  }

  function doAiOp(op: "polish" | "rewrite" | "continue") {
    onAiOp?.(op);
    setSelBar(null);
  }

  return (
    <div style={{ position: "relative" }}>
      {selBar && onAiOp && (
        <div style={{
          position: "fixed", left: selBar.x, top: selBar.y,
          transform: "translateX(-50%)", zIndex: 100,
          display: "flex", gap: 4, padding: "4px 8px",
          background: "var(--bg-primary)", border: "1px solid var(--border-subtle)",
          borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,.3)",
        }}>
          <button onClick={() => doAiOp("polish")} title="润色" style={{ padding: "4px 8px" }}><Wand2 size={14} /></button>
          <button onClick={() => doAiOp("rewrite")} title="改写" style={{ padding: "4px 8px" }}><Bot size={14} /></button>
          <button onClick={() => doAiOp("continue")} title="续写" style={{ padding: "4px 8px" }}><Sparkles size={14} /></button>
        </div>
      )}

      <div style={{ display: "flex", gap: 4, marginBottom: 8, padding: 4, background: "var(--bg-secondary)", borderRadius: 6 }}>
        <button type="button" onClick={() => exec("bold")} title="加粗"><Bold size={14} /></button>
        <button type="button" onClick={() => exec("italic")} title="斜体"><Italic size={14} /></button>
        <button type="button" onClick={() => exec("formatBlock", "h3")} title="标题"><Heading size={14} /></button>
        <button type="button" onClick={() => exec("formatBlock", "p")} title="正文"><Undo size={14} /></button>
      </div>
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={e => onChange((e.target as HTMLDivElement).innerHTML)}
        dangerouslySetInnerHTML={{ __html: value }}
        style={{
          minHeight: 300, padding: 12, border: "1px solid var(--border-subtle)",
          borderRadius: 8, outline: "none", fontSize: 15, lineHeight: 1.8,
          background: "var(--bg-primary)",
        }}
      />
    </div>
  );
}
