import React, { useEffect, useState } from "react";
import { Bot, CircleCheck, CircleDashed } from "lucide-react";
import { api } from "../lib/api";

type Role = { role_key: string; provider: string; model: string; provider_status?: { status?: string } };
const LABELS: Record<string, string> = {
  planner: "大纲规划",
  chapter_skeleton: "章节骨架",
  scene_expander: "场景扩写",
  dialogue_editor: "对白编辑",
  continuity_reviewer: "连续性审阅",
  publication_editor: "发布编辑",
};

export function EditorRoleStatus({ projectId }: { projectId?: string }) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!projectId) return;
    let active = true;
    setLoading(true);
    api<{ roles: Role[] }>(`/api/v1/authoring/provider-roles?project_id=${encodeURIComponent(projectId)}`)
      .then(data => { if (active) setRoles(data.roles || []); })
      .catch(() => { if (active) setRoles([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId]);
  if (!projectId || (!loading && !roles.length)) return null;
  return (
    <div className="editor-role-status" aria-label="AI 角色路由状态">
      <div className="editor-role-status-title"><Bot size={13} />协作角色</div>
      <div className="editor-role-chips">
        {roles.map(role => {
          const ready = role.provider_status?.status === "available";
          return <span key={role.role_key} className={ready ? "ready" : "pending"} title={`${role.provider} · ${role.model}`}>
            {ready ? <CircleCheck size={11} /> : <CircleDashed size={11} />}{LABELS[role.role_key] || role.role_key} · {role.provider}
          </span>;
        })}
      </div>
    </div>
  );
}
