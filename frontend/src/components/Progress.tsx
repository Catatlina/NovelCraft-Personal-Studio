import React, { useState } from "react";
import { ApiError, api } from "../lib/api";

type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string; output?: Record<string, unknown>; error?: string | null; attempt?: number; started_at?: string | null; finished_at?: string | null };
type Run = { id: string; nodes: RunNode[]; context: Record<string, unknown> };
type Wrapped<T> = { data: T };

const PLANNING_NODES = new Set([
  // V2 four-stage keys
  "plan_idea", "plan_market_fit", "plan_story_pattern", "plan_core_gameplay",
  "plan_world_architecture", "plan_character_system", "plan_conflict_map",
  "blueprint_volume_plan", "blueprint_chapter_outline", "blueprint_scene_beat",
  // legacy runs
  "n3", "n4", "n5", "n6",
]);
const HUMAN_NODE_KEYS = new Set(["human_confirm_title", "n2"]);
const RETRYABLE_STATUSES = new Set(["failed", "pending_budget"]);

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    succeeded: "green",
    running: "cyan",
    failed: "red",
    waiting_human: "orange",
    pending_budget: "orange",
    pending: "gray",
    queued: "gray",
    skipped: "gray",
  };
  return map[status] ?? "gray";
}

function statusDot(status: string): string {
  const map: Record<string, string> = {
    succeeded: "green",
    running: "cyan",
    failed: "red",
    waiting_human: "orange",
    pending_budget: "orange",
    pending: "gray",
    queued: "gray",
    skipped: "gray",
  };
  return map[status] ?? "gray";
}

function readableLabel(key: string): string {
  const labels: Record<string, string> = {
    synopsis: "简介", selling_points: "核心卖点", worldview: "世界观", characters: "人物卡",
    outline: "大纲", name: "名称", rules: "规则", title: "标题", arc: "人物弧",
  };
  return labels[key] || key.replaceAll("_", " ");
}

function OutputValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span style={{ color: "var(--text-3)" }}>未产出</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return <span>{String(value)}</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><OutputValue value={item} /></li>)}</ul> : <span style={{ color: "var(--text-3)" }}>未产出</span>;
  if (typeof value === "object") return <div style={{ display: "grid", gap: 6 }}>{Object.entries(value as Record<string, unknown>).map(([key, item]) => <div key={key}><strong>{readableLabel(key)}：</strong><OutputValue value={item} /></div>)}</div>;
  return <span>{String(value)}</span>;
}

function formatTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}

