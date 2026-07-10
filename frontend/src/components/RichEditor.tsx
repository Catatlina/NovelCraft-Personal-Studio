import React, { useRef } from "react";
import { Bold, Italic, Heading, Undo } from "lucide-react";

export function RichEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);

  function exec(cmd: string, val?: string) {
    document.execCommand(cmd, false, val);
    ref.current?.focus();
    if (ref.current) onChange(ref.current.innerHTML);
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 8, padding: 4, background: "var(--bg-secondary)", borderRadius: 6 }}>
        <button type="button" onClick={() => exec("bold")} title="加粗" style={{ padding: "4px 8px" }}><Bold size={14} /></button>
        <button type="button" onClick={() => exec("italic")} title="斜体" style={{ padding: "4px 8px" }}><Italic size={14} /></button>
        <button type="button" onClick={() => exec("formatBlock", "h3")} title="标题" style={{ padding: "4px 8px" }}><Heading size={14} /></button>
        <button type="button" onClick={() => exec("formatBlock", "p")} title="正文" style={{ padding: "4px 8px" }}><Undo size={14} /></button>
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
