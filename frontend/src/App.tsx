import React, { useEffect, useMemo, useState } from "react";
import { Layout } from "./components/Layout";
import { Wizard } from "./components/Wizard";
import { Progress } from "./components/Progress";
import { Review } from "./components/Review";
import { Editor } from "./components/Editor";
import { Costs } from "./components/Costs";
import { CommandPalette } from "./components/CommandPalette";
import { DagEditor } from "./components/DagEditor";
import { Settings } from "./components/Settings";
import { Studio } from "./components/Studio";
import { PublishDashboard } from "./components/PublishDashboard";
import { LoginPage } from "./components/LoginPage";
import { Code2, LogOut, Settings as SettingsIcon, Workflow, Layers, Rocket } from "lucide-react";

type ApiResponse<T> = { code: number | string; message: string; data: T };
type Content = { id: string; project_id: string; parent_id: string | null; type: string; title: string; body: TipTapDoc; meta: Record<string, unknown>; status: string };
type TipTapDoc = { type?: string; content?: Array<{ type: string; text?: string }> };
type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string; output: Record<string, unknown> };
type Run = { id: string; project_id: string; novel_id: string; status: string; current_node_key: string | null; context: Record<string, unknown>; nodes: RunNode[] };
type AiCall = { id: string; provider: string; model: string; prompt_name: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number; status: string; created_at: string };
type Knowledge = { id: string; kind: string; title: string; body: string; meta: Record<string, unknown> };
type Version = { id: string; label: string; snapshot: Record<string, unknown>; created_at: string };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string, unknown> };
type Tab = "wizard" | "progress" | "review" | "editor" | "costs" | "prompts" | "dag" | "settings" | "studio" | "publish";

const API = "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!r.ok) throw new Error(await r.text());
  return ((await r.json()) as ApiResponse<T>).data;
}

function docToText(doc: TipTapDoc): string {
  return doc.content?.map(i => i.text ?? "").join("\n\n") ?? "";
}

function textToDoc(text: string): TipTapDoc {
  return { type: "doc", content: text.split(/\n{2,}/).map(t => t.trim()).filter(Boolean).map(t => ({ type: "paragraph", text: t })) };
}

