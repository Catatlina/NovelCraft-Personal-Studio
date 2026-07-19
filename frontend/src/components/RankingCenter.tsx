import React, { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

type Wrapped<T> = { data: T };
type Source = { source_key: string; display_name: string; last_success_at?: string; last_error?: string; capture_status?: string; user_action_required?: boolean; ocr_required?: boolean };
type Snapshot = { id: string; source_key: string; display_name: string; status: string; capture_status?: string; collector?: string; confidence?: number; validation_summary?: Record<string, unknown>; item_count: number; error?: string; captured_at: string };
type Evidence = Record<string, unknown>;
type RankingItem = { id: string; rank_no: number; title: string; author?: string; category?: string; source_url?: string; metadata_status?: string; collector?: string; confidence?: number; evidence?: Evidence; metrics?: { collector?: string; confidence?: number; evidence?: Evidence; validation?: Evidence } };
type MarketAnalysis = { analysis_id: string; summary: string; status: string; analysis_mode: string; market_signals?: Array<{ signal?: string; evidence?: string }>; audience?: { primary?: string; needs?: string[] }; title_patterns?: Array<{ pattern?: string }>; pacing?: { opening?: string; retention_hooks?: string[] }; originality_constraints?: string[]; signals?: any; layers?: any; heatmap?: any; keywords?: any };
type SnapshotDetail = Snapshot & { items: RankingItem[]; latest_analysis?: MarketAnalysis | null };
type Topic = { id: string; title: string; premise: string; genre: string; market_score: number; status: string; target_audience?: string; differentiators?: string[]; market_evidence?: string[]; risk?: string; originality_notes?: string; novel_id?: string };
type ImportItem = Record<string, unknown>;
type CaptureArtifact = { source: string; status?: string; collector?: string; items?: ImportItem[]; source_label?: string };

function errorText(error: unknown): string {
  if (error instanceof ApiError) return JSON.stringify(error.payload);
  return String(error);
}

function parseCsv(text: string): ImportItem[] {
  const records: string[][] = [];
  let record: string[] = [], field = "", quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') { field += '"'; index += 1; }
      else quoted = !quoted;
    } else if (character === "," && !quoted) { record.push(field); field = ""; }
    else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      record.push(field); field = "";
      if (record.some(value => value.trim())) records.push(record);
      record = [];
    } else field += character;
  }
  record.push(field);
  if (record.some(value => value.trim())) records.push(record);
  if (quoted) throw new Error("CSV 存在未闭合的引号");
  const headers = (records.shift() || []).map(value => value.trim().replace(/^\uFEFF/, ""));
  if (!headers.includes("rank") || !headers.includes("title")) throw new Error("CSV 表头必须包含 rank 和 title");
  return records.map(values => Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim() || ""])))
    .filter(item => String(item.title || "").trim());
}

