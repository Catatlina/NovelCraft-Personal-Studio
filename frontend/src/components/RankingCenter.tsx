import React, { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";

type Wrapped<T> = { data: T };
type Source = { source_key: string; display_name: string; last_success_at?: string; last_error?: string; capture_status?: string; user_action_required?: boolean; ocr_required?: boolean };
type Snapshot = { id: string; source_key: string; display_name: string; status: string; capture_status?: string; collector?: string; confidence?: number; validation_summary?: Record<string, unknown>; item_count: number; error?: string; captured_at: string };
type Evidence = Record<string, unknown>;
type RankingItem = { id: string; rank_no: number; title: string; author?: string; category?: string; source_url?: string; metadata_status?: string; collector?: string; confidence?: number; evidence?: Evidence; metrics?: { collector?: string; confidence?: number; evidence?: Evidence; validation?: Evidence } };
type MarketAnalysis = { analysis_id: string; summary: string; status: string; analysis_mode: string; market_signals: Array<{ signal?: string; evidence?: string }>; audience: { primary?: string; needs?: string[] }; title_patterns: Array<{ pattern?: string }>; pacing: { opening?: string; retention_hooks?: string[] }; originality_constraints: string[] };
type SnapshotDetail = Snapshot & { items: RankingItem[]; latest_analysis?: MarketAnalysis | null };
type Topic = { id: string; title: string; premise: string; genre: string; market_score: number; status: string; novel_id?: string };
type ImportItem = Record<string, unknown>;

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
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [openSnapshotId, setOpenSnapshotId] = useState("");
  const [snapshotDetails, setSnapshotDetails] = useState<Record<string, SnapshotDetail>>({});
  const [importItems, setImportItems] = useState<ImportItem[]>([]);
  const [importSource, setImportSource] = useState("manual_import");
  const [importFileName, setImportFileName] = useState("");

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
    setMessage(""); setImportItems([]); setImportFileName(file?.name || "");
    if (!file) return;
    try {
      const text = await file.text();
      if (file.name.toLowerCase().endsWith(".csv")) setImportItems(parseCsv(text));
      else {
        const parsed: unknown = JSON.parse(text);
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
    if (!importItems.length) { setMessage("请先选择包含有效条目的 CSV 或 JSON 文件"); return; }
    if (!importSource.trim()) { setMessage("请填写来源标识"); return; }
    setBusy("import"); setMessage("");
    try {
      const result = await api<Wrapped<{ snapshot_id: string; item_count: number }>>(`/api/v1/ranking/import?project_id=${projectId}`, {
        method: "POST", body: JSON.stringify({ source_label: importSource.trim(), items: importItems }),
      });
      setMessage(`导入成功：${result.data.item_count} 条`); setImportItems([]); setImportFileName("");
      setOpenSnapshotId(result.data.snapshot_id || ""); await load();
    } catch (error) { setMessage(`导入失败：${errorText(error)}`); }
    finally { setBusy(""); }
  }

  async function analyze(snapshot: Snapshot) {
    setBusy(`analysis:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<MarketAnalysis>>(`/api/v1/ranking/snapshots/${snapshot.id}/analyze`, { method: "POST", body: "{}" });
      setSnapshotDetails(current => ({ ...current, [snapshot.id]: { ...(current[snapshot.id] || snapshot), items: current[snapshot.id]?.items || [], latest_analysis: result.data } as SnapshotDetail }));
      setOpenSnapshotId(snapshot.id); setMessage(result.data.summary); await load();
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
        <small>支持 UTF-8 CSV（必须包含 title 表头）或 JSON 数组；导入内容会保留为人工采集证据。</small>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          <input aria-label="榜单来源标识" value={importSource} onChange={event => setImportSource(event.target.value)} placeholder="来源标识，例如 qidian_manual" />
          <input aria-label="选择榜单文件" type="file" accept=".csv,.json,text/csv,application/json" onChange={event => void selectImportFile(event.target.files?.[0])} />
          <button className="primary" disabled={!!busy || !importItems.length} onClick={() => void importRanking()}>{busy === "import" ? "导入中…" : "导入榜单"}</button>
        </div>
        {importFileName && <small>{importFileName}：已解析 {importItems.length} 条，提交前不会上传。</small>}
      </div>
    </section>
    <section className="panel"><h2>榜单快照</h2><table><thead><tr><th>来源</th><th>状态</th><th>数量</th><th>时间</th><th>操作</th></tr></thead>
      <tbody>{snapshots.map(snapshot => <React.Fragment key={snapshot.id}>
        <tr><td>{snapshot.display_name}</td><td><span className={snapshot.status === "failed" || snapshot.capture_status === "needs_review" ? "danger-text" : ""}>{snapshot.status === "failed" ? "失败" : snapshot.capture_status === "needs_review" ? "待人工复核" : snapshot.capture_status === "partial" ? "部分成功" : "成功"}</span></td><td>{snapshot.item_count}</td><td>{new Date(snapshot.captured_at).toLocaleString()}</td><td>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button disabled={!!busy} onClick={() => void toggleSnapshot(snapshot)}>{openSnapshotId === snapshot.id ? "收起" : snapshot.status === "succeeded" ? "查看榜单" : "查看错误"}</button>
            {snapshot.status === "succeeded" && <button disabled={!!busy} onClick={() => void validateMetadata(snapshot)}>{busy === `validate:${snapshot.id}` ? "校验中…" : "交叉校验元数据"}</button>}
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
    <section className="panel"><h2>原创选题池</h2><div className="grid-cards">
      {topics.map(topic => <article className="feature-card" key={topic.id}><strong>{topic.title}</strong><small>{topic.genre} · 市场分 {topic.market_score}</small><p>{topic.premise}</p><button className="primary" disabled={!!topic.novel_id || !!busy} onClick={() => createBook(topic)}>{topic.novel_id ? "已进入书库" : "自动生成整书"}</button></article>)}
    </div></section>
  </div>;
}
