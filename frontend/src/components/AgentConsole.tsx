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
    <div className="card">
      <div className="card-head">
        <div className="card-title"><Terminal size={14} /> Agent 运行控制台</div>
      </div>
      <table style={{ width: "100%", fontSize: 13 }}>
        <thead><tr><th>Agent</th><th>状态</th><th>任务数</th><th>最近运行</th></tr></thead>
        <tbody>
          {agents.map(a => (
            <tr key={a.name}>
              <td style={{ fontWeight: 600 }}>{a.name}</td>
              <td>
                <span className={`badge ${a.status === "running" ? "green" : a.status === "stale" ? "orange" : "gray"}`}>
                  {a.status === "running" ? "运行中" : a.status === "stale" ? "异常未收敛" : "空闲"}
                </span>
              </td>
              <td>{a.task_count}</td>
              <td style={{ fontSize: 11, color: "var(--text-muted)" }}>{a.last_run}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!agents.length && <div className="empty"><p>暂无 Agent 运行记录 — 启动一次生成工作流后此处显示真实节点统计。</p></div>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button className="btn-sm" onClick={load}><Activity size={12} /> 刷新</button>
      </div>
    </div>
  );
}