function evidenceText(evidence?: Evidence): string {
  if (!evidence || !Object.keys(evidence).length) return "无证据记录";
  return Object.entries(evidence).map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`).join("；");
}

export function RankingCenter({ projectId, onBookCreated }: { projectId: string; onBookCreated: (novelId: string, runId?: string) => Promise<void> }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [bookmarkedTopics, setBookmarkedTopics] = useState<Topic[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [openSnapshotId, setOpenSnapshotId] = useState("");
  const [snapshotDetails, setSnapshotDetails] = useState<Record<string, SnapshotDetail>>({});
  const [importItems, setImportItems] = useState<ImportItem[]>([]);
  const [captureArtifact, setCaptureArtifact] = useState<CaptureArtifact | null>(null);
  const [importSource, setImportSource] = useState("manual_import");
  const [importFileName, setImportFileName] = useState("");
  const [topicTab, setTopicTab] = useState<"all" | "bookmarked">("all");
  const [scanWarning, setScanWarning] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"single" | "multi">("single");
  const [multiAnalysisResult, setMultiAnalysisResult] = useState<any>(null);
  const [multiAnalysisLoading, setMultiAnalysisLoading] = useState(false);

  async function load() {
    const [s, p, t] = await Promise.allSettled([
      api<Wrapped<Source[]>>(`/api/v1/ranking/sources?project_id=${projectId}`),
      api<Wrapped<Snapshot[]>>(`/api/v1/ranking/snapshots?project_id=${projectId}`),
      api<Wrapped<Topic[]>>(`/api/v1/ranking/topics?project_id=${projectId}`),
    ]);
    if (s.status === "fulfilled") setSources(s.value.data);
    if (p.status === "fulfilled") setSnapshots(p.value.data);
    if (t.status === "fulfilled") setTopics(t.value.data);
    const failed = [s, p, t].filter(item => item.status === "rejected");
    if (failed.length) setMessage(`${failed.length} 个分区加载失败，其他数据仍可使用`);
  }

  useEffect(() => { void load().catch(error => setMessage(String(error))); }, [projectId]);

  async function scan(source: Source) {
    setBusy(`scan:${source.source_key}`); setMessage("");
    try {
      const result = await api<Wrapped<{ item_count: number }>>(`/api/v1/ranking/sources/${source.source_key}/scan?project_id=${projectId}`, { method: "POST", body: "{}" });
      setMessage(`${source.display_name}采集成功：${result.data.item_count} 本`); await load();
    } catch (error) { setMessage(`采集失败：${errorText(error)}`); await load(); }
    finally { setBusy(""); }
  }

  async function scanAll() {
    setBusy("scan-all"); setMessage("一键采集所有平台中...");
    try {
      const result = await api<Wrapped<{ scanned: string[], errors: Record<string,any>, succeeded: number, failed: number }>>(`/api/v1/ranking/scan-all?project_id=${projectId}`, { method: "POST", body: "{}" });
      const { scanned, succeeded, failed } = result.data;
      setMessage(`一键采集完成：${succeeded}/${scanned.length + failed} 平台成功`);
      await load();
    } catch (error) { setMessage(`一键采集失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function selectImportFile(file?: File) {
    setMessage(""); setImportItems([]); setCaptureArtifact(null); setImportFileName(file?.name || "");
    if (!file) return;
    try {
      const text = await file.text();
      if (file.name.toLowerCase().endsWith(".csv")) setImportItems(parseCsv(text));
      else {
        const parsed: unknown = JSON.parse(text);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)
          && typeof (parsed as CaptureArtifact).source === "string"
          && ["fanqie", "qidian", "zongheng", "manual"].includes((parsed as CaptureArtifact).source)
          && ("status" in (parsed as Record<string, unknown>) || "collector" in (parsed as Record<string, unknown>))) {
          const artifact = parsed as CaptureArtifact;
          setCaptureArtifact(artifact);
          setImportItems(Array.isArray(artifact.items) ? artifact.items : []);
          setImportSource(artifact.source_label || artifact.source);
          return;
        }
        const data = Array.isArray(parsed) ? parsed : (parsed as { items?: unknown })?.items;
        if (!Array.isArray(data)) throw new Error("JSON 必须是条目数组或包含 items 数组");
        setImportItems(data.filter(item => item && typeof item === "object") as ImportItem[]);
        if (!Array.isArray(parsed)) {
          const label = (parsed as { source_label?: unknown; source?: unknown }).source_label || (parsed as { source?: unknown }).source;
          if (typeof label === "string" && label.trim()) setImportSource(label.trim());
        }
      }
    } catch (error) { setMessage(`文件解析失败：${errorText(error)}`); }
  }

  async function importRanking() {
    if (!captureArtifact && !importItems.length) { setMessage("请先选择包含有效条目的 CSV、JSON 或采集工件"); return; }
    if (!importSource.trim()) { setMessage("请填写来源标识"); return; }
    setBusy("import"); setMessage("");
    try {
      const result = captureArtifact
        ? await api<Wrapped<{ snapshot_id: string; item_count: number; capture_status?: string; status?: string }>>(`/api/v1/ranking/capture-import?project_id=${projectId}`, {
            method: "POST", body: JSON.stringify({ ...captureArtifact, source_label: importSource.trim() }),
          })
        : await api<Wrapped<{ snapshot_id: string; item_count: number; capture_status?: string; status?: string }>>(`/api/v1/ranking/import?project_id=${projectId}`, {
            method: "POST", body: JSON.stringify({ source_label: importSource.trim(), items: importItems }),
          });
      const reviewHint = result.data.capture_status === "needs_review" ? "，低置信度条目需人工确认后才能分析" : "";
      setMessage(`导入成功：${result.data.item_count} 条${reviewHint}`);
      setImportItems([]); setCaptureArtifact(null); setImportFileName("");
      setOpenSnapshotId(result.data.snapshot_id || ""); await load();
    } catch (error) { setMessage(`导入失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function analyze(snapshot: Snapshot) {
    setBusy(`analysis:${snapshot.id}`); setMessage("");
    try {
      // Use new 10-layer analysis endpoint
      const result = await api<Wrapped<any>>(`/api/v1/ranking/analyze`, {
        method: "POST",
        body: JSON.stringify({
          snapshot_id: snapshot.id,
          platforms: [snapshot.source_key],
          analysis_mode: "single",
        }),
      });
      const data = result.data;
      setSnapshotDetails(current => ({
        ...current,
        [snapshot.id]: {
          ...(current[snapshot.id] || snapshot),
          items: current[snapshot.id]?.items || [],
          latest_analysis: {
            analysis_id: data.analysis_id,
            summary: `十层分析完成：${data.succeeded_layers}/${data.total_layers}层`,
            status: data.status,
            analysis_mode: "ten_layer",
            signals: data.TrendReport?.market_trends || [],
            layers: data.ScanResult || {},
            heatmap: data.HeatMap,
            keywords: data.KeywordCloud,
          },
        } as SnapshotDetail,
      }));
      setOpenSnapshotId(snapshot.id);
      setMessage(`十层分析完成：${data.succeeded_layers}/${data.total_layers}层通过`);
      await load();
    } catch (error) { setMessage(`分析失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function analyzeMultiPlatform() {
    const succeeded = snapshots.filter(s => s.status === "succeeded");
    if (succeeded.length < 2) { setMessage("需要至少 2 个成功的快照才能进行聚合分析"); return; }
    setMultiAnalysisLoading(true); setMessage(""); setMultiAnalysisResult(null);
    try {
      const platformKeys = [...new Set(succeeded.map(s => s.source_key))];
      const result = await api<Wrapped<any>>(`/api/v1/ranking/analyze`, {
        method: "POST",
        body: JSON.stringify({
          snapshot_id: succeeded[0].id,
          analysis_mode: "multi",
          platforms: platformKeys,
        }),
      });
      setMultiAnalysisResult(result.data);
      setMessage(`多平台聚合分析完成：${result.data.succeeded_layers || 0}/${result.data.total_layers || 0}层通过`);
    } catch (error) { setMessage(`聚合分析失败：${errorText(error)}`); }
    finally { setMultiAnalysisLoading(false); }
  }

  async function retrySnapshot(snapshot: Snapshot) {
    setBusy(`retry:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<{ snapshot_id?: string; item_count?: number }>>(`/api/v1/ranking/snapshots/${snapshot.id}/retry`, { method: "POST", body: "{}" });
      setMessage(`重试成功：采集 ${result.data.item_count ?? 0} 本`);
      setOpenSnapshotId(result.data.snapshot_id || "");
      await load();
    } catch (error) { setMessage(`重试失败：${errorText(error)}`); await load(); }
    finally { setBusy(""); }
  }

  async function validateMetadata(snapshot: Snapshot) {
    setBusy(`validate:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<{ checked: number; summary: Record<string, number>; status: string }>>(`/api/v1/ranking/snapshots/${snapshot.id}/validate-metadata`, {
        method: "POST", body: JSON.stringify({ provider: "open_library", force: false, limit: 20 }),
      });
      setMessage(`元数据交叉校验完成：检查 ${result.data.checked} 条；${Object.entries(result.data.summary).map(([key, value]) => `${key} ${value}`).join("，")}`);
      const detail = await api<Wrapped<SnapshotDetail>>(`/api/v1/ranking/snapshots/${snapshot.id}`);
      setSnapshotDetails(current => ({ ...current, [snapshot.id]: detail.data }));
      setOpenSnapshotId(snapshot.id); await load();
    } catch (error) { setMessage(`元数据校验失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function confirmCapture(snapshot: Snapshot) {
    setBusy(`confirm:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<{ capture_status: string; status: string }>>(`/api/v1/ranking/snapshots/${snapshot.id}/confirm-capture`, {
        method: "POST", body: "{}",
      });
      setMessage(`采集证据已确认：${result.data.capture_status}`);
      await load();
      const detail = await api<Wrapped<SnapshotDetail>>(`/api/v1/ranking/snapshots/${snapshot.id}`);
      setSnapshotDetails(current => ({ ...current, [snapshot.id]: detail.data }));
      setOpenSnapshotId(snapshot.id);
    } catch (error) { setMessage(`确认失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function toggleSnapshot(snapshot: Snapshot) {
    if (openSnapshotId === snapshot.id) { setOpenSnapshotId(""); return; }
    setOpenSnapshotId(snapshot.id);
    if (snapshot.status !== "succeeded" || snapshotDetails[snapshot.id]) return;
    setBusy(`detail:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<SnapshotDetail>>(`/api/v1/ranking/snapshots/${snapshot.id}`);
      setSnapshotDetails(current => ({ ...current, [snapshot.id]: result.data }));
    } catch (error) { setMessage(`快照详情加载失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function createBook(topic: Topic) {
    setBusy(`book:${topic.id}`); setMessage("");
    try {
      const result = await api<Wrapped<{ novel_id: string; run_id?: string; status: string; warning?: string }>>(`/api/v1/ranking/topics/${topic.id}/generate-book`, {
        method: "POST", body: JSON.stringify({ auto_start: true, target_words: 800000 }),
      });
      await onBookCreated(result.data.novel_id, result.data.run_id);
      setMessage(result.data.run_id ? "小说已进入书库并启动自动生成" : `小说已进入书库，工作流待恢复：${result.data.warning || "队列不可用"}`);
      await load();
    } catch (error) { setMessage(`立项或打开失败：${errorText(error)}`); await load(); }
    finally { setBusy(""); }
  }

  // ── Topic Pool Actions ───────────────────────────────────
  async function toggleBookmark(topic: Topic) {
    setBusy(`bookmark:${topic.id}`); setMessage("");
    try {
      await api(`/api/v1/ranking/topics/${topic.id}/bookmark`, { method: "POST", body: JSON.stringify({ bookmark: true }) });
      await load();
    } catch (error) { setMessage(`收藏失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function deleteTopic(topic: Topic) {
    if (!confirm(`确定删除选题「${topic.title}」？`)) return;
    setBusy(`delete-topic:${topic.id}`); setMessage("");
    try {
      await api(`/api/v1/ranking/topics/${topic.id}`, { method: "DELETE" });
      setMessage(`已删除「${topic.title}」`);
      await load();
    } catch (error) { setMessage(`删除失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function batchDeleteAll() {
    const ids = (topicTab === "bookmarked" ? bookmarkedTopics : topics).map(t => t.id);
    if (!ids.length) return;
    if (!confirm(`确定删除全部 ${ids.length} 个选题？此操作不可撤销。`)) return;
    setBusy("batch-delete"); setMessage("");
    try {
      await api("/api/v1/ranking/topics/batch-delete", { method: "POST", body: JSON.stringify({ ids }) });
      setMessage(`已批量删除 ${ids.length} 个选题`);
      await load();
    } catch (error) { setMessage(`批量删除失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function loadBookmarked() {
    try {
      const result = await api<Wrapped<Topic[]>>(`/api/v1/ranking/topics/bookmarked?project_id=${projectId}`);
      setBookmarkedTopics(Array.isArray(result.data) ? result.data : (result.data as any)?.topics || []);
    } catch { /* ignore */ }
  }

  useEffect(() => { if (topicTab === "bookmarked") void loadBookmarked(); }, [topicTab, projectId]);

  // Status badge helper
  const statusBadge = (status: string, captureStatus?: string) => {
    if (status === "failed") return <span className="badge red">失败</span>;
    if (captureStatus === "needs_review") return <span className="badge orange">待人工复核</span>;
    if (captureStatus === "partial") return <span className="badge orange">部分成功</span>;
    return <span className="badge green">成功</span>;
  };

  const sourcesPager = usePagination({ items: sources, pageSize: 10, mode: "client" });
  const snapshotsPager = usePagination({ items: snapshots, pageSize: 10, mode: "client" });
  const topicsView = topicTab === "bookmarked" ? bookmarkedTopics : topics;
  const topicsPager = usePagination({ items: topicsView, pageSize: 10, mode: "client" });
  const openItems = openSnapshotId ? (snapshotDetails[openSnapshotId]?.items || []) : [];
  const snapshotItemsPager = usePagination({ items: openItems, pageSize: 10, mode: "client" });

  return <div style={{ display: "grid", gap: 20 }}>
    {/* ── Page head ── */}
    <div className="page-head">
      <div>
        <h1>榜单中心</h1>
        <p>采集各大平台热门榜单，AI 分析市场趋势与原创选题</p>
      </div>
      <div className="head-actions">
        <button
          className="btn-primary"
          style={{ width: "auto", padding: "0 24px", height: 42 }}
          disabled={!!busy}
          onClick={scanAll}
        >
          🚀 {busy === "scan-all" ? "采集中…" : "一键采集所有平台"}
        </button>
      </div>
    </div>

    {/* ── Message banner ── */}
    {message && (
      <div
        style={{
          padding: "10px 16px",
          borderRadius: "var(--r-md)",
          background: "var(--primary-dim)",
          color: "var(--primary-light)",
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        {message}
      </div>
    )}

    {/* ── Source cards + import ── */}
    <div className="card">
      <div className="card-head">
        <div className="card-title" style={{ gap: 6 }}>
          <span>📡</span> 榜单源
        </div>
        <span className="card-sub">{sources.length} 个平台</span>
      </div>
      <div className="grid grid-3">
        {sourcesPager.pageData.map(source => {
          const healthLabel = source.last_error ? "异常" : source.last_success_at ? "健康" : "未采集";
          const healthBadge = source.last_error ? "red" : source.last_success_at ? "green" : "gray";
          return <div className="card" key={source.source_key} style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
              <strong style={{ fontSize: 14 }}>{source.display_name}</strong>
              <span className={`badge ${healthBadge}`}>{healthLabel}</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.6 }}>
              <div>{source.last_success_at ? `最近成功：${new Date(source.last_success_at).toLocaleString()}` : "最近成功：暂无"}</div>
              {source.capture_status && <div>采集状态：{source.capture_status}</div>}
              {source.user_action_required && <div style={{ color: "var(--red)" }}>需要用户在浏览器完成验证后重新采集</div>}
              {source.ocr_required && <div>该来源需要截图/OCR 采集</div>}
              {source.last_error && <div style={{ color: "var(--red)" }}>{source.last_error}</div>}
            </div>
            <button
              className="btn-sm btn-primary"
              style={{ marginTop: 10, width: "100%" }}
              disabled={!!busy}
              onClick={() => scan(source)}
            >
              {busy === `scan:${source.source_key}` ? "采集中…" : "立即扫榜"}
            </button>
          </div>;
        })}
        <Pagination
          page={sourcesPager.page}
          pageSize={sourcesPager.pageSize}
          total={sources.length}
          onPageChange={sourcesPager.setPage}
          onPageSizeChange={sourcesPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>

      {/* ── Import section ── */}
      <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid var(--border)" }}>
        <strong style={{ fontSize: 14, display: "block", marginBottom: 4 }}>导入已有榜单文件</strong>
        <small style={{ color: "var(--text-2)" }}>支持 UTF-8 CSV、普通 JSON 数组，或浏览器/OCR 采集工件。番茄 OCR / 起点会话工件会自动保留截图、置信度和来源证据。</small>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginTop: 10 }}>
          <input
            aria-label="榜单来源标识"
            value={importSource}
            onChange={event => setImportSource(event.target.value)}
            placeholder="来源标识，例如 qidian_manual"
            className="form-input"
            style={{ width: 200 }}
          />
          <input
            aria-label="选择榜单文件"
            type="file"
            accept=".csv,.json,text/csv,application/json"
            onChange={event => void selectImportFile(event.target.files?.[0])}
            style={{ fontSize: 13 }}
          />
          <button
            className="btn-primary"
            style={{ width: "auto", padding: "0 18px", height: 38 }}
            disabled={!!busy || !importItems.length}
            onClick={() => void importRanking()}
          >
            {busy === "import" ? "导入中…" : "导入榜单"}
          </button>
        </div>
        {importFileName && (
          <small style={{ color: "var(--text-2)", display: "block", marginTop: 6 }}>
            {importFileName}：{captureArtifact ? `识别为 ${captureArtifact.source} 采集工件，状态 ${captureArtifact.status || "succeeded"}` : "已解析"}{" "}
            {importItems.length} 条，提交前不会上传。
          </small>
        )}
      </div>
    </div>

    {/* ── Analysis mode selector ── */}
    {snapshots.filter(s => s.status === "succeeded").length > 0 && (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <strong style={{ fontSize: 13 }}>分析模式：</strong>
          <div className="seg" style={{ width: "auto" }}>
            <button
              className={analysisMode === "single" ? "on" : ""}
              onClick={() => { setAnalysisMode("single"); setMultiAnalysisResult(null); }}
            >
              📋 单平台分析
            </button>
            <button
              className={analysisMode === "multi" ? "on" : ""}
              onClick={() => setAnalysisMode("multi")}
            >
              📊 多平台聚合
            </button>
          </div>
        </div>
        {analysisMode === "multi" && snapshots.filter(s => s.status === "succeeded").length >= 2 && (
          <button
            className="btn-primary"
            style={{ width: "auto", padding: "0 20px", height: 40, fontSize: 14 }}
            disabled={multiAnalysisLoading}
            onClick={() => void analyzeMultiPlatform()}
          >
            {multiAnalysisLoading ? "聚合分析中…" : "🚀 多平台聚合分析"}
          </button>
        )}
        {analysisMode === "multi" && snapshots.filter(s => s.status === "succeeded").length < 2 && (
          <small style={{ color: "var(--text-2)" }}>需要至少 2 个成功快照才能聚合分析</small>
        )}
      </div>
    </div>
    )}

    {/* ── Snapshots table ── */}
    <div className="card">
      <div className="card-head">
        <div className="card-title">
          <span>📸</span> 榜单快照
        </div>
        <span className="card-sub">{snapshots.length} 条记录</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>来源</th>
              <th>状态</th>
              <th>数量</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <div className="empty" style={{ border: "none", padding: 30 }}>
                    <p>暂无快照记录，请先扫描榜单源或导入榜单文件。</p>
                  </div>
                </td>
              </tr>
            ) : (
              snapshotsPager.pageData.map(snapshot => <React.Fragment key={snapshot.id}>
                <tr>
                  <td>{snapshot.display_name}</td>
                  <td>{statusBadge(snapshot.status, snapshot.capture_status)}</td>
                  <td>{snapshot.item_count}</td>
                  <td style={{ fontSize: 12, color: "var(--text-2)" }}>{new Date(snapshot.captured_at).toLocaleString()}</td>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      <button
                        className="btn-sm"
                        style={{ background: "var(--bg-hover)", color: "var(--text-2)" }}
                        disabled={!!busy}
                        onClick={() => void toggleSnapshot(snapshot)}
                      >
                        {openSnapshotId === snapshot.id ? "收起" : snapshot.status === "succeeded" ? "查看榜单" : "查看错误"}
                      </button>
                      {snapshot.status === "succeeded" && (
                        <button
                          className="btn-sm"
                          style={{ background: "var(--bg-hover)", color: "var(--text-2)" }}
                          disabled={!!busy}
                          onClick={() => void validateMetadata(snapshot)}
                        >
                          {busy === `validate:${snapshot.id}` ? "校验中…" : "交叉校验元数据"}
                        </button>
                      )}
                      {snapshot.status === "succeeded" && (snapshot.capture_status === "needs_review" || snapshot.capture_status === "partial") && (
                        <button
                          className="btn-sm btn-primary"
                          style={{ width: "auto" }}
                          disabled={!!busy}
                          onClick={() => void confirmCapture(snapshot)}
                        >
                          {busy === `confirm:${snapshot.id}` ? "确认中…" : "确认采集证据"}
                        </button>
                      )}
                      {snapshot.status === "succeeded" && snapshot.capture_status !== "needs_review" && snapshot.capture_status !== "partial" && (
                        <button
                          className="btn-sm"
                          style={{ background: "var(--bg-hover)", color: "var(--text-2)" }}
                          disabled={!!busy}
                          onClick={() => analyze(snapshot)}
                        >
                          生成分析与选题
                        </button>
                      )}
                      {snapshot.status === "failed" && (
                        <button
                          className="btn-sm btn-primary"
                          style={{ width: "auto" }}
                          disabled={!!busy}
                          onClick={() => retrySnapshot(snapshot)}
                        >
                          {busy === `retry:${snapshot.id}` ? "重试中…" : "重新采集"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {openSnapshotId === snapshot.id && (
                  <tr>
                    <td colSpan={5} style={{ whiteSpace: "normal", padding: "16px 20px" }}>
                      {snapshot.status === "failed" ? (
                        <div style={{ color: "var(--red)", fontSize: 13 }}>
                          <strong>失败详情：</strong>{snapshot.error || "数据源未返回可用榜单，暂无更多错误信息"}
                        </div>
                      ) : busy === `detail:${snapshot.id}` ? (
                        <small style={{ color: "var(--text-2)" }}>正在加载榜单详情…</small>
                      ) : (
                        <div>
                          <strong style={{ fontSize: 14 }}>榜单条目</strong>
                          <ol style={{ margin: "10px 0 0", paddingLeft: 24, fontSize: 13 }}>
                            {snapshotItemsPager.pageData.map(item => {
                              const collector = item.collector || item.metrics?.collector || "未记录";
                              const confidence = item.confidence ?? item.metrics?.confidence;
                              const evidence = item.evidence || item.metrics?.evidence;
                              const lowConfidence = confidence !== undefined && confidence < 0.85;
                              return <li key={item.id} style={{ marginBottom: 10, lineHeight: 1.7 }}>
                                {item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--primary-light)" }}>{item.title || "未命名作品"}</a> : (item.title || "未命名作品")}
                                <small style={{ color: "var(--text-2)" }}> · {item.author || "未知作者"}{item.category ? ` · ${item.category}` : ""}</small>
                                <div><small style={{ color: "var(--text-3)" }}>采集器：{collector} · 置信度：{confidence === undefined ? "未记录" : `${Math.round(confidence * 100)}%`} · 证据：{evidenceText(evidence)}</small></div>
                                <div><small style={{ color: "var(--text-3)" }}>元数据交叉校验：{item.metadata_status || "unvalidated"}{item.metrics?.validation ? ` · ${evidenceText(item.metrics.validation)}` : ""}</small></div>
                                {lowConfidence && <div style={{ color: "var(--red)", fontSize: 12 }}>低置信度：请人工核对原始证据后再用于市场分析。</div>}
                              </li>;
                            })}
                          </ol>
                          <Pagination
                            page={snapshotItemsPager.page}
                            pageSize={snapshotItemsPager.pageSize}
                            total={openItems.length}
                            onPageChange={snapshotItemsPager.setPage}
                            onPageSizeChange={snapshotItemsPager.setPageSize}
                            pageSizeOptions={[10, 20, 50, 100]}
                          />
                          {snapshotDetails[snapshot.id] && snapshotDetails[snapshot.id].items.length === 0 && (
                            <small style={{ color: "var(--text-2)" }}>该快照没有榜单条目</small>
                          )}
                          {snapshotDetails[snapshot.id]?.latest_analysis && (
                            <div className="card" style={{ marginTop: 14, padding: 16, background: "var(--primary-dim)", borderColor: "var(--border-strong)" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                                <strong style={{ fontSize: 14 }}>AI 市场分析</strong>
                                <span className="badge purple">{snapshotDetails[snapshot.id].latest_analysis?.analysis_mode}</span>
                              </div>
                              <p style={{ fontSize: 13, marginBottom: 8 }}>{snapshotDetails[snapshot.id].latest_analysis?.summary || "未产出摘要"}</p>
                              <p style={{ fontSize: 13, marginBottom: 4 }}><b>目标受众：</b>{snapshotDetails[snapshot.id].latest_analysis?.audience?.primary || "未产出"}</p>
                              <p style={{ fontSize: 13, marginBottom: 4 }}><b>标题模式：</b>{snapshotDetails[snapshot.id].latest_analysis?.title_patterns?.map(item => item.pattern).filter(Boolean).join("、") || "未产出"}</p>
                              <p style={{ fontSize: 13, marginBottom: 4 }}><b>开篇节奏：</b>{snapshotDetails[snapshot.id].latest_analysis?.pacing?.opening || "未产出"}</p>
                              <p style={{ fontSize: 13, marginBottom: 4 }}><b>市场信号：</b>{snapshotDetails[snapshot.id].latest_analysis?.market_signals?.map(item => item.signal).filter(Boolean).join("；") || "未产出"}</p>
                              <p style={{ fontSize: 13, marginBottom: 4 }}><b>原创约束：</b>{snapshotDetails[snapshot.id].latest_analysis?.originality_constraints?.join("；") || "未产出"}</p>
                              <small style={{ color: "var(--text-3)" }}>原创风险检查仅作辅助，不构成版权或法律结论。</small>
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>)
            )}
          </tbody>
        </table>
        <Pagination
          page={snapshotsPager.page}
          pageSize={snapshotsPager.pageSize}
          total={snapshots.length}
          onPageChange={snapshotsPager.setPage}
          onPageSizeChange={snapshotsPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>
    </div>

    {/* ── Multi-platform analysis results ── */}
    {multiAnalysisResult && (
    <div className="card">
      <div className="card-head">
        <div className="card-title">
          <span>📊</span> 多平台聚合分析结果
        </div>
        <span className="badge cyan">
          {multiAnalysisResult.succeeded_layers || 0}/{multiAnalysisResult.total_layers || 0} 层通过
        </span>
      </div>
      <div style={{ display: "grid", gap: 16 }}>

        {/* Summary card */}
        <div className="card" style={{ padding: 16, background: "var(--primary-dim)", borderColor: "var(--border-strong)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 15 }}>聚合分析摘要</strong>
            <span className="badge purple">{multiAnalysisResult.status || "unknown"}</span>
          </div>
          {multiAnalysisResult.summary && <p style={{ fontSize: 13, marginBottom: 12 }}>{multiAnalysisResult.summary}</p>}

          {/* Platform breakdown */}
          {multiAnalysisResult.platform_breakdown && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 13 }}>平台分布：</strong>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                {Object.entries(multiAnalysisResult.platform_breakdown as Record<string, number>).map(([platform, count]) => (
                  <span key={platform} className="badge cyan">{platform}: {count}本</span>
                ))}
              </div>
            </div>
          )}

          {/* Total books */}
          {multiAnalysisResult.total_books !== undefined && (
            <p style={{ fontSize: 13 }}><strong>总计分析书籍：</strong>{multiAnalysisResult.total_books} 本</p>
          )}

          {/* Top genres */}
          {multiAnalysisResult.top_genres && Array.isArray(multiAnalysisResult.top_genres) && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 13 }}>热门题材（跨平台）：</strong>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                {multiAnalysisResult.top_genres.map((g: any, i: number) => (
                  <span key={i} className="badge orange">
                    {typeof g === "string" ? g : `${g.genre || g.name}${g.count ? ` (${g.count})` : ""}`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Common selling points */}
          {multiAnalysisResult.common_selling_points && Array.isArray(multiAnalysisResult.common_selling_points) && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 13 }}>共性卖点：</strong>
              <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 13 }}>
                {multiAnalysisResult.common_selling_points.map((sp: any, i: number) => (
                  <li key={i}>{typeof sp === "string" ? sp : `${sp.point || sp.name}${sp.platforms ? ` [${sp.platforms.join(", ")}]` : ""}`}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Market signals */}
          {multiAnalysisResult.market_signals && Array.isArray(multiAnalysisResult.market_signals) && (
            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 13 }}>市场信号：</strong>
              <ul style={{ margin: "6px 0 0", paddingLeft: 20, fontSize: 13 }}>
                {multiAnalysisResult.market_signals.map((s: any, i: number) => (
                  <li key={i}>{typeof s === "string" ? s : `${s.signal || s.name}${s.evidence ? ` — ${s.evidence}` : ""}`}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Layer-by-layer results */}
        {multiAnalysisResult.layers && typeof multiAnalysisResult.layers === "object" && Object.keys(multiAnalysisResult.layers).length > 0 && (
        <details open style={{ cursor: "pointer" }}>
          <summary style={{ padding: "10px 16px", borderRadius: "var(--r-sm)", background: "var(--bg-hover)", fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
            🔍 逐层分析结果（点击展开/收起）
          </summary>
          <div style={{ display: "grid", gap: 10 }}>
            {Object.entries(multiAnalysisResult.layers as Record<string, any>).map(([layerName, layerData]) => (
              <div key={layerName} className="card" style={{ padding: 12 }}>
                <strong style={{ fontSize: 14, color: "var(--primary-light)" }}>
                  {layerName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                </strong>
                {layerData?.status && <small style={{ marginLeft: 8, color: "var(--text-2)" }}>· {layerData.status}</small>}
                {layerData?.summary && <p style={{ margin: "6px 0 0", fontSize: 13 }}>{layerData.summary}</p>}
                {layerData && typeof layerData === "object" && !layerData.summary && !layerData.status && (
                  <pre style={{ margin: "6px 0 0", fontSize: 12, color: "var(--text-2)", whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>
                    {JSON.stringify(layerData, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </details>
        )}

        {/* Heatmap / KeywordCloud */}
        {multiAnalysisResult.heatmap && (
          <details style={{ cursor: "pointer" }}>
            <summary style={{ padding: "10px 16px", borderRadius: "var(--r-sm)", background: "var(--bg-hover)", fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              🔥 热度图数据（点击展开）
            </summary>
            <pre style={{ fontSize: 12, color: "var(--text-3)", whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto", padding: 12, background: "var(--bg-muted)", borderRadius: "var(--r-sm)" }}>
              {JSON.stringify(multiAnalysisResult.heatmap, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
    )}

    {/* ── Topic pool ── */}
    <div className="card">
      <div className="card-head">
        <div className="card-title">
          <span>💡</span> 原创选题池
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className={`btn-sm ${topicTab === "all" ? "btn-primary" : ""}`}
            style={{ width: topicTab === "all" ? "auto" : "auto", background: topicTab !== "all" ? "var(--bg-hover)" : "", color: topicTab !== "all" ? "var(--text-2)" : "" }}
            onClick={() => setTopicTab("all")}
          >
            全部选题 ({topics.length})
          </button>
          <button
            className={`btn-sm ${topicTab === "bookmarked" ? "btn-primary" : ""}`}
            style={{ width: "auto", background: topicTab !== "bookmarked" ? "var(--bg-hover)" : "", color: topicTab !== "bookmarked" ? "var(--text-2)" : "" }}
            onClick={() => { setTopicTab("bookmarked"); void loadBookmarked(); }}
          >
            ⭐ 备选池 ({bookmarkedTopics.length})
          </button>
        </div>
      </div>

      {scanWarning && (
        <div style={{ padding: "8px 12px", borderRadius: "var(--r-sm)", background: "var(--warning-bg)", color: "var(--orange)", fontSize: 12, marginBottom: 12 }}>
          ⚠️ 新一轮扫描后，非备选选题将被清空。建议将心仪选题加入⭐备选池。
        </div>
      )}

      {/* Batch delete button */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, justifyContent: "flex-end" }}>
        {((topicTab === "all" && topics.length > 0) || (topicTab === "bookmarked" && bookmarkedTopics.length > 0)) && (
          <button
            disabled={busy === "batch-delete"}
            onClick={() => void batchDeleteAll()}
            className="btn-sm"
            style={{ background: "transparent", border: "1px solid var(--red)", color: "var(--red)", display: "flex", alignItems: "center", gap: 4 }}
          >
            <span>🗑</span> 全部删除
          </button>
        )}
      </div>

      <div className="grid grid-3">
        {topicsPager.pageData.map(topic => {
          const isBookmarked = (topic as any).meta?.bookmarked || false;
          return (
            <div className="card" key={topic.id} style={{ padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                <strong style={{ fontSize: 14 }}>{topic.title}</strong>
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    disabled={busy === `bookmark:${topic.id}`}
                    onClick={() => void toggleBookmark(topic)}
                    title={isBookmarked ? "已收藏" : "加入备选池"}
                    style={{
                      background: "transparent", border: `1px solid ${isBookmarked ? "var(--orange)" : "var(--border)"}`,
                      borderRadius: 4, cursor: "pointer", padding: "2px 6px", fontSize: 14, color: isBookmarked ? "var(--orange)" : "var(--text-3)",
                    }}
                  >
                    {isBookmarked ? "⭐" : "☆"}
                  </button>
                  <button
                    disabled={busy === `delete-topic:${topic.id}`}
                    onClick={() => void deleteTopic(topic)}
                    title="删除选题"
                    style={{
                      background: "transparent", border: "1px solid var(--border)",
                      borderRadius: 4, cursor: "pointer", padding: "2px 6px", fontSize: 12, color: "var(--red)",
                    }}
                  >
                    🗑
                  </button>
                </div>
              </div>
              <small style={{ color: "var(--text-2)", display: "block", marginBottom: 6 }}>
                {topic.genre} · 市场分 {topic.market_score}{isBookmarked ? " · ⭐ 已收藏" : ""}
              </small>
              <p style={{ fontSize: 13, color: "var(--text-1)", marginBottom: 8 }}>{topic.premise}</p>
              {topic.target_audience && <small style={{ color: "var(--text-2)", display: "block", marginBottom: 2 }}><b>目标受众：</b>{topic.target_audience}</small>}
              {!!topic.differentiators?.length && <small style={{ color: "var(--text-2)", display: "block", marginBottom: 2 }}><b>差异化：</b>{topic.differentiators.join("；")}</small>}
              {!!topic.market_evidence?.length && <small style={{ color: "var(--text-2)", display: "block", marginBottom: 2 }}><b>市场依据：</b>{topic.market_evidence.join("；")}</small>}
              {topic.risk && <small style={{ color: "var(--red)", display: "block", marginBottom: 2 }}><b>风险：</b>{topic.risk}</small>}
              {topic.originality_notes && <small style={{ color: "var(--text-2)", display: "block", marginBottom: 2 }}><b>原创边界：</b>{topic.originality_notes}</small>}
              <button
                className="btn-sm btn-primary"
                style={{ marginTop: 8, width: "100%" }}
                disabled={!!busy}
                onClick={() => topic.novel_id ? void onBookCreated(topic.novel_id) : void createBook(topic)}
              >
                {topic.novel_id ? "打开书库作品" : "创建作品并生成策划+首章"}
              </button>
            </div>
          );
        })}

        {/* Empty states */}
        {topicTab === "bookmarked" && !bookmarkedTopics.length && (
          <div className="empty" style={{ gridColumn: "1 / -1" }}>
            <p>备选池为空。点击 ☆ 将选题加入备选池。</p>
          </div>
        )}
        {topicTab === "all" && !topics.length && (
          <div className="empty" style={{ gridColumn: "1 / -1" }}>
            <p>暂无选题。请先扫描榜单并生成分析。</p>
          </div>
        )}
        <Pagination
          page={topicsPager.page}
          pageSize={topicsPager.pageSize}
          total={topicsView.length}
          onPageChange={topicsPager.setPage}
          onPageSizeChange={topicsPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>
    </div>
  </div>;
}
