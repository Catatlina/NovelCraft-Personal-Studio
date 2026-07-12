import React, { useState } from "react";
import { BookOpen, Database, TrendingUp, Play, Loader2 } from "lucide-react";
import { api } from "../lib/api";

export function Studio() {
  const [tab, setTab] = useState<"short"|"knowledge"|"hotspot">("short");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);

  // Short story
  const [template, setTemplate] = useState("viral");
  const [idea, setIdea] = useState("");

  // Knowledge
  const [kQuery, setKQuery] = useState("");
  const [kKind, setKKind] = useState("");
  const [kResults, setKResults] = useState<any[]>([]);

  // Hotspot
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [briefing, setBriefing] = useState<any>(null);

  async function createShortStory() {
    setBusy(true);
    const pid = (await api("/api/v1/projects")).data[0].id;
    const r = await api(`/api/v1/projects/${pid}/short-stories`, {
      method:"POST", body: JSON.stringify({ idea, template, genre: "都市", style: "现代" }),
    });
    setResult(r);
    setBusy(false);
    setMsg("短篇已创建！查看审阅页");
  }

  async function searchKnowledge() {
    const r = await api("/api/v1/projects");
    const pid = r.data[0].id;
    const params = new URLSearchParams({project_id: pid, query: kQuery});
    if (kKind) params.append("kind", kKind);
    const res = await api(`/api/v1/knowledge/search?${params}`, {method:"POST"});
    setKResults(res.data || []);
  }

  async function fetchHotspots() {
    const r = await api("/api/v1/projects");
    const pid = r.data[0].id;
    const res = await api(`/api/v1/knowledge/daily-briefing?project_id=${pid}`, {method:"POST"});
    const data = res.data || {};
    setHotspots(data.topics || []);
    setBriefing(data);
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"180px 1fr",gap:16,minHeight:400}}>
      <div className="panel" style={{display:"flex",flexDirection:"column",gap:4}}>
        <button className={tab==="short"?"active":""} onClick={()=>setTab("short")} style={{justifyContent:"flex-start"}}><BookOpen size={16}/> 短篇创作</button>

        <button className={tab==="knowledge"?"active":""} onClick={()=>setTab("knowledge")} style={{justifyContent:"flex-start"}}><Database size={16}/> 知识库</button>
        <button className={tab==="hotspot"?"active":""} onClick={()=>setTab("hotspot")} style={{justifyContent:"flex-start"}}><TrendingUp size={16}/> 热点</button>
      </div>

      <div className="panel">
        {msg && <div className="error" style={{background:"#1a3a28",color:"var(--success)",marginBottom:8}}>{msg}<button onClick={()=>setMsg("")} style={{float:"right",border:"none",background:"none",color:"var(--success)"}}>×</button></div>}

        {tab === "short" && (
          <div style={{display:"flex",flexDirection:"column",gap:12}}>
            <h2>短篇创作</h2>
            <div style={{display:"flex",gap:8,alignItems:"center"}}>
              <label style={{fontWeight:600,fontSize:14}}>模板:</label>
              <select value={template} onChange={e=>setTemplate(e.target.value)}>
                {["flash","emotional","suspense","viral","dialogue"].map(t=><option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <textarea value={idea} onChange={e=>setIdea(e.target.value)} placeholder="输入创意灵感..." rows={3} />
            <button className="primary" onClick={createShortStory} disabled={busy} style={{width:"fit-content"}}>
              {busy?<Loader2 className="spin" size={16}/>:<Play size={16}/>}生成短篇
            </button>
            {result && (
              <div style={{marginTop:12, padding:12, background:"var(--bg-subtle)", borderRadius:8}}>
                {result.data ? (
                  <>
                    <h4 style={{margin:0}}>{result.data.title || "短篇已生成"}</h4>
                    <p style={{fontSize:13, color:"var(--text-secondary)", marginTop:8, maxHeight:200, overflowY:"auto", whiteSpace:"pre-wrap"}}>
                      {typeof result.data.body === 'string'
                        ? result.data.body.slice(0,500)
                        : (() => { try { return (result.data.body?.content || []).map((p:any) => (p.content||[]).map((n:any) => n.text||'').join('')).join('\n\n').slice(0,500) } catch { return JSON.stringify(result.data.body).slice(0,500) } })()
                      }
                    </p>
                    {result.data.word_count != null && <small style={{color:"var(--text-muted)"}}>{result.data.word_count} 字</small>}
                    {result.data.status && <small style={{color:"var(--text-muted)", marginLeft:8}}>状态: {result.data.status}</small>}
                  </>
                ) : (
                  <>
                    <h4 style={{margin:0}}>生成完成</h4>
                    <pre style={{fontSize:11, maxHeight:300, overflowY:"auto"}}>{JSON.stringify(result, null, 2)}</pre>
                  </>
                )}
              </div>
            )}
          </div>
        )}


        {tab === "knowledge" && (
          <div>
            <h2>知识库检索</h2>
            <div style={{display:"flex",gap:8,marginBottom:12}}>
              <input value={kQuery} onChange={e=>setKQuery(e.target.value)} placeholder="搜索关键词..." style={{flex:1}} />
              <select value={kKind} onChange={e=>setKKind(e.target.value)}>
                <option value="">全部类型</option>
                {["character","worldview","hotspot","article","prompt_ref","golden_line","title","platform_rule"].map(k=><option key={k}>{k}</option>)}
              </select>
              <button className="primary" onClick={searchKnowledge}>搜索</button>
            </div>
            {kResults.map((item:any)=><div key={item.id} style={{padding:"8px 0",borderBottom:"1px solid var(--border-subtle)"}}>
              <small style={{color:"var(--text-muted)"}}>[{item.kind}]</small> <strong>{item.title}</strong>
              <p style={{margin:0,fontSize:14,color:"var(--text-secondary)"}}>{item.body?.slice(0,200)}</p>
            </div>)}
          </div>
        )}

        {tab === "hotspot" && (
          <div>
            <h2>热点监控</h2>
            <button className="primary" onClick={fetchHotspots} style={{marginBottom:12}}><TrendingUp size={16}/> 获取今日热点</button>
            {hotspots.map((t:any,i:number)=><div key={i} style={{padding:"8px 0",borderBottom:"1px solid var(--border-subtle)"}}>
              <strong>{t.title}</strong> <small style={{color:"var(--text-muted)"}}>[{t.category}] 热度:{t.score}</small>
              <p style={{margin:0,fontSize:13,color:"var(--text-secondary)"}}>{t.angle}</p>
            </div>)}
            {briefing?.generated && <div style={{marginTop:12}}><h3>已生成内容草稿</h3>
              {briefing.generated.map((g:any,i:number)=><div key={i} style={{padding:8,border:"1px solid var(--border-subtle)",borderRadius:8,marginBottom:8}}>
                <strong>{g.topic}</strong><pre style={{fontSize:11,color:"var(--text-muted)",whiteSpace:"pre-wrap"}}>{JSON.stringify(g.draft,null,2)?.slice(0,300)}</pre>
              </div>)}
            </div>}
          </div>
        )}
      </div>
    </div>
  );
}
