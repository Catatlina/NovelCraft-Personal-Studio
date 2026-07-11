import React, { useState } from "react";
import { ArrowRight, Save, Settings, User, Zap, GitBranch, Plus, X } from "lucide-react";
import { api } from "../lib/api";

type WFNode = { key: string; kind: "agent"|"human"|"tool"|"branch"; agent?: string; title: string; task?: string };
const NODE_COLORS: Record<string, string> = { agent: "var(--brand-500)", human: "var(--warning)", tool: "var(--info)", branch: "var(--success)" };
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
      <div className="panel" style={{ minHeight: 400 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <GitBranch size={18} />
          <h2 style={{ margin: 0, fontSize: 16 }}>工作流 DAG 设计稿</h2>
          <button onClick={addNode} style={{ marginLeft: "auto" }}><Plus size={14} />添加节点</button>
          <button onClick={saveWorkflow} style={{ marginLeft: 8 }}><Save size={14} />保存{saveMsg && <small style={{marginLeft:4}}>{saveMsg}</small>}</button>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>当前仅系统 Bootstrap 工作流可执行；这里保存的是项目级设计稿，不会被冒充为已运行。</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 0, alignItems: "center" }}>
          {nodes.map((node, i) => (
            <React.Fragment key={node.key}>
              <button
                onClick={() => setSelected(node.key)}
                style={{
                  width: "100%", maxWidth: 400, display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", border: `2px solid ${selected === node.key ? NODE_COLORS[node.kind] : "var(--border-subtle)"}`,
                  borderRadius: 8, background: "var(--bg-surface)", textAlign: "left",
                }}
              >
                <span style={{ width: 32, height: 32, borderRadius: 6, background: NODE_COLORS[node.kind], color: "#fff", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>
                  {node.kind === "agent" ? <Zap size={14} /> : node.kind === "human" ? <User size={14} /> : <Settings size={14} />}
                </span>
                <div style={{ flex: 1 }}>
                  <strong style={{ fontSize: 14 }}>{node.title}</strong>
                  <small style={{ display: "block", color: "var(--text-muted)", fontSize: 12 }}>
                    {node.kind}{node.agent ? ` · ${node.agent}` : ""}{node.task ? ` · ${node.task}` : ""}
                  </small>
                </div>
                <button onClick={(e) => { e.stopPropagation(); removeNode(node.key); }} style={{ border: "none", padding: 4, opacity: 0.5 }}><X size={14} /></button>
              </button>
              {i < nodes.length - 1 && <ArrowRight size={20} style={{ color: "var(--text-muted)", margin: "4px 0" }} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {selected && (
        <div className="panel">
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>节点配置</h2>
          {(() => {
            const n = nodes.find(x => x.key === selected)!;
            return (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
                  类型
                  <select value={n.kind} onChange={e => updateNode(n.key, "kind", e.target.value)}>
                    {KINDS.map(k => <option key={k} value={k}>{k}</option>)}
                  </select>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
                  标题 <input value={n.title} onChange={e => updateNode(n.key, "title", e.target.value)} />
                </label>
                {n.kind === "agent" && (
                  <>
                    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
                      Agent <input value={n.agent || ""} onChange={e => updateNode(n.key, "agent", e.target.value)} placeholder="Writer" />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
                      任务类型 <input value={n.task || ""} onChange={e => updateNode(n.key, "task", e.target.value)} placeholder="gen_chapter" />
                    </label>
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
