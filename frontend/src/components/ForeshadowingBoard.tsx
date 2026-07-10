import React, { useEffect, useState } from "react";
import { Lightbulb, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "../lib/api";

type Foreshadowing = {
  id: string; content: string; status: string;
  planned_resolve_chapter: number; chapter_id: string;
};

export function ForeshadowingBoard({ novelId }: { novelId: string }) {
  const [items, setItems] = useState<Foreshadowing[]>([]);

  useEffect(() => {
    api<Foreshadowing[]>(`/api/v1/novels/${novelId}/foreshadowings`).then(setItems).catch(() => {});
  }, [novelId]);

  const planted = items.filter(i => i.status === "planted");
  const resolved = items.filter(i => i.status === "resolved");

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div className="panel" style={{ flex: 1 }}>
        <h3><Lightbulb size={14} /> 种植中 ({planted.length})</h3>
        {planted.map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border-subtle)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
            <small style={{ color: "var(--text-muted)" }}>计划第{f.planned_resolve_chapter}章回收</small>
          </div>
        ))}
        {!planted.length && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>暂无种植伏笔</p>}
      </div>
      <div className="panel" style={{ flex: 1 }}>
        <h3><CheckCircle size={14} /> 已回收 ({resolved.length})</h3>
        {resolved.slice(0, 10).map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border-subtle)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
