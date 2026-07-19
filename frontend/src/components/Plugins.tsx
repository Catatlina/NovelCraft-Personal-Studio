import React, { useState, useEffect, useCallback } from "react";
import { Puzzle, Loader2, RefreshCw, AlertTriangle, CheckCircle2, Download, Power, Ban } from "lucide-react";
import { api } from "../lib/api";

// ── Types ────────────────────────────────────────────────────────────────────
// lib/api returns the full envelope { code, message, data }; unwrap `.data`.
interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

interface SkillItem {
  name: string;
  category: string;
  source: string;
  cached: boolean;
}

interface SkillsData {
  status: "ok" | "unavailable";
  skill_count: number;
  skills: SkillItem[];
  source: string;
  error?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

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
        background: isError ? "var(--danger-bg)" : "var(--bg-base)",
        color: isError ? "var(--red)" : "var(--text-2)",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{children}</div>
      {action}
    </div>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  hotspot: "热点",
  account: "账号",
  source: "来源",
  creative: "创作",
  analysis: "分析",
  retrieval: "检索",
  tool: "工具",
};

function categoryLabel(c: string): string {
  if (!c) return "其他";
  return CATEGORY_LABELS[c] ?? c;
}

// ── Component ────────────────────────────────────────────────────────────────

export function Plugins() {
  const [data, setData] = useState<SkillsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<ApiEnvelope<SkillsData>>("/api/v1/skills/community")
      .then((resp) => {
        setData(resp?.data ?? null);
      })
      .catch((e: unknown) => {
        const err = e as { payload?: { message?: string }; message?: string };
        setError(err?.payload?.message || err?.message || "技能目录加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const unavailable = !!data && data.status === "unavailable";
  const showCatalog = !!data && data.status === "ok";

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <b>NovelCraft</b> › 插件管理
      </div>

      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>插件管理</h1>
          <p>社区技能目录 · 安装 / 启用状态</p>
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
          正在加载社区技能…
        </Banner>
      )}

      {/* Network error state */}
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

      {/* Upstream unavailable — surface the real error, never fake success */}
      {!loading && !error && unavailable && (
        <Banner
          tone="error"
          action={
            <button className="btn-sm btn-ghost" onClick={load}>
              重试
            </button>
          }
        >
          <AlertTriangle size={16} />
          <span>
            技能源暂不可用：{data?.error || "上游服务无响应"}
          </span>
        </Banner>
      )}

      {/* Catalog */}
      {!loading && showCatalog && (
        <>
          <Banner tone="info">
            <CheckCircle2 size={16} />
            <span>
              共 {data?.skill_count ?? data?.skills.length ?? 0} 个社区技能 · 来源：
              <code style={{ marginLeft: 6, color: "var(--text-1)" }}>{data?.source}</code>
            </span>
          </Banner>

          {data!.skills.length === 0 ? (
            <div className="empty">
              <div className="empty-ic">
                <Puzzle size={48} />
              </div>
              <h3>暂无技能</h3>
              <p>当前技能源没有返回可安装的技能。</p>
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 16,
              }}
            >
              {data!.skills.map((s) => (
                <div className="card" key={s.name} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <div
                      className="qic"
                      style={{
                        background: "var(--primary-dim)",
                        color: "var(--primary-light)",
                        width: 38,
                        height: 38,
                        flexShrink: 0,
                      }}
                    >
                      <Puzzle size={18} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <strong style={{ fontSize: 14, color: "var(--text-1)" }}>{s.name}</strong>
                      <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                        <span className="badge gray">{categoryLabel(s.category)}</span>
                        {s.cached ? (
                          <span className="badge green">
                            <CheckCircle2 size={11} style={{ marginRight: 3 }} />
                            已缓存
                          </span>
                        ) : (
                          <span className="badge cyan">远程</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-3)",
                      wordBreak: "break-all",
                    }}
                  >
                    来源：{s.source}
                  </div>

                  {/* 安装 / 启用 / 禁用 —— 后端暂未提供变更接口，按钮置灰并标注 */}
                  <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
                    <button className="btn-sm btn-ghost" disabled title="后端暂未提供安装接口">
                      <Download size={13} />
                      安装
                    </button>
                    <button className="btn-sm btn-ghost" disabled title="后端暂未提供启用接口">
                      <Power size={13} />
                      启用
                    </button>
                    <button className="btn-sm btn-ghost" disabled title="后端暂未提供禁用接口">
                      <Ban size={13} />
                      禁用
                    </button>
                  </div>
                  <p style={{ fontSize: 11, color: "var(--text-3)", margin: 0 }}>
                    后端暂未提供安装 / 启用 / 禁用接口，操作按钮仅作展示。
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
