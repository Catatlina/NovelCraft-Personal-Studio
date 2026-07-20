import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Database,
  Edit3,
  FileText,
  Layers,
  Library,
  Lightbulb,
  PlugZap,
  RefreshCw,
  Rocket,
  Settings,
  TrendingUp,
  Upload,
  Users,
  Workflow,
  Zap,
} from "lucide-react";
import { ApiError, api as baseApi } from "../lib/api";
import "../styles/proto.css";

type ApiResponse<T> = { code: number | string; message: string; data: T };

interface Project {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  status?: string;
}

interface Stats {
  ai_calls?: number;
  total_ai_calls?: number;
  contents?: number;
  db_size?: string;
}

interface Book {
  id: string;
  title: string;
  genre?: string;
  synopsis?: string;
  status?: string;
  total_words?: number;
  chapter_count?: number;
  updated_at?: string;
  created_at?: string;
  meta?: Record<string, unknown>;
}

interface Snapshot {
  id: string;
  display_name?: string;
  source_key?: string;
  status?: string;
  capture_status?: string;
  captured_at?: string;
  item_count?: number;
}

interface Topic {
  id: string;
  title: string;
  genre?: string;
  market_score?: number;
  status?: string;
  created_at?: string;
}

interface Health {
  status?: string;
  database?: string;
  redis?: string;
  worker?: string;
  ai_provider?: string;
  ai_key_configured?: boolean;
  queue_depth?: number;
}

interface DashboardV2Props {
  projectId: string;
  onNavigate: (tab: string) => void;
  onProjectSelected?: (project: Project) => void;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await baseApi<ApiResponse<T>>(path, init);
  return response.data;
}

