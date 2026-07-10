/** M5: Collaboration operations + member management */
import React, { useState, useEffect } from "react";
import { UserPlus, Shield, Trash2, Activity } from "lucide-react";
import { api } from "../lib/api";

type Member = { id: string; email: string; role: string; joined_at: string };
type Log = { id: string; action: string; detail: string; created_at: string };

export function CollaborationPanel({ projectId }: { projectId: string }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");

  useEffect(() => {
    api<Member[]>(`/api/v1/projects/${projectId}/members`).then(d => setMembers(d || []));
    api<Log[]>(`/api/v1/projects/${projectId}/operation-logs`).then(d => setLogs(d || []));
  }, [projectId]);

  async function invite() {
    if (!inviteEmail) return;
    await api(`/api/v1/projects/${projectId}/members/invite`, { method: "POST", body: JSON.stringify({ email: inviteEmail, role: inviteRole }) });
    setInviteEmail("");
    const d = await api<Member[]>(`/api/v1/projects/${projectId}/members`);
    setMembers(d || []);
  }

  const roleIcon = (r: string) => r === "owner" ? <Shield size={12} /> : r === "editor" ? <Activity size={12} /> : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel">
        <h3><UserPlus size={14} /> 成员管理</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} style={{ flex: 1 }} />
          <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
            <option value="viewer">只读</option>
            <option value="editor">编辑</option>
          </select>
          <button onClick={invite}>邀请</button>
        </div>
        <table style={{ width: "100%", fontSize: 13, marginTop: 8 }}>
          <tbody>
            {members.map(m => (
              <tr key={m.id}>
                <td style={{ fontWeight: 600 }}>{roleIcon(m.role)} {m.email}</td>
                <td style={{ color: "var(--text-muted)" }}>{m.role}</td>
                <td style={{ fontSize: 11 }}>{new Date(m.joined_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>操作日志</h3>
        {logs.slice(0, 20).map(l => (
          <div key={l.id} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid var(--border-subtle)" }}>
            <strong>{l.action}</strong>
            <span style={{ marginLeft: 8, color: "var(--text-muted)" }}>{l.detail}</span>
            <small style={{ float: "right" }}>{new Date(l.created_at).toLocaleString()}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
