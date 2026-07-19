import React, { useEffect, useState } from "react";
import { Key, Cpu, DollarSign, Save, RefreshCw, Code2, Settings2, Check, X, PlugZap, Users, Upload, Download, Database } from "lucide-react";
import { api, getApiKey, getApiUrl, getModel, setApiKey, setApiUrl, setModel } from "../lib/api";
import { Pagination, ConfirmDialog } from "./ui";
import { usePagination } from "../hooks/usePagination";

type Provider = { name: string; key_configured: boolean; base_url: string; default_model: string };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string,unknown>; fallback_json: any[] };
type Budget = { id: string; project_id: string; scope: string; limit_cny: number; spent_cny: number };
type Prompt = { id: string; name: string; version: string; model: string; template: string };
type AppSetting = { key: string; value: string; description: string; updated_at: string };
type ConnectionField = { key: string; label: string; type: string; required?: boolean };
type ConnectionSpec = { category: string; display_name: string; help?: string; fields: ConnectionField[] };
type ConnectionItem = { id: string; platform: string; account_name: string; display_name: string; category: string; configured_fields: string[]; missing_required: string[]; updated_at: string };

const TABS = [
  { id: "general", label: "通用", icon: Settings2 },
  { id: "ai", label: "AI Provider", icon: Cpu },
  { id: "budget", label: "预算", icon: DollarSign },
  { id: "members", label: "成员", icon: Users },
] as const;

type TabId = typeof TABS[number]["id"];