function formatNumber(value: unknown): string {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return "0";
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1).replace(/\.0$/, "")}w`;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
}

function formatDate(value?: string): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function getErrorMessage(caught: unknown): string {
  if (caught instanceof ApiError) {
    const payload = caught.payload as any;
    return payload?.detail || payload?.message || payload?.error || `HTTP ${caught.status}`;
  }
  return caught instanceof Error ? caught.message : String(caught);
}

function statusBadge(status?: string) {
  if (!status) return "badge gray";
  if (["succeeded", "active", "ok", "ready", "completed", "confirmed"].includes(status)) return "badge green";
  if (["failed", "error"].includes(status)) return "badge red";
  if (["pending", "running", "generating", "planning"].includes(status)) return "badge orange";
  return "badge gray";
}

function EmptyBlock({ title, description, primary, onPrimary, secondary, onSecondary }: {
  title: string;
  description: string;
  primary?: string;
  onPrimary?: () => void;
  secondary?: string;
  onSecondary?: () => void;
}) {
  return (
    <div className="empty" style={{ padding: "30px 18px" }}>
      <div className="empty-ic"><Layers size={26} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
        {primary ? <button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={onPrimary}>{primary}</button> : null}
        {secondary ? <button className="btn-sm btn-ghost" onClick={onSecondary}>{secondary}</button> : null}
      </div>
    </div>
  );
}

export function DashboardV2({ projectId, onNavigate, onProjectSelected }: DashboardV2Props) {
  const [activeTab, setActiveTab] = useState("全部");
  const [loading, setLoading] = useState(true);
  const [savingProject, setSavingProject] = useState(false);
  const [error, setError] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [books, setBooks] = useState<Book[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [health, setHealth] = useState<Health>({});

  const selectedProject = useMemo(() => {
    return projects.find(project => project.id === projectId) || projects[0] || null;
  }, [projects, projectId]);

  const projectForQueries = projectId || selectedProject?.id || "";
  const latestBook = books[0] || null;
  const latestSnapshot = snapshots[0] || null;

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const [healthResult, projectRows, statRows] = await Promise.all([
        api<Health>("/api/v1/healthz").catch(() => ({} as Health)),
        api<Project[]>("/api/v1/projects"),
        api<Stats>("/api/v1/stats/overview").catch(() => ({} as Stats)),
      ]);
      setHealth(healthResult || {});
      setProjects(projectRows || []);
      setStats(statRows || {});

      const activeProjectId = projectId || projectRows?.[0]?.id || "";
      if (!activeProjectId) {
        setBooks([]);
        setSnapshots([]);
        setTopics([]);
        return;
      }

      const [bookRows, snapshotRows, topicRows] = await Promise.all([
        api<Book[]>(`/api/v1/ranking/library/books?project_id=${encodeURIComponent(activeProjectId)}&limit=8`).catch(() => []),
        api<Snapshot[]>(`/api/v1/ranking/snapshots?project_id=${encodeURIComponent(activeProjectId)}`).catch(() => []),
        api<Topic[]>(`/api/v1/ranking/topics?project_id=${encodeURIComponent(activeProjectId)}`).catch(() => []),
      ]);
      setBooks(bookRows || []);
      setSnapshots(snapshotRows || []);
      setTopics(topicRows || []);
      if (!projectId && projectRows?.[0]) onProjectSelected?.(projectRows[0]);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function createProject() {
    setSavingProject(true);
    setError("");
    try {
      const project = await api<Project>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({
          name: "NovelCraft 创作项目",
          description: "由前端工作台创建，可用于扫榜、建书、写作、发布与协作。",
        }),
      });
      setProjects(current => [project, ...current.filter(item => item.id !== project.id)]);
      onProjectSelected?.(project);
      await loadDashboard();
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSavingProject(false);
    }
  }

  const statCards = [
    {
      label: "真实项目",
      value: formatNumber(projects.length),
      trend: selectedProject ? `当前：${selectedProject.name}` : "暂无项目",
      iconCls: "ic-purple",
      icon: <BookOpen size={18} />,
    },
    {
      label: "书库作品",
      value: formatNumber(books.length),
      trend: latestBook ? `最近：${latestBook.title}` : "来自书库接口",
      iconCls: "ic-cyan",
      icon: <Library size={18} />,
    },
    {
      label: "榜单快照",
      value: formatNumber(snapshots.length),
      trend: latestSnapshot ? `${latestSnapshot.display_name || latestSnapshot.source_key || "榜单"} · ${latestSnapshot.status || "—"}` : "来自扫榜接口",
      iconCls: "ic-orange",
      icon: <TrendingUp size={18} />,
    },
    {
      label: "AI 调用",
      value: formatNumber(stats.ai_calls ?? stats.total_ai_calls ?? 0),
      trend: health.ai_key_configured ? `${health.ai_provider || "AI"} 已配置` : "AI Key 未由后端确认",
      iconCls: "ic-green",
      icon: <Zap size={18} />,
    },
  ];

  const quickActions = [
    {
      id: "wizard",
      tab: "wizard",
      icon: <Lightbulb size={20} />,
      title: "灵感创作",
      description: "调用 Bootstrap 后端链路，创建作品并进入工作流",
      accent: "var(--primary-light)",
      accentBg: "var(--primary-dim)",
    },
    {
      id: "ranking",
      tab: "ranking",
      icon: <TrendingUp size={20} />,
      title: "扫榜选书",
      description: "采集/导入榜单，AI 分析后生成原创选题",
      accent: "var(--cyan)",
      accentBg: "rgba(34,211,238,.12)",
    },
    {
      id: "library",
      tab: "library",
      icon: <Library size={20} />,
      title: "书库管理",
      description: "打开真实书库，进入编辑、续写、导出与目录管理",
      accent: "var(--green)",
      accentBg: "rgba(52,211,153,.12)",
    },
    {
      id: "editor",
      tab: "editor",
      icon: <Edit3 size={20} />,
      title: "章节编辑器",
      description: "保存章节、版本恢复、AI 润色/续写/去 AI 味",
      accent: "var(--primary-light)",
      accentBg: "var(--primary-dim)",
    },
    {
      id: "studio",
      tab: "studio",
      icon: <Rocket size={20} />,
      title: "内容工作室",
      description: "短篇、自媒体、热点生成、知识库与仿写",
      accent: "var(--orange)",
      accentBg: "rgba(251,146,60,.12)",
    },
    {
      id: "settings",
      tab: "settings",
      icon: <Settings size={20} />,
      title: "配置中心",
      description: "模型路由、预算、平台账号、密码与系统设置",
      accent: "var(--cyan)",
      accentBg: "rgba(34,211,238,.12)",
    },
  ];

  const filteredActions = quickActions.filter(action => {
    if (activeTab === "全部") return true;
    if (activeTab === "创作") return ["wizard", "ranking", "library", "editor"].includes(action.id);
    return ["studio", "settings"].includes(action.id);
  });

  const systemItems = [
    {
      label: "后端 API",
      detail: health.status === "ok" ? "healthz 正常" : "未读取到健康状态",
      ok: health.status === "ok",
    },
    {
      label: "数据库",
      detail: health.database || "未返回",
      ok: health.database === "ok",
    },
    {
      label: "Redis / Worker",
      detail: `${health.redis || "未返回"}；${health.worker || "worker 未返回"}`,
      ok: health.redis === "ok" && String(health.worker || "").startsWith("ok"),
    },
    {
      label: "AI Provider",
      detail: health.ai_key_configured ? `${health.ai_provider || "provider"} 已配置` : "后端未确认可用密钥",
      ok: Boolean(health.ai_key_configured),
    },
  ];

  return (
    <div>
      <div className="breadcrumb">
        <b>NovelCraft</b> › 工作台
      </div>

      <div className="page-head">
        <div>
          <h1>工作台 — 已接入后端的创作中枢</h1>
          <p>这里不再展示样例项目；所有数字、列表和状态都来自当前登录账号的接口。</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={loadDashboard} disabled={loading}>
            <RefreshCw size={14} /> 刷新
          </button>
          <button className="btn-sm btn-primary" style={{ width: "auto" }} onClick={createProject} disabled={savingProject}>
            <Rocket size={14} /> {savingProject ? "创建中…" : "创建项目"}
          </button>
        </div>
      </div>

      {error ? <div className="error" style={{ marginBottom: 16 }}>{error}</div> : null}

      <div className="tabs">
        {["全部", "创作", "运营"].map(tab => (
          <button key={tab} className={`tab${activeTab === tab ? " on" : ""}`} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        {statCards.map(card => (
          <div key={card.label} className="stat">
            <div className="stat-top">
              <span className="stat-label">{card.label}</span>
              <div className={`stat-ic ${card.iconCls}`}>{card.icon}</div>
            </div>
            <div className="stat-val">{loading ? "…" : card.value}</div>
            <div className="stat-trend">{card.trend}</div>
          </div>
        ))}
      </div>

      {!projectForQueries ? (
        <EmptyBlock
          title="还没有真实项目"
          description="创建项目后，扫榜、建书、章节编辑、知识库、发布和协作功能才有统一归属。"
          primary={savingProject ? "创建中…" : "创建项目"}
          onPrimary={createProject}
          secondary="配置 AI"
          onSecondary={() => onNavigate("settings")}
        />
      ) : (
        <div className="layout-2">
          <div>
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head">
                <div className="card-title"><PlugZap size={18} /> 可操作入口</div>
                <span className="card-sub">点击即进入真实功能页</span>
              </div>
              <div className="quick">
                {filteredActions.map(action => (
                  <button key={action.id} type="button" className="qcard" onClick={() => onNavigate(action.tab)}>
                    <div className="qic" style={{ background: action.accentBg, color: action.accent }}>{action.icon}</div>
                    <h4>{action.title}</h4>
                    <p>{action.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head">
                <div className="card-title"><FileText size={18} /> 真实书库</div>
                <button className="btn-sm btn-ghost" onClick={() => onNavigate("library")}>打开书库</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>作品</th><th>题材</th><th>章节/字数</th><th>最近更新</th><th>状态</th></tr></thead>
                  <tbody>
                    {books.length ? books.map(book => (
                      <tr key={book.id} style={{ cursor: "pointer" }} onClick={() => onNavigate("library")}>
                        <td><b>{book.title}</b><div className="cell-sub">{book.synopsis || String(book.meta?.idea || "—")}</div></td>
                        <td>{book.genre || String(book.meta?.genre || "未分类")}</td>
                        <td><b>{formatNumber(book.chapter_count || 0)}</b><div className="cell-sub">{formatNumber(book.total_words || 0)} 字</div></td>
                        <td>{formatDate(book.updated_at || book.created_at)}</td>
                        <td><span className={statusBadge(book.status)}>{book.status || "draft"}</span></td>
                      </tr>
                    )) : (
                      <tr><td colSpan={5}>
                        <EmptyBlock
                          title="书库暂无作品"
                          description="可以从灵感创作直接建书，也可以先扫榜生成原创选题后入库。"
                          primary="灵感创作"
                          onPrimary={() => onNavigate("wizard")}
                          secondary="扫榜选书"
                          onSecondary={() => onNavigate("ranking")}
                        />
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="grid grid-2">
              <div className="card">
                <div className="card-head">
                  <div className="card-title"><Upload size={18} /> 最近榜单快照</div>
                  <button className="btn-sm btn-ghost" onClick={() => onNavigate("ranking")}>导入/分析</button>
                </div>
                {snapshots.length ? (
                  <div style={{ display: "grid", gap: 10 }}>
                    {snapshots.slice(0, 4).map(snapshot => (
                      <div key={snapshot.id} className="ticket">
                        <h5>{snapshot.display_name || snapshot.source_key || "榜单快照"}</h5>
                        <div className="meta">
                          <span className={statusBadge(snapshot.status)}>{snapshot.status || "unknown"}</span>
                          <span>{snapshot.capture_status || "capture"}</span>
                          <span>{formatDate(snapshot.captured_at)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyBlock title="暂无榜单快照" description="导入 CSV 或扫描榜源后，这里会显示真实快照和分析状态。" primary="去扫榜" onPrimary={() => onNavigate("ranking")} />
                )}
              </div>
              <div className="card">
                <div className="card-head">
                  <div className="card-title"><BarChart3 size={18} /> AI 选题候选</div>
                  <button className="btn-sm btn-ghost" onClick={() => onNavigate("ranking")}>生成作品</button>
                </div>
                {topics.length ? (
                  <div style={{ display: "grid", gap: 10 }}>
                    {topics.slice(0, 4).map(topic => (
                      <div key={topic.id} className="ticket">
                        <h5>{topic.title}</h5>
                        <div className="meta">
                          <span className="badge purple">{topic.genre || "未分类"}</span>
                          <span>分数 {Number(topic.market_score || 0).toFixed(1)}</span>
                          <span>{topic.status || "candidate"}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyBlock title="暂无原创选题" description="先完成榜单分析，AI 会把市场信号转成原创题材候选。" primary="分析榜单" onPrimary={() => onNavigate("ranking")} />
                )}
              </div>
            </div>
          </div>

          <div>
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-head">
                <div className="card-title"><Activity size={18} /> 系统接入状态</div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {systemItems.map(item => (
                  <div key={item.label} className="activity">
                    {item.ok ? <CheckCircle2 size={18} color="var(--green)" /> : <AlertCircle size={18} color="var(--orange)" />}
                    <div>
                      <strong style={{ fontSize: 13 }}>{item.label}</strong>
                      <span className="cell-sub" style={{ display: "block" }}>{item.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div className="card-title"><Workflow size={18} /> 下一步操作链</div>
              </div>
              <div style={{ display: "grid", gap: 10 }}>
                <button className="ticket" style={{ textAlign: "left" }} onClick={() => onNavigate(books.length ? "editor" : "wizard")}>
                  <h5>1. {books.length ? "继续写当前作品" : "先创建第一部作品"}</h5>
                  <div className="meta"><span className="badge cyan">{books.length ? "编辑器" : "Bootstrap"}</span><span>{books.length ? latestBook?.title : "调用 /projects/{id}/novels"}</span></div>
                </button>
                <button className="ticket" style={{ textAlign: "left" }} onClick={() => onNavigate(snapshots.length ? "ranking" : "ranking")}>
                  <h5>2. 扫榜形成选题池</h5>
                  <div className="meta"><span className="badge purple">Ranking</span><span>{snapshots.length} 个快照 / {topics.length} 个选题</span></div>
                </button>
                <button className="ticket" style={{ textAlign: "left" }} onClick={() => onNavigate("settings")}>
                  <h5>3. 检查 AI 与平台配置</h5>
                  <div className="meta"><span className={health.ai_key_configured ? "badge green" : "badge orange"}>{health.ai_key_configured ? "已配置" : "待配置"}</span><span>模型路由 / 预算 / 发布账号</span></div>
                </button>
                <button className="ticket" style={{ textAlign: "left" }} onClick={() => onNavigate("collaboration")}>
                  <h5>4. 协作与权限</h5>
                  <div className="meta"><span className="badge gray">Members</span><span>邀请、成员、审计日志</span></div>
                </button>
              </div>
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-head">
                <div className="card-title"><Database size={18} /> 数据口径</div>
              </div>
              <p style={{ color: "var(--text-2)", fontSize: 13, lineHeight: 1.7 }}>
                项目来自 /projects，书库来自 /ranking/library/books，榜单来自 /ranking/snapshots，选题来自 /ranking/topics，AI 与数据库状态来自 /stats/overview 与 /healthz。
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
