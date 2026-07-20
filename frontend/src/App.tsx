import React, { useEffect, useMemo, useRef, useState } from "react";
import { Layout } from "./components/Layout";
import { Wizard } from "./components/Wizard";
import { Progress } from "./components/Progress";
import { Review } from "./components/Review";
import { Costs } from "./components/Costs";
import { Billing } from "./components/Billing";
import { CommandPalette } from "./components/CommandPalette";
import { DagEditor } from "./components/DagEditor";
import { Settings } from "./components/Settings";
import { Studio } from "./components/Studio";
import { PublishDashboard } from "./components/PublishDashboard";
import { LoginPage } from "./components/LoginPage";
import { RankingCenter } from "./components/RankingCenter";
import { BookLibrary } from "./components/BookLibrary";
import { HotspotDashboard } from "./components/HotspotDashboard";
import { KnowledgeBrowser } from "./components/KnowledgeBrowser";
import { FanoutMatrix } from "./components/FanoutMatrix";
import { VersionTree } from "./components/VersionTree";
import { ForeshadowingBoard } from "./components/ForeshadowingBoard";
import { CollaborationPanel } from "./components/Collaboration";
import { AgentConsole } from "./components/AgentConsole";
import { ApiError, api as baseApi, apiStream } from "./lib/api";
import { cacheDelete, cacheGet, cacheSet, deleteMutation, enqueueMutation, listMutations, updateMutation } from "./lib/offlineCache";
import { Code2, LogOut, Settings as SettingsIcon, Workflow, Layers, Rocket } from "lucide-react";
import { Overview } from "./components/Overview";
import { Plugins } from "./components/Plugins";
import { Prompts } from "./components/Prompts";
import { ThemeProvider } from "./components/ThemeProvider";

type ApiResponse<T> = { code: number | string; message: string; data: T };
type Content = { id: string; project_id: string; parent_id: string | null; type: string; title: string; body: TipTapDoc; meta: Record<string, unknown>; status: string; updated_at: string; sync_status?: "applied" | "conflict" };
type TipTapDoc = { type?: string; content?: Array<{ type: string; text?: string }> };
type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string; output: Record<string, unknown> };
type Run = { id: string; project_id: string; novel_id: string; status: string; current_node_key: string | null; context: Record<string, unknown>; nodes: RunNode[] };
type AiCall = { id: string; provider: string; model: string; prompt_name: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number; status: string; created_at: string };
type Knowledge = { id: string; kind: string; title: string; body: string; meta: Record<string, unknown> };
type Version = { id: string; label: string; reason?: string; snapshot: Record<string, unknown>; created_at: string };
type Budget = { id: string; scope: string; limit_cny: number; spent_cny: number };
type ModelRoute = { id: string; task_type: string; provider: string; model: string; params: Record<string, unknown> };
type Tab = "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard" | "progress" | "review" | "editor" | "costs" | "billing" | "prompts" | "dag" | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout" | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins";

const API = "";
const Editor = React.lazy(() => import("./components/Editor").then(module => ({ default: module.Editor })));

// Thin wrapper over lib/api.ts — adds key + auth, unwraps {data} from API response
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const fullResp = await baseApi<ApiResponse<T>>(path, init);
  return fullResp.data;
}

function docToText(doc: TipTapDoc): string {
  return doc.content?.map(i => i.text ?? "").join("\n\n") ?? "";
}

