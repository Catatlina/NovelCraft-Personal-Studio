import React, { useEffect, useState, useCallback } from "react";
import { Search } from "lucide-react";

type Command = { id: string; label: string; action: () => void };

export function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const toggle = useCallback(() => setOpen(o => !o), []);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); toggle(); }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggle]);

  const filtered = commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));

  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center", paddingTop: "15vh" }} onClick={() => setOpen(false)}>
      <div style={{ background: "var(--bg-surface)", borderRadius: 12, width: 520, maxHeight: "60vh", overflow: "hidden", border: "1px solid var(--border-strong)", boxShadow: "var(--shadow-md)" }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
          <Search size={18} style={{ color: "var(--text-muted)" }} />
          <input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索命令..." style={{ border: "none", background: "transparent", flex: 1, fontSize: 15, outline: "none", color: "var(--text-primary)" }} />
          <kbd style={{ fontSize: 12, color: "var(--text-muted)", border: "1px solid var(--border-subtle)", borderRadius: 4, padding: "2px 6px" }}>esc</kbd>
        </div>
        <div style={{ overflow: "auto", maxHeight: "calc(60vh - 52px)", padding: 8 }}>
          {filtered.map(c => (
            <button key={c.id} onClick={() => { c.action(); setOpen(false); }} style={{ width: "100%", justifyContent: "flex-start", padding: "10px 12px", border: "none", borderRadius: 8, marginBottom: 2 }}>
              {c.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
