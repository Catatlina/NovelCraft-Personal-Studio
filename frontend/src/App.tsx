import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  Globe2,
  Layers,
  Library,
  Loader2,
  LogOut,
  PlugZap,
  RefreshCw,
  Rocket,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Upload,
  Workflow,
  XCircle,
} from "lucide-react";
import { LoginPage } from "./components/LoginPage";
import { ApiError, api as rawApi } from "./lib/api";
import "./styles/proto.css";

type ApiEnvelope<T> = { code: number | string; message: string; data: T };
type Project = { id: string; name: string; description?: string };
type Book = { id: string; title: string; genre?: string; synopsis?: string; chapter_count?: number; total_words?: number; status?: string; updated_at?: string; meta?: Record<string, unknown> };
type Content = { id: string; project_id: string; parent_id?: string | null; type: string; title: string; body?: any; meta?: Record<string, unknown>; status?: string; updated_at?: string };
type Snapshot = { id: string; source_key?: string; display_name?: string; status?: string; capture_status?: string; item_count?: number; error?: string };
type Topic = { id: string; title: string; premise?: string; genre?: string; market_score?: number; status?: string };
type Run = { id: string; project_id: string; novel_id: string; status: string; current_node_key?: string | null; nodes?: Array<{ node_key: string; title?: string; status: string; output?: any }> };
type AiCall = { id: string; provider: string; model: string; task_type: string; cost_cny?: number; status?: string; created_at?: string };
type OpenApiOperation = { method: string; path: string; tag: string; summary: string; operation: any };
type Toast = { kind: "ok" | "error" | "info"; text: string };
type ConnectionField = { key: string; label: string; type: string; required?: boolean };
type ConnectionSpec = { category: string; display_name: string; help?: string; fields: ConnectionField[] };
type ConnectionItem = { id: string; platform: string; account_name: string; display_name?: string; category?: string; configured_fields?: string[]; missing_required?: string[]; updated_at?: string };

type Tab =
  | "dashboard"
  | "create"
  | "ranking"
  | "library"
  | "editor"
  | "hotspot"
  | "publish"
  | "knowledge"
  | "settings"
  | "api";

const tabs: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
  { id: "dashboard", label: "真实工作台", icon: <Gauge size={17} /> },
  { id: "create", label: "创作主链", icon: <Rocket size={17} /> },
  { id: "ranking", label: "扫榜书库", icon: <BarChart3 size={17} /> },
  { id: "library", label: "书库编辑", icon: <Library size={17} /> },
  { id: "editor", label: "编辑审阅", icon: <FileText size={17} /> },
  { id: "hotspot", label: "热点内容", icon: <Activity size={17} /> },
  { id: "publish", label: "发布回流", icon: <Send size={17} /> },
  { id: "knowledge", label: "知识协作", icon: <Database size={17} /> },
  { id: "settings", label: "配置运维", icon: <Settings size={17} /> },
  { id: "api", label: "全量接口", icon: <TerminalSquare size={17} /> },
];

function unwrap<T>(value: any): T {
  if (value && typeof value === "object" && "data" in value && "code" in value) return value.data as T;
  return value as T;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return unwrap<T>(await rawApi<ApiEnvelope<T> | T>(path, init));
}

function errorText(caught: unknown) {
  if (caught instanceof ApiError) {
    const payload = caught.payload as any;
    const detail = payload?.detail || payload?.message || payload?.error;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(item => item?.msg || JSON.stringify(item)).join("；");
    if (detail && typeof detail === "object") return JSON.stringify(detail);
    return `HTTP ${caught.status}`;
  }
  return caught instanceof Error ? caught.message : String(caught);
}

function textFromDoc(doc: any): string {
  if (!doc) return "";
  if (typeof doc === "string") return doc;
  if (Array.isArray(doc.content)) {
    return doc.content.map((node: any) => {
      if (node.text) return node.text;
      if (Array.isArray(node.content)) return node.content.map((child: any) => child.text || "").join("");
      return "";
    }).filter(Boolean).join("\n\n");
  }
  return "";
}

function docFromText(text: string) {
  return {
    type: "doc",
    content: text.split(/\n{2,}/).map(part => part.trim()).filter(Boolean).map(text => ({
      type: "paragraph",
      content: [{ type: "text", text }],
    })),
  };
}

function formatJson(value: unknown) {
  try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}

function badge(status?: string) {
  if (!status) return "badge gray";
  if (["ok", "ready", "succeeded", "published", "active", "completed", "接口可访问"].includes(status)) return "badge green";
  if (["failed", "error"].includes(status)) return "badge red";
  if (["running", "pending", "generating", "blocked", "缺上下文"].includes(status)) return "badge orange";
  return "badge gray";
}

function displayStatus(status?: string) {
  if (!status) return "unknown";
  const map: Record<string, string> = {
    ok: "正常",
    ready: "就绪",
    succeeded: "成功",
    completed: "完成",
    active: "启用",
    configured: "已配置",
    failed: "失败",
    error: "错误",
    pending: "等待中",
    running: "运行中",
    partial: "部分成功",
  };
  return map[status] || status;
}

