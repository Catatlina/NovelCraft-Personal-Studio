import React, { useState, useEffect } from "react";
import { Send, Globe, BarChart3, Users, UserPlus, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { Pagination, Accordion } from "./ui";
import { usePagination } from "../hooks/usePagination";

export function PublishDashboard() {
  const [platforms] = useState(["wechat","toutiao","xiaohongshu","zhihu","medium","substack","twitter","wordpress","royalroad","kdp"]);
  const [selected, setSelected] = useState<string[]>([]);
  const [contentId, setContentId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [tab, setTab] = useState<"publish"|"overseas"|"roi"|"team">("publish");
  const [translateResult, setTranslateResult] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [logs, setLogs] = useState<any[]>([]);
  const [sensitiveResult, setSensitiveResult] = useState<{ passed: boolean; blocked_words: string[] } | null>(null);
  // NC-PUB-003: 效果看板 + AI 反哺建议
  const [dashboard, setDashboard] = useState<any>(null);
  const [feedback, setFeedback] = useState<any>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");

  const recordsPager = usePagination({ items: records, pageSize: 10, mode: "client" });
  const membersPager = usePagination({ items: members, pageSize: 10, mode: "client" });
  const logsPager = usePagination({ items: logs, pageSize: 10, mode: "client" });

  useEffect(() => {
    api("/api/v1/publish/records").then(d=>setRecords(d.data||[]));
  }, [result]);

  useEffect(() => {
    if (tab === "roi") api("/api/v1/analytics/dashboard").then(d=>setDashboard(d.data||null)).catch(()=>setDashboard(null));
  }, [tab]);

  async function loadFeedback() {
    setFeedbackBusy(true); setFeedbackError("");
    try {
      const projects = await api("/api/v1/projects");
      const r = await api("/api/v1/analytics/feedback", { method: "POST",
        body: JSON.stringify({ project_id: projects.data?.[0]?.id }) });
      setFeedback(r.data || null);
    } catch (caught) {
      setFeedbackError(`AI 反哺建议失败：${String(caught)}`);
    } finally { setFeedbackBusy(false); }
  }

  async function doPublish() {
    if (!contentId) return;
    const safety = await checkSensitive(contentId);
    if (safety && !safety.passed) {
      setResult({ blocked: true, words: safety.blocked_words });
      return;
    }
    const settled = await Promise.allSettled(selected.map(platform =>
      api(`/api/v1/publish?content_id=${contentId}&platform=${encodeURIComponent(platform)}`, {method:"POST"})
    ));
    setResult({ items: settled.map((item, index) => item.status === "fulfilled"
      ? { platform: selected[index], status: "queued", response: item.value }
      : { platform: selected[index], status: "failed", error: String(item.reason) }) });
  }

  async function doTranslate() {
    if (!contentId) return;
    const r = await api(`/api/v1/overseas/translate?content_id=${contentId}&target_lang=en`, {method:"POST"});
    setTranslateResult(r);
  }

  async function checkSensitive(id: string): Promise<{ passed: boolean; blocked_words: string[] } | null> {
    try {
      const r = await api<{ data: { passed: boolean; blocked_words: string[] } }>(`/api/v1/contents/${id}/check-sensitive`, { method: "POST" });
      setSensitiveResult(r.data);
      return r.data;
    } catch {
      setSensitiveResult(null);
      return null;
    }
  }

  async function loadMembers() {
    const r = await api("/api/v1/projects");
    const pid = r.data?.[0]?.id;
    if (pid) {
      const m = await api(`/api/v1/collaboration/members?project_id=${pid}`);
      setMembers(m.data||[]);
      const l = await api(`/api/v1/collaboration/logs?project_id=${pid}`);
      setLogs(l.data||[]);
    }
  }

  async function inviteMember() {
    if (!inviteEmail) return;
    const r = await api("/api/v1/projects");
    const pid = r.data?.[0]?.id;
    if (pid) {
      await api(`/api/v1/collaboration/invite?project_id=${pid}&email=${inviteEmail}&role=${inviteRole}`, {method:"POST"});
      setInviteEmail(""); loadMembers();
    }
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"180px 1fr",gap:16}}>
      <div className="card" style={{display:"flex",flexDirection:"column",gap:4,padding:12}}>
        <button
          className={`tab ${tab==="publish"?"on":""}`}
          onClick={()=>setTab("publish")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><Send size={16}/> 发布</button>

        <button
          className={`tab ${tab==="overseas"?"on":""}`}
          onClick={()=>setTab("overseas")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><Globe size={16}/> 出海</button>

        <button
          className={`tab ${tab==="roi"?"on":""}`}
          onClick={()=>setTab("roi")}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><BarChart3 size={16}/> 数据</button>

        <button
          className={`tab ${tab==="team"?"on":""}`}
          onClick={()=>{setTab("team");loadMembers();}}
          style={{justifyContent:"flex-start",textAlign:"left"}}
        ><Users size={16}/> 团队</button>
      </div>

      <div className="card">
        <div className="field" style={{marginBottom:16}}>
          <label>Content ID</label>
          <input className="form-input" value={contentId} onChange={e=>setContentId(e.target.value)} placeholder="输入 Content ID..." />
        </div>

        {tab === "publish" && (
          <div>
            <div className="card-head">
              <div className="card-title"><Send size={18}/> 选择平台发布</div>
            </div>
            <div style={{display:"flex",flexWrap:"wrap",gap:6,margin:"8px 0 14px"}}>
              {platforms.map(p=>(
                <label key={p} style={{display:"flex",alignItems:"center",gap:4,fontSize:13,padding:"4px 10px",border:"1px solid var(--border)",borderRadius:6,background:selected.includes(p)?"var(--primary)":"transparent",color:selected.includes(p)?"var(--brand-foreground)":"var(--text-2)",cursor:"pointer",transition:"all .15s"}}>
                  <input type="checkbox" checked={selected.includes(p)} onChange={()=>setSelected(prev=>prev.includes(p)?prev.filter(x=>x!==p):[...prev,p])} style={{display:"none"}}/>
                  {p}
                </label>
              ))}
            </div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
              <button className="btn-sm" onClick={()=>void checkSensitive(contentId)} disabled={!contentId} style={{border:"1px solid var(--border)",borderRadius:"var(--r-sm)",background:"var(--bg-hover)",color:"var(--text-2)"}}>
                <AlertTriangle size={14}/> 敏感词检查
              </button>
              <button className="btn-sm btn-primary" onClick={doPublish} disabled={!contentId||selected.length===0} style={{width:"fit-content"}}>
                <Send size={14}/> 发布到 {selected.length} 个平台
              </button>
            </div>
            {sensitiveResult && (sensitiveResult.passed
              ? <div style={{marginTop:8,padding:"6px 10px",borderRadius:"var(--r-sm)",fontSize:13,color:"var(--green)",background:"var(--success-bg)"}}>
                  <span className="dot green" style={{display:"inline-block",marginRight:6}}/>敏感词检查通过
                </div>
              : <div style={{marginTop:8,padding:"6px 10px",borderRadius:"var(--r-sm)",fontSize:13,color:"var(--red)",background:"var(--danger-bg)"}}>
                  检测到敏感词：{sensitiveResult.blocked_words.join("、")}
                </div>)}
            {result && (
              <Accordion items={[{
                key: "publish-raw",
                title: "发布回执（原始返回）",
                defaultOpen: false,
                content: (
                  <pre style={{fontSize:11,marginTop:12,padding:12,borderRadius:"var(--r-sm)",border:"1px solid var(--border)",color:"var(--text-2)",whiteSpace:"pre-wrap"}}>{JSON.stringify(result,null,2)}</pre>
                ),
              }]} />
            )}
          </div>
        )}

        {tab === "overseas" && (
          <div>
            <div className="card-head">
              <div className="card-title"><Globe size={18}/> 出海翻译</div>
            </div>
            <p className="cell-sub" style={{marginBottom:12}}>翻译管线: 分段翻译 → 文学润色 → 文化本地化 → 禁忌检查 → SEO优化</p>
            <button className="btn-sm btn-primary" onClick={doTranslate} disabled={!contentId} style={{width:"fit-content"}}>
              <Globe size={14}/> 英文本地化
            </button>
            {translateResult && (
              <div className="card" style={{marginTop:12,padding:16}}>
                <div className="card-head" style={{marginBottom:8}}>
                  <strong>翻译结果</strong>
                </div>
                <p style={{fontSize:13,whiteSpace:"pre-wrap",color:"var(--text-2)",margin:0}}>{translateResult.data?.translated?.slice(0,500)}</p>
              </div>
            )}
          </div>
        )}

        {tab === "roi" && (
          <div>
            {dashboard && (
              <div data-testid="performance-dashboard">
                <div className="card-head">
                  <div className="card-title"><BarChart3 size={18}/> 效果看板</div>
                </div>
                <div className="grid grid-4" style={{marginBottom:16}}>
                  <div className="stat">
                    <div className="stat-top">
                      <span className="stat-label">阅读</span>
                      <div className="stat-ic ic-purple"><BarChart3 size={18}/></div>
                    </div>
                    <div className="stat-val">{dashboard.totals?.total_reads ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-top">
                      <span className="stat-label">点赞</span>
                      <div className="stat-ic ic-green"><BarChart3 size={18}/></div>
                    </div>
                    <div className="stat-val">{dashboard.totals?.total_likes ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-top">
                      <span className="stat-label">分享</span>
                      <div className="stat-ic ic-cyan"><BarChart3 size={18}/></div>
                    </div>
                    <div className="stat-val">{dashboard.totals?.total_shares ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-top">
                      <span className="stat-label">收益</span>
                      <div className="stat-ic ic-orange"><BarChart3 size={18}/></div>
                    </div>
                    <div className="stat-val">¥{dashboard.totals?.total_revenue ?? 0}</div>
                  </div>
                </div>
                {(dashboard.roi_by_platform || []).length > 0 && (
                  <div className="table-wrap" style={{marginBottom:16}}>
                    <table><thead><tr><th>平台</th><th>条数</th><th>阅读</th><th>收益</th><th>RPM</th></tr></thead>
                    <tbody>
                      {dashboard.roi_by_platform.map((p:any)=><tr key={p.platform}>
                        <td>{p.platform}</td><td>{p.posts}</td><td>{p.reads}</td><td>¥{p.revenue}</td><td>{p.rpm}</td>
                      </tr>)}
                    </tbody></table>
                  </div>
                )}
                <h3 style={{fontSize:15,fontWeight:600,marginBottom:8}}>选题反哺</h3>
                {(dashboard.topic_suggestions || []).length > 0 ? (
                  dashboard.topic_suggestions.map((s:any,i:number)=>(
                    <div key={i} className="activity" style={{padding:"6px 0"}}>
                      <div>
                        <p>{s.suggestion}</p>
                        {s.source_title && <time className="cell-sub">（依据：{s.source_title}，{s.reads} 阅读）</time>}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty" style={{padding:24}}>
                    <p>暂无选题建议</p>
                  </div>
                )}
                <button className="btn-sm" disabled={feedbackBusy} onClick={()=>void loadFeedback()} style={{marginTop:12,border:"1px solid var(--border)",borderRadius:"var(--r-sm)",background:"var(--bg-hover)",color:"var(--text-2)"}}>
                  AI 深度反哺建议
                </button>
                {feedbackError && (
                  <div style={{marginTop:8,padding:"6px 10px",borderRadius:"var(--r-sm)",fontSize:13,color:"var(--red)",background:"var(--danger-bg)"}}>{feedbackError}</div>
                )}
                {feedback?.status === "no_data" && (
                  <div className="cell-sub" style={{marginTop:8}}>{feedback.message}</div>
                )}
                {feedback?.status === "ok" && (
                  <div className="card" style={{marginTop:8,padding:14}} data-testid="ai-feedback">
                    {(feedback.topic_suggestions || []).map((s:any,i:number)=>(
                      <div key={i} style={{padding:"4px 0"}}>
                        <strong style={{fontSize:13}}>{s.suggestion}</strong>
                        <div className="cell-sub">{s.rationale}{s.based_on?.length ? `（依据内容：${s.based_on.length} 篇）` : ""}</div>
                      </div>
                    ))}
                    {(feedback.writing_advice || []).length > 0 && (
                      <div style={{marginTop:8}}>
                        <strong style={{fontSize:13}}>写作建议</strong>
                        {feedback.writing_advice.map((a:string,i:number)=><div key={i} style={{fontSize:13,color:"var(--text-2)"}}>· {a}</div>)}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            <h3 style={{fontSize:15,fontWeight:600,margin:"16px 0 8px"}}>发布记录</h3>
            <div className="table-wrap">
              <table><thead><tr><th>平台</th><th>模式</th><th>状态</th><th>时间</th></tr></thead>
              <tbody>
                {recordsPager.pageData.map((r:any)=><tr key={r.id}>
                  <td>{r.platform}</td><td>{r.mode}</td>
                  <td>
                    <span className={`badge ${r.status==="published"?"green":"orange"}`}>{r.status}</span>
                  </td>
                  <td className="cell-sub">{r.created_at?.slice(0,16)}</td>
                </tr>)}
              </tbody></table>
              <Pagination
                page={recordsPager.page}
                pageSize={recordsPager.pageSize}
                total={records.length}
                onPageChange={recordsPager.setPage}
                onPageSizeChange={recordsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </div>
          </div>
        )}

        {tab === "team" && (
          <div>
            <div className="card-head">
              <div className="card-title"><Users size={18}/> 团队成员</div>
            </div>
            <div className="table-wrap" style={{marginBottom:20}}>
              <table><thead><tr><th>邮箱</th><th>角色</th><th>加入时间</th></tr></thead>
              <tbody>{membersPager.pageData.map((m:any,i:number)=><tr key={i}><td>{m.email}</td><td>{m.role}</td><td className="cell-sub">{m.created_at?.slice(0,16)}</td></tr>)}</tbody></table>
              <Pagination
                page={membersPager.page}
                pageSize={membersPager.pageSize}
                total={members.length}
                onPageChange={membersPager.setPage}
                onPageSizeChange={membersPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </div>

            <h3 style={{fontSize:15,fontWeight:600,marginBottom:12}}>邀请成员</h3>
            <div style={{display:"flex",gap:8,alignItems:"flex-end"}}>
              <div className="field" style={{flex:1,marginBottom:0}}>
                <label>邮箱</label>
                <input className="form-input" value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} placeholder="email@example.com" />
              </div>
              <div className="field" style={{width:120,marginBottom:0}}>
                <label>角色</label>
                <select className="form-input" value={inviteRole} onChange={e=>setInviteRole(e.target.value)}>
                  <option value="editor">编辑者</option>
                  <option value="viewer">查看者</option>
                </select>
              </div>
              <button className="btn-sm btn-primary" onClick={inviteMember}><UserPlus size={14}/>邀请</button>
            </div>

            <h3 style={{fontSize:15,fontWeight:600,margin:"20px 0 12px"}}>操作日志</h3>
            <div className="table-wrap">
              <table><thead><tr><th>用户</th><th>操作</th><th>目标</th><th>时间</th></tr></thead>
              <tbody>{logsPager.pageData.map((l:any,i:number)=><tr key={i}><td>{l.email}</td><td>{l.action}</td><td className="cell-sub">{l.target}</td>                  <td className="cell-sub">{l.created_at?.slice(0,16)}</td></tr>)}</tbody></table>
              <Pagination
                page={logsPager.page}
                pageSize={logsPager.pageSize}
                total={logs.length}
                onPageChange={logsPager.setPage}
                onPageSizeChange={logsPager.setPageSize}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
