import React, { useEffect, useState } from "react";
import { Key, Cpu, DollarSign, Save, RefreshCw, Code2, Settings2, Check, X } from "lucide-react";
import { api } from "../lib/api";

type Provider = { name: string; key_configured: boolean; base_url: string; default_model: string };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string,unknown>; fallback_json: any[] };
type Budget = { id: string; project_id: string; scope: string; limit_cny: number; spent_cny: number };
type Prompt = { id: string; name: string; version: string; model: string; template: string };
type AppSetting = { key: string; value: string; description: string; updated_at: string };

export function Settings({ projectId = "" }: { projectId?: string }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [settings, setAppSettings] = useState<AppSetting[]>([]);
  const [subtab, setSubtab] = useState<"providers"|"routes"|"budgets"|"prompts"|"appsettings"|"data"|"account">("appsettings");
  const [pwOld, setPwOld] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [apiKey, setApiKeyLocal] = useState("");
  const [apiUrl, setApiUrlLocal] = useState("");
  const [model, setModelLocal] = useState("");
  const [saved, setSaved] = useState(true);
  const [editRoute, setEditRoute] = useState<ModelRoute|null>(null);
  const [editBudget, setEditBudget] = useState<{pid:string;scope:string;limit:number}|null>(null);
  const [editSetting, setEditSetting] = useState<{key:string;value:string;description:string}|null>(null);
  const [msg, setMsg] = useState("");
  const [stats, setStats] = useState<{ ai_calls: number; contents: number; db_size: string } | null>(null);

  // Load saved API config on mount
  useEffect(() => {
    import("../lib/api").then(({ getApiKey, getApiUrl, getModel }) => {
      setApiKeyLocal(getApiKey()); setApiUrlLocal(getApiUrl()); setModelLocal(getModel());
    });
  }, []);

  useEffect(() => {
    api("/api/v1/admin/providers").then(d=>setProviders(d.data||[]));
    api("/api/v1/admin/model-routes").then(d=>setRoutes(d.data||[]));
    api("/api/v1/admin/budgets").then(d=>setBudgets(d.data||[]));
    api("/api/v1/admin/prompts").then(d=>setPrompts(d.data||[]));
    api("/api/v1/admin/settings").then(d=>setAppSettings(d.data||[]));
    api("/api/v1/stats/overview").then(d=>setStats(d.data||null)).catch(()=>setStats(null));
  }, []);

  async function saveRoute() {
    if (!editRoute) return;
    await api(`/api/v1/admin/model-routes/${editRoute.task_type}`, {
      method: "PUT", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({provider:editRoute.provider, model:editRoute.model, params:editRoute.params, fallbacks:editRoute.fallback_json||[]}),
    });
    setMsg("路由已保存"); setEditRoute(null);
    const r = await api("/api/v1/admin/model-routes");
    setRoutes(r.data||[]);
  }

  async function saveBudget() {
    if (!editBudget) return;
    await api(`/api/v1/admin/budgets/${editBudget.pid}/${encodeURIComponent(editBudget.scope)}`, {
      method: "PUT", body: JSON.stringify({ limit_cny: editBudget.limit }),
    });
    const refreshed = await api("/api/v1/admin/budgets");
    setBudgets(refreshed.data || []);
    setEditBudget(null);
  }

  async function saveApiConfig() {
    const { setApiKey, setApiUrl, setModel } = await import("../lib/api");
    setApiKey(apiKey); setApiUrl(apiUrl); setModel(model);
    setSaved(true);
    setMsg("API 配置已保存");
  }

  async function saveSetting() {
    if (!editSetting) return;
    await api(`/api/v1/admin/settings/${editSetting.key}`, {
      method:"PUT", body: JSON.stringify({value: editSetting.value}),
    });
    setMsg(`${editSetting.key} 已保存`);
    setEditSetting(null);
    const r = await api("/api/v1/admin/settings");
    setAppSettings(r.data||[]);
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"200px 1fr",gap:16,minHeight:400}}>
      <div className="panel" style={{display:"flex",flexDirection:"column",gap:4}}>
        <button className={subtab==="appsettings"?"active":""} onClick={()=>setSubtab("appsettings")} style={{justifyContent:"flex-start"}}><Settings2 size={16}/> 全局配置</button>
        <button className={subtab==="providers"?"active":""} onClick={()=>setSubtab("providers")} style={{justifyContent:"flex-start"}}><Key size={16}/> Providers</button>
        <button className={subtab==="routes"?"active":""} onClick={()=>setSubtab("routes")} style={{justifyContent:"flex-start"}}><Cpu size={16}/> 模型路由</button>
        <button className={subtab==="budgets"?"active":""} onClick={()=>setSubtab("budgets")} style={{justifyContent:"flex-start"}}><DollarSign size={16}/> 预算</button>
        <button className={subtab==="prompts"?"active":""} onClick={()=>setSubtab("prompts")} style={{justifyContent:"flex-start"}}><Code2 size={16}/> Prompts</button>
        <button className={subtab==="data"?"active":""} onClick={()=>setSubtab("data")} style={{justifyContent:"flex-start"}}><Save size={16}/> 数据</button>
        <button className={subtab==="account"?"active":""} onClick={()=>setSubtab("account")} style={{justifyContent:"flex-start"}}><Key size={16}/> 账号</button>
      </div>

      <div className="panel" style={{overflow:"auto"}}>
        {msg && <div className="error" style={{background:"#1a3a28",color:"var(--success)",border:"1px solid var(--success)",marginBottom:8}}>{msg}<button onClick={()=>setMsg("")} style={{float:"right",border:"none",background:"none",color:"var(--success)"}}>×</button></div>}

        {subtab==="appsettings" && (
          <div>
            <h3>全局系统配置</h3>
            <p style={{fontSize:12,color:"var(--text-muted)"}}>下方 API 配置仅保存在当前浏览器会话（BYOK）；定时任务和 Worker 请通过环境变量配置并重启服务。</p>
            <div style={{display:"flex",gap:8,alignItems:"center",marginBottom:12}}>
              <input placeholder="DeepSeek API Key" value={apiKey}
                onChange={e => { setApiKeyLocal(e.target.value); setSaved(false); }}
                style={{flex:1}} />
            </div>
            <div style={{display:"flex",gap:8,marginBottom:12}}>
              <input placeholder="API 地址，例 https://api.deepseek.com/v1" value={apiUrl}
                onChange={e => { setApiUrlLocal(e.target.value); setSaved(false); }}
                style={{flex:1,fontSize:13}} />
              <input placeholder="模型名，例 deepseek-chat" value={model}
                onChange={e => { setModelLocal(e.target.value); setSaved(false); }}
                style={{flex:1,fontSize:13}} />
            </div>
            <div style={{marginBottom:12}}>
              <button className="primary" onClick={saveApiConfig} disabled={saved} style={{justifyContent:"center"}}>
                {saved ? "✅ 已保存" : "💾 保存 API 配置"}
              </button>
            </div>
            <table><thead><tr><th>配置项</th><th>值</th><th>说明</th><th>操作</th></tr></thead>
            <tbody>
              {settings.map((s:AppSetting) => (
                <tr key={s.key}>
                  <td style={{fontSize:13,fontWeight:600}}>{s.key}</td>
                  <td style={{fontSize:12,color:"var(--text-muted)",maxWidth:200,overflow:"hidden",textOverflow:"ellipsis"}}>{s.value}</td>
                  <td style={{fontSize:12,color:"var(--text-secondary)"}}>{s.description}</td>
                  <td><button onClick={()=>setEditSetting({key:s.key,value:s.value.replace(/[*]+/g,""),description:s.description})} style={{fontSize:12}}>编辑</button></td>
                </tr>
              ))}
            </tbody></table>
            {editSetting && (
              <div className="panel" style={{marginTop:12}}>
                <h3>编辑: {editSetting.key}</h3>
                <p style={{fontSize:12,color:"var(--text-muted)"}}>{editSetting.description}</p>
                <div style={{display:"flex",flexDirection:"column",gap:8,marginTop:8}}>
                  <label>值
                    <input value={editSetting.value}
                      type={editSetting.key.includes("api_key")?"password":"text"}
                      onChange={e=>setEditSetting({...editSetting,value:e.target.value})}
                      style={{width:"100%"}} />
                  </label>
                  <div style={{display:"flex",gap:8}}>
                    <button className="primary" onClick={saveSetting}><Save size={14}/>保存</button>
                    <button onClick={()=>setEditSetting(null)}>取消</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

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
                  <label>Provider <select value={editRoute.provider} onChange={e=>setEditRoute({...editRoute,provider:e.target.value})}>{["deepseek","claude","openai","gemini","mock"].map(p=><option key={p}>{p}</option>)}</select></label>
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

        {subtab==="data" && (
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <div>
              <h3>导入知识库</h3>
              <input type="file" accept=".txt,.md,.json,.jsonl,.pdf,.docx" disabled={!projectId} onChange={async e=>{
                const f=e.target.files?.[0]; if(!f)return;
                const form = new FormData(); form.append("file", f);
                await api(`/api/v1/knowledge/import?project_id=${projectId}`,{method:"POST",body:form});
                alert("导入成功");
              }} />
              {!projectId && <small className="muted">请先选择项目再导入。</small>}
            </div>
            <div>
              <h3>导出知识库</h3>
              <button onClick={async()=>{
                if (!projectId) { alert("请先选择项目"); return; }
                const r=await api(`/api/v1/knowledge?project_id=${projectId}`);
                const blob=new Blob([JSON.stringify(r.data||[],null,2)],{type:"application/json"});
                const a=document.createElement("a");a.href=URL.createObjectURL(blob);
                a.download="novelcraft_knowledge.json";a.click();
              }}>导出 JSON</button>
            </div>
            <div>
              <h3>数据统计</h3>
              <table><tbody>
                {[{label:"AI 调用次数",value:stats?stats.ai_calls:"加载中…"},{label:"内容条数",value:stats?stats.contents:"加载中…"},{label:"数据库大小",value:stats?stats.db_size:"加载中…"}].map((m,i)=>
                  <tr key={i}><td>{m.label}</td><td style={{fontWeight:600}}>{m.value}</td></tr>
                )}
              </tbody></table>
            </div>
          </div>
        )}

        {subtab==="account" && (
          <div style={{display:"flex",flexDirection:"column",gap:12,maxWidth:420}}>
            <h3>修改密码</h3>
            <input type="password" placeholder="当前密码" value={pwOld} onChange={e=>setPwOld(e.target.value)} />
            <input type="password" placeholder="新密码（至少 8 位）" value={pwNew} onChange={e=>setPwNew(e.target.value)} />
            <button disabled={!pwOld || pwNew.length < 8} onClick={async()=>{
              setPwMsg("");
              try {
                await api("/api/v1/auth/change-password",{method:"POST",body:JSON.stringify({old_password:pwOld,new_password:pwNew})});
                setPwOld(""); setPwNew(""); setPwMsg("密码已修改，其他设备的登录已失效。");
              } catch (err:any) {
                const detail = err?.payload?.detail;
                setPwMsg(typeof detail==="string" ? detail : "修改失败，请检查当前密码。");
              }
            }}>更新密码</button>
            {pwMsg && <small className="muted">{pwMsg}</small>}
          </div>
        )}
      </div>
    </div>
  );
}
