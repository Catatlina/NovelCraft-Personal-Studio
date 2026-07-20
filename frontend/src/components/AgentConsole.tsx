import React, { useState, useEffect, useCallback } from "react";
import { Bot, Play, RotateCw, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { EmptyState } from "./ui";

interface Agent {
  id: string; slug: string; name: string; version: string;
  category: string; description: string; goal: any; workflow: any;
  trigger_type: string; status: string;
}
interface AgentRun {
  id: string; agent_id: string; status: string; progress: number;
  current_step: string; started_at: string; error_message?: string;
}

export function AgentConsole() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [aRes, rRes] = await Promise.allSettled([
        api<{ items: Agent[] }>("/api/v1/agents"),
        api<{ items: AgentRun[] }>("/api/v1/agents/runs?limit=10"),
      ]);
      if (aRes.status === "fulfilled" && aRes.value) setAgents(aRes.value.items ?? []);
      if (rRes.status === "fulfilled" && rRes.value) setRuns(rRes.value.items ?? []);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runAgent = async (agentId: string) => {
    setRunningId(agentId);
    try {
      await api(`/api/v1/agents/${agentId}/run`);
    } catch { /* toast handled by api layer */ }
    setRunningId(null);
    load();
  };

  const statusIcon = (s: string) => {
    switch (s) {
      case "completed": return <CheckCircle2 size={14} color="var(--success)" />;
      case "failed": return <XCircle size={14} color="var(--danger)" />;
      case "running": return <Loader2 size={14} color="var(--info)" className="nc-animate-pulse" />;
      default: return <Clock size={14} color="var(--text-muted)" />;
    }
  };

  const statusLabel = (s: string) => {
    const map: Record<string, string> = { pending: "等待中", running: "运行中", completed: "已完成", failed: "失败", waiting_human: "待确认" };
    return map[s] ?? s;
  };

  return (
    <div>
      <div className="breadcrumb"><b>星禾AI</b> › 智能体</div>
      <div className="page-head">
        <div>
          <h1>Agent 中心</h1>
          <p>管理和运行 AI Agent，自动化完成复杂创作任务</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={load}><RotateCw size={14} />刷新</button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}><Loader2 size={24} className="nc-animate-pulse" /><p style={{ marginTop: 12 }}>加载中…</p></div>
      ) : agents.length === 0 ? (
        <EmptyState icon={<Bot size={32} />} title="暂无可用 Agent" description="Agent 系统将在启动时自动注册内置 Agents" />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
          {agents.map(a => (
            <div key={a.id} className="panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 36, height: 36, borderRadius: "var(--radius-md)", background: "var(--brand-50)", color: "var(--brand-500)", display: "grid", placeItems: "center" }}>
                    <Bot size={18} />
                  </div>
                  <div>
                    <strong style={{ fontSize: 14 }}>{a.name}</strong>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>v{a.version} · {a.trigger_type === "manual" ? "手动" : a.trigger_type === "scheduled" ? "定时" : "事件"}</div>
                  </div>
                </div>
                <button
                  className="btn-sm btn-primary"
                  onClick={() => runAgent(a.id)}
                  disabled={runningId === a.id}
                  style={{ gap: 4 }}
                >
                  {runningId === a.id ? <Loader2 size={12} className="nc-animate-pulse" /> : <Play size={12} />}
                  运行
                </button>
              </div>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>{a.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recent Runs */}
      {runs.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ marginBottom: 12, fontSize: 16 }}>最近运行</h2>
          <div className="card-list">
            {runs.map(r => (
              <article key={r.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {statusIcon(r.status)}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13 }}>{statusLabel(r.status)}</div>
                  {r.current_step && <small>{r.current_step}</small>}
                </div>
                <div style={{ textAlign: "right" }}>
                  {r.progress > 0 && <div style={{ fontSize: 12, color: "var(--brand-500)" }}>{r.progress}%</div>}
                  <small>{r.started_at ? new Date(r.started_at).toLocaleString("zh-CN") : ""}</small>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
