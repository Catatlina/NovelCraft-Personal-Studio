import React, { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleDashed, PlugZap, RefreshCw, XCircle } from "lucide-react";
import { ApiError, api } from "../lib/api";
import "../styles/proto.css";

type Tab =
  | "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard"
  | "progress" | "review" | "editor" | "costs" | "prompts" | "dag"
  | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout"
  | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins";

type MatrixRow = {
  page: string;
  action: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  endpoint: string;
  tab: Tab;
  probe?: string;
  needs?: "project" | "novel" | "content" | "manual" | "credentials";
};

type ProbeState = {
  status: "checking" | "ok" | "blocked" | "manual" | "error";
  message: string;
};

function endpoint(path: string, vars: Record<string, string>) {
  return path
    .replaceAll("{project_id}", encodeURIComponent(vars.project_id || ""))
    .replaceAll("{novel_id}", encodeURIComponent(vars.novel_id || ""))
    .replaceAll("{content_id}", encodeURIComponent(vars.content_id || ""));
}

function apiMessage(caught: unknown) {
  if (caught instanceof ApiError) {
    const payload = caught.payload as any;
    const detail = payload?.detail || payload?.message || payload?.error;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map(item => item?.msg || JSON.stringify(item)).join("；");
    if (detail && typeof detail === "object") return JSON.stringify(detail);
    return `HTTP ${caught.status}`;
  }
  return caught instanceof Error ? caught.message : String(caught);
}

function badgeClass(status: ProbeState["status"]) {
  if (status === "ok") return "badge green";
  if (status === "error") return "badge red";
  if (status === "manual") return "badge cyan";
  return "badge orange";
}

function iconFor(status: ProbeState["status"]) {
  if (status === "ok") return <CheckCircle2 size={13} />;
  if (status === "error") return <XCircle size={13} />;
  return <CircleDashed size={13} />;
}

const ROWS: MatrixRow[] = [
  { page: "概览/工作台", action: "读取项目与健康状态", method: "GET", endpoint: "/api/v1/projects", probe: "/api/v1/projects", tab: "dashboard" },
  { page: "概览/工作台", action: "读取统计总览", method: "GET", endpoint: "/api/v1/stats/overview", probe: "/api/v1/stats/overview", tab: "overview" },
  { page: "扫榜选书", action: "榜源列表/扫描/导入/分析", method: "GET", endpoint: "/api/v1/ranking/sources", probe: "/api/v1/ranking/sources", tab: "ranking", needs: "project" },
  { page: "书库管理", action: "书库列表与详情", method: "GET", endpoint: "/api/v1/ranking/library/books?project_id={project_id}", probe: "/api/v1/ranking/library/books?project_id={project_id}&limit=1", tab: "library", needs: "project" },
  { page: "灵感创作", action: "创建作品并启动 Bootstrap", method: "POST", endpoint: "/api/v1/projects/{project_id}/novels + /api/v1/novels/{novel_id}/bootstrap", tab: "wizard", needs: "project" },
  { page: "创作进度", action: "读取/确认工作流节点", method: "GET", endpoint: "/api/v1/runs/latest?project_id={project_id}", probe: "/api/v1/runs/latest?project_id={project_id}", tab: "progress", needs: "project" },
  { page: "编辑器", action: "章节保存、AI 续写/润色/去AI味", method: "PUT", endpoint: "/api/v1/contents/{content_id}", tab: "editor", needs: "content" },
  { page: "审阅", action: "叙事时间线与人物弧线", method: "GET", endpoint: "/api/v1/novels/{novel_id}/narrative", probe: "/api/v1/novels/{novel_id}/narrative", tab: "review", needs: "novel" },
  { page: "伏笔看板", action: "伏笔种植/回收记录", method: "GET", endpoint: "/api/v1/novels/{novel_id}/foreshadowings", probe: "/api/v1/novels/{novel_id}/foreshadowings", tab: "foreshadowing", needs: "novel" },
  { page: "热点追踪", action: "热点源、日报与内容生成", method: "GET", endpoint: "/api/v1/hotspots", probe: "/api/v1/hotspots", tab: "hotspot", needs: "credentials" },
  { page: "内容工作室", action: "短篇/仿写/知识检索", method: "GET", endpoint: "/api/v1/knowledge?project_id={project_id}", probe: "/api/v1/knowledge?project_id={project_id}", tab: "studio", needs: "project" },
  { page: "多平台分发", action: "按平台改写/分发", method: "POST", endpoint: "/api/v1/contents/{content_id}/fanout", tab: "fanout", needs: "content" },
  { page: "知识库", action: "知识列表、搜索、导入、重建索引", method: "GET", endpoint: "/api/v1/knowledge?project_id={project_id}", probe: "/api/v1/knowledge?project_id={project_id}", tab: "knowledge", needs: "project" },
  { page: "发布看板", action: "发布记录、敏感词、人工回执、ROI", method: "GET", endpoint: "/api/v1/publish/records", probe: "/api/v1/publish/records", tab: "publish" },
  { page: "成本追踪", action: "AI 调用、预算、模型路由", method: "GET", endpoint: "/api/v1/ai-calls", probe: "/api/v1/ai-calls", tab: "costs" },
  { page: "Prompt 管理", action: "Prompt 库读取", method: "GET", endpoint: "/api/v1/admin/prompts", probe: "/api/v1/admin/prompts", tab: "prompts" },
  { page: "工作流编排", action: "读取/保存自定义 DAG", method: "GET", endpoint: "/api/v1/admin/workflows", probe: "/api/v1/admin/workflows", tab: "dag", needs: "project" },
  { page: "版本树", action: "章节版本列表与恢复", method: "GET", endpoint: "/api/v1/contents/{content_id}/versions", probe: "/api/v1/contents/{content_id}/versions", tab: "versions", needs: "content" },
  { page: "协作管理", action: "成员、邀请、操作日志", method: "GET", endpoint: "/api/v1/collaboration/members?project_id={project_id}", probe: "/api/v1/collaboration/members?project_id={project_id}", tab: "collaboration", needs: "project" },
  { page: "插件管理", action: "社区技能与工具节点", method: "GET", endpoint: "/api/v1/skills/community", probe: "/api/v1/skills/community", tab: "plugins" },
  { page: "智能体", action: "Agent 状态聚合", method: "GET", endpoint: "/api/v1/agents/status", probe: "/api/v1/agents/status", tab: "agents" },
  { page: "设置", action: "Provider、预算、平台连接", method: "GET", endpoint: "/api/v1/admin/providers", probe: "/api/v1/admin/providers", tab: "settings" },
];

