import React, { useState, useEffect, useCallback, useMemo } from "react";
import { FlaskConical, Loader2, RefreshCw, AlertTriangle, Play, FileText } from "lucide-react";
import { api } from "../lib/api";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

// ── Types ────────────────────────────────────────────────────────────────────
// lib/api returns the full envelope { code, message, data }; unwrap `.data`.
interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

interface PromptRow {
  id?: string;
  name?: string;
  version?: string | number;
  model?: string;
  category?: string;
  upstream?: string;
  template?: string;
  golden_cases?: unknown; // number | unknown[] | undefined
  [key: string]: unknown;
}

interface LabResult {
  model: string;
  output?: string;
  status: "ok" | "error";
  error?: string;
}

interface LabResponse {
  prompt?: string;
  models?: string | string[];
  results?: LabResult[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Normalize a prompt registry payload into PromptRow[]. Tolerates a bare array
 *  OR an enveloped { data: [...] } / { items: [...] } shape (defensive). */
function asPromptList(v: unknown): PromptRow[] {
  if (Array.isArray(v)) return v as PromptRow[];
  if (v && typeof v === "object") {
    const rec = v as Record<string, unknown>;
    if (Array.isArray(rec.data)) return rec.data as PromptRow[];
    if (Array.isArray(rec.items)) return rec.items as PromptRow[];
  }
  return [];
}

/** golden_cases may be a count (number) or an array — surface a stable count. */
function goldenCount(v: unknown): number {
  if (Array.isArray(v)) return v.length;
  if (typeof v === "number") return v;
  return 0;
}

/** Inline page banner (loading / error / info). Tokens only, never alert(). */
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

const PLACEHOLDER = "—";

// ── Component ────────────────────────────────────────────────────────────────

export function Prompts({ prompts, projectId }: { prompts: any[]; projectId: string }) {
  // Registry list (read-only). Seeded from the prop, re-fetched on refresh.
  const [list, setList] = useState<PromptRow[]>(() => asPromptList(prompts));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Lab (A/B) state
  const [selected, setSelected] = useState("");
  const [inputText, setInputText] = useState("");
  const [models, setModels] = useState("deepseek-chat");
  const [labLoading, setLabLoading] = useState(false);
  const [labError, setLabError] = useState("");
  const [lab, setLab] = useState<LabResponse | null>(null);

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api<ApiEnvelope<PromptRow[]> | PromptRow[]>("/api/v1/admin/prompts")
      .then((resp) => {
        setList(asPromptList(resp));
      })
      .catch((e: unknown) => {
        const err = e as { payload?: { message?: string }; message?: string };
        setError(err?.payload?.message || err?.message || "Prompt 注册表加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  // Fetch authoritative data on mount (idempotent with parent's load), and keep
  // the list in sync if the parent later passes a fresh prop.
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setList((prev) => (prev.length === 0 ? asPromptList(prompts) : prev));
  }, [prompts]);

  const names = useMemo(
    () => Array.from(new Set(list.map((p) => p.name).filter((n): n is string => !!n))),
    [list],
  );

  // Default the lab dropdown to the first available prompt name.
  useEffect(() => {
    if (!selected && names.length > 0) setSelected(names[0]);
  }, [names, selected]);

  const runLab = useCallback(async () => {
    if (!selected) {
      setLabError("请先选择一个 Prompt");
      return;
    }
    if (!inputText.trim()) {
      setLabError("请输入用于对比的输入文本（input_text）");
      return;
    }
    setLabLoading(true);
    setLabError("");
    setLab(null);
    try {
      // Real A/B endpoint. api() returns the envelope, so unwrap `.data`.
      const r = await api<any>("/api/v1/prompts/lab", {
        method: "POST",
        body: JSON.stringify({
          prompt_name: selected,
          input_text: inputText,
          project_id: projectId,
          models,
        }),
      });
      const data = (r && typeof r === "object" && "data" in r ? r.data : r) as LabResponse;
      setLab(data ?? {});
    } catch (e: unknown) {
      const err = e as { payload?: { message?: string; detail?: string }; message?: string };
      setLabError(
        err?.payload?.message ||
          err?.payload?.detail ||
          err?.message ||
          "实验室对比请求失败",
      );
    } finally {
      setLabLoading(false);
    }
  }, [selected, inputText, projectId, models]);

  const toggle = (key: string) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const results = lab?.results ?? [];

  const listPager = usePagination({ items: list, pageSize: 10, mode: "client" });

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <b>NovelCraft</b> › Prompt 管理
      </div>

      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>Prompt 管理</h1>
          <p>后端注册表（只读）· 浏览 Prompt 版本，并在实验室中对多个模型做对比</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={load} disabled={loading}>
            <RefreshCw size={14} />
            刷新
          </button>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 12 }}>
          Prompt 版本由后端注册表管理，前端仅可读与实验室对比，不提供写接口。
        </p>
      </div>

      {/* Loading state */}
      {loading && (
        <Banner tone="info">
          <Loader2 size={16} />
          正在加载 Prompt 注册表…
        </Banner>
      )}

      {/* Network / load error — never alert(), always an in-page banner */}
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

      {/* Intro note */}
      <Banner tone="info">
        Prompt 来自后端注册表，前端只读。下方列表可展开查看 golden_cases 与模板；右侧
        「实验室」可对同一 Prompt 在多个模型上运行并对比输出。
      </Banner>

      {/* ============ Registry list ============ */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <div className="card-title">
            <FileText size={18} />
            Prompt 注册表
          </div>
          <span className="card-sub">{list.length} 条</span>
        </div>

        {!loading && !error && list.length === 0 ? (
          <div className="empty" style={{ border: "none", padding: 24 }}>
            <p>暂无 Prompt 注册表数据</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>名称</th>
                  <th>版本</th>
                  <th>模型</th>
                  <th>分类 / 来源</th>
                </tr>
              </thead>
              <tbody>
                {listPager.pageData.map((p, i) => {
                  const key = p.id ?? `${p.name ?? "p"}-${p.version ?? i}-${i}`;
                  const open = !!expanded[key];
                  const gc = goldenCount(p.golden_cases);
                  return (
                    <React.Fragment key={key}>
                      <tr
                        onClick={() => toggle(key)}
                        style={{ cursor: "pointer" }}
                        title="点击展开 golden_cases 与模板"
                      >
                        <td>
                          <b style={{ color: "var(--text-1)" }}>{p.name ?? PLACEHOLDER}</b>
                        </td>
                        <td>{p.version ?? PLACEHOLDER}</td>
                        <td>{p.model ?? PLACEHOLDER}</td>
                        <td>{p.category ?? p.upstream ?? PLACEHOLDER}</td>
                      </tr>
                      {open && (
                        <tr>
                          <td colSpan={4} style={{ background: "var(--bg-muted)", whiteSpace: "normal" }}>
                            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--text-2)" }}>
                              <span>
                                Golden cases：<b style={{ color: "var(--text-1)" }}>{gc}</b>
                              </span>
                              {p.upstream && <span>upstream：{String(p.upstream)}</span>}
                              {p.category && <span>category：{String(p.category)}</span>}
                              {p.model && <span>model：{String(p.model)}</span>}
                            </div>
                            {p.template && (
                              <pre
                                style={{
                                  marginTop: 10,
                                  padding: 12,
                                  background: "var(--bg-base)",
                                  border: "1px solid var(--border-subtle)",
                                  borderRadius: "var(--r-sm)",
                                  fontSize: 12,
                                  color: "var(--text-2)",
                                  whiteSpace: "pre-wrap",
                                  overflowX: "auto",
                                }}
                              >
                                {String(p.template)}
                              </pre>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
            <Pagination
              page={listPager.page}
              pageSize={listPager.pageSize}
              total={list.length}
              onPageChange={listPager.setPage}
              onPageSizeChange={listPager.setPageSize}
              pageSizeOptions={[10, 20, 50, 100]}
            />
          </div>
        )}
        <p style={{ fontSize: 11, color: "var(--text-3)", margin: "12px 0 0" }}>
          Prompt 版本由后端注册表管理，前端仅可读与实验室对比。
        </p>
      </div>

      {/* ============ Lab (A/B) ============ */}
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <FlaskConical size={18} />
            实验室 (Lab) · 多模型对比
          </div>
          <span className="card-sub">POST /api/v1/prompts/lab</span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>选择 Prompt</label>
            <select className="form-input" value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">— 请选择 —</option>
              {names.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--text-2)" }}>模型（逗号分隔）</label>
            <input
              className="form-input"
              value={models}
              onChange={(e) => setModels(e.target.value)}
              placeholder="deepseek-chat"
            />
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          <label style={{ fontSize: 12, color: "var(--text-2)" }}>输入文本 (input_text)</label>
          <textarea
            className="form-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            rows={4}
            placeholder="输入用于对比的示例文本…"
            style={{ minHeight: 90, fontFamily: "var(--font-ui)", lineHeight: 1.6 }}
          />
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button
            onClick={runLab}
            disabled={labLoading}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              height: 34,
              padding: "0 16px",
              borderRadius: "var(--r-sm)",
              fontWeight: 600,
              fontSize: 13,
              cursor: labLoading ? "default" : "pointer",
              background: "var(--primary)",
              color: "var(--brand-foreground)",
              border: "none",
              opacity: labLoading ? 0.7 : 1,
            }}
          >
            {labLoading ? <Loader2 size={14} /> : <Play size={14} />}
            {labLoading ? "对比中…" : "运行对比"}
          </button>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
            project_id：{projectId || "（未选择项目）"}
          </span>
        </div>

        {/* Lab error — visible, no alert, no silent fallback */}
        {labError && (
          <Banner
            tone="error"
            action={
              <button className="btn-sm btn-ghost" onClick={runLab}>
                重试
              </button>
            }
          >
            <AlertTriangle size={16} />
            {labError}
          </Banner>
        )}

        {/* Lab results */}
        {results.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="card-sub" style={{ marginBottom: 8 }}>
              对比结果（{results.length} 个模型）
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                gap: 12,
              }}
            >
              {results.map((res, idx) => (
                <div
                  key={res.model ?? idx}
                  className="card"
                  style={{
                    borderColor: res.status === "error" ? "var(--red)" : "var(--border-subtle)",
                    margin: 0,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <b style={{ fontSize: 13, color: "var(--text-1)" }}>{res.model}</b>
                    {res.status === "error" ? (
                      <span className="badge red">错误</span>
                    ) : (
                      <span className="badge green">正常</span>
                    )}
                  </div>
                  {res.status === "error" ? (
                    <div style={{ fontSize: 12, color: "var(--red)", whiteSpace: "pre-wrap" }}>
                      {res.error || "未知错误"}
                    </div>
                  ) : (
                    <pre
                      style={{
                        margin: 0,
                        fontSize: 12,
                        color: "var(--text-2)",
                        whiteSpace: "pre-wrap",
                        overflowX: "auto",
                        fontFamily: "var(--font-ui)",
                      }}
                    >
                      {res.output ?? "（无输出）"}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
