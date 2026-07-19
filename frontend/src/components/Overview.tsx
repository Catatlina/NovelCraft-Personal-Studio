import React, { useState, useEffect, useCallback } from "react";
import { BarChart3, Loader2, RefreshCw, AlertTriangle, TrendingUp } from "lucide-react";
import { api } from "../lib/api";
import "../styles/proto.css";

// ── Types ────────────────────────────────────────────────────────────────────
// Backend envelope shape: { code, message, data } — lib/api returns the full
// envelope, so callers unwrap `.data` manually (see PublishDashboard.tsx).
interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

// Backend contract (publish_hub.aggregate_platform_stats, lines 263-267) returns
// `total_`-prefixed keys. Some earlier contract drafts described unprefixed keys
// (reads/likes/...). We keep the prefixed shape as the source of truth and add the
// unprefixed variants as tolerated aliases so the component survives either form.
interface Totals {
  total_reads?: number;
  total_likes?: number;
  total_shares?: number;
  total_revenue?: number;
  total_posts?: number;
  reads?: number;
  likes?: number;
  shares?: number;
  revenue?: number;
  posts?: number;
}

interface NormalizedTotals {
  reads: number;
  likes: number;
  shares: number;
  revenue: number;
  posts: number;
}

/** Collapse either backend shape (total_-prefixed or unprefixed) into one stable
 *  structure so downstream rendering never depends on which key the backend sent. */
function normalizeTotals(t: Totals | undefined): NormalizedTotals {
  const src = t ?? {};
  return {
    reads: src.total_reads ?? src.reads ?? 0,
    likes: src.total_likes ?? src.likes ?? 0,
    shares: src.total_shares ?? src.shares ?? 0,
    revenue: src.total_revenue ?? src.revenue ?? 0,
    posts: src.total_posts ?? src.posts ?? 0,
  };
}

interface RoiPlatform {
  platform: string;
  posts: number;
  reads: number;
  likes: number;
  revenue: number;
  rpm: number;
}

interface TopPost {
  post_id: string;
  title: string;
  platform: string;
  reads: number;
  likes: number;
  revenue: number;
}

interface TopicSuggestion {
  suggestion: string;
  source_post_id: string | null;
  source_title: string | null;
  platform: string | null;
  reads: number;
}

