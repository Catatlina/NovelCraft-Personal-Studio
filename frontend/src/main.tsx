import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  Check,
  CircleDollarSign,
  FileText,
  GitBranch,
  Loader2,
  Play,
  RotateCcw,
  Save,
  Sparkles,
  Wand2
} from "lucide-react";
import "./styles.css";

const API = "";

type ApiResponse<T> = { code: number | string; message: string; data: T };
type Project = { id: string; name: string; description: string };
type Content = {
  id: string;
  project_id: string;
  parent_id: string | null;
  type: string;
  title: string;
  body: TipTapDoc;
  meta: Record<string, unknown>;
  status: string;
};
type TipTapDoc = { type?: string; content?: Array<{ type: string; text?: string }> };
type NodeStatus = "pending" | "running" | "waiting_human" | "succeeded" | "failed";
type RunNode = {
  node_key: string;
  kind: string;
  agent: string | null;
  title: string;
  status: NodeStatus;
  output: Record<string, unknown>;
};
type Run = {
  id: string;
  project_id: string;
  novel_id: string;
  status: string;
  current_node_key: string | null;
  context: Record<string, unknown>;
  nodes: RunNode[];
};
type AiCall = {
  id: string;
  provider: string;
  model: string;
  prompt_name: string;
  task_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_cny: number;
  latency_ms: number;
  status: string;
  created_at: string;
};
type Knowledge = { id: string; kind: string; title: string; body: string; meta: Record<string, unknown> };
type Version = { id: string; label: string; snapshot: Record<string, unknown>; created_at: string };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string, unknown> };
type Tab = "wizard" | "progress" | "review" | "editor" | "costs";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) throw new Error(await response.text());
  const payload = (await response.json()) as ApiResponse<T>;
  return payload.data;
}

function docToText(doc: TipTapDoc): string {
  return doc.content?.map((item) => item.text ?? "").join("\n\n") ?? "";
}