function textToDoc(text: string): TipTapDoc {
  return { type: "doc", content: text.split(/\n{2,}/).map(t => t.trim()).filter(Boolean).map(t => ({ type: "paragraph", text: t })) };
}

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [token, setToken] = useState(() => sessionStorage.getItem("nc_token") || "");
  const [userEmail, setUserEmail] = useState("");
  const [project, setProject] = useState<{ id: string; name: string } | null>(null);
  const [novel, setNovel] = useState<Content | null>(null);
  const [characters, setCharacters] = useState<any[]>([]);
  const [narrative, setNarrative] = useState<{ timeline: any[]; arcs: any[] }>({ timeline: [], arcs: [] });
  const [chapter, setChapter] = useState<Content | null>(null);
  const [chapters, setChapters] = useState<Content[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const restoringRun = useRef(false);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [aiCalls, setAiCalls] = useState<AiCall[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [routes, setRoutes] = useState<ModelRoute[]>([]);
  const [idea, setIdea] = useState("一个写作者发现自己删掉的章节正在现实里发生。");
  const [genre, setGenre] = useState("都市奇幻");
  const [style, setStyle] = useState("克制、悬疑、强画面感");
  const [targetWords, setTargetWords] = useState(800000);
  const [editorText, setEditorText] = useState("");
  const [selection, setSelection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offlineNotice, setOfflineNotice] = useState("");
  const [streamPreview, setStreamPreview] = useState("");
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);
  const [offlineAiResults, setOfflineAiResults] = useState<Array<{ id: string; text: string }>>([]);
  const [editorAiReview, setEditorAiReview] = useState<any>(null);
  const replayingOffline = useRef(false);
  const editorTextRef = useRef(editorText);

  useEffect(() => {
    if (!token) return;
    // Try offline cache first
    cacheGet<{ id: string; name: string }[]>("projects").then(cached => {
      if (cached?.length) setProject(cached[0]);
    });
    cacheGet<Content>("currentNovel").then(cached => { if (cached) setNovel(cached); });
    // Then fetch from API
    api<{ id: string; name: string }[]>("/api/v1/projects").then(p => {
      setProject(p[0] ?? null);
      cacheSet("projects", p);
    }).catch(e => setError(String(e)));
  }, [token]);

  useEffect(() => {
    if (!token || !project || run || restoringRun.current) return;
    restoringRun.current = true;
    const savedRunId = localStorage.getItem(`nc_current_run:${project.id}`) || "";
    const path = savedRunId
      ? `/api/v1/runs/${savedRunId}`
      : `/api/v1/runs/latest?project_id=${encodeURIComponent(project.id)}`;
    api<Run>(path)
      .then(restored => {
        setRun(restored);
        localStorage.setItem(`nc_current_run:${project.id}`, restored.id);
        return api<Content>(`/api/v1/contents/${restored.novel_id}`);
      })
      .then(content => { setNovel(content); void cacheSet("currentNovel", content); })
      .catch(async firstError => {
        if (!savedRunId) {
          if (!(firstError instanceof ApiError && firstError.status === 404)) setError(String(firstError));
          return;
        }
        localStorage.removeItem(`nc_current_run:${project.id}`);
        try {
          const restored = await api<Run>(`/api/v1/runs/latest?project_id=${encodeURIComponent(project.id)}`);
          setRun(restored);
          localStorage.setItem(`nc_current_run:${project.id}`, restored.id);
          const content = await api<Content>(`/api/v1/contents/${restored.novel_id}`);
          setNovel(content); void cacheSet("currentNovel", content);
        } catch {
          // A project without workflow runs is a valid initial state.
          if (!(firstError instanceof ApiError && firstError.status === 404)) setError(String(firstError));
        }
      })
      .finally(() => { restoringRun.current = false; });
  }, [token, project?.id, run?.id]);

  useEffect(() => {
    if (!run) return;
    // 终态（成功/失败）后停止轮询，避免无限每 2 秒请求 runs/contents
    if (run.status === "succeeded" || run.status === "failed") return;
    const poll = setInterval(() => { if (run) refreshRun(run.id); }, 2000);
    return () => clearInterval(poll);
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (tab !== "review" || !novel) { setNarrative({ timeline: [], arcs: [] }); return; }
    api<{ timeline: any[]; arcs: any[] }>(`/api/v1/novels/${novel.id}/narrative`)
      .then(data => setNarrative({ timeline: data.timeline || [], arcs: data.arcs || [] }))
      .catch(() => setNarrative({ timeline: [], arcs: [] }));
  }, [tab, novel?.id]);

  useEffect(() => {
    if (!novel || !project) return;
    const contentsKey = `contents:${novel.id}`;
    const knowledgeKey = `knowledge:${novel.id}`;
    cacheGet<Content[]>(contentsKey).then(items => {
      setChapters((items || []).filter(item => item.type === "chapter"));
      const cachedChapter = items?.find(item => item.type === "chapter") ?? null;
      if (cachedChapter) {
        setChapter(cachedChapter); setEditorText(docToText(cachedChapter.body)); void loadVersions(cachedChapter.id);
        cacheGet<Content>(`offline-content:${cachedChapter.id}`).then(offline => {
          if (offline) { setChapter(offline); setEditorText(docToText(offline.body)); }
        });
      }
    });
    cacheGet<Knowledge[]>(knowledgeKey).then(cached => { if (cached) setKnowledge(cached); });
    api<Content[]>(`/api/v1/contents?project_id=${project.id}&parent_id=${novel.id}`).then(items => {
      void cacheSet(contentsKey, items);
      const chapterItems = items.filter(i => i.type === "chapter").sort((a, b) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
      setChapters(chapterItems);
      const ch = chapterItems.find(item => item.id === chapter?.id) ?? chapterItems[0] ?? null;
      setChapter(ch);
      if (ch) { setEditorText(docToText(ch.body)); loadVersions(ch.id); }
    }).catch(() => undefined);
    api<Knowledge[]>(`/api/v1/knowledge?project_id=${project.id}&content_id=${novel.id}`).then(items => {
      setKnowledge(items); void cacheSet(knowledgeKey, items);
    }).catch(() => undefined);
  }, [novel?.id, run?.status]);

  function selectChapter(chapterId: string) {
    const selected = chapters.find(item => item.id === chapterId) ?? null;
    setChapter(selected);
    setEditorText(selected ? docToText(selected.body) : "");
    setVersions([]);
    if (selected) void loadVersions(selected.id);
  }

  useEffect(() => { if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls); }, [run?.id, run?.status]);
  useEffect(() => {
    if (!project) return;
    // NOTE: api<T>() already unwraps the envelope once, so the resolved value
    // is the bare array. The previous `response.data` was always undefined.
    api<Budget[] | { data?: Budget[] }>(`/api/v1/admin/budgets?project_id=${project.id}`).then(r => setBudgets(Array.isArray(r) ? r : (r.data ?? [])));
    api<ModelRoute[] | { data?: ModelRoute[] }>("/api/v1/admin/model-routes").then(r => setRoutes(Array.isArray(r) ? r : (r.data ?? [])));
  }, [project?.id, run?.status]);

  useEffect(() => {
    if (!token) return;
    const replay = () => { void replayOfflineMutations(); };
    window.addEventListener("online", replay);
    void replayOfflineMutations();
    return () => window.removeEventListener("online", replay);
  }, [token, chapter?.id]);

  useEffect(() => { editorTextRef.current = editorText; }, [editorText]);

  async function refreshRun(runId: string) {
    const r = await api<Run>(`/api/v1/runs/${runId}`);
    setRun(r);
    localStorage.setItem(`nc_current_run:${r.project_id}`, r.id);
    const n = await api<Content>(`/api/v1/contents/${r.novel_id}`);
    setNovel(n);
    void cacheSet("currentNovel", n);
  }

  async function startBootstrap() {
    if (!project) return;
    setBusy(true); setError("");
    try {
      const c = await api<Content>(`/api/v1/projects/${project.id}/novels`, { method: "POST", body: JSON.stringify({ idea, genre, style, target_words: targetWords }) });
      setNovel(c);
      void cacheSet("currentNovel", c);
      const s = await api<{ run_id: string }>(`/api/v1/novels/${c.id}/bootstrap`, { method: "POST", body: JSON.stringify({ auto_confirm_title: false }) });
      setTab("progress");
      await refreshRun(s.run_id);
    } catch (e: any) {
      const msg = e?.payload?.message || e?.message || String(e);
      setError(msg);
    } finally { setBusy(false); }
  }

  async function confirmTitle(title: string) {
    if (!run) return;
    await api(`/api/v1/runs/${run.id}/nodes/n2/confirm`, { method: "POST", body: JSON.stringify({ selected_title: title }) });
    await refreshRun(run.id);
  }

  async function regenerateTitles(feedback: string) {
    if (!run) return;
    await api(`/api/v1/runs/${run.id}/titles/regenerate`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    });
    await refreshRun(run.id);
  }

  async function saveChapter() {
    if (!chapter) return;
    const mutationId = crypto.randomUUID();
    const body = {
      body: textToDoc(editorText), label: "offline_save",
      base_updated_at: chapter.updated_at, client_mutation_id: mutationId,
    };
    if (!navigator.onLine) {
      await queueOfflineMutation(mutationId, "content_update", `/api/v1/contents/${chapter.id}`, "PUT", body);
      const optimistic = { ...chapter, body: body.body };
      setChapter(optimistic);
      await cacheSet(`offline-content:${chapter.id}`, optimistic);
      setOfflineNotice("内容已离线保存，联网后自动同步");
      return;
    }
    try {
      const updated = await api<Content>(`/api/v1/contents/${chapter.id}`, { method: "PUT", body: JSON.stringify(body) });
      if (updated.sync_status === "conflict") {
        setChapter(updated);
        await cacheDelete(`offline-content:${chapter.id}`);
        setOfflineNotice("检测到版本冲突，离线稿已保存到版本树");
        await loadVersions(chapter.id);
        return;
      }
      setChapter(updated); await cacheDelete(`offline-content:${chapter.id}`); loadVersions(updated.id);
    } catch (caught) {
      if (caught instanceof ApiError && !isOfflineApiError(caught)) throw caught;
      await queueOfflineMutation(mutationId, "content_update", `/api/v1/contents/${chapter.id}`, "PUT", body);
      const optimistic = { ...chapter, body: body.body };
      setChapter(optimistic);
      await cacheSet(`offline-content:${chapter.id}`, optimistic);
      setOfflineNotice("网络不可用，内容已进入同步队列");
    }
  }

  async function runEditorOp(op: string) {
    if (!chapter) return;
    const selectedText = op === "rewrite_chapter" ? editorText : selection;
    if (!selectedText.trim()) return;
    const mutationId = crypto.randomUUID();
    const url = `/api/v1/contents/${chapter.id}/ai/${op}`;
    const body = { selection: selectedText, instruction: op === "rewrite_chapter" ? "整章重写，保留核心剧情，优化小说平台阅读体验" : "保持当前风格", client_mutation_id: mutationId };
    if (!navigator.onLine) {
      await queueOfflineMutation(mutationId, "ai_operation", url, "POST", body);
      setOfflineNotice("AI 操作已排队，联网后自动执行");
      return;
    }
    try {
      if (!["polish", "rewrite", "rewrite_chapter", "deai"].includes(op)) {
        // 流式优先：增量预览，完成后一次性替换选区
        setStreamPreview("");
        const { text } = await apiStream(`${url}/stream`, { method: "POST", body: JSON.stringify(body) },
          delta => setStreamPreview(previous => previous + delta));
        setStreamPreview("");
        setEditorText(current => current.replace(selectedText, text)); setSelection("");
        if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
        return;
      }
    } catch (streamError) {
      setStreamPreview("");
      if (streamError instanceof ApiError && streamError.status === 404) {
        // 旧后端无流式端点 → 走非流式
      } else if (streamError instanceof ApiError && !isOfflineApiError(streamError) && streamError.status !== 502) {
        setError(streamError.message || "AI 操作失败");
        return;
      }
    }
    try {
      const output = await api<{ text: string; review_7dim?: any; next_chapter_plan?: any }>(url, { method: "POST", body: JSON.stringify(body) });
      setEditorText(current => op === "rewrite_chapter" ? output.text : current.replace(selectedText, output.text)); setSelection("");
      setEditorAiReview({ review: output.review_7dim, next: output.next_chapter_plan });
      if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
    } catch (caught) {
      if (caught instanceof ApiError && !isOfflineApiError(caught)) {
        setError(caught.message || "AI 操作失败");
        return;
      }
      await queueOfflineMutation(mutationId, "ai_operation", url, "POST", body);
      setOfflineNotice("网络不可用，AI 操作已进入出站队列");
    }
  }

  async function queueOfflineMutation(
    id: string,
    kind: "content_update" | "ai_operation",
    url: string,
    method: "POST" | "PUT",
    body: Record<string, unknown>,
  ) {
    await enqueueMutation({ id, kind, url, method, body });
    setOfflineQueueCount((await listMutations()).length);
  }

  async function replayOfflineMutations() {
    if (!navigator.onLine || replayingOffline.current) return;
    replayingOffline.current = true;
    try {
      const mutations = await listMutations("pending");
      setOfflineQueueCount((await listMutations()).length);
      for (const mutation of mutations) {
        try {
          const response = await baseApi<ApiResponse<any>>(mutation.url, {
            method: mutation.method,
            body: JSON.stringify(mutation.body),
          });
          if (mutation.kind === "content_update" && response.data?.sync_status === "conflict") {
            await deleteMutation(mutation.id);
            setChapter(response.data as Content);
            const conflictContentId = mutation.url.split("/").at(-1);
            if (conflictContentId) await cacheDelete(`offline-content:${conflictContentId}`);
            setOfflineNotice("检测到离线版本冲突，草稿已保存在版本树");
            if (chapter?.id && mutation.url.includes(chapter.id)) await loadVersions(chapter.id);
          } else if (mutation.kind === "ai_operation") {
            const selectedText = String(mutation.body.selection || "");
            if (chapter?.id && mutation.url.includes(chapter.id) && editorTextRef.current.includes(selectedText)) {
              setEditorText(current => current.replace(selectedText, response.data.text || ""));
              await deleteMutation(mutation.id);
              setOfflineNotice("离线 AI 操作已执行并应用");
            } else {
              await updateMutation(mutation.id, { status: "completed", result: response.data });
              setOfflineNotice("离线 AI 操作已完成，结果保留在队列中");
            }
          } else {
            await deleteMutation(mutation.id);
            const syncedContentId = mutation.url.split("/").at(-1);
            if (syncedContentId) await cacheDelete(`offline-content:${syncedContentId}`);
            if (chapter?.id && mutation.url.includes(chapter.id)) {
              const updated = response.data as Content;
              setChapter(updated);
              setEditorText(docToText(updated.body));
              await loadVersions(chapter.id);
            }
            setOfflineNotice("离线内容已同步");
          }
        } catch (caught) {
          const attempts = mutation.attempts + 1;
          const permanentFailure = caught instanceof ApiError && caught.status < 500;
          if (permanentFailure) {
            await deleteMutation(mutation.id);
            setOfflineNotice("离线队列中有请求被服务器拒绝，请重新执行该操作");
            break;
          }
          await updateMutation(mutation.id, {
            attempts,
            error: caught instanceof Error ? caught.message : String(caught),
          });
          if (caught instanceof ApiError && isOfflineApiError(caught)) break;
          if (!navigator.onLine) break;
        }
      }
      const allMutations = await listMutations();
      setOfflineQueueCount(allMutations.length);
      setOfflineAiResults(allMutations.filter(item => item.kind === "ai_operation" && item.status === "completed").map(item => ({
        id: item.id,
        text: String((item.result as { text?: string } | undefined)?.text || ""),
      })));
    } finally {
      replayingOffline.current = false;
    }
  }

  function isOfflineApiError(error: ApiError): boolean {
    const payload = error.payload as { code?: string } | null;
    return error.status === 503 && payload?.code === "OFFLINE";
  }

  async function applyOfflineAiResult(id: string, text: string) {
    if (!text) return;
    setEditorText(current => `${current}\n\n${text}`.trim());
    await deleteMutation(id);
    const allMutations = await listMutations();
    setOfflineQueueCount(allMutations.length);
    setOfflineAiResults(results => results.filter(result => result.id !== id));
    setOfflineNotice("离线 AI 结果已追加到编辑器，请确认后保存");
  }

  async function loadVersions(contentId: string) {
    const key = `versions:${contentId}`;
    try {
      const rows = await api<Version[]>(`/api/v1/contents/${contentId}/versions`);
      setVersions(rows);
      await cacheSet(key, rows);
    } catch {
      const cached = await cacheGet<Version[]>(key);
      if (cached) setVersions(cached);
    }
  }

  async function restoreVersion(versionId: string) {
    if (!chapter) return;
    const r = await api<Content>(`/api/v1/contents/${chapter.id}/versions/restore`, { method: "POST", body: JSON.stringify({ version_id: versionId }) });
    setChapter(r); setEditorText(docToText(r.body)); loadVersions(r.id);
  }

  // V2 runs split quality data across self-review and consistency nodes; legacy runs used n8.
  const review = ({
    ...(run?.nodes.find(n => n.node_key === "n8")?.output ?? {}),
    ...(run?.nodes.find(n => n.node_key === "write_self_review")?.output ?? {}),
    final_consistency_check: run?.nodes.find(n => n.node_key === "final_consistency_check")?.output,
    final_continuity_audit: run?.nodes.find(n => n.node_key === "final_continuity_audit")?.output,
  }) as any;

  const titles: Record<Tab, string> = { dashboard: "工作台", overview: "数据概览", workspace: "工作区", ranking: "扫榜选书", library: "书库管理", wizard: "灵感创作", progress: "创作进度", review: "质量审阅", editor: "章节编辑器", costs: "AI 成本", billing: "订阅与套餐", prompts: "Prompt 管理", dag: "工作流编排", settings: "系统设置", studio: "内容工作室", publish: "发布看板", hotspot: "热点追踪", knowledge: "知识库", fanout: "多平台分发", versions: "版本历史", foreshadowing: "伏笔看板", collaboration: "协作管理", agents: "智能体", plugins: "插件管理" };
  const [prompts, setPrompts] = useState<any[]>([]);

  useEffect(() => { api<any[]>("/api/v1/admin/prompts").then(setPrompts).catch(() => {}); }, [run?.status]);
  const cmdActions = [
    { id: "ranking", label: "扫榜中心 → 自动生成小说", action: () => setTab("ranking") },
    { id: "library", label: "统一书库", action: () => setTab("library") },
    { id: "wizard", label: "创作向导 → 新建小说", action: () => setTab("wizard") },
    { id: "progress", label: "生成进度 → 查看工作流", action: () => setTab("progress") },
    { id: "editor", label: "编辑器 → 写章节", action: () => setTab("editor") },
    { id: "review", label: "审阅 → 查看审核", action: () => setTab("review") },
    { id: "costs", label: "成本追踪 → AI 调用", action: () => setTab("costs") },
    { id: "billing", label: "订阅套餐 → 套餐/用量", action: () => setTab("billing") },
    { id: "prompts", label: "Prompt 管理", action: () => setTab("prompts") },
    { id: "dag", label: "工作流编排 → DAG 编辑器", action: () => setTab("dag") },
    { id: "settings", label: "系统设置 → AI配置/预算", action: () => setTab("settings") },
    { id: "studio", label: "内容工作室 → 短篇/自媒体/热点", action: () => setTab("studio") },
    { id: "publish", label: "发布看板 → 出海/数据", action: () => setTab("publish") },
    { id: "hotspot", label: "热点仪表盘 → 实时热点", action: () => setTab("hotspot") },
    { id: "knowledge", label: "知识库浏览器 → 检索知识", action: () => setTab("knowledge") },
    { id: "fanout", label: "多平台分发 → 一键分发", action: () => setTab("fanout") },
    { id: "versions", label: "版本树 → 版本历史", action: () => setTab("versions") },
    { id: "foreshadowing", label: "伏笔看板 → 伏笔追踪", action: () => setTab("foreshadowing") },
    { id: "collaboration", label: "协作管理 → 团队协作", action: () => setTab("collaboration") },
    { id: "agents", label: "智能体控制台 → Agent 状态", action: () => setTab("agents") },
  ];

  function handleLogin(t: string, email: string) {
    setToken(t); setUserEmail(email);
  }

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
  }

  (window as any).__ncLogout = async () => {
    try {
      await baseApi("/api/v1/auth/logout", { method: "POST" });
    } finally {
      sessionStorage.removeItem("nc_token");
      sessionStorage.removeItem("nc_api_key");
      sessionStorage.removeItem("nc_api_url");
      sessionStorage.removeItem("nc_model");
      setToken("");
      setUserEmail("");
      setProject(null);
    }
  };

  return (
    <ThemeProvider>
    <Layout tab={tab} setTab={setTab} title={titles[tab]} runStatus={run?.status}>
      {error && <div className="error">{error}</div>}
      {tab === "dashboard" && <Overview />}
      {tab === "ranking" && project && <RankingCenter projectId={project.id} onBookCreated={async (novelId, runId) => { const book = await api<Content>(`/api/v1/contents/${novelId}`); setNovel(book); if (runId) { setTab("progress"); await refreshRun(runId); } else setTab("library"); }} />}
      {tab === "library" && project && <BookLibrary projectId={project.id} onOpen={async (bookId) => { const book = await api<Content>(`/api/v1/contents/${bookId}`); setNovel(book); setTab("editor"); }} />}
      {tab === "wizard" && <Wizard {...{ idea, setIdea, genre, setGenre, style, setStyle, targetWords, setTargetWords, busy, startBootstrap }} />}
      {tab === "progress" && <Progress run={run} novel={novel} onConfirm={confirmTitle} onRegenerateTitles={regenerateTitles} />}
      {tab === "review" && <Review chapter={novel} review={review} characters={characters} timeline={narrative.timeline} arcs={narrative.arcs} />}
      {tab === "editor" && <React.Suspense fallback={<div className="panel">正在加载编辑器…</div>}><Editor {...{ chapter, chapters, selectChapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion, offlineNotice, offlineQueueCount, offlineAiResults, applyOfflineAiResult, streamPreview, editorAiReview }} /></React.Suspense>}
      {tab === "costs" && <Costs aiCalls={aiCalls} budgets={budgets} routes={routes} />}
      {tab === "billing" && <Billing />}
      {tab === "prompts" && <Prompts prompts={prompts} projectId={project?.id || ""} />}
      {tab === "dag" && <DagEditor projectId={project?.id || ""} novelId={novel?.id || ""} />}
      {tab === "settings" && <Settings projectId={project?.id || ""} />}
      {tab === "studio" && <Studio />}
      {tab === "publish" && <PublishDashboard />}
      {tab === "hotspot" && <HotspotDashboard />}
      {tab === "knowledge" && project && <KnowledgeBrowser projectId={project.id} />}
      {tab === "fanout" && <FanoutMatrix contentId={novel?.id || ""} />}
      {tab === "versions" && chapter && <VersionTree contentId={chapter.id} versions={versions} onRestore={restoreVersion} />}
      {tab === "foreshadowing" && novel && <ForeshadowingBoard novelId={novel.id} />}
      {tab === "collaboration" && project && <CollaborationPanel projectId={project.id} />}
      {tab === "agents" && <AgentConsole />}
      {tab === "overview" && <Overview />}
      {tab === "workspace" && <Overview />}
      {tab === "plugins" && <Plugins />}
      <CommandPalette commands={cmdActions} />
    </Layout>
    </ThemeProvider>
  );
}
