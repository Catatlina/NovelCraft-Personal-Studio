import React, { useState, useEffect } from "react";
import {
  TrendingUp, Zap, Target, Plus, BookOpen, Trash2, Edit3,
  RefreshCw, Eye, X, ChevronLeft, ChevronRight, Star, FileText
} from "lucide-react";
import { api } from "../lib/api";
import "../styles/novel-prose.css";

type HotspotItem = {
  title: string;
  source: string;
  source_name: string;
  category: string;
  hotness: number;
  trend: string;
  url: string;
  freshness: number;
  fetched_at: string;
};

type OverviewData = {
  summary: string;
  categories: Record<string, number>;
  category_items?: Record<string, HotspotItem[]>;
  trends: Array<{ name: string; label: string; count: number }>;
  predicted_viral: Array<{ title: string; source: string; hotness: number; reason: string }>;
  recommended_angles: Array<{ title: string; source: string; angle: string; hotness: number }>;
  total_hotspots: number;
  sources_active: string[];
  generated_at: string;
};

type ArticleItem = {
  id: string;
  title: string;
  summary: string;
  platform: string;
  hotspot_title: string;
  hotspot_source: string;
  status: string;
  created_at: string;
  project_id: string;
};

type ArticleDetail = {
  id: string;
  title: string;
  body: any;
  full_text: string;
  platform: string;
  hotspot_title: string;
  status: string;
  created_at: string;
  project_id: string;
};

const ALL_PLATFORMS = [
  { key: "baidu", name: "百度" },
  { key: "zhihu", name: "知乎" },
  { key: "weibo", name: "微博" },
  { key: "toutiao", name: "头条" },
  { key: "xiaohongshu", name: "小红书" },
  { key: "douyin", name: "抖音" },
  { key: "kuaishou", name: "快手" },
  { key: "bilibili", name: "B站" },
];

const PAGE_SIZE = 12;

