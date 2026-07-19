import React, { useEffect, useState } from "react";
import { Lightbulb, CheckCircle } from "lucide-react";
import { api } from "../lib/api";

type Foreshadowing = {
  id: string; content: string; status: string;
  planned_resolve_chapter: number; chapter_id: string;
};

export function ForeshadowingBoard({ novelId }: { novelId: string }) {
  const [items, setItems] = useState<Foreshadowing[]>([]);

  useEffect(() => {
    api<Foreshadowing[]>(`/api/v1/novels/${novelId}/foreshadowings`).then((resp: any) => setItems(resp.data || [])).catch(() => {});
  }, [novelId]);

  const planted = items.filter(i => i.status === "planted");
  const resolved = items.filter(i => i.status === "resolved");

  return (
    <div className="grid grid-2">
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <Lightbulb size={16} />
            种植中 ({planted.length})
          </div>
        </div>
        {planted.map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
            <small style={{ color: "var(--text-2)" }}>计划第{f.planned_resolve_chapter}章回收</small>
          </div>
        ))}
        {!planted.length && (
          <div className="empty" style={{ padding: "24px 16px" }}>
            <p style={{ color: "var(--text-2)", fontSize: 13 }}>暂无种植伏笔</p>
          </div>
        )}
      </div>
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <CheckCircle size={16} />
            已回收 ({resolved.length})
          </div>
        </div>
        {resolved.slice(0, 10).map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
          </div>
        ))}
        {!resolved.length && (
          <div className="empty" style={{ padding: "24px 16px" }}>
            <p style={{ color: "var(--text-2)", fontSize: 13 }}>暂无已回收伏笔</p>
          </div>
        )}
      </div>
    </div>
  );
}
