import React, { useState, useEffect } from "react";
import {
  TrendingUp, Zap, Target, Plus, BookOpen, Trash2, Edit3,
  RefreshCw, Eye, X, Star, FileText,
} from "lucide-react";
import { api } from "../lib/api";
import { Pagination, Accordion } from "./ui";
import { usePagination } from "../hooks/usePagination";
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
  const [hotspotTotal, setHotspotTotal] = useState(0);

  // Overview state
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // Article library state
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [articleTotal, setArticleTotal] = useState(0);
  const [articleLoading, setArticleLoading] = useState(false);
  const [articleDetail, setArticleDetail] = useState<ArticleDetail | null>(null);
  const [editArticle, setEditArticle] = useState<{ id: string; title: string; body: string } | null>(null);

  const hotspotPager = usePagination({ total: hotspotTotal, pageSize: 10, mode: "server" });
  const articlePager = usePagination({ total: articleTotal, pageSize: 10, mode: "server" });

  // ── Hotspot loading ──────────────────────────────────────────
  const loadHotspots = async () => {
    setLoading(true);
    setError("");
    try {
      const platformsParam = selectedPlatforms.length ? selectedPlatforms.join(",") : "";
      const result = await api(`/api/v1/hotspots/paginated?platforms=${platformsParam}&page=${hotspotPager.page}&page_size=${hotspotPager.pageSize}`);
      const data = result.data || {};
      setHotspots(data.items || []);
      setHotspotTotal(data.total || 0);
    } catch (caught) {
      setError(`热点获取失败：${String(caught)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadHotspots();
  }, [hotspotPager.page, hotspotPager.pageSize, selectedPlatforms]);

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
      const result = await api(`/api/v1/articles?page=${articlePager.page}&page_size=${articlePager.pageSize}`);
      const data = result.data || {};
      setArticles(data.articles || []);
      setArticleTotal(data.total || 0);
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
  }, [tab, articlePager.page, articlePager.pageSize]);

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
    hotspotPager.setPage(1);
  };

  // ── Trend badge color ────────────────────────────────────────
  const trendBadgeClass = (trend: string) => {
    switch (trend) {
      case "rising": return "badge orange";
      case "new": return "badge cyan";
      case "cooling": return "badge red";
      default: return "badge gray";
    }
  };

  const trendLabel = (trend: string) => {
    switch (trend) {
      case "rising": return "📈 上升";
      case "new": return "🆕 新品";
      case "cooling": return "📉 降温";
      default: return "➡️ 平稳";
    }
  };

  // ── Hotness bar ──────────────────────────────────────────────
  const hotnessColor = (val: number) => {
    if (val >= 80) return "#ff5252";
    if (val >= 60) return "#ff9100";
    if (val >= 40) return "#ffc107";
    return "#00e5ff";
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "published": return "badge green";
      case "draft": return "badge purple";
      case "review": return "badge orange";
      default: return "badge gray";
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Page head ──────────────────────────────────────────── */}
      <div className="page-head">
        <div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <TrendingUp size={20} style={{ color: "var(--primary-light)" }} /> 热点看板
          </h1>
          <p>实时追踪全网热点，AI一键生成多平台内容</p>
        </div>
        <div className="head-actions">
          <button
            className="btn-sm"
            disabled={loading}
            onClick={() => { void loadHotspots(); }}
            style={{
              background: "var(--primary)", color: "var(--brand-foreground)",
              display: "flex", alignItems: "center", gap: 6,
            }}
          >
            <RefreshCw size={14} /> {loading ? "加载中…" : "刷新"}
          </button>
        </div>
      </div>

      {/* ── Main tabs ──────────────────────────────────────────── */}
      <div className="tabs">
        <button className={`tab${tab === "hotspots" ? " on" : ""}`} onClick={() => { setTab("hotspots"); setError(""); }}>
          📊 今日热点
        </button>
        <button className={`tab${tab === "overview" ? " on" : ""}`} onClick={() => { setTab("overview"); setError(""); }}>
          🔍 热点总览
        </button>
        <button className={`tab${tab === "library" ? " on" : ""}`} onClick={() => { setTab("library"); setError(""); }}>
          📚 文库
        </button>
      </div>

      {/* ── Notices ────────────────────────────────────────────── */}
      {error && (
        <div className="card" style={{ borderColor: "var(--border-strong)", padding: 12 }}>
          <span style={{ color: "var(--red)", fontSize: 13 }}>{error}</span>
        </div>
      )}
      {notice && (
        <div className="card" style={{ borderColor: "var(--border-strong)", padding: 12 }}>
          <span style={{ color: "var(--green)", fontSize: 13 }}>{notice}</span>
        </div>
      )}

      {/* ── Toast ──────────────────────────────────────────────── */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 999,
          background: "var(--bg-elev)",
          backdropFilter: "blur(16px)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--r-lg)", padding: "14px 20px",
          display: "flex", alignItems: "center", gap: 12,
          boxShadow: "var(--shadow-card)",
          animation: "fadeUp 0.3s ease-out",
        }}>
          <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-1)" }}>✅ {toast.message}</span>
          {toast.actionLabel && (
            <button
              onClick={toast.onAction}
              className="btn-sm"
              style={{ background: "var(--primary)", color: "var(--brand-foreground)" }}
            >
              {toast.actionLabel}
            </button>
          )}
          <button
            onClick={() => setToast(null)}
            className="btn-ghost"
            style={{ padding: "2px 6px", fontSize: 16 }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ── Tab 1: 今日热点 ──────────────────────────────────── */}
      {tab === "hotspots" && (
        <>
          {/* Platform filter tabs */}
          <div className="tabs">
            {ALL_PLATFORMS.map(p => (
              <button
                key={p.key}
                className={`tab${selectedPlatforms.includes(p.key) ? " on" : ""}`}
                onClick={() => togglePlatform(p.key)}
              >
                {p.name}
              </button>
            ))}
            {selectedPlatforms.length > 0 && (
              <button
                className="tab"
                style={{ color: "var(--red)" }}
                onClick={() => { setSelectedPlatforms([]); hotspotPager.setPage(1); }}
              >
                清除筛选
              </button>
            )}
          </div>

          {/* Hotspot cards as activity/cards */}
          {loading ? (
            <div className="empty">
              <div className="empty-ic">
                <RefreshCw size={24} style={{ animation: "spin 1s linear infinite" }} />
              </div>
              <h3>正在加载热点</h3>
              <p>正在从各平台抓取最新热点数据…</p>
            </div>
          ) : hotspots.length === 0 ? (
            <div className="empty">
              <div className="empty-ic">
                <Zap size={24} />
              </div>
              <h3>暂无热点数据</h3>
              <p>当前筛选条件下没有热点内容，请尝试切换平台或刷新。</p>
            </div>
          ) : (
            <div className="card-grid">
              {hotspots.map((h, i) => {
                const cardKey = `${h.source}:${h.title}`;
                const busy = busyKey === cardKey;
                const generated = generatedKeys.has(cardKey);
                return (
                  <div key={i} className="card" style={{ display: "flex", flexDirection: "column", gap: 10, padding: 16 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.4, flex: 1 }}>
                        {h.title?.slice(0, 60)}
                      </div>
                      <span className={trendBadgeClass(h.trend)}>
                        {trendLabel(h.trend)}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "var(--text-3)" }}>
                      <span>{h.category}</span>
                    </div>
                    {/* Hotness bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--bg-hover)", overflow: "hidden" }}>
                        <div style={{
                          width: `${h.hotness}%`, height: "100%", borderRadius: 3,
                          background: hotnessColor(h.hotness), transition: "width 0.3s",
                        }} />
                      </div>
                      <span style={{ fontSize: 12, color: hotnessColor(h.hotness), fontWeight: 600, minWidth: 36 }}>
                        {h.hotness}
                      </span>
                    </div>
                    <Accordion items={[{
                      key: `hs-detail-${cardKey}`,
                      title: "查看来源详情",
                      defaultOpen: false,
                      content: (
                        <div style={{ fontSize: 12, lineHeight: 1.9, color: "var(--text-2)" }}>
                          <div>平台：{h.source_name || h.source}</div>
                          {h.url ? (
                            <div>来源链接：<a href={h.url} target="_blank" rel="noreferrer" style={{ color: "var(--primary-light)" }}>{h.url}</a></div>
                          ) : null}
                          {h.fetched_at ? <div>发布时间：{new Date(h.fetched_at).toLocaleString()}</div> : null}
                          <div>热度指数：{h.hotness}</div>
                        </div>
                      ),
                    }]} />
                    <button
                      disabled={busy}
                      onClick={() => void generate(h)}
                      className="btn-sm"
                      style={{
                        background: generated
                          ? "var(--success-bg)" : "var(--primary)",
                        color: generated ? "var(--green)" : "var(--brand-foreground)",
                        opacity: busy ? 0.6 : 1,
                        justifyContent: "center",
                      }}
                    >
                      {busy ? "⏳ 生成中…" : generated ? "✓ 已生成" : <><Plus size={12} /> 一键生成</>}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          {hotspotTotal > 0 && (
            <Pagination
              mode="server"
              page={hotspotPager.page}
              pageSize={hotspotPager.pageSize}
              total={hotspotTotal}
              onPageChange={hotspotPager.setPage}
              onPageSizeChange={hotspotPager.setPageSize}
              pageSizeOptions={[10, 20, 50]}
            />
          )}
        </>
      )}

      {/* ── Tab 2: 热点总览 ──────────────────────────────────── */}
      {tab === "overview" && (
        <>
          {overviewLoading ? (
            <div className="empty">
              <div className="empty-ic">
                <RefreshCw size={24} style={{ animation: "spin 1s linear infinite" }} />
              </div>
              <h3>AI 分析中</h3>
              <p>正在生成热点总览与选题推荐…</p>
            </div>
          ) : overview ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* AI Summary */}
              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <FileText size={18} /> AI 热点摘要
                  </div>
                </div>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: "var(--text-2)", margin: 0 }}>
                  {overview.summary}
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
                {/* Categories */}
                <div className="card">
                  <div className="card-head">
                    <div className="card-title">
                      <Target size={18} /> 热点分类
                    </div>
                    <span className="card-sub">{Object.keys(overview.categories).length} 类</span>
                  </div>
                  {Object.entries(overview.categories).map(([cat, count]) => (
                    <div key={cat} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13, borderBottom: "1px solid var(--border)" }}>
                      <span style={{ color: "var(--text-2)" }}>{cat}</span>
                      <span style={{ color: "var(--cyan)", fontWeight: 600 }}>{count}</span>
                    </div>
                  ))}
                </div>

                {/* Trends */}
                <div className="card">
                  <div className="card-head">
                    <div className="card-title">
                      <TrendingUp size={18} /> 趋势分析
                    </div>
                    <span className="card-sub">{overview.trends.length} 项</span>
                  </div>
                  {overview.trends.map(t => (
                    <div key={t.name} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13, borderBottom: "1px solid var(--border)" }}>
                      <span style={{ color: "var(--text-2)" }}>{t.label}</span>
                      <span style={{ color: "var(--orange)", fontWeight: 600 }}>{t.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Predicted viral */}
              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <Zap size={18} /> 爆文预测
                  </div>
                  <span className="card-sub">{overview.predicted_viral.length} 条</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {overview.predicted_viral.map((v, i) => (
                    <div key={i} className="activity" style={{ alignItems: "center" }}>
                      <div className="av-sm">
                        <Star size={14} />
                      </div>
                      <div>
                        <p style={{ fontWeight: 500 }}>{v.title}</p>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <span className="badge gray">{v.source}</span>
                          <span style={{ fontSize: 12, fontWeight: 600, color: hotnessColor(v.hotness) }}>
                            热度 {v.hotness}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommended angles */}
              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <BookOpen size={18} /> 推荐选题
                  </div>
                  <span className="card-sub">{overview.recommended_angles.length} 个</span>
                </div>
                <div className="card-grid">
                  {overview.recommended_angles.map((ra, i) => (
                    <div key={i} className="card" style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{ra.title}</div>
                      <div style={{ fontSize: 12, color: "var(--text-3)" }}>{ra.source} · 热度 {ra.hotness}</div>
                      <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.5 }}>{ra.angle}</div>
                      <button
                        onClick={() => {
                          const h = overview.category_items?.[Object.keys(overview.category_items || {})[0]]?.find(x => x.title?.slice(0, 40) === ra.title);
                          if (h) void generate(h);
                        }}
                        className="btn-sm"
                        style={{ background: "var(--primary)", color: "var(--brand-foreground)", justifyContent: "center" }}
                      >
                        <Plus size={12} /> 一键生成
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty">
              <div className="empty-ic">
                <FileText size={24} />
              </div>
              <h3>暂无总览数据</h3>
              <p>请刷新热点后重试。</p>
            </div>
          )}
        </>
      )}

      {/* ── Tab 3: 文库 ──────────────────────────────────────── */}
      {tab === "library" && (
        <>
          {articleDetail ? (
            /* Article detail */
            <div className="card">
              <div className="card-head">
                <div className="card-title">{articleDetail.title}</div>
                <button onClick={() => setArticleDetail(null)} className="btn-ghost" style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <X size={14} /> 关闭
                </button>
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                <span className="badge cyan">{articleDetail.platform}</span>
                {articleDetail.hotspot_title && <span className="badge gray">📌 {articleDetail.hotspot_title}</span>}
                <span className={statusBadge(articleDetail.status)}>{articleDetail.status}</span>
                <span style={{ fontSize: 12, color: "var(--text-3)" }}>{articleDetail.created_at}</span>
              </div>
              <div className="novel-prose" style={{ background: "var(--bg-hover)", padding: 16, borderRadius: "var(--r-sm)", maxHeight: "60vh", overflow: "auto" }}>
                {articleDetail.full_text || "暂无内容"}
              </div>
            </div>
          ) : editArticle ? (
            /* Edit modal */
            <div className="card">
              <div className="card-head">
                <div className="card-title">编辑文章</div>
              </div>
              <div className="field">
                <label>标题</label>
                <input
                  className="form-input"
                  value={editArticle.title}
                  onChange={e => setEditArticle({ ...editArticle, title: e.target.value })}
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={saveEdit} className="btn-sm" style={{ background: "var(--primary)", color: "var(--brand-foreground)" }}>
                  保存
                </button>
                <button onClick={() => setEditArticle(null)} className="btn-ghost">
                  取消
                </button>
              </div>
            </div>
          ) : (
            <>
              {articleLoading ? (
                <div className="empty">
                  <div className="empty-ic">
                    <RefreshCw size={24} style={{ animation: "spin 1s linear infinite" }} />
                  </div>
                  <h3>加载中</h3>
                </div>
              ) : articles.length === 0 ? (
                <div className="empty">
                  <div className="empty-ic">
                    <BookOpen size={24} />
                  </div>
                  <h3>文库为空</h3>
                  <p>从今日热点生成文章后在此查看。</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>平台</th>
                        <th>热点来源</th>
                        <th>状态</th>
                        <th>创建时间</th>
                        <th style={{ textAlign: "right" }}>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {articles.map(a => (
                        <tr key={a.id}>
                          <td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {a.title}
                          </td>
                          <td><span className="badge cyan">{a.platform}</span></td>
                          <td className="cell-sub">{a.hotspot_title?.slice(0, 24) || "—"}</td>
                          <td><span className={statusBadge(a.status)}>{a.status}</span></td>
                          <td className="cell-sub">{a.created_at?.slice(0, 10)}</td>
                          <td>
                            <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                              <button onClick={() => void viewArticle(a.id)} className="btn-ghost" title="查看" style={{ padding: "4px 8px" }}>
                                <Eye size={14} />
                              </button>
                              <button onClick={() => startEdit(a)} className="btn-ghost" title="编辑" style={{ padding: "4px 8px", color: "var(--yellow)" }}>
                                <Edit3 size={14} />
                              </button>
                              <button onClick={() => void deleteArticle(a.id, a.title)} className="btn-ghost" title="删除" style={{ padding: "4px 8px", color: "var(--red)" }}>
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Article pagination */}
              <Pagination
                mode="server"
                page={articlePager.page}
                pageSize={articlePager.pageSize}
                total={articleTotal}
                onPageChange={articlePager.setPage}
                onPageSizeChange={articlePager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