export function HotspotDashboard() {
  // Tab state
  const [tab, setTab] = useState<"hotspots" | "overview" | "library">("hotspots");

  // Hotspot state
  const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [notice, setNotice] = useState("");
  const [generatedKeys, setGeneratedKeys] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ message: string; actionLabel?: string; onAction?: () => void } | null>(null);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Overview state
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // Article library state
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [articlePage, setArticlePage] = useState(1);
  const [articleTotalPages, setArticleTotalPages] = useState(1);
  const [articleLoading, setArticleLoading] = useState(false);
  const [articleDetail, setArticleDetail] = useState<ArticleDetail | null>(null);
  const [editArticle, setEditArticle] = useState<{ id: string; title: string; body: string } | null>(null);

  // ── Hotspot loading ──────────────────────────────────────────
  const loadHotspots = async () => {
    setLoading(true);
    setError("");
    try {
      const platformsParam = selectedPlatforms.length ? selectedPlatforms.join(",") : "";
      const result = await api(`/api/v1/hotspots/paginated?platforms=${platformsParam}&page=${page}&page_size=${PAGE_SIZE}`);
      const data = result.data || {};
      setHotspots(data.items || []);
      setTotalPages(data.total_pages || 1);
      setTotalItems(data.total || 0);
    } catch (caught) {
      setError(`热点获取失败：${String(caught)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadHotspots();
  }, [page, selectedPlatforms]);

  // ── Overview loading ─────────────────────────────────────────
  const loadOverview = async () => {
    setOverviewLoading(true);
    try {
      const projects = await api("/api/v1/projects");
      const projectId = projects.data?.[0]?.id || "";
      const result = await api(`/api/v1/hotspots/overview?project_id=${projectId}`);
      setOverview(result.data || null);
    } catch (caught) {
      setError(`总览加载失败：${String(caught)}`);
    } finally {
      setOverviewLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "overview" && !overview) {
      void loadOverview();
    }
  }, [tab]);

  // ── Article library ──────────────────────────────────────────
  const loadArticles = async () => {
    setArticleLoading(true);
    try {
      const result = await api(`/api/v1/articles?page=${articlePage}&page_size=${PAGE_SIZE}`);
      const data = result.data || {};
      setArticles(data.articles || []);
      setArticleTotalPages(data.total_pages || 1);
    } catch (caught) {
      setError(`文库加载失败：${String(caught)}`);
    } finally {
      setArticleLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "library") {
      void loadArticles();
    }
  }, [tab, articlePage]);

  // ── One-click generate ───────────────────────────────────────
  const generate = async (h: HotspotItem) => {
    const cardKey = `${h.source}:${h.title}`;
    setBusyKey(cardKey);
    setNotice("");
    setError("");
    try {
      const projects = await api("/api/v1/projects");
      const projectId = projects.data?.[0]?.id;
      if (!projectId) { setError("请先创建项目"); return; }
      const result = await api("/api/v1/hotspots/generate", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          title: h.title,
          source: h.source,
          url: h.url || "",
          platforms: ["wechat", "toutiao", "baijia", "dayu", "xiaohongshu", "douyin"],
        }),
      });
      const count = result.data?.items?.length || 0;
      setNotice(`✅ 已生成 ${count} 篇平台内容草稿。`);
      // Record success on this card + show toast
      setGeneratedKeys(prev => new Set(prev).add(cardKey));
      setToast({
        message: `已生成 ${count} 篇文章`,
        actionLabel: "查看文库 →",
        onAction: () => { setTab("library"); setToast(null); },
      });
      // Auto-dismiss toast after 8 seconds
      setTimeout(() => setToast(prev => prev?.message === `已生成 ${count} 篇文章` ? null : prev), 8000);
    } catch (caught) {
      setError(`内容生成失败：${String(caught)}`);
    } finally {
      setBusyKey("");
    }
  };

  // ── Article view / edit / delete ─────────────────────────────
  const viewArticle = async (id: string) => {
    try {
      const result = await api(`/api/v1/articles/${id}`);
      setArticleDetail(result.data || null);
    } catch (caught) {
      setError(`文章详情加载失败：${String(caught)}`);
    }
  };

  const deleteArticle = async (id: string, title: string) => {
    if (!confirm(`确定删除《${title}》？此操作不可撤销。`)) return;
    try {
      await api(`/api/v1/articles/${id}`, { method: "DELETE" });
      setNotice(`✅ 已删除《${title}》`);
      void loadArticles();
    } catch (caught) {
      setError(`删除失败：${String(caught)}`);
    }
  };

  const startEdit = (article: ArticleItem) => {
    setEditArticle({ id: article.id, title: article.title, body: "" });
  };

  const saveEdit = async () => {
    if (!editArticle) return;
    try {
      await api(`/api/v1/articles/${editArticle.id}`, {
        method: "PUT",
        body: JSON.stringify({ title: editArticle.title, body: editArticle.body }),
      });
      setNotice("✅ 文章已更新");
      setEditArticle(null);
      void loadArticles();
    } catch (caught) {
      setError(`编辑失败：${String(caught)}`);
    }
  };

  // ── Platform toggle ──────────────────────────────────────────
  const togglePlatform = (key: string) => {
    setSelectedPlatforms(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
    setPage(1);
  };

  // ── Trend badge color ────────────────────────────────────────
  const trendStyle = (trend: string) => {
    switch (trend) {
      case "rising": return { bg: "rgba(0,230,118,0.15)", color: "#00e676" };
      case "new": return { bg: "rgba(0,229,255,0.15)", color: "#00e5ff" };
      case "cooling": return { bg: "rgba(255,82,82,0.15)", color: "#ff5252" };
      default: return { bg: "rgba(158,158,158,0.15)", color: "#9e9e9e" };
    }
  };

  // ── Hotness bar ──────────────────────────────────────────────
  const hotnessColor = (val: number) => {
    if (val >= 80) return "#ff5252";
    if (val >= 60) return "#ff9100";
    if (val >= 40) return "#ffc107";
    return "#00e5ff";
  };

  // ── Styles ───────────────────────────────────────────────────
  const tabBtnStyle = (active: boolean) => ({
    padding: "8px 18px",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 14,
    fontWeight: active ? 600 : 400,
    background: active ? "var(--nc-primary, #FF6B35)" : "rgba(255,255,255,0.06)",
    color: active ? "#fff" : "var(--text-muted, #888)",
  });

  const chipStyle = (active: boolean) => ({
    padding: "4px 12px",
    borderRadius: 20,
    border: `1px solid ${active ? "var(--nc-primary, #FF6B35)" : "rgba(255,255,255,0.12)"}`,
    background: active ? "rgba(255,107,53,0.15)" : "transparent",
    color: active ? "var(--nc-primary, #FF6B35)" : "var(--text-muted, #888)",
    fontSize: 12,
    cursor: "pointer",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Header */}
      <div className="panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <TrendingUp size={16} /> 热点看板
        </h3>
        <div style={{ display: "flex", gap: 6 }}>
          <button style={tabBtnStyle(tab === "hotspots")} onClick={() => { setTab("hotspots"); setError(""); }}>
            📊 今日热点
          </button>
          <button style={tabBtnStyle(tab === "overview")} onClick={() => { setTab("overview"); setError(""); }}>
            🔍 热点总览
          </button>
          <button style={tabBtnStyle(tab === "library")} onClick={() => { setTab("library"); setError(""); }}>
            📚 文库
          </button>
        </div>
      </div>

      {error && <div className="panel" style={{ color: "#ff5252", fontSize: 13 }}>{error}</div>}
      {notice && <div className="panel" style={{ color: "#00e676", fontSize: 13 }}>{notice}</div>}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 999,
          background: "var(--nc-card, rgba(22,22,50,0.95))",
          backdropFilter: "blur(16px)",
          border: "1px solid rgba(0,229,255,0.2)",
          borderRadius: 12, padding: "14px 20px",
          display: "flex", alignItems: "center", gap: 12,
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          animation: "slideUp 0.3s ease-out",
        }}>
          <span style={{ fontSize: 14, fontWeight: 500, color: "#e0e0e0" }}>✅ {toast.message}</span>
          {toast.actionLabel && (
            <button
              onClick={toast.onAction}
              style={{
                background: "var(--nc-primary, #FF6B35)", color: "#fff",
                border: "none", borderRadius: 6, padding: "6px 14px",
                fontSize: 13, fontWeight: 600, cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {toast.actionLabel}
            </button>
          )}
          <button
            onClick={() => setToast(null)}
            style={{ background: "transparent", border: "none", color: "#888", cursor: "pointer", fontSize: 16, padding: "2px 6px" }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ── Tab 1: 今日热点 ──────────────────────────────────── */}
      {tab === "hotspots" && (
        <>
          {/* Platform selector chips */}
          <div className="panel" style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>平台筛选：</span>
            {ALL_PLATFORMS.map(p => (
              <button key={p.key} style={chipStyle(selectedPlatforms.includes(p.key))} onClick={() => togglePlatform(p.key)}>
                {p.name}
              </button>
            ))}
            {selectedPlatforms.length > 0 && (
              <button style={{ ...chipStyle(false), color: "#ff5252" }} onClick={() => { setSelectedPlatforms([]); setPage(1); }}>
                清除
              </button>
            )}
            <button disabled={loading} onClick={() => { void loadHotspots(); }} style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, padding: "4px 12px", background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#00e5ff", cursor: "pointer", fontSize: 12 }}>
              <RefreshCw size={12} /> {loading ? "加载中…" : "刷新"}
            </button>
          </div>

          {/* Hotspot cards */}
          {loading ? (
            <div className="panel" style={{ textAlign: "center", color: "var(--text-muted)" }}>正在加载热点…</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {hotspots.map((h, i) => {
                const trendMeta = trendStyle(h.trend);
                const cardKey = `${h.source}:${h.title}`;
                const busy = busyKey === cardKey;
                const generated = generatedKeys.has(cardKey);
                return (
                  <div key={i} className="panel" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.4, flex: 1 }}>{h.title?.slice(0, 60)}</div>
                      <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: trendMeta.bg, color: trendMeta.color, whiteSpace: "nowrap" }}>
                        {h.trend === "rising" ? "📈" : h.trend === "new" ? "🆕" : h.trend === "cooling" ? "📉" : "➡️"}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 11, color: "var(--text-muted)" }}>
                      <span style={{ padding: "1px 6px", borderRadius: 3, background: "rgba(0,229,255,0.1)", color: "#00e5ff" }}>
                        {h.source_name || h.source}
                      </span>
                      <span>{h.category}</span>
                    </div>
                    {/* Hotness bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                        <div style={{ width: `${h.hotness}%`, height: "100%", borderRadius: 3, background: hotnessColor(h.hotness), transition: "width 0.3s" }} />
                      </div>
                      <span style={{ fontSize: 11, color: hotnessColor(h.hotness), fontWeight: 600, minWidth: 36 }}>{h.hotness}</span>
                    </div>
                    <button
                      disabled={busy}
                      onClick={() => void generate(h)}
                      style={{
                        padding: "6px 12px", borderRadius: 6, cursor: busy ? "default" : "pointer",
                        fontSize: 12, fontWeight: 600,
                        background: generated ? "rgba(0,230,118,0.15)" : "var(--nc-primary, #FF6B35)",
                        color: generated ? "#00e676" : "#fff",
                        display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
                        opacity: busy ? 0.6 : 1,
                        border: generated ? "1px solid rgba(0,230,118,0.3)" : "none",
                        transition: "all 0.3s",
                      }}
                    >
                      {busy ? "⏳ 生成中…" : generated ? <>✓ 已生成</> : <><Plus size={12} /> 一键生成</>}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="panel" style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "center" }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#00e5ff", cursor: page <= 1 ? "default" : "pointer", padding: "6px 10px", opacity: page <= 1 ? 0.4 : 1 }}>
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontSize: 13 }}>{page} / {totalPages}（共 {totalItems} 条）</span>
              <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#00e5ff", cursor: page >= totalPages ? "default" : "pointer", padding: "6px 10px", opacity: page >= totalPages ? 0.4 : 1 }}>
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}

      {/* ── Tab 2: 热点总览 ──────────────────────────────────── */}
      {tab === "overview" && (
        <>
          {overviewLoading ? (
            <div className="panel" style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>
              <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} /> AI分析中…
            </div>
          ) : overview ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* AI Summary */}
              <div className="panel">
                <h4 style={{ margin: "0 0 8px", display: "flex", alignItems: "center", gap: 6 }}>
                  <FileText size={14} /> AI 热点摘要
                </h4>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: "var(--text-secondary, #ccc)", margin: 0 }}>
                  {overview.summary}
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
                {/* Categories */}
                <div className="panel">
                  <h4 style={{ margin: "0 0 8px" }}>📂 热点分类</h4>
                  {Object.entries(overview.categories).map(([cat, count]) => (
                    <div key={cat} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <span>{cat}</span>
                      <span style={{ color: "#00e5ff", fontWeight: 600 }}>{count}</span>
                    </div>
                  ))}
                </div>

                {/* Trends */}
                <div className="panel">
                  <h4 style={{ margin: "0 0 8px" }}>📊 趋势分析</h4>
                  {overview.trends.map(t => (
                    <div key={t.name} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <span>{t.label}</span>
                      <span style={{ color: "#FF6B35", fontWeight: 600 }}>{t.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Predicted viral */}
              <div className="panel">
                <h4 style={{ margin: "0 0 8px" }}>🔥 爆文预测</h4>
                <div style={{ display: "grid", gap: 6 }}>
                  {overview.predicted_viral.map((v, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: 13 }}>
                      <Star size={12} color="#ff9100" />
                      <span style={{ flex: 1 }}>{v.title}</span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{v.source}</span>
                      <span style={{ fontSize: 11, color: hotnessColor(v.hotness) }}>{v.hotness}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommended angles */}
              <div className="panel">
                <h4 style={{ margin: "0 0 8px" }}>💡 推荐选题</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 8 }}>
                  {overview.recommended_angles.map((ra, i) => (
                    <div key={i} className="panel" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{ra.title}</div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{ra.source} · 热度 {ra.hotness}</div>
                      <div style={{ fontSize: 12, color: "#ccc", lineHeight: 1.5 }}>{ra.angle}</div>
                      <button
                        onClick={() => {
                          const h = overview.category_items?.[Object.keys(overview.category_items || {})[0]]?.find(x => x.title?.slice(0, 40) === ra.title);
                          if (h) void generate(h);
                        }}
                        style={{
                          padding: "6px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                          fontSize: 12, fontWeight: 600,
                          background: "var(--nc-primary, #FF6B35)", color: "#fff",
                          display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
                        }}
                      >
                        <Plus size={12} /> 一键生成
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="panel" style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>
              暂无总览数据。请刷新热点后重试。
            </div>
          )}
        </>
      )}

      {/* ── Tab 3: 文库 ──────────────────────────────────────── */}
      {tab === "library" && (
        <>
          {articleDetail ? (
            /* Article detail modal */
            <div className="panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ margin: 0 }}>{articleDetail.title}</h3>
                <button onClick={() => setArticleDetail(null)}
                  style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#888", cursor: "pointer", padding: "4px 10px", display: "flex", alignItems: "center", gap: 4 }}>
                  <X size={14} /> 关闭
                </button>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
                平台：{articleDetail.platform} · 热点：{articleDetail.hotspot_title} · 状态：{articleDetail.status} · {articleDetail.created_at}
              </div>
              <div className="novel-prose" style={{ background: "rgba(255,255,255,0.03)", padding: 16, borderRadius: 8, maxHeight: "60vh", overflow: "auto" }}>
                {articleDetail.full_text || "暂无内容"}
              </div>
            </div>
          ) : editArticle ? (
            /* Edit modal */
            <div className="panel">
              <h4 style={{ margin: "0 0 12px" }}>编辑文章</h4>
              <label style={{ fontSize: 12, color: "var(--text-muted)" }}>标题</label>
              <input
                style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.04)", color: "#fff", marginBottom: 12 }}
                value={editArticle.title}
                onChange={e => setEditArticle({ ...editArticle, title: e.target.value })}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={saveEdit} style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--nc-primary, #FF6B35)", color: "#fff", cursor: "pointer" }}>
                  保存
                </button>
                <button onClick={() => setEditArticle(null)} style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.12)", background: "transparent", color: "#888", cursor: "pointer" }}>
                  取消
                </button>
              </div>
            </div>
          ) : (
            <>
              {articleLoading ? (
                <div className="panel" style={{ textAlign: "center", color: "var(--text-muted)" }}>加载中…</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {articles.map(a => (
                    <div key={a.id} className="panel" style={{ padding: 14, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{a.title}</div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 6 }}>
                          {a.summary?.slice(0, 120)}{(a.summary || "").length > 120 ? "…" : ""}
                        </div>
                        <div style={{ display: "flex", gap: 6, fontSize: 11, color: "var(--text-muted)", flexWrap: "wrap" }}>
                          <span style={{ padding: "1px 6px", borderRadius: 3, background: "rgba(0,229,255,0.1)", color: "#00e5ff" }}>{a.platform}</span>
                          {a.hotspot_title && <span>📌 {a.hotspot_title?.slice(0, 20)}</span>}
                          <span>{a.status}</span>
                          <span>{a.created_at?.slice(0, 10)}</span>
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        <button onClick={() => void viewArticle(a.id)}
                          style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, color: "#00e5ff", cursor: "pointer", padding: "4px 8px", display: "flex", alignItems: "center", gap: 2, fontSize: 11 }}>
                          <Eye size={12} /> 查看
                        </button>
                        <button onClick={() => startEdit(a)}
                          style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, color: "#ffc107", cursor: "pointer", padding: "4px 8px", display: "flex", alignItems: "center", gap: 2, fontSize: 11 }}>
                          <Edit3 size={12} /> 编辑
                        </button>
                        <button onClick={() => void deleteArticle(a.id, a.title)}
                          style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, color: "#ff5252", cursor: "pointer", padding: "4px 8px", display: "flex", alignItems: "center", gap: 2, fontSize: 11 }}>
                          <Trash2 size={12} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}
                  {!articles.length && <div className="panel" style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>文库为空。从今日热点生成文章后在此查看。</div>}
                </div>
              )}

              {/* Article pagination */}
              {articleTotalPages > 1 && (
                <div className="panel" style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "center" }}>
                  <button disabled={articlePage <= 1} onClick={() => setArticlePage(p => p - 1)}
                    style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#00e5ff", cursor: articlePage <= 1 ? "default" : "pointer", padding: "6px 10px", opacity: articlePage <= 1 ? 0.4 : 1 }}>
                    <ChevronLeft size={14} />
                  </button>
                  <span style={{ fontSize: 13 }}>{articlePage} / {articleTotalPages}</span>
                  <button disabled={articlePage >= articleTotalPages} onClick={() => setArticlePage(p => p + 1)}
                    style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 6, color: "#00e5ff", cursor: articlePage >= articleTotalPages ? "default" : "pointer", padding: "6px 10px", opacity: articlePage >= articleTotalPages ? 0.4 : 1 }}>
                    <ChevronRight size={14} />
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
