import React, { useState } from "react";
import { ApiError, api } from "../lib/api";
import { StepTimeline } from "./ui";
import type { TimelineStep, StepStatus } from "./ui";

/* ============================ Types ============================ */

type TipTapDoc = { type?: string; content?: Array<{ type: string; text?: string }> };

/** Mirrors App.tsx's `Content` shape so the `novel` prop accepts it structurally. */
type Content = {
  id: string;
  project_id: string;
  parent_id: string | null;
  type: string;
  title: string;
  body: TipTapDoc;
  meta: Record<string, unknown>;
  status: string;
  updated_at: string;
  sync_status?: "applied" | "conflict";
};

type RunNode = {
  node_key: string;
  kind: string;
  agent: string | null;
  title: string;
  status: string;
  output?: Record<string, unknown>;
  error?: string | null;
  attempt?: number;
  started_at?: string | null;
  finished_at?: string | null;
};

/**
 * Aligned with the real Run produced by App/backend: the live object also
 * carries `status` and `current_node_key` (see App.tsx), so we widen the type
 * to avoid type errors when reading `run.status` / `run.current_node_key`.
 */
type Run = {
  id: string;
  nodes: RunNode[];
  context: Record<string, unknown>;
  status?: string;
  current_node_key?: string | null;
};

type Wrapped<T> = { data: T };

/* ===================== Constants / helpers ===================== */

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

/** Map a node status to its semantic badge class (doc12-aligned). */
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

/** Map the overall run status to a Chinese label + badge class for 《创作总览》. */
function runStatusZh(status?: string): { label: string; badge: string } {
  switch (status) {
    case "running":   return { label: "进行中", badge: "cyan" };
    case "succeeded": return { label: "已完成", badge: "green" };
    case "failed":    return { label: "失败",   badge: "red" };
    default:          return { label: "草稿",   badge: "gray" };
  }
}

function readableLabel(key: string): string {
  const labels: Record<string, string> = {
    synopsis: "简介", selling_points: "核心卖点", worldview: "世界观", characters: "人物卡",
    outline: "大纲", name: "名称", rules: "规则", title: "标题", arc: "人物弧",
  };
  return labels[key] || key.replaceAll("_", " ");
}

/** Recursively renders an arbitrary agent output tree. */
function OutputValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <span style={{ color: "var(--text-muted)" }}>未产出</span>;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return value.length
      ? <ul>{value.map((item, index) => <li key={index}><OutputValue value={item} /></li>)}</ul>
      : <span style={{ color: "var(--text-muted)" }}>未产出</span>;
  }
  if (typeof value === "object") {
    return (
      <div style={{ display: "grid", gap: 6 }}>
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key}><strong>{readableLabel(key)}：</strong><OutputValue value={item} /></div>
        ))}
      </div>
    );
  }
  return <span>{String(value)}</span>;
}

function formatTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

/** Compact key/value tile used in the 《创作总览》 detailed-data row. */
function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: "var(--bg-subtle)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-3)",
      }}
    >
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-primary)", wordBreak: "break-word" }}>{value}</div>
    </div>
  );
}

/* ============================ Progress ============================ */

