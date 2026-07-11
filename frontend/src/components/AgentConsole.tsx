import React, { useState, useEffect } from "react";
import { Terminal, Play, Pause, RotateCcw, Activity } from "lucide-react";
import { api } from "../lib/api";

type AgentStatus = { name: string; status: string; task_count: number; last_run: string };

export function AgentConsole() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);

  useEffect(() => {
    // TODO: replace with real API
    // Simulated agent status — would come from Celery inspect in production
    setAgents([
      { name: "StoryArchitect", status: "idle", task_count: 0, last_run: "--" },
      { name: "Writer", status: "idle", task_count: 0, last_run: "--" },
      { name: "Reviewer", status: "idle", task_count: 0, last_run: "--" },
      { name: "Celery Worker", status: "running", task_count: 0, last_run: "--" },
    ]);
  }, []);

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
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button onClick={() => api("/api/v1/healthz")}><Activity size={12} /> 刷新</button>
        <button><RotateCcw size={12} /> 重启Worker</button>
      </div>
    </div>
  );
}
