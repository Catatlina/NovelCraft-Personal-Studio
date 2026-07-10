import React, { useState, useEffect } from "react";
import { Send, Globe, BarChart3, Users, UserPlus, AlertTriangle } from "lucide-react";

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

  useEffect(() => {
    fetch("/api/v1/publish/records").then(r=>r.json()).then(d=>setRecords(d.data||[]));
  }, [result]);

  async function doPublish() {
    if (!contentId) return;
    const r = await fetch(`/api/v1/publish?content_id=${contentId}&platform=${selected.join(",")}`, {method:"POST"});
    setResult(await r.json());
  }

  async function doTranslate() {
    if (!contentId) return;
    const r = await fetch(`/api/v1/overseas/translate?content_id=${contentId}&target_lang=en`, {method:"POST"});
    setTranslateResult(await r.json());
  }

  async function checkSensitive(contentId: string) {
    return;
  }

  async function loadMembers() {
    const r = await fetch("/api/v1/projects").then(r=>r.json());
    const pid = r.data?.[0]?.id;
    if (pid) {
      const m = await fetch(`/api/v1/collaboration/members?project_id=${pid}`).then(r=>r.json());
      setMembers(m.data||[]);
      const l = await fetch(`/api/v1/collaboration/logs?project_id=${pid}`).then(r=>r.json());
      setLogs(l.data||[]);
    }
  }

  async function inviteMember() {
    if (!inviteEmail) return;
    const r = await fetch("/api/v1/projects").then(r=>r.json());
    const pid = r.data?.[0]?.id;
    if (pid) {
      await fetch(`/api/v1/collaboration/invite?project_id=${pid}&email=${inviteEmail}&role=${inviteRole}`, {method:"POST"});
      setInviteEmail(""); loadMembers();
    }
  }

  return (
    <div style={{display:"grid",gridTemplateColumns:"180px 1fr",gap:16}}>
      <div className="panel" style={{display:"flex",flexDirection:"column",gap:4}}>
        <button className={tab==="publish"?"active":""} onClick={()=>setTab("publish")} style={{justifyContent:"flex-start"}}><Send size={16}/> 发布</button>
        <button className={tab==="overseas"?"active":""} onClick={()=>setTab("overseas")} style={{justifyContent:"flex-start"}}><Globe size={16}/> 出海</button>
        <button className={tab==="roi"?"active":""} onClick={()=>setTab("roi")} style={{justifyContent:"flex-start"}}><BarChart3 size={16}/> 数据</button>
        <button className={tab==="team"?"active":""} onClick={()=>{setTab("team");loadMembers();}} style={{justifyContent:"flex-start"}}><Users size={16}/> 团队</button>
      </div>

      <div className="panel">
        <div style={{display:"flex",gap:8,marginBottom:16}}>
          <input value={contentId} onChange={e=>setContentId(e.target.value)} placeholder="Content ID..." style={{flex:1}} />
        </div>

        {tab === "publish" && (
          <div>
            <h3>选择平台发布</h3>
            <div style={{display:"flex",flexWrap:"wrap",gap:6,margin:"8px 0"}}>
              {platforms.map(p=>(
                <label key={p} style={{display:"flex",alignItems:"center",gap:4,fontSize:14,padding:"4px 8px",border:"1px solid var(--border-subtle)",borderRadius:6,background:selected.includes(p)?"var(--brand-500)":"transparent",color:selected.includes(p)?"#fff":"inherit"}}>
                  <input type="checkbox" checked={selected.includes(p)} onChange={()=>setSelected(prev=>prev.includes(p)?prev.filter(x=>x!==p):[...prev,p])} style={{display:"none"}}/>
                  {p}
                </label>
              ))}
            </div>
            <button className="primary" onClick={doPublish} disabled={!contentId||selected.length===0}><Send size={14}/> 发布到 {selected.length} 个平台</button>
            {result && <pre style={{fontSize:11,marginTop:12}}>{JSON.stringify(result,null,2)}</pre>}
          </div>
        )}

        {tab === "overseas" && (
          <div>
            <h3>出海翻译</h3>
            <p style={{color:"var(--text-muted)",fontSize:13}}>翻译管线: 分段翻译 → 文学润色 → 文化本地化 → 禁忌检查 → SEO优化</p>
            <button className="primary" onClick={doTranslate} disabled={!contentId}><Globe size={14}/> 英文本地化</button>
            {translateResult && (
              <div style={{marginTop:12}}>
                <div style={{padding:12,border:"1px solid var(--border-subtle)",borderRadius:8}}>
                  <strong>翻译结果:</strong>
                  <p style={{fontSize:13,whiteSpace:"pre-wrap"}}>{translateResult.data?.translated?.slice(0,500)}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "roi" && (
          <div>
            <h3>发布记录</h3>
            <table><thead><tr><th>平台</th><th>模式</th><th>状态</th><th>时间</th></tr></thead>
            <tbody>
              {records.slice(0,20).map((r:any)=><tr key={r.id}>
                <td>{r.platform}</td><td>{r.mode}</td>
                <td style={{color:r.status==="published"?"var(--success)":"var(--warning)"}}>{r.status}</td>
                <td style={{fontSize:12}}>{r.created_at?.slice(0,16)}</td>
              </tr>)}
            </tbody></table>
          </div>
        )}

        {tab === "team" && (
          <div>
            <h3>团队成员</h3>
            <table><thead><tr><th>邮箱</th><th>角色</th><th>加入时间</th></tr></thead>
            <tbody>{members.map((m:any,i:number)=><tr key={i}><td>{m.email}</td><td>{m.role}</td><td style={{fontSize:12}}>{m.created_at?.slice(0,16)}</td></tr>)}</tbody></table>

            <h3 style={{marginTop:16}}>邀请成员</h3>
            <div style={{display:"flex",gap:8}}>
              <input value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} placeholder="email@example.com" style={{flex:1}} />
              <select value={inviteRole} onChange={e=>setInviteRole(e.target.value)}>
                <option value="editor">编辑者</option>
                <option value="viewer">查看者</option>
              </select>
              <button className="primary" onClick={inviteMember}><UserPlus size={14}/>邀请</button>
            </div>

            <h3 style={{marginTop:16}}>操作日志</h3>
            <table><thead><tr><th>用户</th><th>操作</th><th>目标</th><th>时间</th></tr></thead>
            <tbody>{logs.slice(0,20).map((l:any,i:number)=><tr key={i}><td>{l.email}</td><td>{l.action}</td><td style={{fontSize:12}}>{l.target}</td><td style={{fontSize:11}}>{l.created_at?.slice(0,16)}</td></tr>)}</tbody></table>
          </div>
        )}
      </div>
    </div>
  );
}
