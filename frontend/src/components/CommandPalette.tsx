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
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(11,15,25,0.55)", // --bg with opacity
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        display: "flex", justifyContent: "center", paddingTop: "15vh",
      }}
      onClick={() => setOpen(false)}
    >
      <div
        style={{
          background: "var(--bg-elev)", borderRadius: "var(--r-xl)", width: 520, maxHeight: "60vh",
          overflow: "hidden", border: "1px solid var(--border-strong)",
          boxShadow: "var(--shadow-card), 0 0 40px rgba(99,102,241,.12)",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search bar */}
        <div className="search-box" style={{ width: "100%", borderRadius: 0, border: "none", borderBottom: "1px solid var(--border)", padding: "12px 16px" }}>
          <Search size={18} style={{ color: "var(--text-3)", flexShrink: 0 }} />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="搜索命令..."
          />
          <kbd style={{
            fontSize: 12, color: "var(--text-3)", border: "1px solid var(--border)",
            borderRadius: 4, padding: "2px 6px", fontFamily: "inherit", flexShrink: 0,
          }}>
            esc
          </kbd>
        </div>

        {/* Results */}
        <div style={{ overflow: "auto", maxHeight: "calc(60vh - 52px)", padding: 8 }}>
          {filtered.map(c => (
            <button
              key={c.id}
              onClick={() => { c.action(); setOpen(false); }}
              style={{
                width: "100%", justifyContent: "flex-start", padding: "10px 12px",
                border: "none", borderRadius: "var(--r-sm)", marginBottom: 2,
                background: "transparent", color: "var(--text-2)", fontSize: 14,
                fontWeight: 500, textAlign: "left", cursor: "pointer",
                transition: "background .15s, color .15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-1)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-2)"; }}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
