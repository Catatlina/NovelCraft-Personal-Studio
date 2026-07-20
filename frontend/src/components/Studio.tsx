import React, { useState } from "react";
import { BookOpen, Database, TrendingUp, Play, Loader2, CopyCheck } from "lucide-react";
import { api } from "../lib/api";
import { Accordion } from "./ui";

export function Studio() {
  const [tab, setTab] = useState<"short"|"knowledge"|"hotspot"|"imitation">("short");
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
  const [sourceText, setSourceText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [imitateInstruction, setImitateInstruction] = useState("提炼文风并仿写为原创网文开篇");

  async function createShortStory() {
    setBusy(true); setMsg("");
    try {
      const pid = (await api("/api/v1/projects")).data[0].id;
      const r = await api(`/api/v1/projects/${pid}/short-stories`, {
        method:"POST", body: JSON.stringify({ idea, template, genre: "都市", style: "现代" }),
      });
      setResult(r);
      setMsg("短篇已创建！查看审阅页");
    } catch (caught) {
      setMsg(`短篇生成失败：${String(caught)}`);
    } finally {
      setBusy(false);
    }
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

  async function runImitation() {
    setBusy(true); setMsg("");
    try {
      const r = await api("/api/v1/projects");
      const pid = r.data[0].id;
      const res = await api("/api/v1/imitation", {
        method: "POST",
        body: JSON.stringify({ project_id: pid, source_text: sourceText, source_url: sourceUrl, instruction: imitateInstruction }),
      });
      setResult(res);
      setMsg("仿写样稿已生成。");
    } catch (caught) {
      setMsg(`仿写失败：${String(caught)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"180px 1fr",gap:16,minHeight:400}}>
      <div className="card" style={{display:"flex",flexDirection:"column",gap:4,padding:12}}>
        <button
          className={`tab ${tab==="short"?"on":""}`}
          onClick={()=>setTab("short")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><BookOpen size={16}/> 短篇创作</button>

        <button
          className={`tab ${tab==="knowledge"?"on":""}`}
          onClick={()=>setTab("knowledge")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><Database size={16}/> 知识库</button>

        <button
          className={`tab ${tab==="hotspot"?"on":""}`}
          onClick={()=>setTab("hotspot")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><TrendingUp size={16}/> 热点</button>

        <button
          className={`tab ${tab==="imitation"?"on":""}`}
          onClick={()=>setTab("imitation")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><CopyCheck size={16}/> 仿写</button>
      </div>

      <div className="card">
        {msg && (
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"8px 14px",borderRadius:"var(--r-sm)",marginBottom:12,fontSize:13,background:"var(--success-bg)",color:"var(--green)"}}>
            <span>{msg}</span>
            <button onClick={()=>setMsg("")} style={{border:"none",background:"none",color:"var(--green)",fontSize:18,lineHeight:1,cursor:"pointer"}}>×</button>
          </div>
        )}

        {tab === "short" && (
          <div style={{display:"flex",flexDirection:"column",gap:12}}>
            <div className="card-head">
              <div className="card-title"><BookOpen size={18}/> 短篇创作</div>
            </div>
            <div className="field">
              <label>模板</label>
              <select className="form-input" value={template} onChange={e=>setTemplate(e.target.value)}>
                {["flash","emotional","suspense","viral","dialogue"].map(t=><option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="field">
              <label>创意灵感</label>
              <textarea className="form-input" value={idea} onChange={e=>setIdea(e.target.value)} placeholder="输入创意灵感..." rows={3} />
            </div>
            <button className="btn-sm btn-primary" onClick={createShortStory} disabled={busy} style={{width:"fit-content"}}>
              {busy?<Loader2 className="spin" size={16}/>:<Play size={16}/>}生成短篇
            </button>
            {result && (
              <div className="card" style={{marginTop:12}}>
                {result.data ? (
                  <>
                    <h4 style={{margin:0,fontSize:15}}>{result.data.title || "短篇已生成"}</h4>
                    <p style={{fontSize:13,color:"var(--text-2)",marginTop:8,maxHeight:200,overflowY:"auto",whiteSpace:"pre-wrap"}}>
                      {typeof result.data.body === 'string'
                        ? result.data.body.slice(0,500)
                        : (() => { try { return (result.data.body?.content || []).map((p:any) => (p.content||[]).map((n:any) => n.text||'').join('')).join('\n\n').slice(0,500) } catch { return JSON.stringify(result.data.body).slice(0,500) } })()
                      }
                    </p>
                    <div style={{display:"flex",gap:8,marginTop:8}}>
                      {result.data.word_count != null && <span className="badge purple">{result.data.word_count} 字</span>}
                      {result.data.status && <span className="badge cyan">{result.data.status}</span>}
                    </div>
                  </>
                ) : (
                  <>
                    <h4 style={{margin:0,fontSize:15}}>生成完成</h4>
                    <Accordion items={[{
                      key: "short-raw",
                      title: "原始返回",
                      defaultOpen: false,
                      content: (
                        <pre style={{fontSize:11,maxHeight:300,overflowY:"auto",marginTop:8,color:"var(--text-2)"}}>{JSON.stringify(result, null, 2)}</pre>
                      ),
                    }]} />
                  </>
                )}
              </div>
            )}
          </div>
        )}


        {tab === "knowledge" && (
          <div>
            <div className="card-head">
              <div className="card-title"><Database size={18}/> 知识库检索</div>
            </div>
            <div style={{display:"flex",gap:8,marginBottom:12}}>
              <input className="form-input" value={kQuery} onChange={e=>setKQuery(e.target.value)} placeholder="搜索关键词..." style={{flex:1}} />
              <select className="form-input" value={kKind} onChange={e=>setKKind(e.target.value)} style={{width:140}}>
                <option value="">全部类型</option>
                {["character","worldview","hotspot","article","prompt_ref","golden_line","title","platform_rule"].map(k=><option key={k}>{k}</option>)}
              </select>
              <button className="btn-sm btn-primary" onClick={searchKnowledge}>搜索</button>
            </div>
            {kResults.length > 0 ? (
              kResults.map((item:any)=>(
                <div key={item.id} className="activity" style={{padding:"8px 0"}}>
                  <div>
                    <p style={{display:"flex",alignItems:"center",gap:6}}>
                      <span className="badge gray" style={{fontSize:10}}>{item.kind}</span>
                      <strong>{item.title}</strong>
                    </p>
                    <p style={{margin:0,fontSize:13,color:"var(--text-2)"}}>{item.body?.slice(0,200)}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty">
                <div className="empty-ic"><Database size={26}/></div>
                <h3>暂无结果</h3>
                <p>输入关键词搜索知识库</p>
              </div>
            )}
          </div>
        )}

        {tab === "hotspot" && (
          <div>
            <div className="card-head">
              <div className="card-title"><TrendingUp size={18}/> 热点监控</div>
            </div>
            <button className="btn-sm btn-primary" onClick={fetchHotspots} style={{marginBottom:12}}>
              <TrendingUp size={16}/> 获取今日热点
            </button>
            {hotspots.length > 0 ? hotspots.map((t:any,i:number)=>(
              <div key={i} className="activity" style={{padding:"8px 0"}}>
                <div>
                  <p style={{display:"flex",alignItems:"center",gap:6,marginBottom:2}}>
                    <strong>{t.title}</strong>
                    <span className="badge orange">{t.category}</span>
                    <span className="cell-sub">热度:{t.score}</span>
                  </p>
                  <p style={{margin:0,fontSize:13,color:"var(--text-2)"}}>{t.angle}</p>
                </div>
              </div>
            )) : (
              <div className="empty">
                <div className="empty-ic"><TrendingUp size={26}/></div>
                <h3>暂无热点</h3>
                <p>点击按钮获取今日热点数据</p>
              </div>
            )}
            {briefing?.generated && (
              <div style={{marginTop:12}}>
                <h3 style={{fontSize:15,fontWeight:600,marginBottom:8}}>已生成内容草稿</h3>
                {briefing.generated.map((g:any,i:number)=>(
                  <div key={i} className="card" style={{marginBottom:8,padding:14}}>
                    <div className="card-head" style={{marginBottom:8}}>
                      <strong>{g.topic}</strong>
                    </div>
                    <pre style={{fontSize:11,color:"var(--text-2)",whiteSpace:"pre-wrap",margin:0}}>{JSON.stringify(g.draft,null,2)?.slice(0,300)}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "imitation" && (
          <div style={{display:"flex",flexDirection:"column",gap:12}}>
            <div className="card-head">
              <div className="card-title"><CopyCheck size={18}/> 仿写模块</div>
            </div>
            <div className="field">
              <label>原文链接（可选）</label>
              <input className="form-input" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)} placeholder="原文 HTTPS 链接（可选）" />
            </div>
            <div className="field">
              <label>原文内容</label>
              <textarea className="form-input" value={sourceText} onChange={e=>setSourceText(e.target.value)} placeholder="或粘贴原文，至少 200 字" rows={8} />
            </div>
            <div className="field">
              <label>仿写要求</label>
              <input className="form-input" value={imitateInstruction} onChange={e=>setImitateInstruction(e.target.value)} placeholder="仿写要求" />
            </div>
            <button className="btn-sm btn-primary" onClick={runImitation} disabled={busy || (!sourceText.trim() && !sourceUrl.trim())} style={{width:"fit-content"}}>
              {busy?<Loader2 className="spin" size={16}/>:<CopyCheck size={16}/>}生成原创仿写
            </button>
            {result?.data?.copyright_warning && (
              <div className={`badge ${result.data.copyright_risk === "manual_review" ? "red" : "gray"}`} style={{padding:"8px 14px",borderRadius:"var(--r-sm)",fontSize:13,whiteSpace:"normal",textAlign:"left"}}>
                <strong>版权/相似度提示：</strong>{result.data.copyright_warning}
                {result.data.similarity && <span> 相似度 {Math.round((result.data.similarity.similarity || 0) * 100)}%，处理建议：{result.data.similarity.action}</span>}
              </div>
            )}
            {result?.data && (
              <Accordion items={[{
                key: "imitation-raw",
                title: "原始返回",
                defaultOpen: false,
                content: (
                  <pre style={{fontSize:11,maxHeight:300,overflowY:"auto",padding:12,borderRadius:"var(--r-sm)",border:"1px solid var(--border)",color:"var(--text-2)",whiteSpace:"pre-wrap",margin:0}}>{JSON.stringify(result.data, null, 2)}</pre>
                ),
              }]} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
