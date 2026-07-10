import React, { useEffect, useState } from "react";
import { Key, Cpu, DollarSign, Save, RefreshCw, Code2 } from "lucide-react";

type Provider = { name: string; key_configured: boolean; base_url: string; default_model: string };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string,unknown>; fallback_json: any[] };
type Budget = { id: string; project_id: string; scope: string; limit_cny: number; spent_cny: number };
type Prompt = { id: string; name: string; version: string; model: string; template: string };

export function Settings() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [subtab, setSubtab] = useState<"providers"|"routes"|"budgets"|"prompts">("providers");
  const [editRoute, setEditRoute] = useState<ModelRoute|null>(null);
  const [editBudget, setEditBudget] = useState<{pid:string;scope:string;limit:number}|null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/v1/admin/providers").then(r=>r.json()).then(d=>setProviders(d.data||[]));
    fetch("/api/v1/admin/model-routes").then(r=>r.json()).then(d=>setRoutes(d.data||[]));
    fetch("/api/v1/admin/budgets").then(r=>r.json()).then(d=>setBudgets(d.data||[]));
    fetch("/api/v1/admin/prompts").then(r=>r.json()).then(d=>setPrompts(d.data||[]));
  }, []);

  async function saveRoute() {
    if (!editRoute) return;
    await fetch(`/api/v1/admin/model-routes/${editRoute.task_type}`, {
      method: "PUT", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({provider:editRoute.provider, model:editRoute.model, params:editRoute.params, fallbacks:editRoute.fallback_json||[]}),
    });
    setMsg("路由已保存"); setEditRoute(null);
    const r = await fetch("/api/v1/admin/model-routes").then(r=>r.json());
    setRoutes(r.data||[]);
  }

  async function saveBudget() {
    if (!editBudget) return;
    await fetch(`/api/v1/admin/budgets/${editBudget.pid}/${editBudget.scope}?limit_cny=${editBudget.limit}`, {method:"PUT"});
    setMsg("预算已更新"); setEditBudget(null);
    const r = await fetch("/api/v1/admin/budgets").then(r=>r.json());
    setBudgets(r.data||[]);
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"200px 1fr",gap:16,minHeight:400}}>
      <div className="panel" style={{display:"flex",flexDirection:"column",gap:4}}>
        <button className={subtab==="providers"?"active":""} onClick={()=>setSubtab("providers")} style={{justifyContent:"flex-start"}}><Key size={16}/> Providers</button>
        <button className={subtab==="routes"?"active":""} onClick={()=>setSubtab("routes")} style={{justifyContent:"flex-start"}}><Cpu size={16}/> 模型路由</button>
        <button className={subtab==="budgets"?"active":""} onClick={()=>setSubtab("budgets")} style={{justifyContent:"flex-start"}}><DollarSign size={16}/> 预算</button>
        <button className={subtab==="prompts"?"active":""} onClick={()=>setSubtab("prompts")} style={{justifyContent:"flex-start"}}><Code2 size={16}/> Prompts</button>
      </div>

      <div className="panel" style={{overflow:"auto"}}>
        {msg && <div className="error" style={{background:"#1a3a28",color:"var(--success)",border:"1px solid var(--success)",marginBottom:8}}>{msg}<button onClick={()=>setMsg("")} style={{float:"right",border:"none",background:"none",color:"var(--success)"}}>×</button></div>}

        {subtab==="providers" && (
          <table><thead><tr><th>Provider</th><th>API Key</th><th>Base URL</th><th>默认模型</th></tr></thead>
          <tbody>{providers.map(p=><tr key={p.name}><td><strong>{p.name}</strong></td><td>{p.key_configured?"✅ 已配置":"⚠️ 未配置"}</td><td style={{fontSize:12,color:"var(--text-muted)"}}>{p.base_url}</td><td>{p.default_model}</td></tr>)}</tbody></table>
        )}

        {subtab==="routes" && (
          <div>
            <table><thead><tr><th>任务类型</th><th>Provider</th><th>模型</th><th>操作</th></tr></thead>
            <tbody>{routes.map(r=><tr key={r.id}><td style={{fontSize:13}}>{r.task_type}</td><td>{r.provider}</td><td style={{fontSize:13}}>{r.model}</td><td><button onClick={()=>setEditRoute({...r})}><RefreshCw size={14}/> 编辑</button></td></tr>)}</tbody></table>
            {editRoute && (
              <div className="panel" style={{marginTop:12}}>
                <h3>编辑: {editRoute.task_type}</h3>
                <div style={{display:"flex",flexDirection:"column",gap:8}}>
                  <label>Provider <select value={editRoute.provider} onChange={e=>setEditRoute({...editRoute,provider:e.target.value})}>{["deepseek","claude","openai","gemini"].map(p=><option key={p}>{p}</option>)}</select></label>
                  <label>模型 <input value={editRoute.model} onChange={e=>setEditRoute({...editRoute,model:e.target.value})} /></label>
                  <div style={{display:"flex",gap:8}}><button className="primary" onClick={saveRoute}><Save size={14}/>保存</button><button onClick={()=>setEditRoute(null)}>取消</button></div>
                </div>
              </div>
            )}
          </div>
        )}

        {subtab==="budgets" && (
          <div>
            <table><thead><tr><th>项目</th><th>范围</th><th>已用</th><th>限额</th><th>操作</th></tr></thead>
            <tbody>{budgets.map(b=><tr key={b.id}><td style={{fontSize:12}}>{b.project_id?.slice(0,8)}</td><td>{b.scope}</td><td>¥{Number(b.spent_cny).toFixed(4)}</td><td>¥{Number(b.limit_cny).toFixed(2)}</td><td><button onClick={()=>setEditBudget({pid:b.project_id,scope:b.scope,limit:Number(b.limit_cny)})}><RefreshCw size={14}/> 调整</button></td></tr>)}</tbody></table>
            {editBudget && (
              <div className="panel" style={{marginTop:12}}>
                <h3>调整预算: {editBudget.scope}</h3>
                <div style={{display:"flex",flexDirection:"column",gap:8}}>
                  <label>限额(¥) <input type="number" value={editBudget.limit} onChange={e=>setEditBudget({...editBudget,limit:Number(e.target.value)})} step={0.5} min={0} /></label>
                  <div style={{display:"flex",gap:8}}><button className="primary" onClick={saveBudget}><Save size={14}/>保存</button><button onClick={()=>setEditBudget(null)}>取消</button></div>
                </div>
              </div>
            )}
          </div>
        )}

        {subtab==="prompts" && (
          <table><thead><tr><th>名称</th><th>版本</th><th>模型</th><th>模板(前80字)</th></tr></thead>
          <tbody>{prompts.slice(0,30).map(p=><tr key={p.id}><td style={{fontSize:13}}>{p.name}</td><td>{p.version}</td><td>{p.model}</td><td style={{fontSize:12,color:"var(--text-muted)",maxWidth:300,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{p.template?.slice(0,80)}</td></tr>)}</tbody></table>
        )}
      </div>
    </div>
  );
}
