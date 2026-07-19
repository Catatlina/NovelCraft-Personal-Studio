import React, { useState } from "react";
import { Search, BookOpen, FileText } from "lucide-react";
import { api } from "../lib/api";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

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

  const resultsPager = usePagination({ items: results, pageSize: 10, mode: "client" });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="card">
        <div className="card-head">
          <div className="card-title"><BookOpen size={14} /> 知识库检索</div>
        </div>
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
          <button className="btn-sm" disabled={!projectId} onClick={search}><Search size={14} /> 搜索</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 8 }}>
        {resultsPager.pageData.map(item => (
          <div key={item.id} className="card" style={{ fontSize: 13, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontWeight: 600 }}>{item.title?.slice(0, 60)}</span>
              <span className="badge gray">
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

      <Pagination
        page={resultsPager.page}
        pageSize={resultsPager.pageSize}
        total={results.length}
        onPageChange={resultsPager.setPage}
        onPageSizeChange={resultsPager.setPageSize}
        pageSizeOptions={[10, 20, 50, 100]}
      />

      {results.length === 0 && query && (
        <div className="empty">
          <div className="empty-ic"><FileText size={26} /></div>
          <h3>未找到匹配的知识条目</h3>
          <p>尝试更换关键词或筛选条件</p>
        </div>
      )}
    </div>
  );
}