export function Progress({
  run,
  novel,
  onConfirm,
  onRegenerateTitles,
}: {
  run: Run | null;
  novel: Content | null;
  onConfirm: (title: string) => Promise<void>;
  onRegenerateTitles: (feedback: string) => Promise<void>;
}) {
  const nodes = run?.nodes ?? [];
  const human = nodes.find((n) => HUMAN_NODE_KEYS.has(n.node_key));
  const titles = (run?.context?.title_candidates as string[]) ?? [];
  const selectedTitle = typeof run?.context?.selected_title === "string" ? run.context.selected_title : "";
  const [customTitle, setCustomTitle] = useState("");
  const [titleFeedback, setTitleFeedback] = useState("");
  const [titleBusy, setTitleBusy] = useState(false);
  const [retrying, setRetrying] = useState("");
  const [retryMessage, setRetryMessage] = useState("");
  const [selectedNodeKey, setSelectedNodeKey] = useState("");

  // 《创作总览》field sources ------------------------------------------------
  const titleCandidates = run?.context?.title_candidates as string[] | undefined;
  const novelName: string =
    novel?.title ??
    (run?.context?.selected_title as string | undefined) ??
    titleCandidates?.[0] ??
    "未命名作品";

  const statusInfo = runStatusZh(run?.status);

  const succeededCount = nodes.filter((n) => n.status === "succeeded").length;
  const total = nodes.length;
  const percent = total === 0 ? 0 : Math.round((succeededCount / total) * 100);

  const currentKey = run?.current_node_key ?? (run?.context?.current_node_key as string | undefined);
  const hasActiveFlow = run?.status === "running" || nodes.some((n) => n.status === "running" || n.node_key === currentKey);

  // ETA is a frontend weighted estimate (90s/non-succeeded node), NOT real data.
  let eta = "—";
  if (hasActiveFlow && total > succeededCount) {
    const remaining = total - succeededCount;
    const etaDate = new Date(Date.now() + remaining * 90 * 1000);
    eta = "预计 " + etaDate.toLocaleString("zh-CN", { hour12: false });
  }

  const recentNode = nodes
    .filter((n) => n.status === "succeeded")
    .sort((a, b) => new Date(b.finished_at ?? 0).getTime() - new Date(a.finished_at ?? 0).getTime())[0];
  const recentTitle = recentNode?.title ?? "—";

  const nextNode =
    nodes.find((n) => n.status === "running" || n.node_key === currentKey) ??
    nodes.find((n) => n.status !== "succeeded");
  const nextTitle = nextNode?.title ?? "等待流程推进";

  // nodes -> TimelineStep[] mapping -----------------------------------------
  const steps: TimelineStep[] = nodes.map((n) => {
    const stepStatus: StepStatus =
      n.status === "succeeded"
        ? "done"
        : n.status === "running" || n.node_key === currentKey
          ? "active"
          : "waiting";
    return {
      key: n.node_key,
      label: n.title,
      status: stepStatus,
      detail: <NodeDetail node={n} onRetry={retry} />,
    };
  });

  // Preserve the original selection logic: explicit key -> context current -> running -> first.
  const selectedNode =
    nodes.find((n) => n.node_key === (selectedNodeKey || (run?.context?.current_node_key as string | undefined))) ??
    nodes.find((n) => n.status === "running") ??
    nodes[0];

  async function retry(node: RunNode) {
    if (!run) return;
    setRetrying(node.node_key);
    setRetryMessage("");
    try {
      await api<Wrapped<{ run_id: string; node_key: string }>>(
        `/api/v1/runs/${run.id}/nodes/${node.node_key}/retry`,
        { method: "POST", body: "{}" },
      );
      setRetryMessage(`${node.title} 已重新进入队列，状态将自动刷新。`);
    } catch (error) {
      const detail = error instanceof ApiError ? JSON.stringify(error.payload) : String(error);
      setRetryMessage(`${node.title} 重试失败：${detail}`);
    } finally {
      setRetrying("");
    }
  }

  async function regenerateTitles() {
    setTitleBusy(true);
    setRetryMessage("");
    try {
      await onRegenerateTitles(titleFeedback.trim());
      setTitleFeedback("");
      setRetryMessage("已生成一组新的书名候选，请选择或直接填写书名。");
    } catch (error) {
      const detail = error instanceof ApiError ? JSON.stringify(error.payload) : String(error);
      setRetryMessage(`重新生成书名失败：${detail}`);
    } finally {
      setTitleBusy(false);
    }
  }

  // Node detail, reused both inside the timeline step and the left column card.
  // Defined inline so it closes over `retrying` for the per-node "重试中…" label.
  function NodeDetail({ node, onRetry }: { node: RunNode; onRetry: (n: RunNode) => void }) {
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <div style={{ minWidth: 0 }}>
            <strong style={{ fontSize: 15, color: "var(--text-primary)" }}>{node.title}</strong>
            <div><code style={{ color: "var(--text-secondary)", fontSize: 12 }}>{node.node_key}</code></div>
          </div>
          <span className={`badge ${statusBadge(node.status)}`}>{node.status}</span>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>
          {node.agent ?? node.kind} · 尝试 {node.attempt ?? 0} 次
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: 12 }}>
          开始 {formatTime(node.started_at)} · 完成 {formatTime(node.finished_at)}
        </p>
        {node.error && <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 8 }}>{node.error}</div>}
        {RETRYABLE_STATUSES.has(node.status) && (
          <button
            className="btn-sm btn-primary"
            style={{ width: "auto", marginTop: 12 }}
            disabled={!!retrying}
            onClick={() => void onRetry(node)}
          >
            {retrying === node.node_key ? "重试中…" : "重试此节点"}
          </button>
        )}
        <h3 style={{ fontSize: 14, fontWeight: 600, marginTop: 16, marginBottom: 8, color: "var(--text-primary)" }}>输出</h3>
        {node.output && Object.keys(node.output).length ? (
          <OutputValue value={node.output} />
        ) : (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>该节点尚未产出可展示内容。</p>
        )}
      </div>
    );
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

      {/* 《创作总览》 */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">创作总览</div>
          <span className="badge purple">{nodes.length} 节点</span>
        </div>

        {/* 顶部核心数据概览 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginBottom: 4 }}>小说名</div>
              <h2 style={{ fontSize: "var(--text-xl)", fontWeight: 700, color: "var(--text-primary)", wordBreak: "break-word" }}>{novelName}</h2>
            </div>
            <span className={`badge ${statusInfo.badge}`}>{statusInfo.label}</span>
          </div>

          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>完成度</span>
              <span style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", fontWeight: 600 }}>{percent}%</span>
            </div>
            <div style={{ height: "var(--space-2)", background: "var(--bg-subtle)", borderRadius: "var(--radius-full)", overflow: "hidden" }}>
              <div
                style={{
                  width: `${percent}%`,
                  height: "100%",
                  background: "var(--brand-500)",
                  borderRadius: "var(--radius-full)",
                  transition: "width var(--dur-base) var(--ease-standard)",
                }}
              />
            </div>
          </div>
        </div>

        {/* 中部主流程 */}
        <div style={{ marginBottom: 20 }}>
          <StepTimeline steps={steps} />
        </div>

        {/* 底部详细数据 */}
        <div className="grid grid-4" style={{ gap: 12 }}>
          <DetailItem label="已完成阶段数" value={`${succeededCount} / ${total}`} />
          <DetailItem label="预计完成" value={eta} />
          <DetailItem label="最近任务" value={recentTitle} />
          <DetailItem label="下一步" value={nextTitle} />
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
            <NodeDetail node={selectedNode} onRetry={retry} />
          ) : (
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>暂无节点。</p>
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
              <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>请从 {titles.length} 个候选中选择；没有合适的可重新生成，或直接填写自己的书名。</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {titles.map((t) => (
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
                  <input
                    className="form-input"
                    maxLength={120}
                    placeholder="自己填写书名"
                    value={customTitle}
                    onChange={(event) => setCustomTitle(event.target.value)}
                  />
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
                  <input
                    className="form-input"
                    maxLength={500}
                    placeholder="告诉 AI 新书名应强调什么"
                    value={titleFeedback}
                    onChange={(event) => setTitleFeedback(event.target.value)}
                  />
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
            <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
              {human?.status === "succeeded" ? (
                <>已确认书名：<strong>{selectedTitle || String(human?.output?.selected_title || "已确认")}</strong></>
              ) : (
                "等待书名候选生成..."
              )}
            </p>
          )}
        </div>
      </div>

      {/* Planning artifacts (kept untouched for Wave D accordion refactor) */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">策划产物</div>
        </div>
        <div className="grid grid-3">
          {nodes.filter((node) => PLANNING_NODES.has(node.node_key)).map((node) => (
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
