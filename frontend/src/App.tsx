import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Layout, type AppTab } from "./components/Layout";
import { Wizard } from "./components/Wizard";
import { Progress, type GenerationHistoryItem } from "./components/Progress";
import { Review } from "./components/Review";
import { CommandPalette } from "./components/CommandPalette";
import { Settings } from "./components/Settings";
import { V7Dashboard } from "./v7/pages/V7Dashboard";
import { LoginPage } from "./components/LoginPage";
import { BookLibrary } from "./components/BookLibrary";
import { ApiError, api as baseApi, apiRaw, apiStream } from "./lib/api";
import { cacheDelete, cacheGet, cacheSet, deleteMutation, enqueueMutation, listMutations, updateMutation } from "./lib/offlineCache";
import { WorkspaceDashboard } from "./components/WorkspaceDashboard";
import { RankingCenter } from "./components/RankingCenter";
import { NotFoundPage } from "./components/NotFoundPage";
import { buildAiEditPreview, normalizeParagraphBreaks } from "./lib/editorPreview";
import { cleanNovelTitle } from "./lib/titleDisplay";

type ApiResponse<T> = { code: number | string; message: string; data: T };
type Project = { id: string; name: string; description?: string };
type Content = { id: string; project_id: string; parent_id: string | null; type: string; title: string; body: TipTapDoc; meta: Record<string, unknown>; status: string; updated_at: string; sync_status?: "applied" | "conflict" };
type TipTapDoc = { type?: string; content?: Array<{ type: string; text?: string }> };
type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string; output: Record<string, unknown> };
type Run = { id: string; project_id: string; novel_id: string; status: string; current_node_key: string | null; context: Record<string, unknown>; nodes: RunNode[] };
type AiCall = { id: string; provider: string; model: string; prompt_name: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number; status: string; created_at: string };
type Version = { id: string; label: string; reason?: string; snapshot: Record<string, unknown>; created_at: string };
type PendingAiEdit = {
  op: string;
  originalText: string;
  proposedText: string;
  nextText: string;
  sourceMutationId?: string;
};
type Tab = AppTab;

const API = "";
const Editor = React.lazy(() => import("./components/Editor").then(module => ({ default: module.Editor })));
const PUBLIC_TABS = new Set<Tab>(["dashboard", "wizard", "library", "progress", "editor", "review", "settings", "ranking", "v7"]);
const LEGACY_TAB_REDIRECTS: Record<string, Tab> = {
  home: "dashboard",
  overview: "dashboard",
  workspace: "dashboard",
  create: "wizard",
  inspiration: "wizard",
  books: "library",
  "book-library": "library",
  run: "progress",
  workflow: "progress",
  write: "editor",
  chapters: "editor",
  quality: "review",
  config: "settings",
};

function routeFromLocation(): { tab: Tab; notFound: boolean } {
  const hashValue = window.location.hash.replace(/^#\/?/, "").split(/[/?]/)[0];
  const queryValue = new URLSearchParams(window.location.search).get("tab") || "";
  const requested = hashValue || queryValue;
  if (!requested) return { tab: "dashboard", notFound: false };
  if (PUBLIC_TABS.has(requested as Tab)) return { tab: requested as Tab, notFound: false };
  if (LEGACY_TAB_REDIRECTS[requested]) return { tab: LEGACY_TAB_REDIRECTS[requested], notFound: false };
  return { tab: "dashboard", notFound: true };
}

// Thin typed alias over the canonical data-unwrapping client.
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return baseApi<T>(path, init);
}

function docToText(doc: TipTapDoc): string {
  return textValue(doc);
}

export function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.map(item => textValue(item)).filter(Boolean).join("\n\n");
  }
  if (value && typeof value === "object") {
    const candidate = value as {
      text?: unknown;
      content?: unknown;
      paragraphs?: unknown;
      body?: unknown;
    };
    if (typeof candidate.text === "string") return candidate.text;
    if (candidate.text !== undefined) return textValue(candidate.text);
    if (Array.isArray(candidate.content)) {
      return textValue(candidate.content);
    }
    if (Array.isArray(candidate.paragraphs)) return textValue(candidate.paragraphs);
    if (candidate.body !== undefined) return textValue(candidate.body);
    // Never stringify an arbitrary response object.  That turns malformed
    // TipTap/provider payloads into literal "[object Object]" prose and can
    // corrupt the editor preview before the user has confirmed anything.
    return "";
  }
  return typeof value === "number" || typeof value === "boolean" ? String(value) : "";
}

function textToDoc(text: unknown): TipTapDoc {
  const normalized = textValue(text);
  return { type: "doc", content: normalized.split(/\n{2,}/).map(t => t.trim()).filter(Boolean).map(t => ({ type: "paragraph", text: t })) };
}

const EDITOR_OPERATION_TIMEOUT_MS = 120_000;

function withTimeout<T>(work: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    work.then(value => {
      window.clearTimeout(timer);
      resolve(value);
    }).catch(error => {
      window.clearTimeout(timer);
      reject(error);
    });
  });
}

function displayRunStatus(run: Run | null): string | undefined {
  if (!run) return undefined;
  const statuses = new Set((run.nodes || []).map(node => node.status));
  if (statuses.has("running") || statuses.has("queued")) return "running";
  if (statuses.has("pending_approval") || statuses.has("waiting_human")) return "pending_approval";
  if (statuses.has("failed") || statuses.has("pending_budget") || statuses.has("pending_provider") || statuses.has("needs_review")) return "needs_review";
  if (statuses.has("pending")) return "pending";
  return run.status;
}

