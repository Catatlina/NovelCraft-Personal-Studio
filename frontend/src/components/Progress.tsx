import React, { useState } from "react";
import { ApiError, api } from "../lib/api";

type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string; output?: Record<string, unknown>; error?: string | null; attempt?: number; started_at?: string | null; finished_at?: string | null };
type Run = { id: string; nodes: RunNode[]; context: Record<string, unknown> };
type Wrapped<T> = { data: T };

const PLANNING_NODES = new Set(["n3", "n4", "n5", "n6"]);
const RETRYABLE_STATUSES = new Set(["pending_provider", "failed", "pending_budget"]);

function readableLabel(key: string): string {
  const labels: Record<string, string> = {
    synopsis: "简介", selling_points: "核心卖点", worldview: "世界观", characters: "人物卡",
    outline: "大纲", name: "名称", rules: "规则", title: "标题", arc: "人物弧",
  };
  return labels[key] || key.replaceAll("_", " ");
}

function OutputValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="muted">未产出</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><OutputValue value={item} /></li>)}</ul> : <span className="muted">未产出</span>;
  if (typeof value === "object") return <div style={{ display: "grid", gap: 6 }}>{Object.entries(value as Record<string, unknown>).map(([key, item]) => <div key={key}><strong>{readableLabel(key)}：</strong><OutputValue value={item} /></div>)}</div>;
  return <span>{String(value)}</span>;
}

function formatTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}

export function Progress({ run, onConfirm }: { run: Run | null; onConfirm: (title: string) => void }) {
  const nodes = run?.nodes ?? [];
  const human = nodes.find(n => n.node_key === "n2");
  const titles = (run?.context?.title_candidates as string[]) ?? [];
  const selectedTitle = typeof run?.context?.selected_title === "string" ? run.context.selected_title : "";
  const rankingTitleAccepted = human?.status === "succeeded" && (human.output?.source === "ranking_topic" || (!!selectedTitle && titles.length === 0));
  const [retrying, setRetrying] = useState("");
  const [retryMessage, setRetryMessage] = useState("");

  async function retry(node: RunNode) {
    if (!run) return;
    setRetrying(node.node_key); setRetryMessage("");
    try {
      await api<Wrapped<{ run_id: string; node_key: string }>>(`/api/v1/runs/${run.id}/nodes/${node.node_key}/retry`, { method: "POST", body: "{}" });
      setRetryMessage(`${node.title} 已重新进入队列，状态将自动刷新。`);
    } catch (error) {
      const detail = error instanceof ApiError ? JSON.stringify(error.payload) : String(error);
      setRetryMessage(`${node.title} 重试失败：${detail}`);
    } finally { setRetrying(""); }
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="panel">
        <h2>策划与首章生成</h2>
        <p className="muted">本工作流交付书名、简介卖点、世界观、人物卡、大纲和第一章；整书续写属于后续章节生产流程。</p>
        {retryMessage && <p>{retryMessage}</p>}
      </div>
      <div className="review-grid">
      <div className="panel">
        <div className="timeline">
          {nodes.map(n => (
            <div key={n.node_key} className={`node ${n.status}`}>
              <span>{n.node_key}</span>
              <div>
                <strong>{n.title}</strong><br />
                <small style={{color:"var(--text-muted)"}}>{n.agent ?? n.kind} · 尝试 {n.attempt ?? 0} 次</small><br />
                <small style={{color:"var(--text-muted)"}}>开始 {formatTime(n.started_at)} · 完成 {formatTime(n.finished_at)}</small>
                {n.error && <div className="danger-text"><small>{n.error}</small></div>}
                {RETRYABLE_STATUSES.has(n.status) && <button disabled={!!retrying} onClick={() => void retry(n)}>{retrying === n.node_key ? "重试中…" : "重试此节点"}</button>}
              </div>
              <em>{n.status}</em>
            </div>
          ))}
        </div>
      </div>
      <div className="panel human-gate">
        <h2>书名确认</h2>
        {rankingTitleAccepted ? <p>已采用榜单候选书名：<strong>{selectedTitle || String(human?.output?.selected_title || "已确认")}</strong></p> : human?.status === "waiting_human" ? (
          <div className="title-choices">
            {titles.map(t => <button key={t} onClick={() => onConfirm(t)}>{t}</button>)}
          </div>
        ) : (
          <p style={{color:"var(--text-muted)"}}>
            {human?.status === "succeeded" ? "书名已确认，继续执行..." : "等待书名候选生成..."}
          </p>
        )}
      </div>
      </div>
      <div className="panel">
        <h2>策划产物</h2>
        <div className="grid-cards">
          {nodes.filter(node => PLANNING_NODES.has(node.node_key)).map(node => <article className="feature-card" key={node.node_key}>
            <strong>{node.title}</strong><small>{node.status}</small>
            {node.output && Object.keys(node.output).length ? <OutputValue value={node.output} /> : <p className="muted">该节点尚未产出可展示内容。</p>}
          </article>)}
        </div>
      </div>
    </div>
  );
}
