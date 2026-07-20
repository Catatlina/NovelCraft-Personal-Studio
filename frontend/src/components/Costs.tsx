import React, { useEffect, useState } from "react";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";
import { api } from "../lib/api";

// Backend envelope shape: { code, message, data } — lib/api returns the full
// envelope, so callers unwrap `.data` manually.
interface ApiEnvelope<T> {
  code: number | string;
  message: string;
  data: T;
}

type AiCall = { id: string; provider: string; model: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string };

// Per-user Token metering (P0-T4) — returned by GET /api/v1/analytics/usage?scope=user
interface TokenBill {
  month: string;
  words_used: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_used: number;
  calls: number;
  projects_count: number;
}

const fmtInt = (n: number | undefined): string => (n ?? 0).toLocaleString("zh-CN");
const fmtMoney = (n: number | undefined): string => `¥${Number(n ?? 0).toFixed(2)}`;

export function Costs({ aiCalls, budgets, routes }: {
  aiCalls: AiCall[]; budgets: Budget[]; routes: ModelRoute[];
}) {
  const safeCalls = Array.isArray(aiCalls) ? aiCalls : [];
  const safeBudgets = Array.isArray(budgets) ? budgets : [];
  const safeRoutes = Array.isArray(routes) ? routes : [];
  const total = safeCalls.reduce((s, c) => s + Number(c.cost_cny), 0);

  const callsPager = usePagination({ items: safeCalls, pageSize: 10, mode: "client" });
  const budgetsPager = usePagination({ items: safeBudgets, pageSize: 10, mode: "client" });
  const routesPager = usePagination({ items: safeRoutes, pageSize: 10, mode: "client" });

  // ── 我的 Token 账单（按用户聚合的当月用量） ───────────────────────────────
  const [bill, setBill] = useState<TokenBill | null>(null);
  const [billErr, setBillErr] = useState<string>("");
  const [billLoading, setBillLoading] = useState<boolean>(true);

  useEffect(() => {
    let active = true;
    setBillLoading(true);
    setBillErr("");
    api<ApiEnvelope<TokenBill>>("/api/v1/analytics/usage?scope=user")
      .then((resp) => { if (active) setBill(resp.data); })
      .catch((e) => {
        if (!active) return;
        const payload = e?.payload;
        const msg =
          (payload && (payload.detail?.message || payload.detail || payload.message)) ||
          e?.message ||
          "加载 Token 账单失败";
        setBillErr(typeof msg === "string" ? msg : "加载 Token 账单失败");
      })
      .finally(() => { if (active) setBillLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <div>
      {/* ── 我的 Token 账单（P0-T4 per-user metering） ─────────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <div className="card-title">
            <span style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span>我的 Token 账单</span>
              {bill && (
                <span className="cell-sub">账单月份 {bill.month}</span>
              )}
            </span>
          </div>
        </div>

        {billLoading ? (
          <div className="empty" style={{ padding: 24 }}>
            <p>正在加载本月用量…</p>
          </div>
        ) : billErr ? (
          <div className="empty" style={{ padding: 24 }}>
            <p style={{ color: "var(--red)" }}>{billErr}</p>
          </div>
        ) : bill ? (
          <div className="grid grid-4" style={{ gap: 14 }}>
            <div className="stat">
              <div className="stat-label">本月消耗 Token</div>
              <div className="stat-val" style={{ color: "var(--primary-light)" }}>
                {fmtInt(bill.prompt_tokens + bill.completion_tokens)}
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">生成字数（估算）</div>
              <div className="stat-val">{fmtInt(bill.words_used)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Token 成本</div>
              <div className="stat-val" style={{ color: "var(--green)" }}>
                {fmtMoney(bill.cost_used)}
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">本月调用次数</div>
              <div className="stat-val">{fmtInt(bill.calls)}</div>
            </div>
          </div>
        ) : (
          <div className="empty" style={{ padding: 24 }}>
            <p>暂无用量数据</p>
          </div>
        )}
      </div>

      <div className="layout-2">
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <span style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <span style={{ fontSize: 28, color: "var(--primary-light)" }}>¥{total.toFixed(4)}</span>
                <span className="cell-sub">{safeCalls.length} 次调用</span>
              </span>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>任务</th><th>模型</th><th>Tokens</th><th>成本</th><th>延迟</th></tr></thead>
              <tbody>
                {callsPager.pageData.map(c => (
                  <tr key={c.id}>
                    <td>{c.task_type}</td>
                    <td>{c.provider}/{c.model}</td>
                    <td>{Number(c.prompt_tokens) + Number(c.completion_tokens)}</td>
                    <td>¥{Number(c.cost_cny).toFixed(4)}</td>
                    <td>{c.latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={callsPager.page}
              pageSize={callsPager.pageSize}
              total={safeCalls.length}
              onPageChange={callsPager.setPage}
              onPageSizeChange={callsPager.setPageSize}
              pageSizeOptions={[10, 20, 50, 100]}
            />
          </div>
        </div>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="card-head">
            <div className="card-title">预算</div>
          </div>
          {safeBudgets.length > 0 ? budgetsPager.pageData.map(b => (
            <div key={b.id}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13 }}>
                <span>{b.scope}</span>
                <strong>¥{Number(b.spent_cny).toFixed(4)} / ¥{Number(b.limit_cny).toFixed(2)}</strong>
              </div>
              <meter min={0} max={Number(b.limit_cny)} value={Number(b.spent_cny)} style={{ width: "100%" }} />
            </div>
          )) : (
            <div className="empty" style={{ padding: 24 }}>
              <p>暂无预算数据</p>
            </div>
          )}
          <Pagination
            page={budgetsPager.page}
            pageSize={budgetsPager.pageSize}
            total={safeBudgets.length}
            onPageChange={budgetsPager.setPage}
            onPageSizeChange={budgetsPager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
          <div className="card-head" style={{ marginTop: 4 }}>
            <div className="card-title">模型路由</div>
          </div>
          {safeRoutes.length > 0 ? routesPager.pageData.map(r => (
            <div key={r.id} className="card" style={{ padding: 12 }}>
              <span className="badge gray" style={{ display: "block", width: "fit-content", marginBottom: 6 }}>{r.task_type}</span>
              <strong style={{ fontSize: 13 }}>{r.provider}/{r.model}</strong>
            </div>
          )) : (
            <div className="empty" style={{ padding: 24 }}>
              <p>暂无路由配置</p>
            </div>
          )}
          <Pagination
            page={routesPager.page}
            pageSize={routesPager.pageSize}
            total={safeRoutes.length}
            onPageChange={routesPager.setPage}
            onPageSizeChange={routesPager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
        </div>
      </div>
    </div>
  );
}
