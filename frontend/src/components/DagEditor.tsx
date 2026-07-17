import React, { useState } from "react";
import { ArrowRight, Save, Settings, User, Zap, GitBranch, Plus, X } from "lucide-react";
import { api } from "../lib/api";
import "../styles/proto.css";

type WFNode = { key: string; kind: "agent"|"human"|"tool"|"branch"; agent?: string; title: string; task?: string };
const NODE_COLORS: Record<string, string> = { agent: "var(--primary)", human: "var(--orange)", tool: "var(--cyan)", branch: "var(--green)" };
const KINDS = ["agent","human","tool","branch"] as const;

export function DagEditor({ projectId = "" }: { projectId?: string }) {
  const [nodes, setNodes] = useState<WFNode[]>([
    { key: "n1", kind: "agent", agent: "StoryArchitect", title: "生成书名", task: "gen_titles" },
    { key: "n2", kind: "human", title: "选定书名" },
    { key: "n3", kind: "agent", agent: "StoryArchitect", title: "生成简介", task: "gen_synopsis" },
  ]);
  const [selected, setSelected] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState("");

  function addNode() {
    const key = `n${nodes.length + 1}`;
    setNodes([...nodes, { key, kind: "agent", agent: "Writer", title: "新节点", task: "" }]);
  }

  function updateNode(key: string, field: string, value: string) {
    setNodes(nodes.map(n => n.key === key ? { ...n, [field]: value } as WFNode : n));
  }

  function removeNode(key: string) { setNodes(nodes.filter(n => n.key !== key)); }

  async function saveWorkflow() {
    if (!projectId) { setSaveMsg("❌ 缺少项目，无法保存"); setTimeout(() => setSaveMsg(""), 2000); return; }
    try {
      await api("/api/v1/admin/workflows/custom-dag", {
        method: "PUT", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({nodes, project_id: projectId}),
      });
      setSaveMsg("✅ 设计稿已保存");
    } catch { setSaveMsg("❌ 保存失败"); }
    setTimeout(() => setSaveMsg(""), 2000);
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
      {/* --- DAG Canvas --- */}
      <div className="card" style={{ minHeight: 400 }}>
        <div className="card-head">
          <div className="card-title">
            <GitBranch size={18} />
            工作流 DAG 设计稿
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-sm btn-ghost" onClick={addNode}><Plus size={14} />添加节点</button>
            <button className="btn-sm" style={{ background: "var(--primary)", color: "#fff" }} onClick={saveWorkflow}>
              <Save size={14} />保存{saveMsg && <small style={{marginLeft:4}}>{saveMsg}</small>}
            </button>
          </div>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 16 }}>
          当前仅系统 Bootstrap 工作流可执行；这里保存的是项目级设计稿，不会被冒充为已运行。
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 0, alignItems: "center" }}>
          {nodes.map((node, i) => (
            <React.Fragment key={node.key}>
              <button
                onClick={() => setSelected(node.key)}
                className="card"
                style={{
                  width: "100%", maxWidth: 400, display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", cursor: "pointer",
                  border: `2px solid ${selected === node.key ? NODE_COLORS[node.kind] : "var(--border)"}`,
                  borderRadius: "var(--r-md)", textAlign: "left",
                }}
              >
                <span style={{ width: 32, height: 32, borderRadius: 6, background: NODE_COLORS[node.kind], color: "#fff", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>
                  {node.kind === "agent" ? <Zap size={14} /> : node.kind === "human" ? <User size={14} /> : <Settings size={14} />}
                </span>
                <div style={{ flex: 1 }}>
                  <strong style={{ fontSize: 14, color: "var(--text-1)" }}>{node.title}</strong>
                  <small style={{ display: "block", color: "var(--text-3)", fontSize: 12 }}>
                    {node.kind}{node.agent ? ` · ${node.agent}` : ""}{node.task ? ` · ${node.task}` : ""}
                  </small>
                </div>
                <button onClick={(e) => { e.stopPropagation(); removeNode(node.key); }} className="btn-ghost" style={{ padding: 4, opacity: 0.5 }}><X size={14} /></button>
              </button>
              {i < nodes.length - 1 && <ArrowRight size={20} style={{ color: "var(--text-3)", margin: "4px 0" }} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* --- Node Config Panel --- */}
      {selected && (
        <div className="card">
          <h2 style={{ fontSize: 16, marginBottom: 12, fontWeight: 600, color: "var(--text-1)" }}>节点配置</h2>
          {(() => {
            const n = nodes.find(x => x.key === selected)!;
            return (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div className="field">
                  <label>类型</label>
                  <select className="form-input" value={n.kind} onChange={e => updateNode(n.key, "kind", e.target.value)}>
                    {KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>标题</label>
                  <input className="form-input" value={n.title} onChange={e => updateNode(n.key, "title", e.target.value)} />
                </div>
                {n.kind === "agent" && (
                  <>
                    <div className="field">
                      <label>Agent</label>
                      <input className="form-input" value={n.agent || ""} onChange={e => updateNode(n.key, "agent", e.target.value)} placeholder="Writer" />
                    </div>
                    <div className="field">
                      <label>任务类型</label>
                      <input className="form-input" value={n.task || ""} onChange={e => updateNode(n.key, "task", e.target.value)} placeholder="gen_chapter" />
                    </div>
                  </>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