export default function App() {
  const [tab, setTab] = useState<Tab>("wizard");
  const [token, setToken] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [project, setProject] = useState<{ id: string; name: string } | null>(null);
  const [novel, setNovel] = useState<Content | null>(null);
  const [chapter, setChapter] = useState<Content | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [aiCalls, setAiCalls] = useState<AiCall[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [idea, setIdea] = useState("一个写作者发现自己删掉的章节正在现实里发生。");
  const [genre, setGenre] = useState("都市奇幻");
  const [style, setStyle] = useState("克制、悬疑、强画面感");
  const [targetWords, setTargetWords] = useState(800000);
  const [editorText, setEditorText] = useState("");
  const [selection, setSelection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ id: string; name: string }[]>("/api/v1/projects").then(p => setProject(p[0] ?? null)).catch(e => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!run) return;
    const poll = setInterval(() => { if (run) refreshRun(run.id); }, 2000);
    return () => clearInterval(poll);
  }, [run?.id]);

  useEffect(() => {
    if (!novel || !project) return;
    api<Content[]>(`/api/v1/contents?project_id=${project.id}&parent_id=${novel.id}`).then(items => {
      const ch = items.find(i => i.type === "chapter") ?? null;
      setChapter(ch);
      if (ch) { setEditorText(docToText(ch.body)); loadVersions(ch.id); }
    });
    api<Knowledge[]>(`/api/v1/knowledge?project_id=${project.id}&content_id=${novel.id}`).then(setKnowledge);
  }, [novel?.id, run?.status]);

  useEffect(() => { if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls); }, [run?.id, run?.status]);
  useEffect(() => {
    if (!project) return;
    api<Budget[]>(`/api/v1/admin/budgets?project_id=${project.id}`).then(setBudgets);
    api<ModelRoute[]>("/api/v1/model-routes").then(setRoutes);
  }, [project?.id, run?.status]);

  async function refreshRun(runId: string) {
    const r = await api<Run>(`/api/v1/runs/${runId}`);
    setRun(r);
    const n = await api<Content>(`/api/v1/contents/${r.novel_id}`);
    setNovel(n);
    if (r.status === "succeeded") setTab("review");
  }

  async function startBootstrap() {
    if (!project) return;
    setBusy(true); setError("");
    try {
      const c = await api<Content>(`/api/v1/projects/${project.id}/novels`, { method: "POST", body: JSON.stringify({ idea, genre, style, target_words: targetWords }) });
      setNovel(c);
      const s = await api<{ run_id: string }>(`/api/v1/novels/${c.id}/bootstrap`, { method: "POST", body: "{}" });
      setTab("progress");
      await refreshRun(s.run_id);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function confirmTitle(title: string) {
    if (!run) return;
    await api(`/api/v1/runs/${run.id}/nodes/n2/confirm`, { method: "POST", body: JSON.stringify({ selected_title: title }) });
    await refreshRun(run.id);
  }

  async function saveChapter() {
    if (!chapter) return;
    const u = await api<Content>(`/api/v1/contents/${chapter.id}`, { method: "PUT", body: JSON.stringify({ body: textToDoc(editorText), reason: "manual_save" }) });
    setChapter(u); loadVersions(u.id);
  }

  async function runEditorOp(op: string) {
    if (!chapter || !selection.trim()) return;
    const o = await api<{ text: string }>(`/api/v1/contents/${chapter.id}/ai/${op}`, { method: "POST", body: JSON.stringify({ selection, instruction: "保持当前风格" }) });
    setEditorText(c => c.replace(selection, o.text)); setSelection("");
    if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
  }

  async function loadVersions(contentId: string) {
    const rows = await api<Version[]>(`/api/v1/contents/${contentId}/versions`);
    setVersions(rows);
  }

  async function restoreVersion(versionId: string) {
    if (!chapter) return;
    const r = await api<Content>(`/api/v1/contents/${chapter.id}/versions/restore`, { method: "POST", body: JSON.stringify({ version_id: versionId }) });
    setChapter(r); setEditorText(docToText(r.body)); loadVersions(r.id);
  }

  const review = run?.nodes.find(n => n.node_key === "n8")?.output as { score?: number; dimensions?: Record<string, number>; issues?: string[] } | undefined;

  const titles: Record<Tab, string> = { wizard: "灵感到第一章", progress: "Bootstrap 工作流", review: "质量审阅", editor: "章节编辑器", costs: "AI 调用追踪", prompts: "Prompt 管理", dag: "工作流编排", settings: "系统设置", studio: "内容工作室", publish: "发布看板" };
  const [prompts, setPrompts] = useState<any[]>([]);

  useEffect(() => { api<any[]>("/api/v1/admin/prompts").then(setPrompts).catch(() => {}); }, [run?.status]);
  const cmdActions = [
    { id: "wizard", label: "创作向导 → 新建小说", action: () => setTab("wizard") },
    { id: "progress", label: "生成进度 → 查看工作流", action: () => setTab("progress") },
    { id: "editor", label: "编辑器 → 写章节", action: () => setTab("editor") },
    { id: "review", label: "审阅 → 查看审核", action: () => setTab("review") },
    { id: "costs", label: "成本追踪 → AI 调用", action: () => setTab("costs") },
    { id: "prompts", label: "Prompt 管理", action: () => setTab("prompts") },
    { id: "dag", label: "工作流编排 → DAG 编辑器", action: () => setTab("dag") },
    { id: "settings", label: "系统设置 → AI配置/预算", action: () => setTab("settings") },
    { id: "studio", label: "内容工作室 → 短篇/自媒体/热点", action: () => setTab("studio") },
    { id: "publish", label: "发布看板 → 出海/数据", action: () => setTab("publish") },
  ];

  function handleLogin(t: string, email: string) {
    setToken(t); setUserEmail(email);
  }

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
  }

  (window as any).__ncLogout = () => { setToken(""); setUserEmail(""); };

  return (
    <Layout tab={tab} setTab={setTab} title={titles[tab]} runStatus={run?.status}>
      {error && <div className="error">{error}</div>}
      {tab === "wizard" && <Wizard {...{ idea, setIdea, genre, setGenre, style, setStyle, targetWords, setTargetWords, busy, startBootstrap }} />}
      {tab === "progress" && <Progress run={run} onConfirm={confirmTitle} />}
      {tab === "review" && <Review novel={novel} knowledge={knowledge} review={review} />}
      {tab === "editor" && <Editor {...{ chapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion }} />}
      {tab === "costs" && <Costs aiCalls={aiCalls} budgets={budgets} routes={routes} />}
      {tab === "prompts" && (
        <div className="panel"><h2>Prompt 库</h2>
        <table><thead><tr><th>名称</th><th>版本</th><th>模型</th></tr></thead>
        <tbody>{prompts.map((p: any) => <tr key={p.id}><td>{p.name}</td><td>{p.version}</td><td>{p.model}</td></tr>)}</tbody></table>
        </div>
      )}
      {tab === "dag" && <DagEditor />}
      {tab === "settings" && <Settings />}
      {tab === "studio" && <Studio />}
      {tab === "publish" && <PublishDashboard />}
      <CommandPalette commands={cmdActions} />
    </Layout>
  );
}
