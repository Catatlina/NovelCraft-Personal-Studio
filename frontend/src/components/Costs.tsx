import React from "react";

type AiCall = { id: string; provider: string; model: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string };

export function Costs({ aiCalls, budgets, routes }: {
  aiCalls: AiCall[]; budgets: Budget[]; routes: ModelRoute[];
}) {
  const total = aiCalls.reduce((s, c) => s + Number(c.cost_cny), 0);

  return (
    <div className="review-grid" style={{gridTemplateColumns:"1fr 300px"}}>
      <div className="panel">
        <div style={{display:"flex",alignItems:"baseline",gap:12,marginBottom:16}}>
          <strong style={{fontSize:28,color:"var(--brand-500)"}}>¥{total.toFixed(4)}</strong>
          <span style={{color:"var(--text-muted)"}}>{aiCalls.length} 次调用</span>
        </div>
        <table>
          <thead><tr><th>任务</th><th>模型</th><th>Tokens</th><th>成本</th><th>延迟</th></tr></thead>
          <tbody>
            {aiCalls.map(c => (
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
      </div>
      <div className="panel" style={{display:"flex",flexDirection:"column",gap:14}}>
        <h2>预算</h2>
        {budgets.map(b => (
          <div key={b.id}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
              <span>{b.scope}</span>
              <strong>¥{Number(b.spent_cny).toFixed(4)} / ¥{Number(b.limit_cny).toFixed(2)}</strong>
            </div>
            <meter min={0} max={Number(b.limit_cny)} value={Number(b.spent_cny)} style={{width:"100%"}} />
          </div>
        ))}
        <h2>模型路由</h2>
        {routes.slice(0,10).map(r => (
          <div key={r.id} style={{padding:8,border:"1px solid var(--border-subtle)",borderRadius:"var(--radius-md)"}}>
            <small style={{color:"var(--text-muted)",display:"block"}}>{r.task_type}</small>
            <strong>{r.provider}/{r.model}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
