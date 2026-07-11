import React, { useState } from "react";
import { GitBranch, RotateCcw, GitCompare } from "lucide-react";
import { api } from "../lib/api";

type Version = { id: string; label: string; created_at: string; snapshot: any };

export function VersionTree({ contentId, versions, onRestore }: {
  contentId: string; versions: Version[]; onRestore: (id: string) => void;
}) {
  return (
    <div className="panel" style={{ fontSize: 13 }}>
      <h3><GitBranch size={14} /> 版本树</h3>
      {versions.length === 0 && <div style={{ color: "var(--text-muted)", padding: 16 }}>暂无版本历史</div>}
      {versions.map((v, i) => (
        <div key={v.id} style={{
          display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
          borderBottom: "1px solid var(--border-subtle)",
          marginLeft: i > 0 ? 16 : 0,
        }}>
          <span style={{ fontWeight: 600, flex: 1 }}>{v.label}</span>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {new Date(v.created_at).toLocaleString()}
          </span>
          <button onClick={() => onRestore(v.id)} style={{ fontSize: 12 }}>
            <RotateCcw size={12} /> 恢复
          </button>
        </div>
      ))}
    </div>
  );
}