export function IntegrationMatrix({ projectId, novelId, contentId, onNavigate }: {
  projectId?: string;
  novelId?: string;
  contentId?: string;
  onNavigate: (tab: Tab) => void;
}) {
  const [states, setStates] = useState<Record<string, ProbeState>>({});
  const [busy, setBusy] = useState(false);
  const vars = useMemo(() => ({
    project_id: projectId || "",
    novel_id: novelId || "",
    content_id: contentId || "",
  }), [projectId, novelId, contentId]);

  async function refresh() {
    setBusy(true);
    const next: Record<string, ProbeState> = {};
    for (const row of ROWS) {
      const key = `${row.page}-${row.action}`;
      if (row.needs === "project" && !projectId) {
        next[key] = { status: "blocked", message: "缺项目上下文" };
        continue;
      }
      if (row.needs === "novel" && !novelId) {
        next[key] = { status: "blocked", message: "缺作品上下文" };
        continue;
      }
      if (row.needs === "content" && !contentId) {
        next[key] = { status: "blocked", message: "缺章节/内容上下文" };
        continue;
      }
      if (!row.probe) {
        next[key] = { status: "manual", message: "操作触发型接口" };
        continue;
      }
      try {
        await api(endpoint(row.probe, vars));
        next[key] = { status: "ok", message: "接口可访问" };
      } catch (caught) {
        const message = apiMessage(caught);
        const unauthorized = caught instanceof ApiError && (caught.status === 401 || caught.status === 403);
        next[key] = { status: unauthorized ? "blocked" : "error", message };
      }
    }
    setStates(next);
    setBusy(false);
  }

  useEffect(() => { void refresh(); }, [projectId, novelId, contentId]);

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-head">
        <div className="card-title"><PlugZap size={16} /> 真实接入矩阵</div>
        <button className="btn-sm btn-ghost" onClick={refresh} disabled={busy}>
          <RefreshCw size={14} /> {busy ? "检测中…" : "重新检测"}
        </button>
      </div>
      <p style={{ color: "var(--text-2)", fontSize: 13, marginBottom: 12 }}>
        这里列的是正式 React 前端的页面入口、主要操作和后端接口。绿色表示当前登录态下接口可访问；橙色表示缺项目/作品/章节或需要按钮操作触发；红色表示接口实际报错。
      </p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>页面</th><th>主要操作</th><th>接口</th><th>状态</th><th>入口</th></tr></thead>
          <tbody>
            {ROWS.map(row => {
              const key = `${row.page}-${row.action}`;
              const state = states[key] || { status: "checking", message: "待检测" } as ProbeState;
              return (
                <tr key={key}>
                  <td><b>{row.page}</b></td>
                  <td>{row.action}</td>
                  <td><code>{row.method} {endpoint(row.endpoint, vars) || row.endpoint}</code></td>
                  <td><span className={badgeClass(state.status)}>{iconFor(state.status)} {state.message}</span></td>
                  <td><button className="btn-sm btn-ghost" onClick={() => onNavigate(row.tab)}>打开</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