function textToDoc(text: string): TipTapDoc {
  return {
    type: "doc",
    content: text
      .split(/\n{2,}/)
      .map((part) => part.trim())
      .filter(Boolean)
      .map((textPart) => ({ type: "paragraph", text: textPart }))
  };
}

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [novel, setNovel] = useState<Content | null>(null);
  const [chapter, setChapter] = useState<Content | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [aiCalls, setAiCalls] = useState<AiCall[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [tab, setTab] = useState<Tab>("wizard");
  const [idea, setIdea] = useState("一个写作者发现自己删掉的章节正在现实里发生。");
  const [genre, setGenre] = useState("都市奇幻");
  const [style, setStyle] = useState("克制、悬疑、强画面感");
  const [targetWords, setTargetWords] = useState(800000);
  const [editorText, setEditorText] = useState("");
  const [selection, setSelection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Project[]>("/api/v1/projects").then((projects) => setProject(projects[0] ?? null)).catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!run) return;
    refreshRun(run.id);
    const source = new EventSource(`/api/v1/runs/${run.id}/events`);
    source.addEventListener("node_succeeded", () => refreshRun(run.id));
    source.addEventListener("node_waiting_human", () => refreshRun(run.id));
    source.addEventListener("run_done", () => {
      refreshRun(run.id);
      source.close();
    });
    return () => source.close();
  }, [run?.id]);

  useEffect(() => {
    if (!novel || !project) return;
    api<Content[]>(`/api/v1/contents?project_id=${project.id}&parent_id=${novel.id}`).then((items) => {
      const firstChapter = items.find((item) => item.type === "chapter") ?? null;
      setChapter(firstChapter);
      if (firstChapter) {
        setEditorText(docToText(firstChapter.body));
        loadVersions(firstChapter.id);
      }
    });
    api<Knowledge[]>(`/api/v1/knowledge?project_id=${project.id}&content_id=${novel.id}`).then(setKnowledge);
  }, [novel?.id, run?.status]);

  useEffect(() => {
    if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (!project) return;
    api<Budget[]>(`/api/v1/admin/budgets?project_id=${project.id}`).then(setBudgets);
    api<ModelRoute[]>("/api/v1/model-routes").then(setRoutes);
  }, [project?.id, run?.status]);

  async function refreshRun(runId: string) {
    const nextRun = await api<Run>(`/api/v1/runs/${runId}`);
    setRun(nextRun);
    const nextNovel = await api<Content>(`/api/v1/contents/${nextRun.novel_id}`);
    setNovel(nextNovel);
    if (nextRun.status === "succeeded") setTab("review");
  }

  async function startBootstrap() {
    if (!project) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<Content>(`/api/v1/projects/${project.id}/novels`, {
        method: "POST",
        body: JSON.stringify({ idea, genre, style, target_words: targetWords })
      });
      setNovel(created);
      const started = await api<{ run_id: string }>(`/api/v1/novels/${created.id}/bootstrap`, { method: "POST", body: "{}" });
      const nextRun = await api<Run>(`/api/v1/runs/${started.run_id}`);
      setRun(nextRun);
      setTab("progress");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmTitle(title: string) {
    if (!run) return;
    await api(`/api/v1/runs/${run.id}/nodes/n2/confirm`, {
      method: "POST",
      body: JSON.stringify({ selected_title: title })
    });
    await refreshRun(run.id);
  }

  async function saveChapter() {
    if (!chapter) return;
    const updated = await api<Content>(`/api/v1/contents/${chapter.id}`, {
      method: "PUT",
      body: JSON.stringify({ body: textToDoc(editorText), label: "manual_save" })
    });
    setChapter(updated);
    loadVersions(updated.id);
  }

  async function runEditorOp(op: "polish" | "rewrite" | "continue") {
    if (!chapter || !selection.trim()) return;
    const output = await api<{ text: string }>(`/api/v1/contents/${chapter.id}/ai/${op}`, {
      method: "POST",
      body: JSON.stringify({ selection, instruction: "保持小说当前悬疑风格" })
    });
    setEditorText((current) => current.replace(selection, output.text));
    setSelection("");
    const calls = await api<AiCall[]>(run ? `/api/v1/ai-calls?run_id=${run.id}` : "/api/v1/ai-calls");
    setAiCalls(calls);
  }

  async function loadVersions(contentId: string) {
    const rows = await api<Version[]>(`/api/v1/contents/${contentId}/versions`);
    setVersions(rows);
  }

  async function restoreVersion(versionId: string) {
    if (!chapter) return;
    const restored = await api<Content>(`/api/v1/contents/${chapter.id}/versions/restore`, {
      method: "POST",
      body: JSON.stringify({ version_id: versionId })
    });
    setChapter(restored);
    setEditorText(docToText(restored.body));
    loadVersions(restored.id);
  }

  const totalCost = useMemo(() => aiCalls.reduce((sum, call) => sum + call.cost_cny, 0), [aiCalls]);
  const review = run?.nodes.find((node) => node.node_key === "n8")?.output as
    | { score?: number; dimensions?: Record<string, number>; issues?: string[] }
    | undefined;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">N</div>
          <div>
            <strong>NovelCraft</strong>
            <span>Personal Studio</span>
          </div>
        </div>
        <nav className="nav">
          <TabButton icon={<Sparkles size={18} />} active={tab === "wizard"} label="创作向导" onClick={() => setTab("wizard")} />
          <TabButton icon={<GitBranch size={18} />} active={tab === "progress"} label="生成进度" onClick={() => setTab("progress")} />
          <TabButton icon={<Check size={18} />} active={tab === "review"} label="审阅" onClick={() => setTab("review")} />
          <TabButton icon={<FileText size={18} />} active={tab === "editor"} label="编辑器" onClick={() => setTab("editor")} />
          <TabButton icon={<CircleDollarSign size={18} />} active={tab === "costs"} label="成本追踪" onClick={() => setTab("costs")} />
        </nav>
        <div className="projectBox">
          <span>当前项目</span>
          <strong>{project?.name ?? "加载中"}</strong>
          <small>{novel?.title ?? "尚未创建小说"}</small>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>{project?.description ?? "M1 bootstrap workflow"}</p>
            <h1>{titleFor(tab)}</h1>
          </div>
          <div className={`runPill ${run?.status ?? "idle"}`}>{run?.status ?? "idle"}</div>
        </header>
        {error && <div className="error">{error}</div>}
        {tab === "wizard" && (
          <section className="panel wizard">
            <label>
              灵感
              <textarea value={idea} onChange={(event) => setIdea(event.target.value)} rows={5} />
            </label>
            <div className="formGrid">
              <label>
                题材
                <input value={genre} onChange={(event) => setGenre(event.target.value)} />
              </label>
              <label>
                风格
                <input value={style} onChange={(event) => setStyle(event.target.value)} />
              </label>
              <label>
                目标字数
                <input type="number" value={targetWords} onChange={(event) => setTargetWords(Number(event.target.value))} />
              </label>
            </div>
            <button className="primary" onClick={startBootstrap} disabled={busy || !project}>
              {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              启动 bootstrap
            </button>
          </section>
        )}
        {tab === "progress" && (
          <section className="progressGrid">
            <div className="panel">
              <div className="timeline">
                {(run?.nodes ?? []).map((node) => (
                  <div className={`node ${node.status}`} key={node.node_key}>
                    <span>{node.node_key}</span>
                    <div>
                      <strong>{node.title}</strong>
                      <small>{node.agent ?? node.kind}</small>
                    </div>
                    <em>{node.status}</em>
                  </div>
                ))}
              </div>
            </div>
            <HumanGate run={run} onConfirm={confirmTitle} />
          </section>
        )}
        {tab === "review" && (
          <section className="reviewGrid">
            <div className="panel">
              <h2>{novel?.title ?? "小说审阅"}</h2>
              <p className="synopsis">{String(novel?.meta.synopsis ?? "等待简介生成")}</p>
              <div className="chips">{((novel?.meta.selling_points as string[]) ?? []).map((point) => <span key={point}>{point}</span>)}</div>
              <h3>总纲</h3>
              <ol className="outline">{((novel?.meta.outline as string[]) ?? []).map((item) => <li key={item}>{item}</li>)}</ol>
            </div>
            <div className="panel">
              <h2>人物与世界观</h2>
              <div className="cardList">
                {knowledge.map((item) => (
                  <article key={item.id}>
                    <small>{item.kind}</small>
                    <strong>{item.title}</strong>
                    <p>{item.body}</p>
                  </article>
                ))}
              </div>
            </div>
            <div className="panel">
              <h2>七维审核</h2>
              <div className="score">{review?.score ?? "--"}</div>
              <div className="bars">
                {Object.entries(review?.dimensions ?? {}).map(([name, value]) => (
                  <label key={name}>
                    <span>{name}</span>
                    <meter min={0} max={100} value={value} />
                    <em>{value}</em>
                  </label>
                ))}
              </div>
              <ul className="issues">{(review?.issues ?? []).map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </section>
        )}
        {tab === "editor" && (
          <section className="editorGrid">
            <div className="panel editorPanel">
              <div className="editorHeader">
                <input value={chapter?.title ?? ""} readOnly />
                <button onClick={saveChapter} disabled={!chapter}>
                  <Save size={17} />
                  保存版本
                </button>
              </div>
              <textarea
                value={editorText}
                onChange={(event) => setEditorText(event.target.value)}
                onSelect={(event) => {
                  const target = event.currentTarget;
                  setSelection(target.value.slice(target.selectionStart, target.selectionEnd));
                }}
              />
              <div className="aiBar">
                <button onClick={() => runEditorOp("polish")} disabled={!selection}>
                  <Wand2 size={16} />
                  润色
                </button>
                <button onClick={() => runEditorOp("rewrite")} disabled={!selection}>
                  <Bot size={16} />
                  改写
                </button>
                <button onClick={() => runEditorOp("continue")} disabled={!selection}>
                  <Sparkles size={16} />
                  续写
                </button>
              </div>
            </div>
            <div className="panel versions">
              <h2>版本树</h2>
              {versions.map((version) => (
                <button key={version.id} onClick={() => restoreVersion(version.id)}>
                  <RotateCcw size={15} />
                  <span>{version.label}</span>
                  <small>{new Date(version.created_at).toLocaleString()}</small>
                </button>
              ))}
            </div>
          </section>
        )}
        {tab === "costs" && (
          <section className="costGrid">
            <div className="panel">
              <div className="costHeader">
                <strong>¥{totalCost.toFixed(4)}</strong>
                <span>{aiCalls.length} calls</span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>任务</th>
                    <th>模型</th>
                    <th>Tokens</th>
                    <th>成本</th>
                    <th>延迟</th>
                  </tr>
                </thead>
                <tbody>
                  {aiCalls.map((call) => (
                    <tr key={call.id}>
                      <td>{call.task_type}</td>
                      <td>{call.provider}/{call.model}</td>
                      <td>{call.prompt_tokens + call.completion_tokens}</td>
                      <td>¥{call.cost_cny.toFixed(4)}</td>
                      <td>{call.latency_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="panel routePanel">
              <h2>预算</h2>
              {budgets.map((budget) => (
                <div className="budgetRow" key={budget.id}>
                  <span>{budget.scope}</span>
                  <strong>¥{budget.spent_cny.toFixed(4)} / ¥{budget.limit_cny.toFixed(2)}</strong>
                  <meter min={0} max={budget.limit_cny} value={budget.spent_cny} />
                </div>
              ))}
              <h2>模型路由</h2>
              <div className="routeList">
                {routes.slice(0, 10).map((route) => (
                  <div key={route.id}>
                    <span>{route.task_type}</span>
                    <strong>{route.provider}/{route.model}</strong>
                  </div>
                ))}
              </div>
            </aside>
          </section>
        )}
      </section>
    </main>
  );
}

function TabButton(props: { icon: React.ReactNode; active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={props.active ? "active" : ""} onClick={props.onClick}>
      {props.icon}
      {props.label}
    </button>
  );
}

function HumanGate({ run, onConfirm }: { run: Run | null; onConfirm: (title: string) => void }) {
  const human = run?.nodes.find((node) => node.node_key === "n2");
  const titles = (run?.context.title_candidates as string[] | undefined) ?? [];
  return (
    <div className="panel humanGate">
      <h2>人工确认</h2>
      {human?.status === "waiting_human" ? (
        <div className="titleChoices">
          {titles.map((title) => (
            <button key={title} onClick={() => onConfirm(title)}>
              {title}
            </button>
          ))}
        </div>
      ) : (
        <p>{human?.status === "succeeded" ? "书名已确认，工作流继续执行。" : "等待书名候选生成。"}</p>
      )}
    </div>
  );
}

function titleFor(tab: Tab) {
  return {
    wizard: "灵感到第一章",
    progress: "Bootstrap 工作流",
    review: "质量审阅",
    editor: "章节编辑器",
    costs: "AI 调用追踪"
  }[tab];
}

createRoot(document.getElementById("root")!).render(<App />);