export function Progress({ run, onConfirm, onRegenerateTitles }: { run: Run | null; onConfirm: (title: string) => Promise<void>; onRegenerateTitles: (feedback: string) => Promise<void> }) {
  const nodes = run?.nodes ?? [];
  const human = nodes.find(n => HUMAN_NODE_KEYS.has(n.node_key));
  const titles = (run?.context?.title_candidates as string[]) ?? [];
  const selectedTitle = typeof run?.context?.selected_title === "string" ? run.context.selected_title : "";
  const [customTitle, setCustomTitle] = useState("");
  const [titleFeedback, setTitleFeedback] = useState("");
  const [titleBusy, setTitleBusy] = useState(false);
  const [retrying, setRetrying] = useState("");
  const [retryMessage, setRetryMessage] = useState("");
  const [selectedNodeKey, setSelectedNodeKey] = useState("");
  const selectedNode = nodes.find(n => n.node_key === (selectedNodeKey || run?.context?.current_node_key)) ?? nodes.find(n => n.status === "running") ?? nodes[0];

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

  async function regenerateTitles() {
    setTitleBusy(true); setRetryMessage("");
    try {
      await onRegenerateTitles(titleFeedback.trim());
      setTitleFeedback("");
      setRetryMessage("已生成一组新的书名候选，请选择或直接填写书名。");
    } catch (error) {
      const detail = error instanceof ApiError ? JSON.stringify(error.payload) : String(error);
      setRetryMessage(`重新生成书名失败：${detail}`);
    } finally { setTitleBusy(false); }
  }

  return (
    <div className="grid">
      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>策划与首章生成</h1>
          <p>本工作流交付书名、简介卖点、世界观、人物卡、大纲和第一章；整书续写属于后续章节生产流程。</p>
        </div>
        {retryMessage && (
          <span className={`badge ${retryMessage.includes("失败") ? "red" : "green"}`}>{retryMessage}</span>
        )}
      </div>

      {/* Run status / node flow */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <span>工作流节点</span>
          </div>
          <span className="badge purple">{nodes.length} 节点</span>
        </div>
        <div className="dag">
          {nodes.map((n, i) => (
            <React.Fragment key={n.node_key}>
              {i > 0 && <div className="arrow">→</div>}
              <button
                type="button"
                className={`node ${selectedNode?.node_key === n.node_key ? "run" : ""}`}
                onClick={() => setSelectedNodeKey(n.node_key)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span className={`dot ${statusDot(n.status)}`} />
                  <h5>{n.title}</h5>
                </div>
                <p>{n.agent ?? n.kind} · 尝试 {n.attempt ?? 0} 次</p>
                <p>开始 {formatTime(n.started_at)}</p>
                <span className={`badge ${statusBadge(n.status)}`} style={{ marginTop: 6 }}>{n.status}</span>
                {n.error && <p style={{ color: "var(--red)", fontSize: "11px", marginTop: 4 }}>{n.error}</p>}
              </button>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Two-column: node detail + title confirmation */}
      <div className="layout-2">
        {/* Node detail card */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">节点详情</div>
          </div>
          {selectedNode ? (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div>
                  <strong style={{ fontSize: 15 }}>{selectedNode.title}</strong>
                  <div><code>{selectedNode.node_key}</code></div>
                </div>
                <span className={`badge ${statusBadge(selectedNode.status)}`}>{selectedNode.status}</span>
              </div>
              <p style={{ color: "var(--text-3)", fontSize: 12 }}>{selectedNode.agent ?? selectedNode.kind} · 尝试 {selectedNode.attempt ?? 0} 次</p>
              <p style={{ color: "var(--text-3)", fontSize: 12 }}>开始 {formatTime(selectedNode.started_at)} · 完成 {formatTime(selectedNode.finished_at)}</p>
              {selectedNode.error && <div style={{ color: "var(--red)", fontSize: 13, marginTop: 8 }}>{selectedNode.error}</div>}
              {RETRYABLE_STATUSES.has(selectedNode.status) && (
                <button
                  className="btn-sm btn-primary"
                  style={{ width: "auto", marginTop: 12 }}
                  disabled={!!retrying}
                  onClick={() => void retry(selectedNode)}
                >
                  {retrying === selectedNode.node_key ? "重试中…" : "重试此节点"}
                </button>
              )}
              <h3 style={{ fontSize: 14, fontWeight: 600, marginTop: 16, marginBottom: 8 }}>输出</h3>
              {selectedNode.output && Object.keys(selectedNode.output).length ? (
                <OutputValue value={selectedNode.output} />
              ) : (
                <p style={{ color: "var(--text-3)", fontSize: 13 }}>该节点尚未产出可展示内容。</p>
              )}
            </>
          ) : (
            <p style={{ color: "var(--text-3)", fontSize: 13 }}>暂无节点。</p>
          )}
        </div>

        {/* Title confirmation card */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">书名确认</div>
            {human?.status && human.status !== "waiting_human" && (
              <span className={`badge ${statusBadge(human.status)}`}>{human.status}</span>
            )}
          </div>
          {human?.status === "waiting_human" ? (
            <div className="grid">
              <p style={{ color: "var(--text-2)", fontSize: 13 }}>请从 {titles.length} 个候选中选择；没有合适的可重新生成，或直接填写自己的书名。</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {titles.map(t => (
                  <button
                    key={t}
                    className="btn-ghost"
                    style={{ textAlign: "left", justifyContent: "flex-start" }}
                    disabled={titleBusy}
                    onClick={() => void onConfirm(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="field">
                <label className="form-label">自定义书名</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="form-input" maxLength={120} placeholder="自己填写书名" value={customTitle} onChange={event => setCustomTitle(event.target.value)} />
                  <button
                    className="btn-sm btn-primary"
                    style={{ width: "auto", flexShrink: 0 }}
                    disabled={titleBusy || !customTitle.trim()}
                    onClick={() => void onConfirm(customTitle.trim())}
                  >
                    使用
                  </button>
                </div>
              </div>
              <div className="field">
                <label className="form-label">反馈给 AI 重新生成</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="form-input" maxLength={500} placeholder="告诉 AI 新书名应强调什么" value={titleFeedback} onChange={event => setTitleFeedback(event.target.value)} />
                  <button
                    className="btn-sm btn-primary"
                    style={{ width: "auto", flexShrink: 0 }}
                    disabled={titleBusy}
                    onClick={() => void regenerateTitles()}
                  >
                    {titleBusy ? "生成中…" : "重新生成"}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-2)", fontSize: 13 }}>
              {human?.status === "succeeded" ? <>已确认书名：<strong>{selectedTitle || String(human?.output?.selected_title || "已确认")}</strong></> : "等待书名候选生成..."}
            </p>
          )}
        </div>
      </div>

      {/* Planning artifacts */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">策划产物</div>
        </div>
        <div className="grid grid-3">
          {nodes.filter(node => PLANNING_NODES.has(node.node_key)).map(node => (
            <div className="card" key={node.node_key}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <strong>{node.title}</strong>
                <span className={`badge ${statusBadge(node.status)}`}>{node.status}</span>
              </div>
              {node.output && Object.keys(node.output).length ? (
                <OutputValue value={node.output} />
              ) : (
                <p style={{ color: "var(--text-3)", fontSize: 13 }}>该节点尚未产出可展示内容。</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
