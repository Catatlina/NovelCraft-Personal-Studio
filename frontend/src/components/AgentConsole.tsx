import React, { useState, useEffect } from "react";
import { Terminal, Activity } from "lucide-react";
import { api } from "../lib/api";

type AgentStatus = { name: string; status: string; task_count: number; last_run: string };

export function AgentConsole() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);

  const load = () => {
    api<{ data: AgentStatus[] }>("/api/v1/agents/status")
      .then(d => setAgents(d.data || []))
      .catch(() => setAgents([]));
  };

  useEffect(load, []);

  return (
    <div className="panel">
      <h3><Terminal size={14} /> Agent 运行控制台</h3>
      <table style={{ width: "100%", fontSize: 13 }}>
        <thead><tr><th>Agent</th><th>状态</th><th>任务数</th><th>最近运行</th></tr></thead>
        <tbody>
          {agents.map(a => (
            <tr key={a.name}>
              <td style={{ fontWeight: 600 }}>{a.name}</td>
              <td>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 4,
                  color: a.status === "running" ? "var(--success)" : "var(--text-muted)"
                }}>
                  <Activity size={10} />
                  {a.status === "running" ? "运行中" : "空闲"}
                </span>
              </td>
              <td>{a.task_count}</td>
              <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{a.last_run}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!agents.length && <p className="muted" style={{ fontSize: 12 }}>暂无 Agent 运行记录 — 启动一次生成工作流后此处显示真实节点统计。</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button onClick={load}><Activity size={12} /> 刷新</button>
      </div>
    </div>
  );
}