export function Settings({ projectId = "" }: { projectId?: string }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [settings, setAppSettings] = useState<AppSetting[]>([]);
  const [connectionSpecs, setConnectionSpecs] = useState<Record<string, ConnectionSpec>>({});
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [connectionCategory, setConnectionCategory] = useState("hotspot");
  const [connectionPlatform, setConnectionPlatform] = useState("");
  const [connectionAccount, setConnectionAccount] = useState("default");
  const [connectionCreds, setConnectionCreds] = useState<Record<string,string>>({});
  const [activeTab, setActiveTab] = useState<TabId>("general");
  const [pwOld, setPwOld] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [apiKey, setApiKeyLocal] = useState("");
  const [apiUrl, setApiUrlLocal] = useState("");
  const [model, setModelLocal] = useState("");
  const [saved, setSaved] = useState(true);
  const [editRoute, setEditRoute] = useState<ModelRoute|null>(null);
  const [editBudget, setEditBudget] = useState<{pid:string;scope:string;limit:number}|null>(null);
  const [editSetting, setEditSetting] = useState<{key:string;value:string;description:string}|null>(null);
  const [msg, setMsg] = useState("");
  const [stats, setStats] = useState<{ ai_calls: number; contents: number; db_size: string } | null>(null);
  const [deleteConnId, setDeleteConnId] = useState<string | null>(null);

  const settingsPager = usePagination({ items: settings, pageSize: 10, mode: "client" });
  const budgetsPager = usePagination({ items: budgets, pageSize: 10, mode: "client" });
  const promptsPager = usePagination({ items: prompts, pageSize: 10, mode: "client" });
  const connectionsPager = usePagination({ items: connections, pageSize: 10, mode: "client" });
  const providersPager = usePagination({ items: providers, pageSize: 10, mode: "client" });
  const routesPager = usePagination({ items: routes, pageSize: 10, mode: "client" });

  // Load saved API config on mount
  useEffect(() => {
    setApiKeyLocal(getApiKey()); setApiUrlLocal(getApiUrl()); setModelLocal(getModel());
  }, []);

  useEffect(() => {
    const reportAdminError = (caught: unknown) => setMsg(`管理配置加载失败：${String(caught)}`);
    api("/api/v1/admin/providers").then(d=>setProviders(d.data||[])).catch(reportAdminError);
    api("/api/v1/admin/model-routes").then(d=>setRoutes(d.data||[])).catch(reportAdminError);
    api("/api/v1/admin/budgets").then(d=>setBudgets(d.data||[])).catch(reportAdminError);
    api("/api/v1/admin/prompts").then(d=>setPrompts(d.data||[])).catch(reportAdminError);
    api("/api/v1/admin/settings").then(d=>setAppSettings(d.data||[])).catch(reportAdminError);
    loadConnections().catch(reportAdminError);
    api("/api/v1/stats/overview").then(d=>setStats(d.data||null)).catch(()=>setStats(null));
  }, []);

  async function loadConnections() {
    const specs = await api("/api/v1/platform-connections/specs");
    const specData = specs.data || {};
    setConnectionSpecs(specData);
    if (!connectionPlatform) {
      const first = Object.entries(specData).find(([, spec]: any) => spec.category === connectionCategory)?.[0] || Object.keys(specData)[0] || "";
      setConnectionPlatform(first);
    }
    const rows = await api("/api/v1/platform-connections");
    setConnections(rows.data || []);
  }

  const platformsForCategory = Object.entries(connectionSpecs)
    .filter(([, spec]) => spec.category === connectionCategory);
  const activeSpec = connectionSpecs[connectionPlatform];

  async function saveConnection() {
    if (!connectionPlatform) return;
    await api("/api/v1/platform-connections", {
      method: "POST",
      body: JSON.stringify({ platform: connectionPlatform, account_name: connectionAccount || "default", credentials: connectionCreds }),
    });
    setMsg("平台连接已保存（敏感字段已加密，不会回显）");
    setConnectionCreds({});
    await loadConnections();
  }

  async function deleteConnection(id: string) {
    await api(`/api/v1/platform-connections/${id}`, { method: "DELETE" });
    setMsg("平台连接已删除");
    await loadConnections();
  }

  async function testConnection(platform: string) {
    const result = await api(`/api/v1/platform-connections/${platform}/test`, { method: "POST" });
    setMsg(`检测结果：${result.data?.status || "unknown"}`);
  }

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
    <div className="settings-shell">

      {/* ── Left sidebar tab navigation ── */}
      <div style={{display:"flex", flexDirection:"column", borderRight:"1px solid var(--border)", padding:"12px 8px", gap:2}}>
        <div style={{fontSize:11, fontWeight:600, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:".5px", padding:"8px 12px 12px"}}>设置</div>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              display:"flex", alignItems:"center", gap:10,
              padding:"10px 12px", borderRadius:"var(--r-sm)",
              fontSize:"13.5px", fontWeight:500,
              color: activeTab === t.id ? "var(--primary-light)" : "var(--text-2)",
              background: activeTab === t.id ? "var(--primary-dim)" : "transparent",
              transition:"background .15s, color .15s",
              textAlign:"left", width:"100%",
            }}
          >
            <t.icon size={17} />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* ── Content area ── */}
      <div style={{overflow:"auto", padding:"24px"}}>

        {/* Toast message */}
        {msg && (
          <div style={{
            background:"var(--success-bg)", color:"var(--green)", border:"1px solid var(--green)",
            borderRadius:"var(--r-sm)", padding:"10px 14px", marginBottom:16,
            display:"flex", alignItems:"center", justifyContent:"space-between", fontSize:13
          }}>
            <span>{msg}</span>
            <button onClick={()=>setMsg("")} style={{color:"var(--green)", border:"none", background:"none", cursor:"pointer", fontSize:16, lineHeight:1}}>×</button>
          </div>
        )}

        {/* ============ 通用 Tab ============ */}
        {activeTab === "general" && (
          <div style={{display:"flex", flexDirection:"column", gap:24}}>

            {/* API 配置 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:4}}>API 配置</h3>
              <p style={{fontSize:12, color:"var(--text-3)", marginBottom:14}}>
                下方 API 配置仅保存在当前浏览器会话（BYOK），会作为 X-Api-Key / X-Api-Base-Url / X-Model 传给当前请求。
              </p>

              <div className="form-group">
                <label className="form-label">API Key</label>
                <div style={{display:"flex", gap:8}}>
                  <input
                    type={showKey ? "text" : "password"}
                    className="form-input"
                    placeholder="DeepSeek / Claude / OpenAI / Gemini"
                    value={apiKey}
                    autoComplete="off"
                    onChange={e => { setApiKeyLocal(e.target.value); setSaved(false); }}
                    style={{flex:1}}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(v => !v)}
                    style={{
                      whiteSpace:"nowrap", padding:"0 14px", height:46,
                      border:"1px solid var(--border)", borderRadius:"var(--r-sm)",
                      background:"var(--bg-hover)", color:"var(--text-2)", fontSize:13,
                      fontWeight:500, cursor:"pointer"
                    }}
                  >
                    {showKey ? "隐藏" : "显示"}
                  </button>
                </div>
              </div>

              <div style={{display:"flex", gap:12}}>
                <div className="form-group" style={{flex:1}}>
                  <label className="form-label">API 地址</label>
                  <input
                    className="form-input"
                    placeholder="https://api.deepseek.com/v1"
                    value={apiUrl}
                    onChange={e => { setApiUrlLocal(e.target.value); setSaved(false); }}
                    style={{fontSize:13}}
                  />
                </div>
                <div className="form-group" style={{flex:1}}>
                  <label className="form-label">模型</label>
                  <input
                    className="form-input"
                    placeholder="留空使用路由"
                    value={model}
                    onChange={e => { setModelLocal(e.target.value); setSaved(false); }}
                    style={{fontSize:13}}
                  />
                </div>
              </div>

              {model.includes("flash") && (
                <div style={{fontSize:12, color:"var(--orange)", marginBottom:12}}>
                  Flash 是速度优先模型，容易出现长篇设定漂移；小说规划和正文建议使用 deepseek-v4-pro。
                </div>
              )}

              <button className="btn-primary" onClick={saveApiConfig} disabled={saved} style={{maxWidth:220}}>
                {saved ? "✅ 已保存" : "💾 保存 API 配置"}
              </button>
            </section>

            {/* 系统配置表 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>系统配置</h3>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>配置项</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>值</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>说明</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {settingsPager.pageData.map((s:AppSetting) => (
                    <tr key={s.key} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontSize:13, fontWeight:600}}>{s.key}</td>
                      <td style={{padding:"10px 12px", fontSize:12, color:"var(--text-2)", maxWidth:180, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{s.value}</td>
                      <td style={{padding:"10px 12px", fontSize:12, color:"var(--text-3)"}}>{s.description}</td>
                      <td style={{padding:"10px 12px"}}>
                        <button
                          onClick={()=>setEditSetting({key:s.key,value:s.value.replace(/[*]+/g,""),description:s.description})}
                          style={{
                            fontSize:12, padding:"6px 12px", borderRadius:"var(--r-sm)",
                            border:"1px solid var(--border)", background:"var(--bg-hover)",
                            color:"var(--text-2)", cursor:"pointer", fontWeight:500
                          }}
                        >
                          编辑
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={settingsPager.page}
                pageSize={settingsPager.pageSize}
                total={settings.length}
                onPageChange={settingsPager.setPage}
                onPageSizeChange={settingsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />

              {editSetting && (
                <div style={{marginTop:16, padding:16, background:"var(--bg-hover)", borderRadius:"var(--r-md)", border:"1px solid var(--border)"}}>
                  <h4 style={{fontSize:14, fontWeight:600, marginBottom:4}}>编辑: {editSetting.key}</h4>
                  <p style={{fontSize:12, color:"var(--text-3)", marginBottom:12}}>{editSetting.description}</p>
                  <div className="field">
                    <label>值</label>
                    <input
                      className="form-input"
                      type={editSetting.key.includes("api_key")?"password":"text"}
                      value={editSetting.value}
                      onChange={e=>setEditSetting({...editSetting,value:e.target.value})}
                    />
                  </div>
                  <div style={{display:"flex", gap:8}}>
                    <button className="btn-primary" onClick={saveSetting} style={{maxWidth:120, height:38}}><Save size={14}/>保存</button>
                    <button onClick={()=>setEditSetting(null)} className="btn-secondary" style={{maxWidth:80, height:38, marginTop:0}}>取消</button>
                  </div>
                </div>
              )}
            </section>

            {/* 数据导入导出 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>知识库</h3>
              <div style={{display:"flex", gap:16, flexWrap:"wrap"}}>
                <div>
                  <label className="form-label">导入知识库</label>
                  <input
                    type="file"
                    accept=".txt,.md,.json,.jsonl,.pdf,.docx"
                    disabled={!projectId}
                    onChange={async e=>{
                      const f=e.target.files?.[0]; if(!f)return;
                      const form = new FormData(); form.append("file", f);
                      await api(`/api/v1/knowledge/import?project_id=${projectId}`,{method:"POST",body:form});
                      setMsg("导入成功");
                    }}
                    style={{fontSize:13}}
                  />
                  {!projectId && <div className="hint" style={{fontSize:12, color:"var(--text-3)", marginTop:4}}>请先选择项目再导入。</div>}
                </div>
                <div style={{display:"flex", alignItems:"flex-end"}}>
                  <button
                    onClick={async()=>{
                      if (!projectId) { setMsg("请先选择项目"); return; }
                      const r=await api(`/api/v1/knowledge?project_id=${projectId}`);
                      const blob=new Blob([JSON.stringify(r.data||[],null,2)],{type:"application/json"});
                      const a=document.createElement("a");a.href=URL.createObjectURL(blob);
                      a.download="novelcraft_knowledge.json";a.click();
                    }}
                    className="btn-primary"
                    style={{maxWidth:180, height:38, gap:6}}
                  >
                    <Download size={14}/> 导出 JSON
                  </button>
                </div>
              </div>
            </section>

            {/* 数据统计 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>数据统计</h3>
              <table style={{width:"100%", maxWidth:400, borderCollapse:"collapse"}}>
                <tbody>
                  {[{label:"AI 调用次数",value:stats?.ai_calls ?? "加载中…"},{label:"内容条数",value:stats?.contents ?? "加载中…"},{label:"数据库大小",value:stats?.db_size ?? "加载中…"}].map((m,i)=>
                    <tr key={i} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontSize:13, color:"var(--text-2)"}}>{m.label}</td>
                      <td style={{padding:"10px 12px", fontWeight:600}}>{String(m.value)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </div>
        )}

        {/* ============ AI Provider Tab ============ */}
        {activeTab === "ai" && (
          <div style={{display:"flex", flexDirection:"column", gap:24}}>

            {/* Providers */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>AI Providers</h3>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>Provider</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>API Key</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>Base URL</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>默认模型</th>
                  </tr>
                </thead>
                <tbody>
                  {providersPager.pageData.map(p=>(
                    <tr key={p.name} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontWeight:600}}>{p.name}</td>
                      <td style={{padding:"10px 12px"}}>{p.key_configured ? "✅ 已配置" : "⚠️ 未配置"}</td>
                      <td style={{padding:"10px 12px", fontSize:12, color:"var(--text-2)"}}>{p.base_url}</td>
                      <td style={{padding:"10px 12px"}}>{p.default_model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={providersPager.page}
                pageSize={providersPager.pageSize}
                total={providers.length}
                onPageChange={providersPager.setPage}
                onPageSizeChange={providersPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </section>

            {/* 模型路由 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>模型路由</h3>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>任务类型</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>Provider</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>模型</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {routesPager.pageData.map(r=>(
                    <tr key={r.id} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontSize:13}}>{r.task_type}</td>
                      <td style={{padding:"10px 12px"}}>{r.provider}</td>
                      <td style={{padding:"10px 12px", fontSize:13}}>{r.model}</td>
                      <td style={{padding:"10px 12px"}}>
                        <button
                          onClick={()=>setEditRoute({...r})}
                          style={{
                            fontSize:12, padding:"6px 12px", borderRadius:"var(--r-sm)",
                            border:"1px solid var(--border)", background:"var(--bg-hover)",
                            color:"var(--text-2)", cursor:"pointer", fontWeight:500,
                            display:"inline-flex", alignItems:"center", gap:4
                          }}
                        >
                          <RefreshCw size={14}/> 编辑
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={routesPager.page}
                pageSize={routesPager.pageSize}
                total={routes.length}
                onPageChange={routesPager.setPage}
                onPageSizeChange={routesPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />

              {editRoute && (
                <div style={{marginTop:16, padding:16, background:"var(--bg-hover)", borderRadius:"var(--r-md)", border:"1px solid var(--border)"}}>
                  <h4 style={{fontSize:14, fontWeight:600, marginBottom:12}}>编辑路由: {editRoute.task_type}</h4>
                  <div className="field">
                    <label>Provider</label>
                    <select className="form-input" value={editRoute.provider} onChange={e=>setEditRoute({...editRoute,provider:e.target.value})}>
                      {["deepseek","claude","openai","gemini"].map(p=><option key={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <label>模型</label>
                    <input className="form-input" value={editRoute.model} onChange={e=>setEditRoute({...editRoute,model:e.target.value})} />
                  </div>
                  <div style={{display:"flex", gap:8}}>
                    <button className="btn-primary" onClick={saveRoute} style={{maxWidth:120, height:38}}><Save size={14}/>保存</button>
                    <button onClick={()=>setEditRoute(null)} className="btn-secondary" style={{maxWidth:80, height:38, marginTop:0}}>取消</button>
                  </div>
                </div>
              )}
            </section>

            {/* Prompts */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>Prompts</h3>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>名称</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>版本</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>模型</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>模板(前80字)</th>
                  </tr>
                </thead>
                <tbody>
                  {promptsPager.pageData.map(p=>(
                    <tr key={p.id} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontSize:13}}>{p.name}</td>
                      <td style={{padding:"10px 12px"}}>{p.version}</td>
                      <td style={{padding:"10px 12px"}}>{p.model}</td>
                      <td style={{padding:"10px 12px", fontSize:12, color:"var(--text-2)", maxWidth:260, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{p.template?.slice(0,80)}</td>
                    </tr>
                  ))}
                </tbody>
                <Pagination
                  page={promptsPager.page}
                  pageSize={promptsPager.pageSize}
                  total={prompts.length}
                  onPageChange={promptsPager.setPage}
                  onPageSizeChange={promptsPager.setPageSize}
                  pageSizeOptions={[10, 20, 50, 100]}
                />
              </table>
            </section>
          </div>
        )}

        {/* ============ 预算 Tab ============ */}
        {activeTab === "budget" && (
          <div style={{display:"flex", flexDirection:"column", gap:24}}>

            {/* 预算管理 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>预算管理</h3>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>项目</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>范围</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>已用</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>限额</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {budgetsPager.pageData.map(b=>(
                    <tr key={b.id} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px", fontSize:12}}>{b.project_id?.slice(0,8)}</td>
                      <td style={{padding:"10px 12px"}}>{b.scope}</td>
                      <td style={{padding:"10px 12px"}}>¥{Number(b.spent_cny).toFixed(4)}</td>
                      <td style={{padding:"10px 12px"}}>¥{Number(b.limit_cny).toFixed(2)}</td>
                      <td style={{padding:"10px 12px"}}>
                        <button
                          onClick={()=>setEditBudget({pid:b.project_id,scope:b.scope,limit:Number(b.limit_cny)})}
                          style={{
                            fontSize:12, padding:"6px 12px", borderRadius:"var(--r-sm)",
                            border:"1px solid var(--border)", background:"var(--bg-hover)",
                            color:"var(--text-2)", cursor:"pointer", fontWeight:500,
                            display:"inline-flex", alignItems:"center", gap:4
                          }}
                        >
                          <RefreshCw size={14}/> 调整
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={budgetsPager.page}
                pageSize={budgetsPager.pageSize}
                total={budgets.length}
                onPageChange={budgetsPager.setPage}
                onPageSizeChange={budgetsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />

              {editBudget && (
                <div style={{marginTop:16, padding:16, background:"var(--bg-hover)", borderRadius:"var(--r-md)", border:"1px solid var(--border)"}}>
                  <h4 style={{fontSize:14, fontWeight:600, marginBottom:4}}>调整预算: {editBudget.scope}</h4>
                  <div className="field">
                    <label>限额 (¥)</label>
                    <input className="form-input" type="number" value={editBudget.limit} onChange={e=>setEditBudget({...editBudget,limit:Number(e.target.value)})} step={0.5} min={0} />
                  </div>
                  <div style={{display:"flex", gap:8}}>
                    <button className="btn-primary" onClick={saveBudget} style={{maxWidth:120, height:38}}><Save size={14}/>保存</button>
                    <button onClick={()=>setEditBudget(null)} className="btn-secondary" style={{maxWidth:80, height:38, marginTop:0}}>取消</button>
                  </div>
                </div>
              )}
            </section>

            {/* 平台连接 */}
            <section>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>平台连接</h3>
              <p style={{fontSize:12, color:"var(--text-3)", marginBottom:12}}>
                热点源、发布平台、运维告警等连接配置。敏感字段加密入库，不回显明文。
              </p>

              {/* Category tabs */}
              <div className="tabs">
                {(["hotspot","publish","ops"] as const).map(cat => (
                  <button
                    key={cat}
                    className={`tab ${connectionCategory===cat?'on':''}`}
                    onClick={() => {
                      setConnectionCategory(cat);
                      const first = Object.entries(connectionSpecs).find(([, spec]) => spec.category === cat)?.[0] || "";
                      setConnectionPlatform(first); setConnectionCreds({});
                    }}
                  >
                    {cat === "hotspot" ? "热点源" : cat === "publish" ? "发布平台" : "运维告警"}
                  </button>
                ))}
              </div>

              <div style={{display:"flex", flexDirection:"column", gap:12, padding:"16px", background:"var(--bg-hover)", borderRadius:"var(--r-md)", border:"1px solid var(--border)"}}>
                <div className="field">
                  <label>平台</label>
                  <select className="form-input" value={connectionPlatform} onChange={e => { setConnectionPlatform(e.target.value); setConnectionCreds({}); }}>
                    {platformsForCategory.map(([key, spec]) => <option key={key} value={key}>{spec.display_name}</option>)}
                  </select>
                </div>
                {activeSpec?.help && <p style={{fontSize:12, color:"var(--text-3)"}}>{activeSpec.help}</p>}
                <div className="field">
                  <label>账号/连接名</label>
                  <input className="form-input" value={connectionAccount} onChange={e=>setConnectionAccount(e.target.value)} placeholder="default" />
                </div>
                {activeSpec?.fields?.map(field => (
                  <div className="field" key={field.key}>
                    <label>{field.label}{field.required ? " *" : ""}</label>
                    <input
                      className="form-input"
                      type={field.type === "secret" ? "password" : field.type === "url" ? "url" : "text"}
                      value={connectionCreds[field.key] || ""}
                      onChange={e=>setConnectionCreds({...connectionCreds, [field.key]: e.target.value})}
                      autoComplete="off"
                      placeholder={field.type === "secret" ? "保存后不回显" : ""}
                    />
                  </div>
                ))}
                <button className="btn-primary" onClick={saveConnection} disabled={!connectionPlatform} style={{maxWidth:200, height:38}}><Save size={14}/>保存连接</button>
              </div>

              {/* Existing connections */}
              <h4 style={{fontSize:14, fontWeight:600, marginTop:20, marginBottom:10}}>已配置连接</h4>
              <table style={{width:"100%", borderCollapse:"collapse"}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--border)"}}>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>平台</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>连接名</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>状态</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>字段</th>
                    <th style={{textAlign:"left", padding:"8px 12px", fontSize:12, color:"var(--text-3)", fontWeight:600}}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {connectionsPager.pageData.map(item => (
                    <tr key={item.id} style={{borderBottom:"1px solid var(--border)"}}>
                      <td style={{padding:"10px 12px"}}>{item.display_name}</td>
                      <td style={{padding:"10px 12px"}}>{item.account_name}</td>
                      <td style={{padding:"10px 12px"}}>{item.missing_required?.length ? `缺少 ${item.missing_required.join(", ")}` : "✅ 已配置"}</td>
                      <td style={{padding:"10px 12px", fontSize:12, color:"var(--text-2)"}}>{item.configured_fields.join(", ") || "—"}</td>
                      <td style={{padding:"10px 12px", display:"flex", gap:6}}>
                        <button onClick={()=>testConnection(item.platform)} style={{fontSize:12, padding:"4px 10px", borderRadius:"var(--r-sm)", border:"1px solid var(--border)", background:"var(--bg-hover)", color:"var(--text-2)", cursor:"pointer"}}>检测</button>
                        <button className="btn-sm btn-danger" onClick={()=>setDeleteConnId(item.id)}><X size={12}/>删除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={connectionsPager.page}
                pageSize={connectionsPager.pageSize}
                total={connections.length}
                onPageChange={connectionsPager.setPage}
                onPageSizeChange={connectionsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
              {!connections.length && <p style={{fontSize:12, color:"var(--text-3)", marginTop:8}}>暂无平台连接。</p>}
            </section>
          </div>
        )}

        {/* ============ 成员 Tab ============ */}
        {activeTab === "members" && (
          <div style={{display:"flex", flexDirection:"column", gap:24}}>

            {/* 修改密码 */}
            <section style={{maxWidth:420}}>
              <h3 style={{fontSize:15, fontWeight:600, marginBottom:12}}>修改密码</h3>
              <div className="form-group">
                <label className="form-label">当前密码</label>
                <input className="form-input" type="password" placeholder="输入当前密码" value={pwOld} onChange={e=>setPwOld(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">新密码（至少 8 位）</label>
                <input className="form-input" type="password" placeholder="输入新密码" value={pwNew} onChange={e=>setPwNew(e.target.value)} />
              </div>
              <button
                className="btn-primary"
                disabled={!pwOld || pwNew.length < 8}
                onClick={async()=>{
                  setPwMsg("");
                  try {
                    await api("/api/v1/auth/change-password",{method:"POST",body:JSON.stringify({old_password:pwOld,new_password:pwNew})});
                    setPwOld(""); setPwNew(""); setPwMsg("密码已修改，其他设备的登录已失效。");
                  } catch (err:any) {
                    const detail = err?.payload?.detail;
                    setPwMsg(typeof detail==="string" ? detail : "修改失败，请检查当前密码。");
                  }
                }}
                style={{maxWidth:220, height:38}}
              >
                更新密码
              </button>
              {pwMsg && <p style={{fontSize:12, color:"var(--text-3)", marginTop:8}}>{pwMsg}</p>}
            </section>
          </div>
        )}

      <ConfirmDialog
        open={deleteConnId !== null}
        title="删除平台连接"
        message={deleteConnId ? `确定删除平台连接「${connections.find(c => c.id === deleteConnId)?.display_name || "未知"}」？此操作不可撤销。` : ""}
        confirmText="确认删除"
        cancelText="取消"
        danger
        onConfirm={() => { if (deleteConnId) void deleteConnection(deleteConnId); }}
        onCancel={() => setDeleteConnId(null)}
      />
      </div>
    </div>
  );
}
