import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CircleAlert,
  CircleCheckBig,
  FilePenLine,
  Library,
  RefreshCw,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { api } from "../lib/api";
import type { AppTab } from "./Layout";
import { bookTitle, cleanNovelTitle } from "../lib/titleDisplay";

type Book = {
  id: string;
  title: string;
  status: string;
  meta?: Record<string, unknown>;
  updated_at: string;
  created_at: string;
  total_words?: number;
  chapter_count?: number;
};

type RunNode = { node_key: string; title: string; status: string };
type Run = { status: string; current_node_key: string | null; nodes: RunNode[] };
type AiCall = { id: string; prompt_name: string; task_type: string; status: string; created_at: string };

type Props = {
  projectId?: string;
  currentNovelTitle?: string;
  run?: Run | null;
  chaptersCount?: number;
  aiCalls?: AiCall[];
  userEmail?: string;
  onNavigate: (tab: AppTab) => void;
};

const STATUS_LABELS: Record<string, string> = {
  draft: "创作中",
  active: "创作中",
  succeeded: "已完成",
  published: "已发布",
};

function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "时间未知";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} 天前`;
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(timestamp));
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 12) return "上午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function displayRunStatus(run?: Run | null): string {
  if (!run) return "pending";
  const statuses = new Set((run.nodes || []).map(node => node.status));
  if (statuses.has("running") || statuses.has("queued")) return "running";
  if (statuses.has("pending_approval") || statuses.has("waiting_human")) return "pending_approval";
  if (statuses.has("failed") || statuses.has("pending_budget") || statuses.has("pending_provider") || statuses.has("needs_review")) return "needs_review";
  if (statuses.has("pending")) return "pending";
  return run.status || "pending";
}

export function WorkspaceDashboard({
  projectId,
  currentNovelTitle,
  run,
  chaptersCount = 0,
  aiCalls = [],
  userEmail,
  onNavigate,
}: Props) {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(Boolean(projectId));
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!projectId) {
      setBooks([]);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    api<Book[]>(`/api/v1/library/books?project_id=${encodeURIComponent(projectId)}`)
      .then(items => { if (active) setBooks(items); })
      .catch(caught => { if (active) setError(String(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, reloadKey]);

  const recentBooks = useMemo(
    () => [...books].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 3),
    [books],
  );
  const runDisplayStatus = displayRunStatus(run);
  const failedNodes = run?.nodes.filter(node => ["failed", "pending_budget", "pending_provider", "needs_review"].includes(node.status)) || [];
  const waitingNodes = run?.nodes.filter(node => ["waiting_human", "pending_approval"].includes(node.status)) || [];
  const rawName = userEmail?.split("@")[0] || "创作者";
  const firstName = rawName.length > 16 ? `${rawName.slice(0, 14)}…` : rawName;
  const continueTab: AppTab = runDisplayStatus === "pending_approval" || runDisplayStatus === "running" || runDisplayStatus === "needs_review"
    ? "progress"
    : currentNovelTitle || books.length
      ? "editor"
      : "wizard";
  const focusTitle = runDisplayStatus === "pending_approval"
    ? "有一项创作结果等待你确认"
    : runDisplayStatus === "running"
      ? `Starlume 正在创作${currentNovelTitle ? bookTitle(currentNovelTitle) : ""}`
      : runDisplayStatus === "needs_review"
        ? "创作流程需要你处理"
        : currentNovelTitle
          ? `继续创作${bookTitle(currentNovelTitle)}`
          : books[0]
            ? `继续创作${bookTitle(books[0].title)}`
            : "从一个故事灵感开始";

  const activities = [
    ...aiCalls.slice(0, 4).map(call => ({
      id: `ai-${call.id}`,
      text: `${call.status === "succeeded" ? "完成" : "执行"} ${call.prompt_name || call.task_type || "AI 创作任务"}`,
      at: call.created_at,
    })),
    ...recentBooks.map(book => ({ id: `book-${book.id}`, text: `更新${bookTitle(book.title)}`, at: book.updated_at })),
  ].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()).slice(0, 5);

  return (
    <div className="starlume-dashboard page-enter">
      <section className="dashboard-welcome">
        <div>
          <p className="eyebrow">{new Intl.DateTimeFormat("zh-CN", { dateStyle: "long" }).format(new Date())}</p>
          <h2>{greeting()}，{firstName}</h2>
          <p>今天也写一点，让故事继续发光。</p>
        </div>
        <button type="button" className="primary-action" onClick={() => onNavigate("wizard")}>
          <WandSparkles size={18} /> 新建小说
        </button>
      </section>

      <section className="dashboard-grid dashboard-focus-grid">
        <article className="starlume-card focus-card">
          <div className="card-heading">
            <span className="card-icon indigo"><FilePenLine size={19} /></span>
            <span>今日继续写</span>
          </div>
          <h3>{focusTitle}</h3>
          <p>
            {runDisplayStatus === "running" && run?.current_node_key
              ? `当前步骤：${run.nodes.find(node => node.node_key === run.current_node_key)?.title || run.current_node_key}`
              : `${chaptersCount} 个章节已进入当前工作区`}
          </p>
          <button type="button" className="text-action" onClick={() => onNavigate(continueTab)}>
            {continueTab === "progress" ? "查看创作进度" : continueTab === "editor" ? "打开编辑器" : "开始创作"}
            <ArrowRight size={16} />
          </button>
        </article>

        <article className="starlume-card quality-card">
          <div className="card-heading">
            <span className={`card-icon ${failedNodes.length ? "danger" : waitingNodes.length ? "warning" : "success"}`}>
              {failedNodes.length || waitingNodes.length ? <CircleAlert size={19} /> : <CircleCheckBig size={19} />}
            </span>
            <span>质量提醒</span>
          </div>
          {failedNodes.length > 0 ? (
            <>
              <h3>{failedNodes.length} 个步骤执行失败</h3>
              <p>{failedNodes[0].title || failedNodes[0].node_key} 需要检查后重试。</p>
              <button type="button" className="text-action" onClick={() => onNavigate("progress")}>立即处理 <ArrowRight size={16} /></button>
            </>
          ) : waitingNodes.length > 0 ? (
            <>
              <h3>{waitingNodes.length} 项等待人工确认</h3>
              <p>AI 结果不会自动覆盖你的创作决定。</p>
              <button type="button" className="text-action" onClick={() => onNavigate("progress")}>前往确认 <ArrowRight size={16} /></button>
            </>
          ) : (
            <>
              <h3>当前没有阻塞项</h3>
              <p>新的审阅问题会在这里明确提示。</p>
              <button type="button" className="text-action" onClick={() => onNavigate("review")}>查看审阅 <ArrowRight size={16} /></button>
            </>
          )}
        </article>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <div><p className="eyebrow">你的故事</p><h3>进行中的小说</h3></div>
          <button type="button" className="quiet-action" onClick={() => onNavigate("library")}>查看全部 <ArrowRight size={15} /></button>
        </div>
        {loading ? (
          <div className="starlume-card dashboard-state" aria-live="polite"><span className="spinner" /> 正在读取书库…</div>
        ) : error ? (
          <div className="starlume-card dashboard-state error-state">
            <CircleAlert size={22} />
            <div><strong>书库暂时无法加载</strong><p>{error}</p></div>
            <button type="button" className="quiet-action" onClick={() => setReloadKey(key => key + 1)}><RefreshCw size={15} /> 重试</button>
          </div>
        ) : recentBooks.length === 0 ? (
          <div className="starlume-card dashboard-state empty-state">
            <BookOpen size={28} />
            <div><strong>书架还是空的</strong><p>创建第一本小说后，它会出现在这里。</p></div>
            <button type="button" className="quiet-action" onClick={() => onNavigate("wizard")}>创建小说</button>
          </div>
        ) : (
          <div className="book-card-grid">
            {recentBooks.map(book => {
              const targetWords = Number(book.meta?.target_words || 0);
              const percent = targetWords > 0 ? Math.min(100, Math.round(((book.total_words || 0) / targetWords) * 100)) : null;
              return (
                <button type="button" className="starlume-card book-project-card" key={book.id} onClick={() => onNavigate("library")}>
                  <div className="book-project-top">
                    <span className="book-glyph"><BookOpen size={20} /></span>
                    <span className="book-status">{STATUS_LABELS[book.status] || "创作中"}</span>
                  </div>
                  <h4>{cleanNovelTitle(book.title)}</h4>
                  <p>{book.chapter_count || 0} 章 · {(book.total_words || 0).toLocaleString("zh-CN")} 字</p>
                  {percent !== null && <div className="fine-progress" aria-label={`目标字数完成 ${percent}%`}><span style={{ width: `${percent}%` }} /></div>}
                  <small>最近更新于 {relativeTime(book.updated_at || book.created_at)}</small>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="dashboard-grid dashboard-lower-grid">
        <div className="dashboard-section">
          <div className="section-heading"><div><p className="eyebrow">快速抵达</p><h3>快捷工具</h3></div></div>
          <div className="quick-tools">
            {[
              { tab: "wizard" as AppTab, label: "创作向导", icon: <Sparkles size={20} /> },
              { tab: "editor" as AppTab, label: "章节编辑", icon: <FilePenLine size={20} /> },
              { tab: "library" as AppTab, label: "我的书库", icon: <Library size={20} /> },
              { tab: "review" as AppTab, label: "一致性审阅", icon: <CircleCheckBig size={20} /> },
            ].map(tool => (
              <button type="button" key={tool.tab} onClick={() => onNavigate(tool.tab)}>
                <span>{tool.icon}</span>{tool.label}
              </button>
            ))}
          </div>
        </div>
        <div className="dashboard-section recent-section">
          <div className="section-heading"><div><p className="eyebrow">真实记录</p><h3>最近活动</h3></div></div>
          <div className="activity-list starlume-card">
            {activities.length ? activities.map(activity => (
              <div className="activity-row" key={activity.id}>
                <span className="activity-dot" />
                <span>{activity.text}</span>
                <time>{relativeTime(activity.at)}</time>
              </div>
            )) : <div className="activity-empty">完成一次创作后，活动记录会显示在这里。</div>}
          </div>
        </div>
      </section>
    </div>
  );
}