function readCsv(text: string) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  const headers = (lines.shift() || "").split(",").map(item => item.trim());
  return lines.map(line => {
    const cols = line.split(",").map(item => item.trim());
    const row: Record<string, string> = {};
    headers.forEach((header, index) => { row[header] = cols[index] || ""; });
    return row;
  });
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("nc_token") || "");
  const [userEmail, setUserEmail] = useState("");
  const [tab, setTab] = useState<Tab>("dashboard");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [health, setHealth] = useState<any>({});
  const [stats, setStats] = useState<any>({});
  const [books, setBooks] = useState<Book[]>([]);
  const [contents, setContents] = useState<Content[]>([]);
  const [currentBook, setCurrentBook] = useState<Book | null>(null);
  const [currentContent, setCurrentContent] = useState<Content | null>(null);
  const [editorText, setEditorText] = useState("");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [aiCalls, setAiCalls] = useState<AiCall[]>([]);
  const [openapi, setOpenapi] = useState<OpenApiOperation[]>([]);
  const [operationFilter, setOperationFilter] = useState("");
  const [logs, setLogs] = useState<Array<{ at: string; text: string }>>([]);
  const lastRunTimer = useRef<number | null>(null);

  function notify(kind: Toast["kind"], text: string) {
    setToast({ kind, text });
    setLogs(items => [{ at: new Date().toLocaleTimeString(), text }, ...items].slice(0, 80));
  }

  async function loadOpenApi() {
    const response = await fetch("/openapi.json", { credentials: "include" });
    const schema = await response.json();
    const ops: OpenApiOperation[] = [];
    Object.entries<any>(schema.paths || {}).forEach(([path, methods]) => {
      Object.entries<any>(methods).forEach(([method, operation]) => {
        if (!["get", "post", "put", "delete", "patch"].includes(method)) return;
        ops.push({
          method: method.toUpperCase(),
          path,
          tag: operation.tags?.[0] || "main",
          summary: operation.summary || operation.operationId || "",
          operation,
        });
      });
    });
    setOpenapi(ops.sort((a, b) => `${a.tag}${a.path}`.localeCompare(`${b.tag}${b.path}`)));
  }

  async function refreshCore() {
    if (!token) return;
    setBusy(true);
    try {
      const [healthRows, projectRows, statRows, callRows] = await Promise.all([
        api<any>("/api/v1/healthz").catch(() => ({})),
        api<Project[]>("/api/v1/projects"),
        api<any>("/api/v1/stats/overview").catch(() => ({})),
        api<AiCall[]>("/api/v1/ai-calls").catch(() => []),
      ]);
      setHealth(healthRows || {});
      setProjects(projectRows || []);
      setStats(statRows || {});
      setAiCalls(Array.isArray(callRows) ? callRows : []);
      const selected = projectId || projectRows?.[0]?.id || "";
      if (selected && selected !== projectId) setProjectId(selected);
      if (selected) await refreshProject(selected);
    } catch (caught) {
      notify("error", errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function refreshProject(pid = projectId) {
    if (!pid) return;
    const [bookRows, snapshotRows, topicRows] = await Promise.all([
      api<Book[]>(`/api/v1/ranking/library/books?project_id=${encodeURIComponent(pid)}&limit=100`).catch(() => []),
      api<Snapshot[]>(`/api/v1/ranking/snapshots?project_id=${encodeURIComponent(pid)}`).catch(() => []),
      api<Topic[]>(`/api/v1/ranking/topics?project_id=${encodeURIComponent(pid)}`).catch(() => []),
    ]);
    setBooks(bookRows || []);
    setSnapshots(snapshotRows || []);
    setTopics(topicRows || []);
  }

  async function loadBook(bookId: string) {
    const detail = await api<any>(`/api/v1/ranking/library/books/${bookId}`);
    setCurrentBook(detail.book || detail);
    const chapterRows: Content[] = Array.isArray(detail.chapters) ? detail.chapters : [];
    setContents(chapterRows);
    const latest = detail.latest_chapter || chapterRows[0] || null;
    setCurrentContent(latest);
    setEditorText(textFromDoc(latest?.body));
    setTab("editor");
  }

  async function loadLatestRun(pid = projectId) {
    if (!pid) return;
    try {
      const latest = await api<Run>(`/api/v1/runs/latest?project_id=${encodeURIComponent(pid)}`);
      setRun(latest);
      return latest;
    } catch {
      setRun(null);
      return null;
    }
  }

  useEffect(() => {
    if (!token) return;
    void loadOpenApi();
    void refreshCore();
    return () => {
      if (lastRunTimer.current) window.clearInterval(lastRunTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!projectId) return;
    void refreshProject(projectId);
    void loadLatestRun(projectId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function handleLogin(nextToken: string, email: string) {
    setToken(nextToken);
    setUserEmail(email);
  }

  async function logout() {
    await rawApi("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    sessionStorage.clear();
    setToken("");
  }

  if (!token) return <LoginPage onLogin={handleLogin} />;

  const selectedProject = projects.find(item => item.id === projectId) || projects[0] || null;
  const filteredOps = openapi.filter(op => {
    const q = operationFilter.trim().toLowerCase();
    return !q || [op.method, op.path, op.tag, op.summary].join(" ").toLowerCase().includes(q);
  });

  return (
    <div style={{ height: "100vh", position: "relative", overflow: "hidden" }}>
      <div className="bg-ambient" /><div className="bg-grid" />
      <div className="app-shell" style={{ display: "flex" }}>
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-icon"><Sparkles size={18} /></div>
            <span className="brand-text">NovelCraft</span>
          </div>
          <div className="nav-group">
            <div className="nav-group-title">全新真实前端</div>
            {tabs.map(item => (
              <button key={item.id} className={`nav-item${tab === item.id ? " active" : ""}`} onClick={() => setTab(item.id)}>
                {item.icon}<span className="nav-label">{item.label}</span>
              </button>
            ))}
          </div>
          <div className="sidebar-bottom">
            <button className="nav-item" onClick={() => void refreshCore()}><RefreshCw size={17} /><span className="label">刷新接口</span></button>
            <button className="nav-item" onClick={() => void logout()}><LogOut size={17} /><span className="label">退出</span></button>
          </div>
        </aside>
        <main className="app-main">
          <header className="topbar">
            <div className="search-box"><Search size={16} /><input placeholder="搜索接口、页面或操作…" value={operationFilter} onChange={event => setOperationFilter(event.target.value)} onFocus={() => setTab("api")} /></div>
            <select className="form-input" style={{ width: 260 }} value={projectId} onChange={event => setProjectId(event.target.value)}>
              {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <div className="topbar-right">
              <span className={badge(health.status || "ok")}>{health.status || "unknown"}</span>
              <div className="avatar">{(userEmail || "U").slice(0, 1).toUpperCase()}</div>
            </div>
          </header>
          <div className="content">
            {toast && <div className={toast.kind === "error" ? "error" : "card"} style={{ marginBottom: 12, padding: 12 }}>{toast.text}</div>}
            {tab === "dashboard" && <DashboardView {...{ selectedProject, stats, health, books, snapshots, topics, aiCalls, openapi, setTab, refreshCore, busy }} />}
            {tab === "create" && <CreateView project={selectedProject} notify={notify} setTab={setTab} refreshCore={refreshCore} setRun={setRun} />}
            {tab === "ranking" && <RankingView project={selectedProject} snapshots={snapshots} topics={topics} notify={notify} refreshProject={refreshProject} setRun={setRun} loadBook={loadBook} />}
            {tab === "library" && <LibraryView project={selectedProject} books={books} loadBook={loadBook} refreshProject={refreshProject} notify={notify} />}
            {tab === "editor" && <EditorView currentBook={currentBook} contents={contents} currentContent={currentContent} setCurrentContent={setCurrentContent} editorText={editorText} setEditorText={setEditorText} notify={notify} refreshCore={refreshCore} />}
            {tab === "hotspot" && <HotspotView project={selectedProject} notify={notify} />}
            {tab === "publish" && <PublishView project={selectedProject} currentContent={currentContent} books={books} notify={notify} />}
            {tab === "knowledge" && <KnowledgeView project={selectedProject} notify={notify} />}
            {tab === "settings" && <SettingsView project={selectedProject} notify={notify} />}
            {tab === "api" && <ApiExplorer operations={filteredOps} project={selectedProject} currentBook={currentBook} currentContent={currentContent} notify={notify} />}
            <LogPanel logs={logs} run={run} loadLatestRun={() => void loadLatestRun()} />
          </div>
        </main>
      </div>
    </div>
  );
}

function DashboardView({ selectedProject, stats, health, books, snapshots, topics, aiCalls, openapi, setTab, refreshCore, busy }: {
  selectedProject: Project | null;
  stats: any;
  health: any;
  books: Book[];
  snapshots: Snapshot[];
  topics: Topic[];
  aiCalls: AiCall[];
  openapi: OpenApiOperation[];
  setTab: (tab: Tab) => void;
  refreshCore: () => void;
  busy: boolean;
}) {
  return (
    <section>
      <div className="breadcrumb"><b>NovelCraft</b> › 新前端</div>
      <div className="page-head">
        <div>
          <h1>NovelCraft Real Studio</h1>
          <p>这是重写后的前端入口：数据来自后端接口，缺上下文就显示阻断，不再展示原型假数据。</p>
        </div>
        <button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={refreshCore} disabled={busy}><RefreshCw size={14} /> {busy ? "刷新中…" : "刷新全局数据"}</button>
      </div>
      <div className="grid grid-4">
        <Stat label="后端接口" value={openapi.length} hint="OpenAPI operations" icon={<PlugZap size={18} />} />
        <Stat label="当前项目" value={selectedProject ? "1" : "0"} hint={selectedProject?.name || "未选择"} icon={<Layers size={18} />} />
        <Stat label="书库作品" value={books.length} hint="来自 /ranking/library/books" icon={<BookOpen size={18} />} />
        <Stat label="AI 调用" value={aiCalls.length} hint={health.ai_provider || stats.ai_calls ? "真实调用记录" : "暂无记录"} icon={<Sparkles size={18} />} />
      </div>
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <ActionCard title="扫榜 → 分析 → 建书" desc={`${snapshots.length} 个快照，${topics.length} 个选题`} icon={<BarChart3 />} onClick={() => setTab("ranking")} />
        <ActionCard title="书库 → 编辑 → 审阅" desc={`${books.length} 本作品，可打开真实章节`} icon={<Library />} onClick={() => setTab("library")} />
        <ActionCard title="全量接口控制台" desc="所有后端 OpenAPI 路由都能检索和调用" icon={<TerminalSquare />} onClick={() => setTab("api")} />
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head"><div className="card-title"><ShieldCheck size={16} /> 系统状态</div></div>
        <table><tbody>
          <tr><th>API</th><td>{health.status || "unknown"}</td></tr>
          <tr><th>数据库</th><td>{health.database || "unknown"}</td></tr>
          <tr><th>Redis / Worker</th><td>{health.redis || "unknown"} / {health.worker || "unknown"}</td></tr>
          <tr><th>Provider</th><td>{health.ai_provider || (health.ai_key_configured ? "已配置" : "未确认")}</td></tr>
        </tbody></table>
      </div>
    </section>
  );
}

function Stat({ label, value, hint, icon }: { label: string; value: React.ReactNode; hint: string; icon: React.ReactNode }) {
  return <div className="stat"><div className="stat-top"><span className="stat-label">{label}</span><span className="stat-ic ic-purple">{icon}</span></div><div className="stat-val">{value}</div><div className="stat-trend">{hint}</div></div>;
}

function ActionCard({ title, desc, icon, onClick }: { title: string; desc: string; icon: React.ReactNode; onClick: () => void }) {
  return <button className="qcard" style={{ textAlign: "left" }} onClick={onClick}><div className="qic">{icon}</div><h4>{title}</h4><p>{desc}</p></button>;
}

function CreateView({ project, notify, setTab, refreshCore, setRun }: {
  project: Project | null; notify: (kind: Toast["kind"], text: string) => void; setTab: (tab: Tab) => void; refreshCore: () => Promise<void>; setRun: (run: Run | null) => void;
}) {
  const [projectName, setProjectName] = useState("NovelCraft 创作项目");
  const [idea, setIdea] = useState("一个写作者发现自己删掉的章节正在现实里发生。");
  const [genre, setGenre] = useState("都市奇幻");
  const [style, setStyle] = useState("克制、悬疑、强画面感");
  const [targetWords, setTargetWords] = useState(800000);
  const [busy, setBusy] = useState(false);

  async function createProject() {
    setBusy(true);
    try {
      await api<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify({ name: projectName, description: "由重写前端创建" }) });
      notify("ok", "项目已创建");
      await refreshCore();
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }

  async function createNovelAndBootstrap() {
    if (!project) return notify("error", "请先创建或选择项目");
    setBusy(true);
    try {
      const novel = await api<Content>(`/api/v1/projects/${project.id}/novels`, { method: "POST", body: JSON.stringify({ idea, genre, style, target_words: targetWords }) });
      const boot = await api<{ run_id: string }>(`/api/v1/novels/${novel.id}/bootstrap`, { method: "POST", body: JSON.stringify({ auto_confirm_title: false }) });
      const run = await api<Run>(`/api/v1/runs/${boot.run_id}`);
      setRun(run);
      notify("ok", "作品已创建，Bootstrap 工作流已启动");
      setTab("library");
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }

  return (
    <section>
      <div className="page-head"><div><h1>创作主链</h1><p>项目、作品、Bootstrap 工作流都走真实接口。</p></div></div>
      <div className="grid grid-2">
        <div className="card"><div className="card-head"><div className="card-title"><Layers size={16} /> 项目</div></div>
          <label className="form-label">项目名称</label><input className="form-input" value={projectName} onChange={e => setProjectName(e.target.value)} />
          <button className="btn-sm btn-primary" style={{ width: "auto", marginTop: 12 }} onClick={createProject} disabled={busy}>创建项目</button>
          <p className="cell-sub" style={{ marginTop: 10 }}>当前：{project?.name || "暂无项目"}</p>
        </div>
        <div className="card"><div className="card-head"><div className="card-title"><Rocket size={16} /> 创建作品并生成策划+首章</div></div>
          <label className="form-label">创意</label><textarea className="form-input" rows={5} value={idea} onChange={e => setIdea(e.target.value)} />
          <div className="grid grid-3" style={{ marginTop: 10 }}>
            <input className="form-input" value={genre} onChange={e => setGenre(e.target.value)} />
            <input className="form-input" value={style} onChange={e => setStyle(e.target.value)} />
            <input className="form-input" type="number" value={targetWords} onChange={e => setTargetWords(Number(e.target.value || 0))} />
          </div>
          <button className="btn-sm btn-primary" style={{ width: "auto", marginTop: 12 }} onClick={createNovelAndBootstrap} disabled={busy || !project}>创建作品并生成策划+首章</button>
        </div>
      </div>
    </section>
  );
}

function RankingView({ project, snapshots, topics, notify, refreshProject, setRun, loadBook }: {
  project: Project | null; snapshots: Snapshot[]; topics: Topic[]; notify: (kind: Toast["kind"], text: string) => void; refreshProject: (id?: string) => Promise<void>; setRun: (run: Run | null) => void; loadBook: (bookId: string) => Promise<void>;
}) {
  const [selectedSnapshot, setSelectedSnapshot] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const snapshotId = selectedSnapshot || snapshots[0]?.id || "";

  async function importCsv(file: File | null) {
    if (!project || !file) return;
    setBusy(true);
    try {
      const rows = readCsv(await file.text());
      await api(`/api/v1/ranking/import?project_id=${encodeURIComponent(project.id)}`, {
        method: "POST",
        body: JSON.stringify({
          source_key: "manual",
          source_label: "manual",
          items: rows.map((row, index) => ({
            rank: Number(row.rank || index + 1),
            title: row.title,
            author: row.author || "",
            category: row.category || "",
            confidence: 1,
            evidence: { source_label: "manual" },
          })),
          metadata_validation: { source: "frontend_csv" },
        }),
      });
      notify("ok", "榜单已导入");
      await refreshProject(project.id);
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }

  async function analyze() {
    if (!snapshotId) return notify("error", "请先导入或选择榜单快照");
    setBusy(true);
    try {
      await api(`/api/v1/ranking/snapshots/${snapshotId}/analyze`, { method: "POST" });
      notify("ok", "分析完成，选题已生成");
      if (project) await refreshProject(project.id);
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }

  async function generateBook(topic: Topic) {
    setBusy(true);
    try {
      const result = await api<{ novel_id: string; run_id?: string }>(`/api/v1/ranking/topics/${topic.id}/generate-book`, { method: "POST", body: JSON.stringify({ auto_start: true, target_words: 800000, style: "商业网文、节奏紧凑、人物驱动" }) });
      if (result.run_id) setRun(await api<Run>(`/api/v1/runs/${result.run_id}`));
      notify("ok", "作品已入库");
      if (project) await refreshProject(project.id);
      await loadBook(result.novel_id);
      if (project) await refreshProject(project.id);
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }

  return (
    <section>
      <div className="page-head"><div><h1>扫榜书库</h1><p>导入榜单、真实 AI 分析、生成原创选题并入库。</p></div><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={analyze} disabled={busy || !snapshotId}>生成分析与选题</button></div>
      <div className="card" style={{ marginBottom: 16 }}>
        <label className="form-label" htmlFor="ranking-csv">选择榜单 CSV</label>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input id="ranking-csv" className="form-input" type="file" accept=".csv,text/csv" onChange={e => setCsvFile(e.target.files?.[0] || null)} disabled={busy || !project} />
          <button className="btn-sm btn-primary" style={{ width: "auto", whiteSpace: "nowrap" }} onClick={() => void importCsv(csvFile)} disabled={busy || !project || !csvFile}>导入榜单</button>
        </div>
        <p className="cell-sub" style={{ marginTop: 8 }}>{csvFile ? `已选择：${csvFile.name}` : "请上传 CSV；导入后快照会写入后端数据库。"}</p>
      </div>
      <div className="grid grid-2">
        <div className="card"><div className="card-head"><div className="card-title"><Upload size={16} /> 快照</div></div>
          <table><thead><tr><th>来源</th><th>状态</th><th>数量</th></tr></thead><tbody>{snapshots.map(s => { const status = s.status || s.capture_status; return <tr key={s.id} onClick={() => setSelectedSnapshot(s.id)}><td>{s.display_name || s.source_key || "manual"}</td><td><span className={badge(status)}>{displayStatus(status)}</span></td><td>{s.item_count || 0}</td></tr>; })}</tbody></table>
        </div>
        <div className="card"><div className="card-head"><div className="card-title"><Sparkles size={16} /> 选题</div></div>
          {topics.length ? topics.map(topic => <div className="ticket" key={topic.id}><h5>{topic.title}</h5><p className="cell-sub">{topic.premise}</p><div className="meta"><span>{topic.genre}</span><button className="btn-sm btn-ghost" onClick={() => void generateBook(topic)}>创建作品并生成策划+首章</button></div></div>) : <div className="empty"><p>暂无选题。请先扫描榜单并生成分析。</p></div>}
        </div>
      </div>
    </section>
  );
}

function LibraryView({ project, books, loadBook, refreshProject, notify }: {
  project: Project | null; books: Book[]; loadBook: (bookId: string) => Promise<void>; refreshProject: (id?: string) => Promise<void>; notify: (kind: Toast["kind"], text: string) => void;
}) {
  return <section><div className="page-head"><div><h1>书库编辑</h1><p>读取真实书库，打开作品进入章节编辑。</p></div><button className="btn-sm btn-ghost" onClick={() => project && refreshProject(project.id)}>刷新书库</button></div>
    <div className="grid grid-3">{books.map(book => <div className="book book-row" key={book.id}><div className="book-cover">{(book.title || "书").slice(0, 1)}</div><div className="book-info"><h4>{book.title}</h4><p>{book.genre || "未分类"} · {book.chapter_count || 0} 章 · {book.total_words || 0} 字</p><button className="btn-sm btn-primary" style={{ width: "auto", marginTop: 8 }} onClick={() => loadBook(book.id).catch(caught => notify("error", errorText(caught)))}>查看详情</button></div></div>)}</div>
    {!books.length && <div className="empty"><h3>书库为空</h3><p>请从创作主链新建，或从扫榜选题生成作品。</p></div>}
  </section>;
}

function EditorView({ currentBook, contents, currentContent, setCurrentContent, editorText, setEditorText, notify, refreshCore }: {
  currentBook: Book | null; contents: Content[]; currentContent: Content | null; setCurrentContent: (content: Content | null) => void; editorText: string; setEditorText: (text: string) => void; notify: (kind: Toast["kind"], text: string) => void; refreshCore: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  async function save() {
    if (!currentContent) return notify("error", "请先打开章节");
    setBusy(true);
    try {
      const updated = await api<Content>(`/api/v1/contents/${currentContent.id}`, { method: "PUT", body: JSON.stringify({ body: docFromText(editorText), label: "frontend_rewrite_save", base_updated_at: currentContent.updated_at }) });
      setCurrentContent(updated); notify("ok", "章节已保存"); await refreshCore();
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }
  async function aiOp(op: string) {
    if (!currentContent) return notify("error", "请先打开章节");
    setBusy(true);
    try {
      const result = await api<{ text: string }>(`/api/v1/contents/${currentContent.id}/ai/${op}`, { method: "POST", body: JSON.stringify({ selection: editorText || currentContent.title, instruction: "保持原始剧情，提升可读性" }) });
      setEditorText(result.text || editorText); notify("ok", `AI ${op} 完成`);
    } catch (caught) { notify("error", errorText(caught)); } finally { setBusy(false); }
  }
  return <section><div className="page-head"><div><h1>编辑审阅</h1><p>{currentBook?.title || "未打开作品"}</p></div><div className="head-actions"><button className="btn-sm btn-ghost" onClick={() => void aiOp("polish")} disabled={busy || !currentContent}>AI 润色</button><button className="btn-sm btn-ghost" onClick={() => void aiOp("deai")} disabled={busy || !currentContent}>去 AI 味</button><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={save} disabled={busy || !currentContent}>保存</button></div></div>
    <div className="layout-2"><div className="card"><textarea className="form-input" rows={22} value={editorText} onChange={e => setEditorText(e.target.value)} placeholder="打开章节后在这里编辑正文" /></div><div className="card"><div className="card-head"><div className="card-title"><BookOpen size={16} /> 章节</div></div>{contents.map(content => <button key={content.id} className={`nav-item${content.id === currentContent?.id ? " active" : ""}`} onClick={() => { setCurrentContent(content); setEditorText(textFromDoc(content.body)); }}>{content.title}</button>)}{!contents.length && <div className="empty"><h3>暂无章节</h3><p>请先生成或导入章节。</p></div>}</div></div>
  </section>;
}

function HotspotView({ project, notify }: { project: Project | null; notify: (kind: Toast["kind"], text: string) => void }) {
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [articles, setArticles] = useState<any[]>([]);
  async function load() {
    try {
      const [h, a] = await Promise.all([api<any[]>("/api/v1/hotspots"), api<any[]>("/api/v1/articles").catch(() => [])]);
      setHotspots(Array.isArray(h) ? h : (h as any)?.items || []);
      setArticles(Array.isArray(a) ? a : (a as any)?.items || []);
      notify("ok", "热点数据已刷新");
    } catch (caught) { notify("error", errorText(caught)); }
  }
  useEffect(() => { void load(); }, []);
  return <section><div className="page-head"><div><h1>热点内容</h1><p>热点、文章库和生成入口都连真实后端。</p></div><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={load}>刷新热点</button></div><div className="grid grid-2"><ListCard title="热点" rows={hotspots.slice(0, 20)} /><ListCard title="文章" rows={articles.slice(0, 20)} /></div></section>;
}

function PublishView({ project, currentContent, books, notify }: { project: Project | null; currentContent: Content | null; books: Book[]; notify: (kind: Toast["kind"], text: string) => void }) {
  const [records, setRecords] = useState<any[]>([]);
  const [url, setUrl] = useState("");
  async function load() { setRecords(await api<any[]>("/api/v1/publish/records").catch(() => [])); }
  async function receipt() {
    const contentId = currentContent?.id || books[0]?.id || "";
    if (!contentId) return notify("error", "请先打开作品或章节");
    try { await api("/api/v1/publish-receipts", { method: "POST", body: JSON.stringify({ content_id: contentId, platform: "manual", status: "published", url, metrics: {} }) }); notify("ok", "发布回执已记录"); await load(); } catch (caught) { notify("error", errorText(caught)); }
  }
  useEffect(() => { void load(); }, []);
  return <section><div className="page-head"><div><h1>发布回流</h1><p>发布记录、人工回执、ROI 数据回流。</p></div><button className="btn-sm btn-ghost" onClick={load}>刷新记录</button></div><div className="grid grid-2"><div className="card"><label className="form-label">发布 URL / 回执链接</label><input className="form-input" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." /><button className="btn-sm btn-primary" style={{ width: "auto", marginTop: 10 }} onClick={receipt}>记录人工发布回执</button></div><ListCard title="发布记录" rows={records} /></div></section>;
}

function KnowledgeView({ project, notify }: { project: Project | null; notify: (kind: Toast["kind"], text: string) => void }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  async function load() { if (!project) return; setRows(await api<any[]>(`/api/v1/knowledge?project_id=${project.id}`).catch(() => [])); }
  async function searchKnowledge() {
    if (!project) return notify("error", "请先选择项目");
    try { setRows(await api<any[]>("/api/v1/knowledge/search", { method: "POST", body: JSON.stringify({ project_id: project.id, query, limit: 20 }) })); } catch (caught) { notify("error", errorText(caught)); }
  }
  useEffect(() => { void load(); }, [project?.id]);
  return <section><div className="page-head"><div><h1>知识协作</h1><p>知识库检索、协作成员、日志都在全量接口中可操作。</p></div></div><div className="card"><div style={{ display: "flex", gap: 8 }}><input className="form-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索知识库..." /><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={searchKnowledge}>搜索</button></div></div><ListCard title="知识结果" rows={rows} /></section>;
}

function SettingsView({ project, notify }: { project: Project | null; notify: (kind: Toast["kind"], text: string) => void }) {
  const [providers, setProviders] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [specs, setSpecs] = useState<Record<string, ConnectionSpec>>({});
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [platform, setPlatform] = useState("wordpress");
  const [accountName, setAccountName] = useState("default");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  async function load() {
    const [p, r, b, specRows, c] = await Promise.all([
      api<any[]>("/api/v1/admin/providers").catch(() => []),
      api<any[]>("/api/v1/admin/model-routes").catch(() => []),
      api<any[]>("/api/v1/admin/budgets").catch(() => []),
      api<Record<string, ConnectionSpec>>("/api/v1/platform-connections/specs").catch(() => ({})),
      api<ConnectionItem[]>("/api/v1/platform-connections").catch(() => []),
    ]);
    const nextSpecs: Record<string, ConnectionSpec> = specRows || {};
    setProviders(p || []); setRoutes(r || []); setBudgets(b || []); setSpecs(nextSpecs); setConnections(c || []);
    if (!nextSpecs[platform]) setPlatform(nextSpecs.wordpress ? "wordpress" : Object.keys(nextSpecs)[0] || "");
  }
  async function saveConnection() {
    if (!platform) return notify("error", "请选择平台");
    try {
      await api("/api/v1/platform-connections", {
        method: "POST",
        body: JSON.stringify({ platform, account_name: accountName || "default", credentials }),
      });
      setCredentials({});
      notify("ok", "平台连接已保存");
      await load();
    } catch (caught) { notify("error", errorText(caught)); }
  }
  useEffect(() => { void load(); }, []);
  const platformOptions = Object.entries(specs)
    .filter(([, spec]) => spec.category === "publish")
    .concat(Object.entries(specs).filter(([, spec]) => spec.category !== "publish"));
  const activeSpec = specs[platform];
  return <section>
    <div className="page-head"><div><h1>配置运维</h1><p>Provider、模型路由、预算、平台连接。</p></div><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={() => load().then(() => notify("ok", "配置已刷新"))}>刷新配置</button></div>
    <div className="grid grid-2">
      <div className="card">
        <div className="card-head"><h2 className="card-title">平台连接</h2><span className="badge gray">{connections.length}</span></div>
        <div className="grid grid-2">
          <div>
            <label className="form-label" htmlFor="connection-platform">平台</label>
            <select id="connection-platform" className="form-input" value={platform} onChange={e => { setPlatform(e.target.value); setCredentials({}); }}>
              {platformOptions.map(([key, spec]) => <option key={key} value={key}>{spec.display_name || key}</option>)}
            </select>
          </div>
          <div>
            <label className="form-label" htmlFor="connection-account">账号/连接名</label>
            <input id="connection-account" className="form-input" value={accountName} onChange={e => setAccountName(e.target.value)} />
          </div>
        </div>
        {activeSpec?.help && <p className="cell-sub" style={{ marginTop: 10 }}>{activeSpec.help}</p>}
        <div className="grid grid-3" style={{ marginTop: 10 }}>
          {(activeSpec?.fields || []).map(field => (
            <div key={field.key}>
              <label className="form-label" htmlFor={`connection-${field.key}`}>{field.label}{field.required ? " *" : ""}</label>
              <input
                id={`connection-${field.key}`}
                className="form-input"
                type={field.type === "secret" ? "password" : field.type === "url" ? "url" : "text"}
                value={credentials[field.key] || ""}
                onChange={e => setCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <button className="btn-sm btn-primary" style={{ width: "auto", marginTop: 12 }} onClick={saveConnection}>保存连接</button>
        <table style={{ marginTop: 14 }}>
          <thead><tr><th>平台</th><th>账号</th><th>状态</th><th>字段</th></tr></thead>
          <tbody>{connections.map(row => {
            const configured = !row.missing_required?.length;
            return <tr key={row.id}><td>{row.display_name || specs[row.platform]?.display_name || row.platform}</td><td>{row.account_name}</td><td><span className={badge(configured ? "configured" : "pending")}>{configured ? "已配置" : "缺字段"}</span></td><td>{row.configured_fields?.join(", ") || "—"}</td></tr>;
          })}</tbody>
        </table>
      </div>
      <ListCard title="Provider" rows={providers} />
      <ListCard title="模型路由" rows={routes} />
      <ListCard title="预算" rows={budgets} />
    </div>
  </section>;
}

function ListCard({ title, rows }: { title: string; rows: any[] }) {
  return <div className="card" style={{ marginTop: 16 }}><div className="card-head"><h2 className="card-title">{title}</h2><span className="badge gray">{rows.length}</span></div>{rows.length ? <pre className="outline-block" style={{ maxHeight: 360, overflow: "auto" }}>{formatJson(rows.slice(0, 30))}</pre> : <div className="empty"><p>暂无数据</p></div>}</div>;
}

function ApiExplorer({ operations, project, currentBook, currentContent, notify }: {
  operations: OpenApiOperation[]; project: Project | null; currentBook: Book | null; currentContent: Content | null; notify: (kind: Toast["kind"], text: string) => void;
}) {
  const tags = Array.from(new Set(operations.map(op => op.tag))).sort();
  const [tag, setTag] = useState("");
  const visible = tag ? operations.filter(op => op.tag === tag) : operations;
  return <section><div className="page-head"><div><h1>全量接口</h1><p>后端 OpenAPI 当前装载 {operations.length} 个操作。GET 可直接调用；写接口需填写参数/JSON。</p></div><select className="form-input" style={{ width: 220 }} value={tag} onChange={e => setTag(e.target.value)}><option value="">全部标签</option>{tags.map(tag => <option key={tag}>{tag}</option>)}</select></div><div className="grid" style={{ gap: 10 }}>{visible.map(op => <OperationCard key={`${op.method}-${op.path}`} op={op} project={project} currentBook={currentBook} currentContent={currentContent} notify={notify} />)}</div></section>;
}

function OperationCard({ op, project, currentBook, currentContent, notify }: { op: OpenApiOperation; project: Project | null; currentBook: Book | null; currentContent: Content | null; notify: (kind: Toast["kind"], text: string) => void }) {
  const [params, setParams] = useState<Record<string, string>>({});
  const [query, setQuery] = useState("{}");
  const [body, setBody] = useState("{}");
  const [result, setResult] = useState("");
  const pathParams = (op.operation.parameters || []).filter((p: any) => p.in === "path").map((p: any) => p.name);
  const queryParams = (op.operation.parameters || []).filter((p: any) => p.in === "query").map((p: any) => p.name);

  useEffect(() => {
    const defaults: Record<string, string> = {};
    pathParams.forEach((name: string) => {
      if (name === "project_id") defaults[name] = project?.id || "";
      else if (name === "novel_id" || name === "book_id") defaults[name] = currentBook?.id || "";
      else if (name === "content_id" || name === "chapter_id") defaults[name] = currentContent?.id || "";
      else if (name === "run_id") defaults[name] = "";
      else if (name === "provider") defaults[name] = "deepseek";
      else if (name === "platform") defaults[name] = "manual";
      else defaults[name] = "";
    });
    setParams(defaults);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [op.path, project?.id, currentBook?.id, currentContent?.id]);

  async function run() {
    try {
      let path = op.path;
      Object.entries(params).forEach(([key, value]) => { path = path.replace(`{${key}}`, encodeURIComponent(value)); });
      const qs = JSON.parse(query || "{}");
      const search = new URLSearchParams();
      Object.entries(qs).forEach(([key, value]) => { if (value !== "" && value !== null && value !== undefined) search.set(key, String(value)); });
      const url = `${path}${search.toString() ? `?${search}` : ""}`;
      const init: RequestInit = { method: op.method };
      if (!["GET", "DELETE"].includes(op.method)) init.body = body.trim() ? JSON.stringify(JSON.parse(body)) : "{}";
      const response = await api<any>(url, init);
      setResult(formatJson(response));
      notify("ok", `${op.method} ${op.path} 调用成功`);
    } catch (caught) {
      const message = errorText(caught);
      setResult(message);
      notify("error", message);
    }
  }

  return <div className="card"><div className="card-head"><div className="card-title"><span className={badge(op.method === "GET" ? "ok" : "pending")}>{op.method}</span> {op.path}</div><button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={run}>调用</button></div><p className="cell-sub">{op.tag} · {op.summary}</p>{pathParams.length ? <div className="grid grid-3" style={{ marginTop: 10 }}>{pathParams.map((name: string) => <div key={name}><label className="form-label">{name}</label><input className="form-input" value={params[name] || ""} onChange={e => setParams(v => ({ ...v, [name]: e.target.value }))} /></div>)}</div> : null}{queryParams.length ? <><label className="form-label" style={{ marginTop: 10 }}>Query JSON</label><textarea className="form-input" rows={2} value={query} onChange={e => setQuery(e.target.value)} /></> : null}{!["GET", "DELETE"].includes(op.method) ? <><label className="form-label" style={{ marginTop: 10 }}>Body JSON</label><textarea className="form-input" rows={4} value={body} onChange={e => setBody(e.target.value)} /></> : null}{result ? <pre className="outline-block" style={{ marginTop: 10, maxHeight: 240, overflow: "auto" }}>{result}</pre> : null}</div>;
}

function LogPanel({ logs, run, loadLatestRun }: { logs: Array<{ at: string; text: string }>; run: Run | null; loadLatestRun: () => void }) {
  return <div className="card" style={{ marginTop: 16 }}><div className="card-head"><div className="card-title"><Workflow size={16} /> 实时状态</div><button className="btn-sm btn-ghost" onClick={loadLatestRun}>刷新工作流</button></div><div className="grid grid-2"><div>{run ? <pre className="outline-block">{formatJson({ id: run.id, status: run.status, current_node_key: run.current_node_key })}</pre> : <p className="cell-sub">暂无工作流</p>}</div><div>{logs.slice(0, 8).map(log => <div className="activity" key={`${log.at}-${log.text}`}><div className="av-sm"><Activity size={14} /></div><div><p>{log.text}</p><time>{log.at}</time></div></div>)}</div></div></div>;
}
