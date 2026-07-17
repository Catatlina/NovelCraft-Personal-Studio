import React, { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";

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

  return <div style={{ display: "grid", gap: 16 }}>
    {message && <div className="panel">{message}</div>}
    <section className="panel"><h2>小说榜单源</h2><div className="grid-cards">
      {sources.map(source => {
        const health = source.last_error ? "异常" : source.last_success_at ? "健康" : "未采集";
        return <article className="feature-card" key={source.source_key}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <strong>{source.display_name}</strong>
          <span className={source.last_error ? "danger-text" : ""} style={{ fontSize: 12 }}>{health}</span>
        </div>
        <small>{source.last_success_at ? `最近成功：${new Date(source.last_success_at).toLocaleString()}` : "最近成功：暂无"}</small>
        {source.capture_status && <small>采集状态：{source.capture_status}</small>}
        {source.user_action_required && <span className="danger-text">需要用户在浏览器完成验证后重新采集</span>}
        {source.ocr_required && <span>该来源需要截图/OCR 采集</span>}
        {source.last_error && <span className="danger-text">{source.last_error}</span>}
        <button className="primary" disabled={!!busy} onClick={() => scan(source)}>{busy === `scan:${source.source_key}` ? "采集中…" : "立即扫榜"}</button>
      </article>; })}
    </div>
      <div style={{ marginTop: 16, display: "grid", gap: 10 }}>
        <strong>导入已有榜单文件</strong>
        <small>支持 UTF-8 CSV、普通 JSON 数组，或浏览器/OCR 采集工件。番茄 OCR / 起点会话工件会自动保留截图、置信度和来源证据。</small>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          <input aria-label="榜单来源标识" value={importSource} onChange={event => setImportSource(event.target.value)} placeholder="来源标识，例如 qidian_manual" />
          <input aria-label="选择榜单文件" type="file" accept=".csv,.json,text/csv,application/json" onChange={event => void selectImportFile(event.target.files?.[0])} />
          <button className="primary" disabled={!!busy || !importItems.length} onClick={() => void importRanking()}>{busy === "import" ? "导入中…" : "导入榜单"}</button>
        </div>
        {importFileName && <small>{importFileName}：{captureArtifact ? `识别为 ${captureArtifact.source} 采集工件，状态 ${captureArtifact.status || "succeeded"}` : "已解析"} {importItems.length} 条，提交前不会上传。</small>}
      </div>
    </section>
    <section className="panel"><h2>榜单快照</h2><table><thead><tr><th>来源</th><th>状态</th><th>数量</th><th>时间</th><th>操作</th></tr></thead>
      <tbody>{snapshots.map(snapshot => <React.Fragment key={snapshot.id}>
        <tr><td>{snapshot.display_name}</td><td><span className={snapshot.status === "failed" || snapshot.capture_status === "needs_review" ? "danger-text" : ""}>{snapshot.status === "failed" ? "失败" : snapshot.capture_status === "needs_review" ? "待人工复核" : snapshot.capture_status === "partial" ? "部分成功" : "成功"}</span></td><td>{snapshot.item_count}</td><td>{new Date(snapshot.captured_at).toLocaleString()}</td><td>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button disabled={!!busy} onClick={() => void toggleSnapshot(snapshot)}>{openSnapshotId === snapshot.id ? "收起" : snapshot.status === "succeeded" ? "查看榜单" : "查看错误"}</button>
            {snapshot.status === "succeeded" && <button disabled={!!busy} onClick={() => void validateMetadata(snapshot)}>{busy === `validate:${snapshot.id}` ? "校验中…" : "交叉校验元数据"}</button>}
            {snapshot.status === "succeeded" && (snapshot.capture_status === "needs_review" || snapshot.capture_status === "partial") && <button className="primary" disabled={!!busy} onClick={() => void confirmCapture(snapshot)}>{busy === `confirm:${snapshot.id}` ? "确认中…" : "确认采集证据"}</button>}
            {snapshot.status === "succeeded" && snapshot.capture_status !== "needs_review" && snapshot.capture_status !== "partial" && <button disabled={!!busy} onClick={() => analyze(snapshot)}>生成分析与选题</button>}
            {snapshot.status === "failed" && <button className="primary" disabled={!!busy} onClick={() => retrySnapshot(snapshot)}>{busy === `retry:${snapshot.id}` ? "重试中…" : "重新采集"}</button>}
          </div>
        </td></tr>
        {openSnapshotId === snapshot.id && <tr><td colSpan={5}>
          {snapshot.status === "failed" ? <div className="danger-text"><strong>失败详情：</strong>{snapshot.error || "数据源未返回可用榜单，暂无更多错误信息"}</div> :
            busy === `detail:${snapshot.id}` ? <small>正在加载榜单详情…</small> :
            <div><strong>榜单前 10 条</strong>
              <ol style={{ margin: "10px 0 0", paddingLeft: 24 }}>
                {(snapshotDetails[snapshot.id]?.items || []).slice(0, 10).map(item => {
                  const collector = item.collector || item.metrics?.collector || "未记录";
                  const confidence = item.confidence ?? item.metrics?.confidence;
                  const evidence = item.evidence || item.metrics?.evidence;
                  const lowConfidence = confidence !== undefined && confidence < 0.85;
                  return <li key={item.id} style={{ marginBottom: 10 }}>
                    {item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer">{item.title || "未命名作品"}</a> : (item.title || "未命名作品")}
                    <small> · {item.author || "未知作者"}{item.category ? ` · ${item.category}` : ""}</small>
                    <div><small>采集器：{collector} · 置信度：{confidence === undefined ? "未记录" : `${Math.round(confidence * 100)}%`} · 证据：{evidenceText(evidence)}</small></div>
                    <div><small>元数据交叉校验：{item.metadata_status || "unvalidated"}{item.metrics?.validation ? ` · ${evidenceText(item.metrics.validation)}` : ""}</small></div>
                    {lowConfidence && <div className="danger-text"><small>低置信度：请人工核对原始证据后再用于市场分析。</small></div>}
                  </li>;
                })}
              </ol>
              {snapshotDetails[snapshot.id] && snapshotDetails[snapshot.id].items.length === 0 && <small>该快照没有榜单条目</small>}
              {snapshotDetails[snapshot.id]?.latest_analysis && <div className="analysis-card" style={{ marginTop: 14 }}>
                <strong>AI 市场分析</strong><small> · {snapshotDetails[snapshot.id].latest_analysis?.analysis_mode}</small>
                <p>{snapshotDetails[snapshot.id].latest_analysis?.summary || "未产出摘要"}</p>
                <p><b>目标受众：</b>{snapshotDetails[snapshot.id].latest_analysis?.audience?.primary || "未产出"}</p>
                <p><b>标题模式：</b>{snapshotDetails[snapshot.id].latest_analysis?.title_patterns?.map(item => item.pattern).filter(Boolean).join("、") || "未产出"}</p>
                <p><b>开篇节奏：</b>{snapshotDetails[snapshot.id].latest_analysis?.pacing?.opening || "未产出"}</p>
                <p><b>市场信号：</b>{snapshotDetails[snapshot.id].latest_analysis?.market_signals?.map(item => item.signal).filter(Boolean).join("；") || "未产出"}</p>
                <p><b>原创约束：</b>{snapshotDetails[snapshot.id].latest_analysis?.originality_constraints?.join("；") || "未产出"}</p>
                <small>原创风险检查仅作辅助，不构成版权或法律结论。</small>
              </div>}
            </div>}
        </td></tr>}
      </React.Fragment>)}</tbody>
    </table></section>
    <section className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>原创选题池</h2>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            style={{
              padding: "6px 14px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
              background: topicTab === "all" ? "var(--nc-primary, #FF6B35)" : "rgba(255,255,255,0.06)",
              color: topicTab === "all" ? "#fff" : "var(--text-muted)",
            }}
            onClick={() => setTopicTab("all")}
          >
            全部选题 ({topics.length})
          </button>
          <button
            style={{
              padding: "6px 14px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600,
              background: topicTab === "bookmarked" ? "var(--nc-primary, #FF6B35)" : "rgba(255,255,255,0.06)",
              color: topicTab === "bookmarked" ? "#fff" : "var(--text-muted)",
            }}
            onClick={() => { setTopicTab("bookmarked"); void loadBookmarked(); }}
          >
            ⭐ 备选池 ({bookmarkedTopics.length})
          </button>
        </div>
      </div>

      {scanWarning && (
        <div style={{ padding: "8px 12px", borderRadius: 6, background: "rgba(255,152,0,0.1)", color: "#ff9100", fontSize: 12, marginBottom: 10 }}>
          ⚠️ 新一轮扫描后，非备选选题将被清空。建议将心仪选题加入⭐备选池。
        </div>
      )}

      {/* Batch delete button */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10, justifyContent: "flex-end" }}>
        {((topicTab === "all" && topics.length > 0) || (topicTab === "bookmarked" && bookmarkedTopics.length > 0)) && (
          <button
            disabled={busy === "batch-delete"}
            onClick={() => void batchDeleteAll()}
            style={{
              padding: "6px 12px", borderRadius: 6, border: "1px solid #ff5252", background: "transparent",
              color: "#ff5252", cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 4,
            }}
          >
            <span>🗑</span> 全部删除
          </button>
        )}
      </div>

      <div className="grid-cards">
        {(topicTab === "bookmarked" ? bookmarkedTopics : topics).map(topic => {
          const isBookmarked = (topic as any).meta?.bookmarked || false;
          return (
            <article className="feature-card" key={topic.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <strong>{topic.title}</strong>
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    disabled={busy === `bookmark:${topic.id}`}
                    onClick={() => void toggleBookmark(topic)}
                    title={isBookmarked ? "已收藏" : "加入备选池"}
                    style={{
                      background: "transparent", border: `1px solid ${isBookmarked ? "#ff9100" : "rgba(255,255,255,0.12)"}`,
                      borderRadius: 4, cursor: "pointer", padding: "2px 6px", fontSize: 14, color: isBookmarked ? "#ff9100" : "#888",
                    }}
                  >
                    {isBookmarked ? "⭐" : "☆"}
                  </button>
                  <button
                    disabled={busy === `delete-topic:${topic.id}`}
                    onClick={() => void deleteTopic(topic)}
                    title="删除选题"
                    style={{
                      background: "transparent", border: "1px solid rgba(255,255,255,0.12)",
                      borderRadius: 4, cursor: "pointer", padding: "2px 6px", fontSize: 12, color: "#ff5252",
                    }}
                  >
                    🗑
                  </button>
                </div>
              </div>
              <small>{topic.genre} · 市场分 {topic.market_score}{isBookmarked ? " · ⭐ 已收藏" : ""}</small>
              <p>{topic.premise}</p>
              {topic.target_audience && <small><b>目标受众：</b>{topic.target_audience}</small>}
              {!!topic.differentiators?.length && <small><b>差异化：</b>{topic.differentiators.join("；")}</small>}
              {!!topic.market_evidence?.length && <small><b>市场依据：</b>{topic.market_evidence.join("；")}</small>}
              {topic.risk && <small className="danger-text"><b>风险：</b>{topic.risk}</small>}
              {topic.originality_notes && <small><b>原创边界：</b>{topic.originality_notes}</small>}
              <button className="primary" disabled={!!busy} onClick={() => topic.novel_id ? void onBookCreated(topic.novel_id) : void createBook(topic)}>
                {topic.novel_id ? "打开书库作品" : "创建作品并生成策划+首章"}
              </button>
            </article>
          );
        })}
        {(topicTab === "bookmarked" && !bookmarkedTopics.length) && (
          <p style={{ color: "var(--text-muted)", fontSize: 13, gridColumn: "1 / -1", textAlign: "center", padding: 20 }}>
            备选池为空。点击 ☆ 将选题加入备选池。
          </p>
        )}
        {(topicTab === "all" && !topics.length) && (
          <p style={{ color: "var(--text-muted)", fontSize: 13, gridColumn: "1 / -1", textAlign: "center", padding: 20 }}>
            暂无选题。请先扫描榜单并生成分析。
          </p>
        )}
      </div>
    </section>
  </div>;
}
