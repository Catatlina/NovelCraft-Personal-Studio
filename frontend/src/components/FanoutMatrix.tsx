import React, { useState } from "react";
import { Send, CheckCircle } from "lucide-react";
import { api } from "../lib/api";

const PLATFORMS = [
  { key: "wechat", name: "微信公众号" },
  { key: "toutiao", name: "今日头条" },
  { key: "xiaohongshu", name: "小红书" },
  { key: "zhihu", name: "知乎" },
  { key: "medium", name: "Medium" },
  { key: "substack", name: "Substack" },
  { key: "twitter", name: "X/Twitter" },
  { key: "wordpress", name: "WordPress" },
];

export function FanoutMatrix({ contentId }: { contentId: string }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [results, setResults] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);

  async function runFanout() {
    setBusy(true);
    const data = await api(`/api/v1/contents/${contentId}/fanout?platforms=${selected.join(",")}`, {
      method: "POST",
    });
    if (data.code === 0) {
      const map: Record<string, any> = {};
      const items = (data.data as any)?.items || [];
      items.forEach((item: any) => { map[item.platform] = item; });
      setResults(map);
    }
    setBusy(false);
  }

  return (
    <div className="panel">
      <h3>一稿多平台分发</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8, marginBottom: 12 }}>
        {PLATFORMS.map(p => (
          <label key={p.key} style={{
            display: "flex", alignItems: "center", gap: 6, padding: 8,
            border: `1px solid ${selected.includes(p.key) ? "var(--primary)" : "var(--border-subtle)"}`,
            borderRadius: 6, cursor: "pointer", fontSize: 13,
          }}>
            <input type="checkbox" checked={selected.includes(p.key)}
              onChange={() => setSelected(s => s.includes(p.key) ? s.filter(k => k !== p.key) : [...s, p.key])} />
            {results[p.key] ? <CheckCircle size={12} style={{ color: "var(--success)" }} /> : null}
            {p.name}
          </label>
        ))}
      </div>
      <button className="primary" onClick={runFanout} disabled={busy || !selected.length}>
        <Send size={14} /> {busy ? "分发中..." : `分发到 ${selected.length} 个平台`}
      </button>
      {Object.keys(results).length > 0 && (
        <div style={{ marginTop: 12, fontSize: 13 }}>
          已完成：{Object.entries(results).map(([k, v]) => <span key={k} style={{ marginRight: 8 }}>✅ {k}</span>)}
        </div>
      )}
    </div>
  );
}