export default function App() {
  const initialRoute = useMemo(routeFromLocation, []);
  const [tab, setTabState] = useState<Tab>(initialRoute.tab);
  const [routeNotFound, setRouteNotFound] = useState(initialRoute.notFound);
  const setTab = useCallback((nextTab: Tab) => {
    const publicTab = PUBLIC_TABS.has(nextTab) ? nextTab : LEGACY_TAB_REDIRECTS[nextTab] || "dashboard";
    setTabState(publicTab);
    setRouteNotFound(false);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/${publicTab}`);
  }, []);
  const [token, setToken] = useState(() => sessionStorage.getItem("nc_token") || "");
  const [userEmail, setUserEmail] = useState(() => sessionStorage.getItem("starlume_user_email") || "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [novel, setNovel] = useState<Content | null>(null);
  const [novels, setNovels] = useState<Content[]>([]);
  const [characters, setCharacters] = useState<any[]>([]);
  const [narrative, setNarrative] = useState<{
    timeline: any[];
    arcs: any[];
    evidence?: Record<string, unknown>;
  }>({ timeline: [], arcs: [] });
  const [chapter, setChapter] = useState<Content | null>(null);
  const [chapters, setChapters] = useState<Content[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const restoringRun = useRef(false);
  const userSelectedProject = useRef(false);
  const userSelectedNovel = useRef(false);
  const novelSelectionEpoch = useRef(0);
  const [aiCalls, setAiCalls] = useState<AiCall[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [idea, setIdea] = useState("一个写作者发现自己删掉的章节正在现实里发生。");
  const [genre, setGenre] = useState("都市");
  const [platform, setPlatform] = useState("fanqie");
  const [subgenre, setSubgenre] = useState("");
  const [stylePlugin, setStylePlugin] = useState("");
  const [style, setStyle] = useState("第三人称、克制、悬疑、强画面感");
  const [targetWords, setTargetWords] = useState(800000);
  const [editorText, setEditorText] = useState("");
  const [selection, setSelection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [offlineNotice, setOfflineNotice] = useState("");
  const [streamPreview, setStreamPreview] = useState("");
  const [pendingAiEdit, setPendingAiEdit] = useState<PendingAiEdit | null>(null);
  const [editorAiLoading, setEditorAiLoading] = useState(false);
  const [editorAiOperation, setEditorAiOperation] = useState("");
  const [nextChapterLoading, setNextChapterLoading] = useState(false);
  const nextChapterPollRef = useRef<number | null>(null);
  useEffect(() => {
    return () => {
      if (nextChapterPollRef.current !== null) {
        window.clearTimeout(nextChapterPollRef.current);
        nextChapterPollRef.current = null;
      }
    };
  }, [novel?.id]);
  // 应用 AI 建议后强制 RichEditor 用最新正文重建一次，确保编辑区立即显示新内容（修复受控同步竞态）。
  const [editorResetNonce, setEditorResetNonce] = useState(0);
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);
  const [offlineAiResults, setOfflineAiResults] = useState<Array<{ id: string; text: string }>>([]);
  const [editorAiReview, setEditorAiReview] = useState<any>(null);
  const [liveReviewing, setLiveReviewing] = useState(false);
  const [liveReviewError, setLiveReviewError] = useState("");
  const [history, setHistory] = useState<GenerationHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const replayingOffline = useRef(false);
  const editorTextRef = useRef(editorText);
  // NC-LIVE-AUDIT: refs so the debounced live reviewer always reads fresh guards.
  const pendingAiEditRef = useRef(pendingAiEdit);
  const streamPreviewRef = useRef(streamPreview);
  const lastReviewTextRef = useRef("");
  const reviewTimerRef = useRef<number | null>(null);
  const reviewRequestKeyRef = useRef("");
  const reviewRequestSeqRef = useRef(0);
  useEffect(() => { pendingAiEditRef.current = pendingAiEdit; }, [pendingAiEdit]);
  useEffect(() => { streamPreviewRef.current = streamPreview; }, [streamPreview]);
  const projectsCacheKey = `projects:${userEmail || "signed-out"}`;
  const selectedProjectKey = `currentProject:${userEmail || "signed-out"}`;
  const currentNovelCacheKey = `currentNovel:${userEmail || "signed-out"}`;

  useEffect(() => {
    const syncRoute = () => {
      const requested = window.location.hash.replace(/^#\/?/, "").split(/[/?]/)[0]
        || new URLSearchParams(window.location.search).get("tab")
        || "dashboard";
      const route = routeFromLocation();
      setTabState(route.tab);
      setRouteNotFound(route.notFound);
      if (LEGACY_TAB_REDIRECTS[requested]) {
        window.history.replaceState(
          null,
          "",
          `${window.location.pathname}${window.location.search}#/${route.tab}`,
        );
      }
    };
    window.addEventListener("hashchange", syncRoute);
    window.addEventListener("popstate", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
      window.removeEventListener("popstate", syncRoute);
    };
  }, []);

  useEffect(() => {
    const requested = window.location.hash.replace(/^#\/?/, "").split(/[/?]/)[0]
      || new URLSearchParams(window.location.search).get("tab")
      || "";
    const canonicalTab = LEGACY_TAB_REDIRECTS[requested];
    if (canonicalTab) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/${canonicalTab}`);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    novelSelectionEpoch.current += 1;
    userSelectedProject.current = false;
    userSelectedNovel.current = false;
    setProject(null);
    setProjects([]);
    setNovel(null);
    setNovels([]);
    setRun(null);
    setChapters([]);
    setChapter(null);
    setEditorText("");
    setHistory([]);
    setHistoryTotal(0);
    setHistoryLoadingMore(false);
    setHistoryError("");

    const applyProjects = (items: Project[]) => {
      if (!active || userSelectedProject.current) return;
      setProjects(items);
      const savedId = localStorage.getItem(selectedProjectKey) || "";
      const selected = items.find(item => item.id === savedId) || items[0] || null;
      setProject(selected);
      if (selected) localStorage.setItem(selectedProjectKey, selected.id);
    };

    // Paint the cached project list first, then let the server refresh win.
    void cacheGet<Project[]>(projectsCacheKey).then(cached => {
      if (cached?.length) applyProjects(cached);
    });
    void api<Project[]>("/api/v1/projects").then(p => {
      if (!active) return;
      applyProjects(p);
      void cacheSet(projectsCacheKey, p);
    }).catch(e => {
      if (active) setError(String(e));
    });
    return () => { active = false; };
  }, [token, userEmail, projectsCacheKey, selectedProjectKey]);

  // 全局作品列表（供 Layout 作品选择器使用）
  useEffect(() => {
    if (!project) return;
    let active = true;
    api<Content[]>(`/api/v1/contents?project_id=${project.id}&limit=200`).then(items => {
      if (!active) return;
      const n = (items || []).filter(i => i.type === "novel");
      setNovels(n);
      if (n.length > 0 && !n.some(item => item.id === novel?.id)) {
        setNovel(n[0]);
        void cacheSet(currentNovelCacheKey, n[0]);
      }
    }).catch(() => {});
    return () => { active = false; };
  }, [project?.id, novel?.id, currentNovelCacheKey]);

  useEffect(() => {
    if (!token || !project || run || restoringRun.current || userSelectedNovel.current) return;
    restoringRun.current = true;
    let active = true;
    const restoreEpoch = novelSelectionEpoch.current;
    const savedRunId = localStorage.getItem(`nc_current_run:${project.id}`) || "";
    const canApply = () => active
      && restoreEpoch === novelSelectionEpoch.current
      && !userSelectedNovel.current;
    const restore = async () => {
      const path = savedRunId
        ? `/api/v1/runs/${savedRunId}`
        : `/api/v1/runs/latest?project_id=${encodeURIComponent(project.id)}`;
      try {
        const restored = await api<Run>(path);
        if (!canApply()) return;
        const content = await api<Content>(`/api/v1/contents/${restored.novel_id}`);
        if (!canApply()) return;
        setRun(restored);
        localStorage.setItem(`nc_current_run:${project.id}`, restored.id);
        setNovel(content);
        void cacheSet(currentNovelCacheKey, content);
      } catch (firstError) {
        if (!savedRunId) {
          if (canApply() && !(firstError instanceof ApiError && firstError.status === 404)) setError(String(firstError));
          return;
        }
        localStorage.removeItem(`nc_current_run:${project.id}`);
        try {
          const restored = await api<Run>(`/api/v1/runs/latest?project_id=${encodeURIComponent(project.id)}`);
          if (!canApply()) return;
          const content = await api<Content>(`/api/v1/contents/${restored.novel_id}`);
          if (!canApply()) return;
          setRun(restored);
          localStorage.setItem(`nc_current_run:${project.id}`, restored.id);
          setNovel(content);
          void cacheSet(currentNovelCacheKey, content);
        } catch {
          // A project without workflow runs is a valid initial state.
          if (canApply() && !(firstError instanceof ApiError && firstError.status === 404)) setError(String(firstError));
        }
      } finally {
        if (active) restoringRun.current = false;
      }
    };
    void restore();
    return () => {
      active = false;
      restoringRun.current = false;
    };
  }, [token, project?.id, run?.id, currentNovelCacheKey]);

  useEffect(() => {
    if (!run) return;
    // 只有 run 与节点都进入终态后才停止轮询；旧数据可能出现 run=succeeded
    // 但节点仍是 pending/failed，不能继续把页面显示成“已完成”。
    const hasActiveNode = run.nodes.some(node => ["pending", "queued", "running"].includes(node.status));
    if ((run.status === "succeeded" || run.status === "failed") && !hasActiveNode) return;
    const poll = setInterval(() => { if (run) refreshRun(run.id); }, 2000);
    return () => clearInterval(poll);
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (tab !== "review" || !novel) { setNarrative({ timeline: [], arcs: [] }); return; }
    api<{ timeline: any[]; arcs: any[]; evidence?: Record<string, unknown> }>(`/api/v1/novels/${novel.id}/narrative`)
      .then(data => setNarrative({ timeline: data.timeline || [], arcs: data.arcs || [], evidence: data.evidence }))
      .catch(() => setNarrative({ timeline: [], arcs: [] }));
  }, [tab, novel?.id]);

  useEffect(() => {
    if (tab !== "review" || chapters.length === 0) return;
    const latest = chapters[chapters.length - 1];
    if (chapter?.id !== latest.id) {
      setChapter(latest);
      setEditorText(docToText(latest.body));
    }
  }, [tab, chapters, chapter?.id]);

  useEffect(() => {
    if (!novel || !project) return;
    let active = true;
    const contentsKey = `contents:${novel.id}`;
    // Preserve deterministic precedence: cached data can paint first, but a
    // later server response must always win. Parallel promises previously let
    // stale IndexedDB rows overwrite freshly saved chapter text after reload.
    void (async () => {
      const cachedItems = await cacheGet<Content[]>(contentsKey);
      if (!active) return;
      const cachedChapters = (cachedItems || []).filter(item => item.type === "chapter");
      setChapters(cachedChapters);
      const cachedChapter = cachedChapters[0] ?? null;
      if (cachedChapter) {
        setChapter(cachedChapter);
        setEditorText(docToText(cachedChapter.body));
        void loadVersions(cachedChapter.id);
        const offline = await cacheGet<Content>(`offline-content:${cachedChapter.id}`);
        if (!active) return;
        if (offline) { setChapter(offline); setEditorText(docToText(offline.body)); }
      }

      try {
        const items = await api<Content[]>(`/api/v1/contents?project_id=${project.id}&parent_id=${novel.id}`);
        if (!active) return;
        void cacheSet(contentsKey, items);
        const chapterItems = items.filter(i => i.type === "chapter").sort((a, b) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
        if (chapterItems.length === 0) return; // 服务器无章节时不覆盖已缓存的内容
        setChapters(chapterItems);
        const current = chapterItems.find(item => item.id === chapter?.id) ?? chapterItems[0] ?? null;
        setChapter(current);
        setEditorText(current ? docToText(current.body) : "");
        if (current) void loadVersions(current.id);
      } catch {
        // Cached chapters remain usable while offline.
      }
    })();
    return () => { active = false; };
  }, [novel?.id, project?.id, run?.status]);

  useEffect(() => {
    if (!project) {
      setHistory([]);
      setHistoryTotal(0);
      setHistoryLoadingMore(false);
      setHistoryError("");
      return;
    }
    let active = true;
    setHistoryLoading(true);
    setHistoryLoadingMore(false);
    setHistoryError("");
    const query = new URLSearchParams({ project_id: project.id, limit: "100" });
    api<{ items: GenerationHistoryItem[]; total: number }>(`/api/v1/history?${query.toString()}`)
      .then(result => {
        if (!active) return;
        setHistory(result.items || []);
        setHistoryTotal(Number(result.total || 0));
      })
      .catch(caught => {
        if (!active) return;
        setHistory([]);
        setHistoryTotal(0);
        setHistoryError(caught instanceof Error ? caught.message : "历史记录加载失败");
      })
      .finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, [project?.id, run?.id, run?.status]);

  async function loadMoreHistory() {
    if (!project || historyLoading || historyLoadingMore || history.length >= historyTotal) return;
    const currentProjectId = project.id;
    setHistoryLoadingMore(true);
    setHistoryError("");
    const query = new URLSearchParams({
      project_id: currentProjectId,
      limit: "100",
      offset: String(history.length),
    });
    try {
      const result = await api<{ items: GenerationHistoryItem[]; total: number }>(`/api/v1/history?${query.toString()}`);
      if (project?.id !== currentProjectId) return;
      setHistory(previous => {
        const known = new Set(previous.map(item => `${item.engine}:${item.id}`));
        return [...previous, ...(result.items || []).filter(item => !known.has(`${item.engine}:${item.id}`))];
      });
      setHistoryTotal(Number(result.total || 0));
    } catch (caught) {
      if (project?.id === currentProjectId) setHistoryError(caught instanceof Error ? caught.message : "更多历史记录加载失败");
    } finally {
      setHistoryLoadingMore(false);
    }
  }

  function handleProjectChange(projectId: string) {
    const next = projects.find(item => item.id === projectId);
    if (!next || next.id === project?.id) return;
    userSelectedProject.current = true;
    novelSelectionEpoch.current += 1;
    userSelectedNovel.current = false;
    localStorage.setItem(selectedProjectKey, next.id);
    setProject(next);
    setNovel(null);
    setNovels([]);
    setRun(null);
    setChapters([]);
    setChapter(null);
    setEditorText("");
    setVersions([]);
    setCharacters([]);
    setNarrative({ timeline: [], arcs: [] });
    setHistory([]);
    setHistoryTotal(0);
    setHistoryLoadingMore(false);
    setHistoryError("");
    setError("");
  }

  function selectChapter(chapterId: string) {
    const selected = chapters.find(item => item.id === chapterId) ?? null;
    if (reviewTimerRef.current) {
      window.clearTimeout(reviewTimerRef.current);
      reviewTimerRef.current = null;
    }
    reviewRequestSeqRef.current += 1;
    reviewRequestKeyRef.current = "";
    lastReviewTextRef.current = "";
    setChapter(selected);
    setEditorText(selected ? docToText(selected.body) : "");
    setSelection("");
    setPendingAiEdit(null);
    setEditorAiReview(null);
    setLiveReviewError("");
    setVersions([]);
    if (selected) void loadVersions(selected.id);
  }

  useEffect(() => { if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls); }, [run?.id, run?.status]);
  useEffect(() => {
    if (!token) return;
    const replay = () => { void replayOfflineMutations(); };
    window.addEventListener("online", replay);
    void replayOfflineMutations();
    return () => window.removeEventListener("online", replay);
  }, [token, chapter?.id]);

  useEffect(() => { editorTextRef.current = editorText; }, [editorText]);

  // NC-LIVE-AUDIT: 打开章节 + 打字停顿时自动审计（1.5s 防抖）；待确认/流式时跳过。
  useEffect(() => {
    if (!chapter?.id) return;
    if (editorText.trim().length < 30) return;
    if (pendingAiEditRef.current || streamPreviewRef.current) return;
    if (editorText.trim() === lastReviewTextRef.current) return;
    if (reviewTimerRef.current) window.clearTimeout(reviewTimerRef.current);
    reviewTimerRef.current = window.setTimeout(() => {
      void requestReview(chapter.id, editorText);
    }, 1500);
    return () => { if (reviewTimerRef.current) window.clearTimeout(reviewTimerRef.current); };
  }, [editorText, chapter?.id]);

  async function refreshRun(runId: string) {
    const r = await api<Run>(`/api/v1/runs/${runId}`);
    setRun(r);
    localStorage.setItem(`nc_current_run:${r.project_id}`, r.id);
    const n = await api<Content>(`/api/v1/contents/${r.novel_id}`);
    setNovel(n);
    void cacheSet(currentNovelCacheKey, n);
  }

  async function openGenerationHistory(item: GenerationHistoryItem) {
    setError("");
    if (item.engine === "v6") {
      try {
        await refreshRun(item.id);
        setTab("progress");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "旧版运行记录加载失败");
      }
      return;
    }
    if (item.novel_id) {
      const opened = await activateNovel(item.novel_id);
      if (opened) setTab("v7");
    }
  }

  async function startBootstrap() {
    if (!project) return;
    setBusy(true); setError("");
    try {
      const c = await api<Content>(`/api/v1/projects/${project.id}/novels`, { method: "POST", body: JSON.stringify({ idea, genre, platform, subgenre, style_plugin: stylePlugin, style, target_words: targetWords }) });
      setNovel(c);
      void cacheSet(currentNovelCacheKey, c);
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

  async function activateNovel(novelId: string, preferredChapterId?: string): Promise<boolean> {
    userSelectedNovel.current = true;
    const selectionEpoch = ++novelSelectionEpoch.current;
    const isCurrentSelection = () => selectionEpoch === novelSelectionEpoch.current;
    setError("");
    const selectedSummary = novels.find(item => item.id === novelId);
    if (selectedSummary) setNovel(selectedSummary);
    setRun(null);
    setChapters([]);
    setChapter(null);
    setEditorText("");
    setVersions([]);
    setPendingAiEdit(null);
    setEditorAiReview(null);
    try {
      const book = await api<Content>(`/api/v1/contents/${novelId}`);
      if (!isCurrentSelection()) return false;
      setNovel(book);
      void cacheSet(currentNovelCacheKey, book);
      const [latestRun, items] = await Promise.all([
        api<Run>(`/api/v1/runs/latest?project_id=${book.project_id}&novel_id=${novelId}`).catch(() => null),
        api<Content[]>(`/api/v1/contents?project_id=${book.project_id}&parent_id=${novelId}`),
      ]);
      if (!isCurrentSelection()) return false;
      setRun(latestRun);
      const chapterItems = (items || [])
        .filter(item => item.type === "chapter")
        .sort((a, b) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
      setChapters(chapterItems);
      const selectedChapter = chapterItems.find(item => item.id === preferredChapterId) ?? chapterItems[0] ?? null;
      setChapter(selectedChapter);
      setEditorText(selectedChapter ? docToText(selectedChapter.body) : "");
      if (selectedChapter) void loadVersions(selectedChapter.id);
      return true;
    } catch (caught) {
      if (isCurrentSelection()) setError(caught instanceof Error ? caught.message : String(caught));
      return false;
    }
  }

  async function saveChapter(textOverride?: string): Promise<boolean> {
    if (!chapter) return false;
    const prevText = docToText(chapter.body);
    const nextText = textOverride ?? editorText;
    const mutationId = crypto.randomUUID();
    const body = {
      body: textToDoc(nextText), label: "offline_save",
      base_updated_at: chapter.updated_at, client_mutation_id: mutationId,
    };
    if (!navigator.onLine) {
      await queueOfflineMutation(mutationId, "content_update", `/api/v1/contents/${chapter.id}`, "PUT", body);
      const optimistic = { ...chapter, body: body.body };
      setChapter(optimistic);
      await cacheSet(`offline-content:${chapter.id}`, optimistic);
      setOfflineNotice("内容已离线保存，联网后自动同步");
      return true;
    }
    try {
      const updated = await api<Content>(`/api/v1/contents/${chapter.id}`, { method: "PUT", body: JSON.stringify(body) });
      if (updated.sync_status === "conflict") {
        setChapter(updated);
        await cacheDelete(`offline-content:${chapter.id}`);
        setOfflineNotice("检测到版本冲突，离线稿已保存到版本树");
        await loadVersions(chapter.id);
        return false;
      }
      setChapter(updated); await cacheDelete(`offline-content:${chapter.id}`); loadVersions(updated.id);
      setChapters(items => items.map(item => item.id === updated.id ? updated : item));
      lastReviewTextRef.current = "";
      setLiveReviewError("");
      sendEditSignal(updated.id, prevText, nextText);
      return true;
    } catch (caught) {
      if (caught instanceof ApiError && !isOfflineApiError(caught)) throw caught;
      await queueOfflineMutation(mutationId, "content_update", `/api/v1/contents/${chapter.id}`, "PUT", body);
      const optimistic = { ...chapter, body: body.body };
      setChapter(optimistic);
      await cacheSet(`offline-content:${chapter.id}`, optimistic);
      setOfflineNotice("网络不可用，内容已进入同步队列");
      return true;
    }
  }

  async function generateNextChapter() {
    if (!novel || !project || nextChapterLoading) return;
    if (!navigator.onLine) {
      setOfflineNotice("当前网络不可用，无法提交下一章生成任务");
      return;
    }
    const novelId = novel.id;
    const projectId = project.id;
    const knownChapterIds = new Set(chapters.map(item => item.id));
    setNextChapterLoading(true);
    setError("");
    try {
      if (chapter && docToText(chapter.body) !== editorTextRef.current) {
        const saved = await saveChapter();
        if (!saved) {
          setOfflineNotice("当前章节保存失败，已停止生成下一章；请先处理版本冲突");
          setNextChapterLoading(false);
          return;
        }
      }
      await api<{ task_id: string }>("/api/v1/novels/" + novelId + "/continue", { method: "POST" });
      setOfflineNotice("下一章已提交生成，完成后会自动加入章节目录");

      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        try {
          const items = await api<Content[]>(
            "/api/v1/contents?project_id=" + encodeURIComponent(projectId) + "&parent_id=" + encodeURIComponent(novelId),
          );
          const chapterItems = (items || [])
            .filter(item => item.type === "chapter")
            .sort((a, b) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
          setChapters(chapterItems);
          const created = chapterItems.find(item => !knownChapterIds.has(item.id));
          if (created) {
            setChapter(created);
            setEditorText(docToText(created.body));
            setSelection("");
            setPendingAiEdit(null);
            setEditorAiReview(null);
            setEditorResetNonce(value => value + 1);
            void loadVersions(created.id);
            setNextChapterLoading(false);
            setOfflineNotice("第" + String(created.meta?.seq || chapterItems.length) + "章《" + created.title + "》已生成，已自动打开");
            nextChapterPollRef.current = null;
            return;
          }
        } catch {
          // The task continues on the worker; a transient refresh failure should not cancel it.
        }
        if (attempts >= 60) {
          setNextChapterLoading(false);
          setOfflineNotice("下一章任务仍在后台生成，稍后刷新章节目录即可查看");
          nextChapterPollRef.current = null;
          return;
        }
        nextChapterPollRef.current = window.setTimeout(() => { void poll(); }, 5000);
      };
      void poll();
    } catch (caught) {
      setNextChapterLoading(false);
      setOfflineNotice(caught instanceof ApiError ? "下一章生成失败：" + caught.message : "下一章生成任务提交失败，请重试");
    }
  }

  // V3-P3-⑩：编辑器 diff 信号采集（fire-and-forget，绝不阻塞保存）
  async function sendEditSignal(chapterId: string, prevText: string, newText: string) {
    if (!project?.id) return;
    if (prevText === newText) return;
    if (!newText.trim()) return;
    try {
      await api(`/api/v1/author-style/${project.id}/signals`, {
        method: "POST",
        body: JSON.stringify({
          content_id: chapterId,
          signals: [
            { signal_type: "edit", kept_text: newText, deleted_text: prevText, edited_text: newText },
          ],
        }),
      });
    } catch {
      /* 风格学习信号失败不影响编辑体验 */
    }
  }

  async function markLiked(text: string) {
    if (!project?.id || !text.trim()) return;
    try {
      await api(`/api/v1/author-style/${project.id}/like`, {
        method: "POST",
        body: JSON.stringify({ content_id: chapter?.id ?? null, text }),
      });
      setOfflineNotice("已记录为偏好表达，将用于强化风格卡");
    } catch {
      /* 标记失败静默 */
    }
  }

  // NC-LIVE-AUDIT: 实时审计——对当前章节文本打分并取回审阅问题，不修改正文。
  // 章节打开（editorText 变化）与打字停顿都会触发；AI 建议待确认/流式生成时暂停。
  async function requestReview(chapterId: string, text: string, force = false, attempt = 0) {
    const trimmed = text.trim();
    if (trimmed.length < 30) return;
    if (!navigator.onLine) return;
    if (pendingAiEditRef.current || streamPreviewRef.current) return;
    if (!force && trimmed === lastReviewTextRef.current) return;
    const requestKey = `${chapterId}:${trimmed}`;
    if (reviewRequestKeyRef.current === requestKey) return;
    reviewRequestKeyRef.current = requestKey;
    const requestSeq = ++reviewRequestSeqRef.current;
    setLiveReviewing(true);
    setLiveReviewError("");
    try {
      const output = await api<{ review_7dim?: any; review?: any; next_chapter_plan?: any; audit_error?: string }>(
        `/api/v1/contents/${chapterId}/review`,
        { method: "POST", body: JSON.stringify({ selection: text, client_mutation_id: crypto.randomUUID() }) },
      );
      if (requestSeq !== reviewRequestSeqRef.current) return;
      const review = output.review ?? output.review_7dim;
      if (!review || typeof review !== "object" || Object.keys(review).length === 0) {
        lastReviewTextRef.current = "";
        setEditorAiReview(null);
        setLiveReviewError(output.audit_error || "实时审计未返回有效结果，请点击重新审计");
        return;
      }
      lastReviewTextRef.current = trimmed;
      setEditorAiReview({ review, next: output.next_chapter_plan });
    } catch (caught) {
      if (requestSeq !== reviewRequestSeqRef.current) return;
      // Provider warm-up, connection reuse and a just-restarted API can fail
      // once when a chapter is opened.  Automatic opening must not turn that
      // transient failure into a manual-only state.  Retry exactly once; the
      // second failure remains visible and actionable.
      if (attempt === 0) {
        setLiveReviewError("实时审阅正在启动，稍后自动重试…");
        window.setTimeout(() => {
          if (
            requestSeq === reviewRequestSeqRef.current
            && editorTextRef.current.trim() === trimmed
            && !pendingAiEditRef.current
            && !streamPreviewRef.current
          ) {
            void requestReview(chapterId, trimmed, true, 1);
          }
        }, 1200);
        return;
      }
      lastReviewTextRef.current = "";
      setEditorAiReview(null);
      setLiveReviewError(caught instanceof ApiError ? `实时审计失败：${caught.message}` : "实时审计失败，请点击重新审计");
      setOfflineNotice(caught instanceof ApiError ? `实时审计失败：${caught.message}` : "实时审计失败，请稍后重试");
    } finally {
      if (reviewRequestKeyRef.current === requestKey) reviewRequestKeyRef.current = "";
      if (requestSeq === reviewRequestSeqRef.current) setLiveReviewing(false);
    }
  }

  async function runEditorOp(op: string, instructionOverride?: string) {
    if (!chapter) return;
    const sourceText = editorTextRef.current;
    const selectedText = op === "rewrite_chapter" || instructionOverride
      ? sourceText
      : selection || (op === "continue" ? sourceText : "");
    if (!selectedText.trim()) {
      setError(op === "continue" ? "当前章节没有可续写内容" : "请先在正文中选择需要处理的文字");
      return;
    }
    setError("");
    setPendingAiEdit(null);
    setEditorAiReview(null);
    setLiveReviewError("");
    const mutationId = crypto.randomUUID();
    const url = `/api/v1/contents/${chapter.id}/ai/${op}`;
    const body = {
      selection: selectedText,
      instruction: instructionOverride || (op === "rewrite_chapter" ? "整章重写，保留核心剧情，优化小说平台阅读体验" : "保持当前风格"),
      client_mutation_id: mutationId,
    };
    if (!navigator.onLine) {
      await queueOfflineMutation(mutationId, "ai_operation", url, "POST", body);
      setOfflineNotice("AI 操作已排队，联网后自动执行");
      return;
    }
    setEditorAiLoading(true);
    setEditorAiOperation(op);
    try {
      if (!["polish", "rewrite", "rewrite_chapter", "deai"].includes(op)) {
        // 流式优先：增量预览，完成后一次性替换选区
        setStreamPreview("");
        try {
          const { text } = await withTimeout(
            apiStream(`${url}/stream`, { method: "POST", body: JSON.stringify(body) },
              delta => setStreamPreview(previous => previous + delta)),
            EDITOR_OPERATION_TIMEOUT_MS,
            "AI 续写等待超时，请检查模型服务后重试",
          );
          setStreamPreview("");
          const normalizedText = normalizeParagraphBreaks(textValue(text));
          if (!normalizedText.trim()) {
            setError("AI 未返回可用正文，请重试");
            return;
          }
          const nextText = buildAiEditPreview(sourceText, selectedText, normalizedText, op, Boolean(selection));
          setPendingAiEdit({ op, originalText: selectedText, proposedText: normalizedText, nextText });
          if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
          return;
        } catch (streamError) {
          setStreamPreview("");
          if (streamError instanceof ApiError && streamError.status === 404) {
            // 旧后端无流式端点 → 走非流式
          } else if (streamError instanceof ApiError && isOfflineApiError(streamError)) {
            await queueOfflineMutation(mutationId, "ai_operation", url, "POST", body);
            setOfflineNotice("网络不可用，AI 操作已进入出站队列");
            return;
          } else {
            setError(streamError instanceof ApiError ? (streamError.message || "AI 操作失败") : (streamError instanceof Error ? streamError.message : "AI 操作失败，请重试"));
            return;
          }
        }
      }
      try {
        const output = await withTimeout(
          api<{ text: string; review?: any; review_7dim?: any; next_chapter_plan?: any }>(url, { method: "POST", body: JSON.stringify(body) }),
          EDITOR_OPERATION_TIMEOUT_MS,
          "AI 操作等待超时，请检查模型服务后重试",
        );
        const normalizedText = normalizeParagraphBreaks(textValue(output?.text));
        if (!normalizedText.trim()) {
          setError("AI 未返回可用正文，请重试");
          return;
        }
        const nextText = buildAiEditPreview(sourceText, selectedText, normalizedText, op, Boolean(selection));
        setPendingAiEdit({ op, originalText: selectedText, proposedText: normalizedText, nextText });
        setEditorAiReview({ review: output.review ?? output.review_7dim, next: output.next_chapter_plan });
        if (run) api<AiCall[]>(`/api/v1/ai-calls?run_id=${run.id}`).then(setAiCalls);
      } catch (caught) {
        if (!(caught instanceof ApiError) || !isOfflineApiError(caught)) {
          setError(caught instanceof ApiError ? (caught.message || "AI 操作失败") : (caught instanceof Error ? caught.message : "AI 操作失败，请重试"));
          return;
        }
        await queueOfflineMutation(mutationId, "ai_operation", url, "POST", body);
        setOfflineNotice("网络不可用，AI 操作已进入出站队列");
      }
    } finally {
      setEditorAiLoading(false);
      setEditorAiOperation("");
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
          const response = await apiRaw<ApiResponse<any>>(mutation.url, {
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
                const proposedText = normalizeParagraphBreaks(String(response.data.text || ""));
                setPendingAiEdit({
                  op: mutation.url.split("/").at(-1) || "ai",
                  originalText: selectedText,
                  proposedText,
                  nextText: buildAiEditPreview(editorTextRef.current, selectedText, proposedText, mutation.url.split("/").at(-1) || "ai", true),
                  sourceMutationId: mutation.id,
                });
              await updateMutation(mutation.id, { status: "completed", result: response.data });
              setOfflineNotice("离线 AI 操作已完成，请预览后决定是否应用");
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
    const normalizedText = normalizeParagraphBreaks(text);
    const nextText = `${editorTextRef.current}\n\n${normalizedText}`.trim();
    setEditorText(nextText);
    setEditorResetNonce(n => n + 1);
    if (id) {
      await deleteMutation(id);
      setOfflineAiResults(results => results.filter(result => result.id !== id));
      setOfflineQueueCount((await listMutations()).length);
    }
    setOfflineNotice("离线 AI 结果已应用到草稿，自动保存会创建可恢复版本");
  }

  async function applyPendingAiEdit() {
    if (!pendingAiEdit) return;
    const proposed = pendingAiEdit;
    try {
      // 先用最新 base_updated_at 落库，再清理预览；这样失败时原文和
      // “待确认”建议都还在，不会出现 UI 显示已应用但服务器仍是旧稿。
      const saved = await saveChapter(pendingAiEdit.nextText);
      if (!saved) {
        setOfflineNotice("应用失败：服务器存在版本冲突，原文未改变，请先处理冲突");
        return;
      }
      setEditorText(proposed.nextText);
      setSelection("");
      if (proposed.sourceMutationId) {
        await deleteMutation(proposed.sourceMutationId);
        setOfflineAiResults(results => results.filter(result => result.id !== proposed.sourceMutationId));
        setOfflineQueueCount((await listMutations()).length);
      }
      setPendingAiEdit(null);
      setLiveReviewError("");
      lastReviewTextRef.current = "";
      setEditorResetNonce(n => n + 1);
      setOfflineNotice("AI 建议已应用到草稿，已创建可恢复版本");
    } catch (caught) {
      setError(caught instanceof ApiError ? `应用 AI 建议失败：${caught.message}` : "应用 AI 建议失败，原文未改变，请重试");
      setOfflineNotice("AI 建议尚未应用，原文保持不变");
    }
  }

  function discardPendingAiEdit() {
    setPendingAiEdit(null);
    setOfflineNotice("已放弃 AI 建议，原文保持不变");
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

  // V7 chapter metadata is authoritative.  Do not merge the latest workflow
  // run into a selected chapter: that made a different chapter's old nodes
  // overwrite the selected V7 audit and produced empty/mismatched cards.
  const chapterMeta = (chapter?.meta || {}) as Record<string, any>;
  const persistedV7Review = (chapterMeta.canonical_review || {}) as Record<string, any>;
  const isV7Chapter = chapterMeta.canonical_engine === "v7" || chapterMeta.source === "v7";
  const legacyReview = ({
    ...((chapterMeta.review_7dim as Record<string, unknown> | undefined) ?? {}),
    ...(run?.nodes.find(n => n.node_key === "n8")?.output ?? {}),
    ...(run?.nodes.find(n => n.node_key === "write_self_review")?.output ?? {}),
    final_consistency_check: run?.nodes.find(n => n.node_key === "final_consistency_check")?.output ?? chapterMeta.final_consistency_check ?? chapterMeta.quality_gate,
    final_continuity_audit: run?.nodes.find(n => n.node_key === "final_continuity_audit")?.output ?? chapterMeta.final_continuity_audit,
  }) as Record<string, unknown>;
  const review = (isV7Chapter ? {
    ...persistedV7Review,
    overall_score: persistedV7Review.overall_score ?? chapterMeta.review_score,
    dimension_scores: persistedV7Review.dimension_scores ?? chapterMeta.dimension_scores,
    audit_report: persistedV7Review.audit_report ?? chapterMeta.audit_report,
    review_evidence: persistedV7Review.review_evidence ?? chapterMeta.review_evidence,
    reader_experience: persistedV7Review.reader_experience ?? chapterMeta.reader_experience,
    issues: persistedV7Review.issues ?? chapterMeta.review_issues,
    continuity: persistedV7Review.continuity ?? chapterMeta.continuity,
    final_continuity_audit: persistedV7Review.final_continuity_audit
      ?? chapterMeta.final_continuity_audit
      ?? (chapterMeta.continuity ? { continuity: chapterMeta.continuity } : undefined),
    provenance: persistedV7Review.provenance ?? chapterMeta.review_provenance,
    canonical_engine: "v7",
  } : legacyReview) as any;

  const titles: Record<Tab, string> = { dashboard: "小说首页", overview: "数据概览", workspace: "小说首页", ranking: "扫榜选书", library: "我的书库", wizard: "创作向导", progress: "创作进度", review: "审阅与一致性", editor: "章节编辑器", costs: "AI 成本", billing: "订阅与套餐", prompts: "Prompt 管理", dag: "工作流编排", settings: "小说设置", studio: "内容工作室", publish: "发布看板", hotspot: "热点追踪", knowledge: "知识库", fanout: "多平台分发", versions: "版本历史", foreshadowing: "伏笔看板", collaboration: "协作管理", agents: "智能体", plugins: "插件管理", skills: "Skill 中心", chat: "AI 对话", marketplace: "模块市场", v7: "V7 智能体" };
  const cmdActions = [
    { id: "dashboard", label: "小说首页", action: () => setTab("dashboard") },
    { id: "wizard", label: "创作向导 · 新建小说", action: () => setTab("wizard") },
    { id: "library", label: "我的书库 · 管理小说", action: () => setTab("library") },
    { id: "progress", label: "创作进度 · 查看 AI 工作流", action: () => setTab("progress") },
    { id: "editor", label: "章节编辑器 · 继续写作", action: () => setTab("editor") },
    { id: "review", label: "审阅与一致性 · 检查小说", action: () => setTab("review") },
    { id: "settings", label: "小说设置 · AI 与创作偏好", action: () => setTab("settings") },
  ];

  function handleLogin(t: string, email: string) {
    sessionStorage.setItem("starlume_user_email", email);
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
      sessionStorage.removeItem("starlume_user_email");
      setToken("");
      setUserEmail("");
      userSelectedProject.current = false;
      setProjects([]);
      setProject(null);
      setNovel(null);
      setNovels([]);
      setRun(null);
      setChapters([]);
      setChapter(null);
      setEditorText("");
      setHistory([]);
      setHistoryTotal(0);
      setHistoryLoadingMore(false);
      setHistoryError("");
    }
  };

  return (
    <Layout tab={tab} setTab={setTab} title={titles[tab]} runStatus={displayRunStatus(run)} userEmail={userEmail}
      projects={projects.map(item => ({ id: item.id, name: item.name }))}
      currentProjectId={project?.id}
      onProjectChange={handleProjectChange}
      novels={novels.map(n => ({ id: n.id, title: cleanNovelTitle(n.title, "待命名作品") }))}
      currentNovelId={novel?.id}
      onNovelChange={(novelId) => { void activateNovel(novelId); }}
      showSelector={tab === "progress" || tab === "editor" || tab === "review"}>
      {error && <div className="error">{error}</div>}
      {routeNotFound ? <NotFoundPage onNavigate={setTab} /> : <>
      {tab === "dashboard" && <WorkspaceDashboard projectId={project?.id} currentNovelTitle={novel?.title} run={run} chaptersCount={chapters.length} aiCalls={aiCalls} userEmail={userEmail} onNavigate={setTab} />}
      {tab === "library" && project && <BookLibrary projectId={project.id} onOpen={async (bookId, chapterId) => {
        if (await activateNovel(bookId, chapterId)) setTab("editor");
      }} />}
      {tab === "ranking" && project && (
        <RankingCenter
          projectId={project.id}
          onBookCreated={async (novelId, runId) => {
            const book = await api<Content>(`/api/v1/contents/${novelId}`);
            setNovel(book);
            void cacheSet(currentNovelCacheKey, book);
            setTab(runId ? "progress" : "library");
          }}
        />
      )}
      {tab === "wizard" && <Wizard {...{ idea, setIdea, genre, setGenre, platform, setPlatform, subgenre, setSubgenre, stylePlugin, setStylePlugin, style, setStyle, targetWords, setTargetWords, busy, startBootstrap, projectId: project?.id }} />}
      {tab === "progress" && <Progress
        run={run}
        novel={novel}
        history={history}
        historyTotal={historyTotal}
        historyLoading={historyLoading}
        historyLoadingMore={historyLoadingMore}
        historyError={historyError}
        onOpenHistory={openGenerationHistory}
        onLoadMoreHistory={loadMoreHistory}
        onConfirm={confirmTitle}
        onRegenerateTitles={regenerateTitles}
        onNewRun={refreshRun}
      />}
      {tab === "review" && <Review chapter={chapter} review={review} characters={characters} timeline={narrative.timeline} arcs={narrative.arcs} narrativeEvidence={narrative.evidence as { timeline_source?: string; arcs_source?: string } | undefined} onRepairApplied={(updated) => {
        if (!chapter) return;
        const merged = { ...chapter, ...updated, body: (updated.body as TipTapDoc | undefined) ?? chapter.body };
        setChapter(merged);
        setChapters(items => items.map(item => item.id === merged.id ? merged : item));
        setEditorText(docToText(merged.body));
        setSelection("");
        setPendingAiEdit(null);
        setEditorAiReview(null);
        setLiveReviewError("");
        lastReviewTextRef.current = "";
        setEditorResetNonce(value => value + 1);
       }} onOpenEditor={async (chapterId?: string) => {
        // 加载最新章节到编辑器
        if (novel && project) {
          const items = await api<Content[]>(`/api/v1/contents?project_id=${project.id}&parent_id=${novel.id}`);
          const chs = (items || []).filter(i => i.type === "chapter").sort((a: any, b: any) => Number(a.meta?.seq || 0) - Number(b.meta?.seq || 0));
          setChapters(chs);
          if (chs.length > 0) {
            const target = (chapterId && chs.find(item => item.id === chapterId)) || chs[chs.length - 1];
            setChapter(target);
            setEditorText(docToText(target.body));
          }
        }
        setTab("editor");
      }} />}
      {tab === "editor" && <div className="editor-page page-enter">
          <React.Suspense fallback={<div className="panel">正在加载编辑器…</div>}>
            <Editor {...{ chapter, chapters, selectChapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion, offlineNotice, offlineQueueCount, offlineAiResults, applyOfflineAiResult, streamPreview, editorAiReview, pendingAiEdit, applyPendingAiEdit, discardPendingAiEdit, markLiked, projectId: project?.id, liveReviewing, liveReviewError, editorResetNonce, editorAiLoading, editorAiOperation, onGenerateNextChapter: generateNextChapter, nextChapterLoading, onRequestReview: () => { if (chapter?.id) void requestReview(chapter.id, editorTextRef.current, true); } }} />
          </React.Suspense>
      </div>}
      {tab === "settings" && <Settings projectId={project?.id || ""} />}
      {tab === "v7" && <V7Dashboard
        novelId={novel?.id ?? null}
        onOpenProgress={() => setTab("progress")}
        onOpenReview={() => setTab("review")}
        onOpenLibrary={() => setTab("library")}
      />}
      </>}
      <CommandPalette commands={cmdActions} />
    </Layout>
  );
}
