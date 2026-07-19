import React, { useState, useEffect, useRef } from "react";
import { ArrowRight, Save, Settings, User, Zap, GitBranch, Plus, X, Play } from "lucide-react";
import { api } from "../lib/api";

type WFNode = { key: string; kind: "agent"|"human"|"tool"|"branch"; agent?: string; title: string; task?: string };
const NODE_COLORS: Record<string, string> = { agent: "var(--primary)", human: "var(--orange)", tool: "var(--cyan)", branch: "var(--green)" };
const KINDS = ["agent","human","tool","branch"] as const;

type SavedWorkflow = { name?: string; nodes?: unknown; definition?: unknown };

/** Extract a node array from a saved-workflow row, tolerant of either a
 *  top-level `nodes` field or a nested `definition.nodes` (string or object). */
function extractWorkflowNodes(raw: SavedWorkflow | null | undefined): WFNode[] | null {
  if (!raw || typeof raw !== "object") return null;
  const candidates: unknown[] = [];
  if (Array.isArray((raw as any).nodes)) candidates.push((raw as any).nodes);
  const def = (raw as any).definition;
  if (def != null) {
    let parsed = def;
    if (typeof def === "string") {
      try { parsed = JSON.parse(def); } catch { parsed = null; }
    }
    if (parsed && typeof parsed === "object" && Array.isArray((parsed as any).nodes)) {
      candidates.push((parsed as any).nodes);
    }
  }
  for (const c of candidates) {
    if (Array.isArray(c) && c.length > 0) return c.map((n, idx) => normalizeWorkflowNode(n, idx));
  }
  return null;
}

function normalizeWorkflowNode(raw: any, i: number): WFNode {
  const kind = (["agent", "human", "tool", "branch"] as const).includes(raw?.kind)
    ? (raw.kind as WFNode["kind"])
    : "agent";
  return {
    key: typeof raw?.key === "string" && raw.key ? raw.key : `n${i + 1}`,
    kind,
    agent: typeof raw?.agent === "string" ? raw.agent : undefined,
    title: typeof raw?.title === "string"
      ? raw.title
      : typeof raw?.label === "string"
        ? raw.label
        : "未命名节点",
    task: typeof raw?.task === "string" ? raw.task : undefined,
  };
}

export function DagEditor({ projectId = "", novelId = "" }: { projectId?: string; novelId?: string }) {
  const [nodes, setNodes] = useState<WFNode[]>([
    { key: "n1", kind: "agent", agent: "StoryArchitect", title: "生成书名", task: "gen_titles" },
    { key: "n2", kind: "human", title: "选定书名" },
    { key: "n3", kind: "agent", agent: "StoryArchitect", title: "生成简介", task: "gen_synopsis" },
  ]);
  const [selected, setSelected] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState("");
  const [loadingWf, setLoadingWf] = useState(false);
  const initRef = useRef(false);

  // 挂载即尝试加载已保存的工作流（优先 custom-dag，否则首个），用其 nodes 初始化本地草稿。
  useEffect(() => {
    if (!projectId || initRef.current) return;
    initRef.current = true;
    let cancelled = false;
    setLoadingWf(true);
    api<{ code: number | string; message: string; data: SavedWorkflow[] }>(
      `/api/v1/admin/workflows?project_id=${encodeURIComponent(projectId)}`,
    )
      .then((resp) => {
        if (cancelled) return;
        const list = resp?.data;
        if (!Array.isArray(list) || list.length === 0) return;
        const wf = list.find((w) => w.name === "custom-dag") ?? list[0];
        const loaded = extractWorkflowNodes(wf);
        if (loaded) setNodes(loaded);
      })
      .catch(() => {
        /* 加载失败不阻塞本地草稿编辑 */
      })
      .finally(() => { if (!cancelled) setLoadingWf(false); });
    return () => { cancelled = true; };
  }, [projectId]);

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

  async function executeWorkflow() {
    if (!projectId) { setSaveMsg("❌ 缺少项目，无法执行"); setTimeout(() => setSaveMsg(""), 2500); return; }
    if (!novelId) { setSaveMsg("⚠️ 请先在编辑器中打开一部小说再执行"); setTimeout(() => setSaveMsg(""), 2500); return; }
    try {
      const resp = await api<{ code: number | string; message: string; data: { run_id?: string; status?: string } }>(
        "/api/v1/admin/workflows/custom-dag/execute",
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: projectId, novel_id: novelId }) },
      );
      const runId = resp?.data?.run_id;
      setSaveMsg(runId ? `✅ 已提交执行（run_id: ${runId}）` : "✅ 已提交执行");
    } catch (e: any) {
      const detail = e?.payload?.detail || e?.payload?.message || e?.message || "执行未成功";
      setSaveMsg(`⚠️ 执行未成功：${detail}`);
    }
    setTimeout(() => setSaveMsg(""), 3000);
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
            <button className="btn-sm btn-ghost" onClick={executeWorkflow} title="执行工作流（需后端 worker 支持）">
              <Play size={14} />执行
            </button>
            <button className="btn-sm" style={{ background: "var(--primary)", color: "var(--brand-foreground)" }} onClick={saveWorkflow}>
              <Save size={14} />保存{saveMsg && <small style={{marginLeft:4}}>{saveMsg}</small>}
            </button>
          </div>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 16 }}>
          {loadingWf
            ? "正在加载已存工作流…"
            : "当前仅系统 Bootstrap 工作流可执行；这里保存的是项目级设计稿，不会被冒充为已运行。"}
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
                <span style={{ width: 32, height: 32, borderRadius: 6, background: NODE_COLORS[node.kind], color: "var(--brand-foreground)", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>
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
