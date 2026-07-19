import React from "react";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

type AiCall = { id: string; provider: string; model: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string };

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

  return (
    <div className="layout-2">
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <span style={{display:"flex",alignItems:"baseline",gap:12}}>
              <span style={{fontSize:28,color:"var(--primary-light)"}}>¥{total.toFixed(4)}</span>
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
                  <td>{Number(c.prompt_tokens)+Number(c.completion_tokens)}</td>
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
      <div className="card" style={{display:"flex",flexDirection:"column",gap:14}}>
        <div className="card-head">
          <div className="card-title">预算</div>
        </div>
        {safeBudgets.length > 0 ? budgetsPager.pageData.map(b => (
          <div key={b.id}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:4,fontSize:13}}>
              <span>{b.scope}</span>
              <strong>¥{Number(b.spent_cny).toFixed(4)} / ¥{Number(b.limit_cny).toFixed(2)}</strong>
            </div>
            <meter min={0} max={Number(b.limit_cny)} value={Number(b.spent_cny)} style={{width:"100%"}} />
          </div>
        )) : (
          <div className="empty" style={{padding:24}}>
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
        <div className="card-head" style={{marginTop:4}}>
          <div className="card-title">模型路由</div>
        </div>
        {safeRoutes.length > 0 ? routesPager.pageData.map(r => (
          <div key={r.id} className="card" style={{padding:12}}>
            <span className="badge gray" style={{display:"block",width:"fit-content",marginBottom:6}}>{r.task_type}</span>
            <strong style={{fontSize:13}}>{r.provider}/{r.model}</strong>
          </div>
        )) : (
          <div className="empty" style={{padding:24}}>
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
  );
}
