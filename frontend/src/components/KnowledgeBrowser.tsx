import React, { useState } from "react";
import { Search, BookOpen, FileText } from "lucide-react";
import { api } from "../lib/api";

type KnowledgeItem = {
  id: string; kind: string; title: string; body: string;
  similarity?: number; meta?: Record<string, unknown>;
};

export function KnowledgeBrowser({ projectId }: { projectId: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeItem[]>([]);
  const [kind, setKind] = useState("");

  async function search() {
    if (!query) return;
    const params = new URLSearchParams({ project_id: projectId, query });
    if (kind) params.set("kind", kind);
    const r = await api<{ data: KnowledgeItem[] }>(`/api/v1/knowledge/search?${params}`, { method: "POST" });
    setResults(r.data || []);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="panel">
        <h3><BookOpen size={14} /> 知识库检索</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            placeholder="搜索知识库..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && search()}
            style={{ flex: 1 }}
          />
          <select value={kind} onChange={e => setKind(e.target.value)}>
            <option value="">全部</option>
            <option value="note">笔记</option>
            <option value="reference">参考</option>
            <option value="hotspot">热点</option>
            <option value="ranking">榜单</option>
          </select>
          <button disabled={!projectId} onClick={search}><Search size={14} /> 搜索</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 8 }}>
        {results.map(item => (
          <div key={item.id} className="panel" style={{ fontSize: 13, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontWeight: 600 }}>{item.title?.slice(0, 60)}</span>
              <span style={{
                fontSize: 10, padding: "2px 6px", borderRadius: 4,
                background: "var(--surface-raised)", color: "var(--text-muted)"
              }}>
                {item.kind}
                {item.similarity ? ` · ${(item.similarity * 100).toFixed(0)}%` : ""}
              </span>
            </div>
            <div style={{ color: "var(--text-muted)", lineHeight: 1.5 }}>
              {item.body?.slice(0, 200)}
            </div>
          </div>
        ))}
      </div>

      {results.length === 0 && query && (
        <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)" }}>
          <FileText size={32} />
          <p>未找到匹配的知识条目</p>
        </div>
      )}
    </div>
  );
}
