import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import {
  BookOpen, FileText, Library, Zap, Lightbulb,
  TrendingUp, Search, BookMarked, Edit3, PenTool,
  Clock, Loader2, AlertCircle, ChevronRight, Sparkles,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface DashboardV2Props {
  projectId: string;
  onNavigate: (tab: string, novelId?: string) => void;
}

interface StatItem {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  loading: boolean;
  accent: string;
}

interface QuickAction {
  id: string;
  tab: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  accent: string;
}

interface RecentProject {
  id: string;
  title: string;
  status: string;
  updated_at: string;
  total_words: number;
  chapter_count: number;
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

const STATUS_MAP: Record<string, { label: string; bg: string; color: string }> = {
  draft: { label: "草稿", bg: "rgba(139,143,168,.15)", color: "#8b8fa8" },
  writing: { label: "写作中", bg: "rgba(91,156,245,.15)", color: "#5b9cf5" },
  completed: { label: "已完成", bg: "rgba(49,181,114,.15)", color: "#31b572" },
  published: { label: "已发布", bg: "rgba(255,107,53,.15)", color: "#FF6B35" },
  archived: { label: "已归档", bg: "rgba(85,89,112,.15)", color: "#555970" },
};

// ── Keyframes (injected once) ────────────────────────────────────────────────

const KEYFRAMES = `
@keyframes nc-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes nc-pulse-glow {
  0%, 100% { box-shadow: 0 0 12px rgba(255,107,53,.15); }
  50%      { box-shadow: 0 0 24px rgba(255,107,53,.3); }
}
@keyframes nc-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-4px); }
}
@keyframes nc-shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
`;

// ── Quick-action definitions ─────────────────────────────────────────────────

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "wizard", tab: "wizard",
    icon: <Lightbulb size={22} />,
    title: "灵感创作",
    description: "从灵感到大纲，AI 驱动创作起点",
    accent: "#FF6B35",
  },
  {
    id: "ranking", tab: "ranking",
    icon: <TrendingUp size={22} />,
    title: "扫榜选书",
    description: "榜单热点分析，智能选题推荐",
    accent: "#00e5ff",
  },
  {
    id: "hotspot", tab: "hotspot",
    icon: <Search size={22} />,
    title: "热点追踪",
    description: "实时热点捕获与创作灵感",
    accent: "#a78bfa",
  },
  {
    id: "library", tab: "library",
    icon: <BookMarked size={22} />,
    title: "书库管理",
    description: "统一书库，管理所有作品",
    accent: "#31b572",
  },
  {
    id: "editor", tab: "editor",
    icon: <Edit3 size={22} />,
    title: "编辑器",
    description: "沉浸写作，AI 辅助润色",
    accent: "#5b9cf5",
  },
  {
    id: "studio", tab: "studio",
    icon: <PenTool size={22} />,
    title: "仿写练习",
    description: "风格模仿与创意写作训练",
    accent: "#f2a93b",
  },
];

// ── Component ────────────────────────────────────────────────────────────────