interface OverviewData {
  metrics_glossary: Record<string, string>;
  totals: Totals;
  roi_by_platform: RoiPlatform[];
  top_posts: TopPost[];
  topic_suggestions: TopicSuggestion[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Inline page banner (loading / error / info). Uses design tokens only — no
 *  bare color values, and never an alert() dialog (doc23). */
function Banner({
  tone,
  children,
  action,
}: {
  tone: "info" | "error";
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  const isError = tone === "error";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "12px 16px",
        borderRadius: "var(--r-md)",
        marginBottom: 16,
        border: `1px solid ${isError ? "var(--red)" : "var(--border-subtle)"}`,
        background: isError ? "rgba(248,113,113,.08)" : "var(--bg-base)",
        color: isError ? "var(--red)" : "var(--text-2)",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{children}</div>
      {action}
    </div>
  );
}

function fmtInt(n: unknown): string {
  const v = typeof n === "number" ? n : Number(n) || 0;
  return v.toLocaleString("zh-CN");
}

function fmtMoney(n: unknown): string {
  const v = typeof n === "number" ? n : Number(n) || 0;
  return `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const PLATFORM_LABELS: Record<string, string> = {
  wechat: "微信",
  toutiao: "头条",
  xiaohongshu: "小红书",
  zhihu: "知乎",
  baijia: "百家号",
  substack: "Substack",
  x: "X / Twitter",
};

function platformLabel(p: string): string {
  if (!p) return "—";
  return PLATFORM_LABELS[p] ?? p;
}

// ── Component ────────────────────────────────────────────────────────────────

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<ApiEnvelope<OverviewData>>("/api/v1/analytics/dashboard")
      .then((resp) => {
        setData(resp?.data ?? null);
      })
      .catch((e: unknown) => {
        const err = e as { payload?: { message?: string }; message?: string };
        setError(err?.payload?.message || err?.message || "数据看板加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const normalizedTotals = normalizeTotals(data?.totals);

  const isEmpty =
    !!data &&
    normalizedTotals.posts === 0 &&
    data.top_posts.length === 0 &&
    data.roi_by_platform.length === 0;

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <b>NovelCraft</b> › 数据概览
      </div>

      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>数据概览</h1>
          <p>效果看板 · 指标口径、汇总、各平台 ROI、Top 内容与可追溯选题建议</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={load} disabled={loading}>
            <RefreshCw size={14} />刷新
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <Banner tone="info">
          <Loader2 size={16} />
          正在加载数据看板…
        </Banner>
      )}

      {/* Error state — never a dialog, always an in-page banner */}
      {!loading && error && (
        <Banner
          tone="error"
          action={
            <button className="btn-sm btn-ghost" onClick={load}>
              重试
            </button>
          }
        >
          <AlertTriangle size={16} />
          {error}
        </Banner>
      )}

      {/* Empty-data state */}
      {!loading && !error && data && isEmpty && (
        <Banner tone="info">
          <BarChart3 size={16} />
          暂无回流数据。发布内容并采集阅读/互动/收益后，这里会自动汇总。
        </Banner>
      )}

      {/* Data view */}
      {!loading && !error && data && (
        <>
          {/* Metrics glossary */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head">
              <div className="card-title">
                <TrendingUp size={18} />
                指标口径
              </div>
              <span className="card-sub">数据含义说明</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 160 }}>指标</th>
                    <th>口径说明</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.metrics_glossary || {}).map(([key, desc]) => (
                    <tr key={key}>
                      <td>
                        <b>{key}</b>
                      </td>
                      <td style={{ color: "var(--text-2)" }}>{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Totals — 5 summary cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: 16,
              marginBottom: 16,
            }}
          >
            <SummaryCard label="总阅读" value={fmtInt(normalizedTotals.reads)} tone="var(--primary-light)" />
            <SummaryCard label="总点赞" value={fmtInt(normalizedTotals.likes)} tone="var(--orange)" />
            <SummaryCard label="总分享" value={fmtInt(normalizedTotals.shares)} tone="var(--cyan)" />
            <SummaryCard label="总收益" value={fmtMoney(normalizedTotals.revenue)} tone="var(--green)" />
            <SummaryCard label="已发布内容" value={fmtInt(normalizedTotals.posts)} tone="var(--text-1)" />
          </div>

          {/* Two columns: ROI table + Top posts */}
          <div className="layout-2" style={{ marginBottom: 16 }}>
            {/* ROI by platform */}
            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <TrendingUp size={18} />
                  各平台 ROI
                </div>
                <span className="card-sub">收益 / 千次阅读</span>
              </div>
              <div className="table-wrap">
                {data.roi_by_platform.length === 0 ? (
                  <div className="empty" style={{ border: "none", padding: 24 }}>
                    <p>暂无平台数据</p>
                  </div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>平台</th>
                        <th>内容</th>
                        <th>阅读</th>
                        <th>点赞</th>
                        <th>收益</th>
                        <th>RPM</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.roi_by_platform.map((r) => (
                        <tr key={r.platform}>
                          <td>
                            <b>{platformLabel(r.platform)}</b>
                            <div className="cell-sub">{r.platform}</div>
                          </td>
                          <td>{fmtInt(r.posts)}</td>
                          <td>{fmtInt(r.reads)}</td>
                          <td>{fmtInt(r.likes)}</td>
                          <td>{fmtMoney(r.revenue)}</td>
                          <td>{fmtMoney(r.rpm)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Top posts */}
            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <BarChart3 size={18} />
                  Top 内容
                </div>
                <span className="card-sub">按阅读排序</span>
              </div>
              <div className="table-wrap">
                {data.top_posts.length === 0 ? (
                  <div className="empty" style={{ border: "none", padding: 24 }}>
                    <p>暂无内容数据</p>
                  </div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>平台</th>
                        <th>阅读</th>
                        <th>点赞</th>
                        <th>收益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_posts.map((p) => (
                        <tr key={p.post_id}>
                          <td>
                            <b>{p.title || "（无标题）"}</b>
                          </td>
                          <td>{platformLabel(p.platform)}</td>
                          <td>{fmtInt(p.reads)}</td>
                          <td>{fmtInt(p.likes)}</td>
                          <td>{fmtMoney(p.revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* Topic suggestions */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                <TrendingUp size={18} />
                选题建议
              </div>
              <span className="card-sub">基于真实回流数据可追溯</span>
            </div>
            {data.topic_suggestions.length === 0 ? (
              <div className="empty" style={{ border: "none", padding: 24 }}>
                <p>暂无选题建议</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {data.topic_suggestions.map((s, i) => (
                  <div
                    key={s.source_post_id ?? `s-${i}`}
                    className="ticket"
                    style={{ margin: 0 }}
                  >
                    <h5>{s.suggestion}</h5>
                    <div className="meta">
                      {s.source_title && <span className="badge gray">{s.source_title}</span>}
                      {s.platform && <span className="badge cyan">{platformLabel(s.platform)}</span>}
                      {typeof s.reads === "number" && <span>{fmtInt(s.reads)} 阅读</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        <div
          className="stat-ic"
          style={{ background: "var(--bg-base)", color: tone, border: "1px solid var(--border-subtle)" }}
        >
          <TrendingUp size={16} />
        </div>
      </div>
      <div className="stat-val">{value}</div>
    </div>
  );
}
