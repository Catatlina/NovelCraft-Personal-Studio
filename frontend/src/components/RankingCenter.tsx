import React, { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";

type Wrapped<T> = { data: T };
type Source = { source_key: string; display_name: string; last_success_at?: string; last_error?: string };
type Snapshot = { id: string; source_key: string; display_name: string; status: string; item_count: number; error?: string; captured_at: string };
type Topic = { id: string; title: string; premise: string; genre: string; market_score: number; status: string; novel_id?: string };

function errorText(error: unknown): string {
  if (error instanceof ApiError) return JSON.stringify(error.payload);
  return String(error);
}

export function RankingCenter({ projectId, onBookCreated }: { projectId: string; onBookCreated: (novelId: string, runId?: string) => Promise<void> }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

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

  async function analyze(snapshot: Snapshot) {
    setBusy(`analysis:${snapshot.id}`); setMessage("");
    try {
      const result = await api<Wrapped<{ summary: string }>>(`/api/v1/ranking/snapshots/${snapshot.id}/analyze`, { method: "POST", body: "{}" });
      setMessage(result.data.summary); await load();
    } catch (error) { setMessage(`分析失败：${errorText(error)}`); }
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
      {sources.map(source => <article className="feature-card" key={source.source_key}>
        <strong>{source.display_name}</strong>
        <small>{source.last_success_at ? `最近成功 ${new Date(source.last_success_at).toLocaleString()}` : "尚未成功采集"}</small>
        {source.last_error && <span className="danger-text">{source.last_error}</span>}
        <button className="primary" disabled={!!busy} onClick={() => scan(source)}>{busy === `scan:${source.source_key}` ? "采集中…" : "立即扫榜"}</button>
      </article>)}
    </div></section>
    <section className="panel"><h2>榜单快照</h2><table><thead><tr><th>来源</th><th>状态</th><th>数量</th><th>时间</th><th /></tr></thead>
      <tbody>{snapshots.map(snapshot => <tr key={snapshot.id}><td>{snapshot.display_name}</td><td>{snapshot.status}</td><td>{snapshot.item_count}</td><td>{new Date(snapshot.captured_at).toLocaleString()}</td><td><button disabled={snapshot.status !== "succeeded" || !!busy} onClick={() => analyze(snapshot)}>生成分析与选题</button></td></tr>)}</tbody>
    </table></section>
    <section className="panel"><h2>原创选题池</h2><div className="grid-cards">
      {topics.map(topic => <article className="feature-card" key={topic.id}><strong>{topic.title}</strong><small>{topic.genre} · 市场分 {topic.market_score}</small><p>{topic.premise}</p><button className="primary" disabled={!!topic.novel_id || !!busy} onClick={() => createBook(topic)}>{topic.novel_id ? "已进入书库" : "自动生成整书"}</button></article>)}
    </div></section>
  </div>;
}