export function DashboardV2({ projectId, onNavigate }: DashboardV2Props) {
  // Stats
  const [projectCount, setProjectCount] = useState<number | null>(null);
  const [chapterToday, setChapterToday] = useState<number | null>(null);
  const [libraryCount, setLibraryCount] = useState<number | null>(null);
  const [aiCallCount, setAiCallCount] = useState<number | string | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  // Recent projects
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState("");

  // ── Fetch all stats in parallel ──────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError("");

    const results = await Promise.allSettled([
      // 1. 总项目数
      api<any[]>("/api/v1/projects").then(arr => Array.isArray(arr) ? arr.length : 0),
      // 2. 今日生成章节 + AI调用次数 (stats/overview)
      api<{ ai_calls?: number; contents?: number }>("/api/v1/stats/overview").catch(() => null),
      // 3. 书库藏书
      projectId
        ? api<any[]>(`/api/v1/ranking/library/books?project_id=${encodeURIComponent(projectId)}&limit=200`)
          .then(arr => Array.isArray(arr) ? arr.length : 0)
        : Promise.resolve(0),
    ]);

    // Project count
    if (results[0].status === "fulfilled") {
      setProjectCount(results[0].value as number);
    } else {
      setProjectCount(0);
    }

    // Stats overview
    if (results[1].status === "fulfilled" && results[1].value) {
      const overview = results[1].value;
      setChapterToday(0); // endpoint doesn't provide today's chapter count yet
      setAiCallCount(overview.ai_calls ?? "--");
    } else {
      setChapterToday(0);
      setAiCallCount("--");
    }

    // Library count
    if (results[2].status === "fulfilled") {
      setLibraryCount(results[2].value as number);
    } else {
      setLibraryCount(0);
    }

    setStatsLoading(false);
  }, [projectId]);

  // ── Fetch recent projects ────────────────────────────────────────────────

  const fetchRecent = useCallback(async () => {
    setRecentLoading(true);
    setRecentError("");
    try {
      const data = await api<any[]>("/api/v1/projects");
      const projects: RecentProject[] = Array.isArray(data)
        ? data.slice(0, 5).map((p: any) => ({
            id: p.id,
            title: p.name || p.title || "未命名项目",
            status: p.status || "draft",
            updated_at: p.updated_at || p.created_at || new Date().toISOString(),
            total_words: p.total_words || p.word_count || 0,
            chapter_count: p.chapter_count || 0,
          }))
        : [];
      setRecentProjects(projects);
    } catch (e: any) {
      setRecentError(e?.message || "加载失败");
    } finally {
      setRecentLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); fetchRecent(); }, [fetchStats, fetchRecent]);

  // ── Build stat cards ─────────────────────────────────────────────────────

  const stats: StatItem[] = [
    {
      label: "总项目数",
      value: statsLoading ? "…" : (projectCount ?? 0),
      icon: <BookOpen size={20} />,
      loading: statsLoading,
      accent: "#FF6B35",
    },
    {
      label: "今日生成章节",
      value: statsLoading ? "…" : (chapterToday ?? 0),
      icon: <FileText size={20} />,
      loading: statsLoading,
      accent: "#00e5ff",
    },
    {
      label: "书库藏书",
      value: statsLoading ? "…" : (libraryCount ?? 0),
      icon: <Library size={20} />,
      loading: statsLoading,
      accent: "#31b572",
    },
    {
      label: "AI 调用次数",
      value: statsLoading ? "…" : (aiCallCount ?? "--"),
      icon: <Zap size={20} />,
      loading: statsLoading,
      accent: "#a78bfa",
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ animation: "nc-fade-in .5s ease-out" }}>
      {/* Inject keyframes once */}
      <style>{KEYFRAMES}</style>

      {/* ── Stats Row ────────────────────────────────────────────────────── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: 16,
        marginBottom: 28,
      }}>
        {stats.map((s, i) => (
          <div key={i} style={{
            background: "rgba(22,22,50,.7)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,.06)",
            borderRadius: 12,
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            gap: 16,
            animation: `nc-fade-in .4s ease-out ${i * 0.08}s both`,
            transition: "transform .2s, box-shadow .2s",
          }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = `0 8px 32px ${s.accent}15`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {/* Icon */}
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: `${s.accent}18`,
              display: "flex", alignItems: "center", justifyContent: "center",
              color: s.accent,
              flexShrink: 0,
            }}>
              {s.icon}
            </div>
            {/* Value + label */}
            <div style={{ minWidth: 0 }}>
              {s.loading ? (
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                  color: "var(--text-muted)", fontSize: 13,
                }}>
                  <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
                  加载中
                </div>
              ) : (
                <>
                  <div style={{
                    fontSize: 28, fontWeight: 800, lineHeight: 1.2,
                    color: "var(--text-primary)",
                    fontVariantNumeric: "tabular-nums",
                  }}>
                    {s.value}
                  </div>
                  <div style={{
                    fontSize: 13, color: "var(--text-muted)",
                    marginTop: 2,
                  }}>
                    {s.label}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* ── Two-column content area ──────────────────────────────────────── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 24,
        marginBottom: 28,
      }}>
        {/* ── Quick Actions ──────────────────────────────────────────────── */}
        <div style={{
          background: "rgba(22,22,50,.7)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,.06)",
          borderRadius: 12,
          padding: 24,
          animation: "nc-fade-in .4s ease-out .2s both",
        }}>
          <h2 style={{
            fontSize: 16, fontWeight: 700, margin: "0 0 18px 0",
            color: "var(--text-primary)",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <Sparkles size={18} color="#FF6B35" />
            快捷入口
          </h2>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: 10,
          }}>
            {QUICK_ACTIONS.map((action, i) => (
              <button
                key={action.id}
                onClick={() => onNavigate(action.tab)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  gap: 8,
                  padding: "14px 16px",
                  background: "rgba(255,255,255,.03)",
                  border: "1px solid rgba(255,255,255,.05)",
                  borderRadius: 10,
                  cursor: "pointer",
                  textAlign: "left",
                  animation: `nc-fade-in .35s ease-out ${0.25 + i * 0.06}s both`,
                  transition: "all .25s ease",
                  minHeight: 0,
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = `${action.accent}12`;
                  e.currentTarget.style.borderColor = `${action.accent}30`;
                  e.currentTarget.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "rgba(255,255,255,.03)";
                  e.currentTarget.style.borderColor = "rgba(255,255,255,.05)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: `${action.accent}18`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: action.accent,
                  flexShrink: 0,
                }}>
                  {action.icon}
                </div>
                <div>
                  <div style={{
                    fontSize: 14, fontWeight: 600,
                    color: "var(--text-primary)",
                    marginBottom: 2,
                  }}>
                    {action.title}
                  </div>
                  <div style={{
                    fontSize: 12, color: "var(--text-muted)",
                    lineHeight: 1.4,
                  }}>
                    {action.description}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* ── Right column: stats error + empty hint ─────────────────────── */}
        <div style={{
          background: "rgba(22,22,50,.7)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          border: "1px solid rgba(255,255,255,.06)",
          borderRadius: 12,
          padding: 24,
          animation: "nc-fade-in .4s ease-out .3s both",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}>
          <h2 style={{
            fontSize: 16, fontWeight: 700, margin: 0,
            color: "var(--text-primary)",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <Clock size={18} color="#00e5ff" />
            系统状态
          </h2>

          {statsError && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "10px 14px",
              background: "rgba(222,75,94,.1)",
              border: "1px solid rgba(222,75,94,.25)",
              borderRadius: 8,
              color: "var(--danger)",
              fontSize: 13,
            }}>
              <AlertCircle size={16} />
              {statsError}
            </div>
          )}

          <div style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: 12,
            color: "var(--text-muted)",
            padding: "24px 0",
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%",
              background: "linear-gradient(135deg, rgba(255,107,53,.12), rgba(0,229,255,.12))",
              display: "flex", alignItems: "center", justifyContent: "center",
              animation: "nc-float 3s ease-in-out infinite",
            }}>
              <Sparkles size={28} color="#FF6B35" opacity={0.7} />
            </div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>
              NovelCraft Personal Studio
            </div>
            <div style={{ fontSize: 12 }}>
              AI 驱动的小说创作工作台
            </div>
          </div>
        </div>
      </div>

      {/* ── Recent Projects ──────────────────────────────────────────────── */}
      <div style={{
        background: "rgba(22,22,50,.7)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid rgba(255,255,255,.06)",
        borderRadius: 12,
        padding: 24,
        animation: "nc-fade-in .4s ease-out .35s both",
      }}>
        <h2 style={{
          fontSize: 16, fontWeight: 700, margin: "0 0 18px 0",
          color: "var(--text-primary)",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <Clock size={18} color="#00e5ff" />
          最近项目
        </h2>

        {recentLoading ? (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            gap: 8, padding: "40px 0", color: "var(--text-muted)", fontSize: 14,
          }}>
            <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} />
            加载中…
          </div>
        ) : recentError ? (
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "10px 14px",
            background: "rgba(222,75,94,.1)",
            border: "1px solid rgba(222,75,94,.25)",
            borderRadius: 8,
            color: "var(--danger)", fontSize: 13,
          }}>
            <AlertCircle size={16} />
            {recentError}
          </div>
        ) : recentProjects.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "40px 0",
            color: "var(--text-muted)", fontSize: 14,
          }}>
            暂无项目，去「灵感创作」开始第一个吧
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {recentProjects.map((p, i) => {
              const statusInfo = STATUS_MAP[p.status] || STATUS_MAP.draft;
              return (
                <button
                  key={p.id}
                  onClick={() => onNavigate("editor", p.id)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(0, 1fr) auto auto auto",
                    gap: 16,
                    alignItems: "center",
                    padding: "14px 18px",
                    background: "rgba(255,255,255,.02)",
                    border: "1px solid rgba(255,255,255,.04)",
                    borderRadius: 10,
                    cursor: "pointer",
                    textAlign: "left",
                    animation: `nc-fade-in .3s ease-out ${0.4 + i * 0.06}s both`,
                    transition: "all .2s ease",
                    minHeight: 0,
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = "rgba(255,107,53,.06)";
                    e.currentTarget.style.borderColor = "rgba(255,107,53,.2)";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "rgba(255,255,255,.02)";
                    e.currentTarget.style.borderColor = "rgba(255,255,255,.04)";
                  }}
                >
                  {/* Title */}
                  <div style={{
                    fontSize: 14, fontWeight: 600,
                    color: "var(--text-primary)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {p.title}
                  </div>
                  {/* Status badge */}
                  <span style={{
                    fontSize: 12, fontWeight: 500,
                    padding: "3px 10px",
                    borderRadius: 9999,
                    background: statusInfo.bg,
                    color: statusInfo.color,
                    whiteSpace: "nowrap",
                  }}>
                    {statusInfo.label}
                  </span>
                  {/* Time */}
                  <span style={{
                    fontSize: 12, color: "var(--text-muted)",
                    whiteSpace: "nowrap",
                  }}>
                    {timeAgo(p.updated_at)}
                  </span>
                  {/* Word count + chevron */}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <span style={{
                      fontSize: 12, color: "var(--text-muted)",
                      whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums",
                    }}>
                      {p.total_words > 0 ? `${(p.total_words / 10000).toFixed(1)} 万字` : "—"}
                    </span>
                    <ChevronRight size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Global spin animation (for Loader2) ──────────────────────────── */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
