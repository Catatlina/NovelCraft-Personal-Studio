import React from "react";
import { GitBranch, RotateCcw } from "lucide-react";
import "../styles/proto.css";

type Version = { id: string; label: string; created_at: string; snapshot: any };

export function VersionTree({ contentId, versions, onRestore }: {
  contentId: string; versions: Version[]; onRestore: (id: string) => void;
}) {
  return (
    <div className="card" style={{ fontSize: 13 }}>
      <div className="card-head">
        <div className="card-title">
          <GitBranch size={16} />
          版本树
        </div>
      </div>
      {versions.length === 0 && (
        <div className="empty">
          <p style={{ color: "var(--text-2)", fontSize: 13 }}>暂无版本历史</p>
        </div>
      )}
      {versions.map((v, i) => (
        <div key={v.id} style={{
          display: "flex", alignItems: "center", gap: 8, padding: "6px 0",
          borderBottom: "1px solid var(--border)",
          marginLeft: i > 0 ? 16 : 0,
        }}>
          <span style={{ fontWeight: 600, flex: 1 }}>{v.label}</span>
          <span style={{ fontSize: 11, color: "var(--text-2)" }}>
            {new Date(v.created_at).toLocaleString()}
          </span>
          <button className="btn-sm btn-ghost" onClick={() => onRestore(v.id)} style={{ padding: "4px 10px" }}>
            <RotateCcw size={12} /> 恢复
          </button>
        </div>
      ))}
    </div>
  );
}
