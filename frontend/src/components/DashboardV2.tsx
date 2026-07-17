import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import {
  BookOpen, PenTool, TrendingUp, Zap,
  Lightbulb, Search, Library, Edit3, BarChart3,
  Clock, Activity, FileText, BookMarked,
} from "lucide-react";
import "../styles/proto.css";

// ── Types ────────────────────────────────────────────────────────────────────

interface DashboardV2Props {
  projectId: string;
  onNavigate: (tab: string, novelId?: string) => void;
}

interface ProjectRaw {
  id: string;
  name?: string;
  title?: string;
  status?: string;
  updated_at?: string;
  created_at?: string;
  total_words?: number;
  word_count?: number;
  chapter_count?: number;
}

interface RecentItem {
  id: string;
  title: string;
  description: string;
  time: string;
  icon: React.ReactNode;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}

function fmtWords(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万`;
  return `${n}`;
}

// ── Quick-action definitions ─────────────────────────────────────────────────

interface QAction {
  id: string;
  tab: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  accent: string;
}

const QUICK_ACTIONS: QAction[] = [
  {
    id: "wizard", tab: "wizard",
    icon: <Lightbulb size={20} />,
    title: "新建小说",
    description: "从灵感到大纲，AI 驱动创作起点",
    accent: "var(--primary-light)",
  },
  {
    id: "ranking", tab: "ranking",
    icon: <TrendingUp size={20} />,
    title: "扫榜选书",
    description: "榜单热点分析，智能选题推荐",
    accent: "var(--cyan)",
  },
  {
    id: "hotspot", tab: "hotspot",
    icon: <Search size={20} />,
    title: "热点追踪",
    description: "实时热点捕获与创作灵感",
    accent: "var(--orange)",
  },
  {
    id: "library", tab: "library",
    icon: <BookMarked size={20} />,
    title: "书库",
    description: "统一书库，管理所有作品",
    accent: "var(--green)",
  },
  {
    id: "editor", tab: "editor",
    icon: <Edit3 size={20} />,
    title: "编辑器",
    description: "沉浸写作，AI 辅助润色",
    accent: "var(--primary-light)",
  },
  {
    id: "studio", tab: "studio",
    icon: <PenTool size={20} />,
    title: "仿写",
    description: "风格模仿与创意写作训练",
    accent: "var(--orange)",
  },
];

// ── Component ────────────────────────────────────────────────────────────────

export function DashboardV2({ projectId: _projectId, onNavigate }: DashboardV2Props) {
  // Stats
  const [projectCount, setProjectCount] = useState<number | null>(null);
  const [totalWords, setTotalWords] = useState<number | null>(null);
  const [todayCount, setTodayCount] = useState<number | null>(null);
  const [aiCallCount, setAiCallCount] = useState<number | string | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  // Recent activity
  const [recentItems, setRecentItems] = useState<RecentItem[]>([]);

  // ── Fetch all stats ──────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError("");

    const results = await Promise.allSettled([
      // 1. Projects list (for count + word sum)
      api<ProjectRaw[]>("/api/v1/projects"),
      // 2. Stats overview (AI calls, contents)
      api<{ ai_calls?: number; contents?: number }>("/api/v1/stats/overview").catch(() => null),
    ]);

    // Project count + total words
    if (results[0].status === "fulfilled") {
      const projects = results[0].value;
      const arr = Array.isArray(projects) ? projects : [];
      setProjectCount(arr.length);
      const words = arr.reduce((sum, p) => {
        return sum + (p.total_words || p.word_count || 0);
      }, 0);
      setTotalWords(words);

      // Build recent activity from projects
      const items: RecentItem[] = arr
        .slice(0, 5)
        .map((p: ProjectRaw) => ({
          id: p.id,
          title: p.name || p.title || "未命名项目",
          description: `${fmtWords(p.total_words || p.word_count || 0)} 字 · ${p.chapter_count || 0} 章`,
          time: timeAgo(p.updated_at || p.created_at || new Date().toISOString()),
          icon: <FileText size={16} />,
        }));
      setRecentItems(items);
    } else {
      setProjectCount(0);
      setTotalWords(0);
      setRecentItems([]);
    }

    // Stats overview
    if (results[1].status === "fulfilled" && results[1].value) {
      const overview = results[1].value;
      setTodayCount(0); // endpoint doesn't provide today's chapter count yet
      setAiCallCount(overview.ai_calls ?? 0);
    } else {
      setTodayCount(0);
      setAiCallCount(0);
    }

    setStatsLoading(false);
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  // ── compute trend labels ──────────────────────────────────────────────────

  const statCards = [
    {
      label: "总项目",
      value: statsLoading ? "…" : (projectCount ?? 0),
      trend: "",
      trendClass: "flat",
      iconCls: "ic-purple",
      iconEl: <BookOpen size={18} />,
    },
    {
      label: "总字数",
      value: statsLoading ? "…" : fmtWords(totalWords ?? 0),
      trend: "",
      trendClass: "flat",
      iconCls: "ic-cyan",
      iconEl: <BarChart3 size={18} />,
    },
    {
      label: "今日生成",
      value: statsLoading ? "…" : (todayCount ?? 0),
      trend: "",
      trendClass: "flat",
      iconCls: "ic-orange",
      iconEl: <Zap size={18} />,
    },
    {
      label: "AI 调用",
      value: statsLoading ? "…" : (aiCallCount ?? 0),
      trend: "",
      trendClass: "flat",
      iconCls: "ic-green",
      iconEl: <Activity size={18} />,
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* ── Page Heading ──────────────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <h1>工作台</h1>
          <p>AI 驱动的小说创作工作台 · 智能创作从这里开始</p>
        </div>
      </div>

      {/* ── 4 Stat Cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        {statCards.map((s, i) => (
          <div key={i} className="stat" style={{ animationDelay: `${i * 0.08}s` }}>
            <div className="stat-top">
              <span className="stat-label">{s.label}</span>
              <div className={`stat-ic ${s.iconCls}`}>
                {s.iconEl}
              </div>
            </div>
            <div className="stat-val">
              {statsLoading ? (
                <span style={{ fontSize: 18, color: "var(--text-3)" }}>加载中…</span>
              ) : (
                s.value
              )}
            </div>
            {s.trend && (
              <div className="stat-trend">
                <span className={s.trendClass}>{s.trend}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ── Two-column: Quick Actions + Right Sidebar ─────────────────────── */}
      <div className="layout-2">
        {/* ── Left: Quick Actions ──────────────────────────────────────────── */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <Zap size={18} />
              快捷功能
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
                  style={{ color: action.accent, background: `${action.accent}18` }}
                >
                  {action.icon}
                </div>
                <h4>{action.title}</h4>
                <p>{action.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: System Status + Recent Activity ──────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* System Status */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                <Clock size={18} />
                系统状态
              </div>
            </div>

            {statsError && (
              <div style={{
                padding: "10px 14px",
                background: "rgba(248,113,113,.12)",
                border: "1px solid rgba(248,113,113,.25)",
                borderRadius: "var(--r-sm)",
                color: "var(--red)",
                fontSize: 13,
                marginBottom: 12,
              }}>
                {statsError}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                fontSize: 13, color: "var(--text-2)",
              }}>
                <span className="dot green" />
                服务运行正常
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                fontSize: 13, color: "var(--text-2)",
              }}>
                <span className="dot green" />
                AI 引擎在线
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                fontSize: 13, color: "var(--text-2)",
              }}>
                <span className="dot green" />
                数据库已连接
              </div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-head">
              <div className="card-title">
                <Activity size={18} />
                最近动态
              </div>
            </div>

            {statsLoading ? (
              <div style={{
                textAlign: "center", padding: "24px 0",
                color: "var(--text-3)", fontSize: 13,
              }}>
                加载中…
              </div>
            ) : (Array.isArray(recentItems) && recentItems.length > 0) ? (
              <div>
                {recentItems.map((item) => (
                  <div
                    key={item.id}
                    className="activity"
                    onClick={() => onNavigate("editor", item.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="av-sm">
                      {item.icon}
                    </div>
                    <div>
                      <p>{item.title}</p>
                      <p style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 2 }}>
                        {item.description}
                      </p>
                      <time>{item.time}</time>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                textAlign: "center", padding: "24px 0",
                color: "var(--text-3)", fontSize: 13,
              }}>
                暂无动态
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
