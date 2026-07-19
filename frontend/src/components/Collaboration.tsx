/** M5: Collaboration operations + member management */
import React, { useState, useEffect } from "react";
import { UserPlus, Shield, Trash2, Activity } from "lucide-react";
import { api } from "../lib/api";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

type Member = { id?: string; email: string; role: string; created_at?: string };
type Log = { id: string; action: string; detail: string; created_at: string };

export function CollaborationPanel({ projectId }: { projectId: string }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");

  useEffect(() => {
    api<{ data: Member[] }>(`/api/v1/collaboration/members?project_id=${projectId}`).then(d => setMembers(d.data || []));
    api<{ data: Log[] }>(`/api/v1/collaboration/logs?project_id=${projectId}`).then(d => setLogs(d.data || []));
  }, [projectId]);

  const membersPager = usePagination({ items: members, pageSize: 10, mode: "client" });
  const logsPager = usePagination({ items: logs, pageSize: 10, mode: "client" });

  async function invite() {
    if (!inviteEmail) return;
    await api(`/api/v1/collaboration/invite?project_id=${projectId}&email=${encodeURIComponent(inviteEmail)}&role=${inviteRole}`, { method: "POST" });
    setInviteEmail("");
    const d = await api<{ data: Member[] }>(`/api/v1/collaboration/members?project_id=${projectId}`);
    setMembers(d.data || []);
  }

  const roleIcon = (r: string) => r === "owner" ? <Shield size={12} /> : r === "editor" ? <Activity size={12} /> : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card">
        <div className="card-head">
          <div className="card-title"><UserPlus size={14} /> 成员管理</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} style={{ flex: 1 }} />
          <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
            <option value="viewer">只读</option>
            <option value="editor">编辑</option>
          </select>
          <button className="btn-sm" onClick={invite}>邀请</button>
        </div>
        <table style={{ width: "100%", fontSize: 13, marginTop: 8 }}>
          <tbody>
            {membersPager.pageData.map(m => (
              <tr key={m.id || m.email}>
                <td style={{ fontWeight: 600 }}>{roleIcon(m.role)} {m.email}</td>
                <td><span className="badge gray">{m.role}</span></td>
                <td style={{ fontSize: 11 }}>{m.created_at ? new Date(m.created_at).toLocaleDateString() : "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination
          page={membersPager.page}
          pageSize={membersPager.pageSize}
          total={members.length}
          onPageChange={membersPager.setPage}
          onPageSizeChange={membersPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>

      <div className="card">
        <div className="card-head">
          <div className="card-title">操作日志</div>
        </div>
        {logs.length === 0 ? (
          <div className="empty"><p>暂无操作日志</p></div>
        ) : logsPager.pageData.map(l => (
          <div key={l.id} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
            <strong>{l.action}</strong>
            <span style={{ marginLeft: 8, color: "var(--text-2)" }}>{l.detail}</span>
            <small style={{ float: "right", color: "var(--text-3)" }}>{new Date(l.created_at).toLocaleString()}</small>
          </div>
        ))}
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
  );
}
