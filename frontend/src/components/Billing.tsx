import React, { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, AlertTriangle, Crown, Check } from "lucide-react";
import { ApiError, api } from "../lib/api";

// Backend envelope shape: { code, message, data } — lib/api returns the full
// envelope, so callers unwrap `.data` manually.
interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

interface Plan {
  id: string;
  name: string;
  description: string;
  price_monthly_cny: number;
  price_yearly_cny: number;
  features: string[];
  max_projects: number;
  max_words_per_month: number;
  ai_models: string[];
  priority_support: boolean;
}

interface Usage {
  month: string;
  words_used: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_used: number;
  calls: number;
  projects_count: number;
}

interface Subscription {
  plan: {
    plan_id: string;
    name: string;
    max_projects: number;
    max_words_per_month: number;
    ai_models: string[];
    monthly_budget_cny: number;
    priority_support: boolean;
  };
  usage: Usage;
}

function fmtInt(n: unknown): string {
  const v = typeof n === "number" ? n : Number(n) || 0;
  return v.toLocaleString("zh-CN");
}

function fmtMoney(n: unknown): string {
  const v = typeof n === "number" ? n : Number(n) || 0;
  return `¥${v.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pct(used: number, limit: number): number {
  if (!limit || limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function Banner({ tone, children, action }: { tone: "info" | "error"; children: React.ReactNode; action?: React.ReactNode }) {
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

function UsageBar({ label, used, limit, format }: { label: string; used: number; limit: number; format: (n: number) => string }) {
  const p = pct(used, limit);
  const over = limit > 0 && used > limit;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span>{label}</span>
        <strong style={{ color: over ? "var(--red)" : "var(--text-1)" }}>
          {format(used)} / {limit > 0 ? format(limit) : "不限"}
        </strong>
      </div>
      <meter
        min={0}
        max={Math.max(limit, used, 1)}
        value={used}
        style={{ width: "100%" }}
        // `over` tints via the native meter; we also surface text color above.
        aria-label={label}
      />
      {over && <div style={{ fontSize: 12, color: "var(--red)", marginTop: 2 }}>已达上限，升级套餐以继续使用</div>}
    </div>
  );
}

export function Billing() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    Promise.allSettled([
      api<ApiEnvelope<Subscription>>("/api/v1/billing/subscription"),
      api<ApiEnvelope<Plan[]>>("/api/v1/billing/plans"),
    ])
      .then(([subRes, plansRes]) => {
        if (subRes.status === "fulfilled") setSubscription(subRes.value?.data ?? null);
        else {
          const e = subRes.reason as { payload?: { message?: string }; message?: string };
          setError(e?.payload?.message || e?.message || "订阅信息加载失败");
        }
        if (plansRes.status === "fulfilled") setPlans(Array.isArray(plansRes.value?.data) ? plansRes.value.data : []);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function upgrade(planId: string) {
    setUpgrading(planId);
    setError("");
    try {
      await api<ApiEnvelope<unknown>>("/api/v1/billing/subscription/upgrade", {
        method: "POST",
        body: JSON.stringify({ plan_id: planId }),
      });
      await load();
    } catch (e: unknown) {
      const err = e as ApiError;
      setError(JSON.stringify(err?.payload ?? err?.message ?? e));
    } finally {
      setUpgrading("");
    }
  }

  const plan = subscription?.plan;
  const usage = subscription?.usage;

  return (
    <div>
      <div className="breadcrumb">
        <b>NovelCraft</b> › 订阅与套餐
      </div>

      <div className="page-head">
        <div>
          <h1>订阅与套餐</h1>
          <p>当前套餐、本月用量与可选升级（MVP：套餐切换无需支付网关）</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={load} disabled={loading}>
            <RefreshCw size={14} />刷新
          </button>
        </div>
      </div>

      {loading && (
        <Banner tone="info">
          <Loader2 size={16} />正在加载套餐与用量…
        </Banner>
      )}

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

      {!loading && !error && plan && usage && (
        <>
          {/* Current plan + usage */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head">
              <div className="card-title">
                <Crown size={18} />
                当前套餐：{plan.name}
              </div>
              <span className="badge cyan">{usage.month} 用量周期</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
              <SummaryStat label="本月生成字数" value={fmtInt(usage.words_used)} tone="var(--primary-light)" />
              <SummaryStat label="本月 AI 调用" value={fmtInt(usage.calls)} tone="var(--orange)" />
              <SummaryStat label="本月 Token 成本" value={fmtMoney(usage.cost_used)} tone="var(--green)" />
              <SummaryStat label="项目数" value={fmtInt(usage.projects_count)} tone="var(--cyan)" />
            </div>
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border-subtle)" }}>
              <UsageBar label="项目数" used={usage.projects_count} limit={plan.max_projects} format={fmtInt} />
              <UsageBar label="本月生成字数" used={usage.words_used} limit={plan.max_words_per_month} format={fmtInt} />
              <UsageBar label="本月 Token 成本" used={usage.cost_used} limit={plan.monthly_budget_cny} format={fmtMoney} />
            </div>
          </div>

          {/* Plan catalog */}
          <div className="card">
            <div className="card-head">
              <div className="card-title">可选套餐</div>
              <span className="card-sub">切换即时生效（MVP 不涉及支付）</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
              {plans.map((p) => {
                const isCurrent = p.id === plan.plan_id;
                return (
                  <div
                    key={p.id}
                    className="card"
                    style={{
                      margin: 0,
                      padding: 16,
                      borderColor: isCurrent ? "var(--primary-light)" : "var(--border-subtle)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ fontSize: 16 }}>{p.name}</strong>
                      {isCurrent && <span className="badge green"><Check size={12} /> 当前</span>}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--text-2)" }}>{p.description}</div>
                    <div style={{ fontSize: 20, color: "var(--primary-light)", fontWeight: 700 }}>
                      {fmtMoney(p.price_monthly_cny)}
                      <span style={{ fontSize: 12, color: "var(--text-3)", fontWeight: 400 }}> / 月</span>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-2)", lineHeight: 1.8 }}>
                      {Array.isArray(p.features) && p.features.length > 0 ? (
                        p.features.map((f, i) => <li key={i}>{f}</li>)
                      ) : (
                        <li>无特性说明</li>
                      )}
                      <li>项目上限：{p.max_projects}</li>
                      <li>月字数上限：{fmtInt(p.max_words_per_month)}</li>
                      <li>模型：{Array.isArray(p.ai_models) && p.ai_models.length ? p.ai_models.join("、") : "—"}</li>
                    </ul>
                    <div style={{ marginTop: "auto", paddingTop: 8 }}>
                      <button
                        className={`btn-sm ${isCurrent ? "btn-ghost" : "btn-primary"}`}
                        disabled={isCurrent || upgrading === p.id}
                        onClick={() => void upgrade(p.id)}
                        style={{ width: "100%" }}
                      >
                        {isCurrent ? "使用中" : upgrading === p.id ? "切换中…" : "升级 / 切换"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        <div className="stat-ic" style={{ background: "var(--bg-base)", color: tone, border: "1px solid var(--border-subtle)" }}>
          <Crown size={16} />
        </div>
      </div>
      <div className="stat-val">{value}</div>
    </div>
  );
}
