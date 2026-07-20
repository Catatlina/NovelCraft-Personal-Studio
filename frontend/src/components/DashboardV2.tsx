import React, { useState } from "react";
import {
  Edit3,
  AlertCircle,
  BookOpen,
  Zap,
  Lightbulb,
  TrendingUp,
  Activity,
  Library,
  FileText,
  Bell,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface DashboardV2Props {
  projectId: string;
  onNavigate: (tab: string) => void;
}

// ── Sample data ──────────────────────────────────────────────────────────────

interface StatCard {
  label: string;
  value: string;
  trend: string;
  trendClass: string;
  iconCls: string;
  iconEl: React.ReactNode;
}

const STAT_CARDS: StatCard[] = [
  {
    label: "今日生成字数",
    value: "—",
    trend: "",
    trendClass: "flat",
    iconCls: "ic-purple",
    iconEl: <Edit3 size={18} />,
  },
  {
    label: "待审阅章节",
    value: "3",
    trend: "⚠️ 需要关注",
    trendClass: "flat",
    iconCls: "ic-orange",
    iconEl: <AlertCircle size={18} />,
  },
  {
    label: "活跃项目",
    value: "5",
    trend: "● 3个进行中",
    trendClass: "flat",
    iconCls: "ic-cyan",
    iconEl: <BookOpen size={18} />,
  },
  {
    label: "本周 AI 调用",
    value: "—",
    trend: "",
    trendClass: "flat",
    iconCls: "ic-green",
    iconEl: <Zap size={18} />,
  },
];

interface QAction {
  id: string;
  tab: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  accent: string;
  accentBg: string;
}

const QUICK_ACTIONS: QAction[] = [
  {
    id: "inspiration",
    tab: "wizard",
    icon: <Lightbulb size={20} />,
    title: "灵感创作",
    description: "从灵感到大纲，AI 驱动起点",
    accent: "var(--primary-light)",
    accentBg: "var(--primary-dim)",
  },
  {
    id: "ranking",
    tab: "ranking",
    icon: <TrendingUp size={20} />,
    title: "扫榜选书",
    description: "榜单热点分析，智能选题",
    accent: "var(--cyan)",
    accentBg: "var(--info-bg)",
  },
  {
    id: "hotspot",
    tab: "hotspot",
    icon: <Activity size={20} />,
    title: "热点追踪",
    description: "实时热点捕获与灵感",
    accent: "var(--orange)",
    accentBg: "var(--warning-bg)",
  },
  {
    id: "library",
    tab: "library",
    icon: <Library size={20} />,
    title: "书库管理",
    description: "统一管理所有作品",
    accent: "var(--green)",
    accentBg: "var(--success-bg)",
  },
  {
    id: "editor",
    tab: "editor",
    icon: <Edit3 size={20} />,
    title: "编辑器",
    description: "沉浸写作，AI 辅助润色",
    accent: "var(--primary-light)",
    accentBg: "var(--primary-dim)",
  },
  {
    id: "review",
    tab: "review",
    icon: <FileText size={20} />,
    title: "审阅",
    description: "批注、协作与版本对比",
    accent: "var(--cyan)",
    accentBg: "var(--info-bg)",
  },
];

interface ProjectRow {
  title: string;
  subtitle: string;
  type: string;
  progress: string;
  edited: string;
  statusLabel: string;
  statusBadge: string;
  dotClass: string;
}

const RECENT_PROJECTS: ProjectRow[] = [
  {
    title: "星渊纪元",
    subtitle: "玄幻 · 连载中",
    type: "小说",
    progress: "68%",
    edited: "10 分钟前",
    statusLabel: "进行中",
    statusBadge: "badge green",
    dotClass: "dot green",
  },
  {
    title: "赛博长安",
    subtitle: "科幻 · 大纲",
    type: "小说",
    progress: "24%",
    edited: "2 小时前",
    statusLabel: "草稿",
    statusBadge: "badge cyan",
    dotClass: "dot gray",
  },
  {
    title: "青梅煮酒",
    subtitle: "都市 · 连载中",
    type: "小说",
    progress: "91%",
    edited: "昨天",
    statusLabel: "进行中",
    statusBadge: "badge green",
    dotClass: "dot green",
  },
  {
    title: "论 AI 写作的边界",
    subtitle: "专栏 · 已发布",
    type: "自媒体",
    progress: "100%",
    edited: "3 天前",
    statusLabel: "已发布",
    statusBadge: "badge purple",
    dotClass: "dot gray",
  },
];

interface SystemStatusItem {
  dotClass: string;
  label: string;
  detail: string;
}

const SYSTEM_STATUS: SystemStatusItem[] = [
  { dotClass: "dot green", label: "API 服务正常", detail: "响应 128ms" },
  { dotClass: "dot green", label: "DeepSeek 在线", detail: "deepseek-v4-pro" },
  { dotClass: "dot orange", label: "本月预算 78%", detail: "可在设置调整限额" },
];

interface TodoItem {
  title: string;
  badge: string;
  badgeClass: string;
  meta: string;
}

const TODO_ITEMS: TodoItem[] = [
  {
    title: "审阅《星渊纪元》第 11 章批注",
    badge: "待处理",
    badgeClass: "badge orange",
    meta: "2 条",
  },
  {
    title: "发布《青梅煮酒》番外至知乎",
    badge: "计划中",
    badgeClass: "badge cyan",
    meta: "今天",
  },
  {
    title: "补充知识库：世界观设定集",
    badge: "草稿",
    badgeClass: "badge gray",
    meta: "—",
  },
];

const TABS = ["全部", "创作", "分析"];

// ── Component ────────────────────────────────────────────────────────────────

export function DashboardV2({ projectId: _projectId, onNavigate }: DashboardV2Props) {
  const [activeTab, setActiveTab] = useState<string>(TABS[0]);

  return (
    <div>
      {/* ── Breadcrumb ─────────────────────────────────────────────────────── */}
      <div className="breadcrumb">
        <b>NovelCraft</b> › 工作台
      </div>

      {/* ── Page head ──────────────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <h1>工作台 — 创作中枢</h1>
        </div>
        <div className="head-actions">
          <button
            className="btn-sm btn-primary"
            onClick={() => onNavigate("wizard")}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              width="15"
              height="15"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>{" "}
            新建项目
          </button>
        </div>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────────────── */}
      <div className="tabs">
        {TABS.map((tab) => (
          <div
            key={tab}
            className={`tab${activeTab === tab ? " on" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </div>
        ))}
      </div>

      {/* ── 4 Stat Cards ───────────────────────────────────────────────────── */}
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        {STAT_CARDS.map((s, i) => (
          <div key={i} className="stat">
            <div className="stat-top">
              <span className="stat-label">{s.label}</span>
              <div className={`stat-ic ${s.iconCls}`}>{s.iconEl}</div>
            </div>
            <div className="stat-val">{s.value}</div>
            <div className="stat-trend">
              <span className={s.trendClass}>{s.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Two-column: Left (quick actions + table) / Right (status + todos) ─ */}
      <div className="layout-2">
        {/* ── Left column ──────────────────────────────────────────────────── */}
        <div>
          {/* Quick actions */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head">
              <div className="card-title">
                <Zap size={18} />
                快捷入口
              </div>
            </div>
            <div className="quick">
              {QUICK_ACTIONS.map((action) => (
                <div
                  key={action.id}
                  className="qcard"
                  onClick={() => onNavigate(action.tab)}
                >
                  <div
                    className="qic"
                    style={{
                      background: action.accentBg,
                      color: action.accent,
                    }}
                  >
                    {action.icon}
                  </div>
                  <h4>{action.title}</h4>
                  <p>{action.description}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Recent projects table */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                <FileText size={18} />
                最近项目
              </div>
              <span className="card-sub">按最近编辑排序</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>项目</th>
                    <th>类型</th>
                    <th>进度</th>
                    <th>最近编辑</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {RECENT_PROJECTS.map((p, i) => (
                    <tr
                      key={i}
                      onClick={() => onNavigate("editor")}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <b>{p.title}</b>
                        <div className="cell-sub">{p.subtitle}</div>
                      </td>
                      <td>{p.type}</td>
                      <td>
                        <b>{p.progress}</b>
                      </td>
                      <td>{p.edited}</td>
                      <td>
                        <span className={p.statusBadge}>
                          <span className={p.dotClass} />
                          {p.statusLabel}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ── Right column ─────────────────────────────────────────────────── */}
        <div>
          {/* System status */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head">
              <div className="card-title">
                <Activity size={18} />
                系统状态
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {SYSTEM_STATUS.map((item, i) => (
                <div key={i} className="activity">
                  <span className={item.dotClass} />
                  <div>
                    <strong style={{ fontSize: 13 }}>{item.label}</strong>
                    <span
                      className="cell-sub"
                      style={{ display: "block" }}
                    >
                      {item.detail}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Todos */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                <Bell size={18} />
                待办
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {TODO_ITEMS.map((item, i) => (
                <div key={i} className="ticket">
                  <h5>{item.title}</h5>
                  <div className="meta">
                    <span className={item.badgeClass}>{item.badge}</span>
                    <span>{item.meta}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
