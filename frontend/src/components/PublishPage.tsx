import React, { useState, useEffect } from "react";
import { Send, Clock, CheckCircle, AlertCircle, Settings } from "lucide-react";
import { api } from "../lib/api";

const PLATFORMS = ["wechat", "toutiao", "xiaohongshu", "zhihu", "medium", "wordpress", "substack", "x"];

export function PublishPage({ contentId }: { contentId: string }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [results, setResults] = useState<Record<string, any>>({});

  async function publish() {
    for (const p of selected) {
      const r = await api<any>(`/api/v1/publish/${p}?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, { method: "POST" });
      setResults(prev => ({ ...prev, [p]: r }));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="panel">
        <h3><Send size={14} /> 发布管理</h3>
        <input placeholder="标题" value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
        <textarea rows={4} placeholder="内容" value={body} onChange={e => setBody(e.target.value)} style={{ width: "100%" }} />
      </div>
      <div className="panel">
        <h3>选择发布平台</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
          {PLATFORMS.map(p => (
            <label key={p} style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4, padding: 4, border: `1px solid ${selected.includes(p) ? "var(--primary)" : "var(--border-subtle)"}`, borderRadius: 4, cursor: "pointer" }}>
              <input type="checkbox" checked={selected.includes(p)} onChange={() => setSelected(s => s.includes(p) ? s.filter(k => k !== p) : [...s, p])} />
              {p}
            </label>
          ))}
        </div>
        <button onClick={publish} disabled={!selected.length} style={{ marginTop: 8 }}>
          <Send size={12} /> 发布到 {selected.length} 个平台
        </button>
      </div>
      {Object.keys(results).length > 0 && (
        <div className="panel">
          <h3>发布结果</h3>
          {Object.entries(results).map(([k, v]) => (
            <div key={k} style={{ fontSize: 13, padding: "4px 0" }}>
              {v?.status === "draft" ? <Clock size={12} /> : <CheckCircle size={12} />} {k}: {v?.status || v?.code || "?"}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
