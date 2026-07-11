import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

type Book = { id: string; title: string; status: string; meta: Record<string, any>; updated_at: string };
type Batch = { id: string; status: string; completed_count: number; requested_count: number; error?: string };
type Wrapped<T> = { data: T };

export function BookLibrary({ projectId, onOpen }: { projectId: string; onOpen: (bookId: string) => Promise<void> }) {
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [batchCount, setBatchCount] = useState(5);
  const [batches, setBatches] = useState<Record<string, Batch>>({});
  const pollers = useRef<Record<string, number>>({});

  useEffect(() => {
    setBooks([]); setError("");
    api<Wrapped<Book[]>>(`/api/v1/ranking/library/books?project_id=${projectId}`).then(result => { setBooks(result.data); setError(""); }).catch(caught => setError(String(caught)));
    return () => { Object.values(pollers.current).forEach(id => window.clearInterval(id)); pollers.current = {}; };
  }, [projectId]);

  const pollBatch = (bookId: string, batchId: string) => {
    if (pollers.current[batchId]) return;
    pollers.current[batchId] = window.setInterval(async () => {
      try {
        const result = await api<Wrapped<Batch>>(`/api/v1/generation-batches/${batchId}`);
        setBatches(prev => ({ ...prev, [bookId]: result.data }));
        if (["succeeded", "failed", "cancelled", "pending_provider"].includes(result.data.status)) {
          window.clearInterval(pollers.current[batchId]); delete pollers.current[batchId];
        }
      } catch { window.clearInterval(pollers.current[batchId]); delete pollers.current[batchId]; }
    }, 3000);
  };

  const continueOne = async (book: Book) => {
    setBusy(book.id); setNotice("");
    try {
      await api(`/api/v1/novels/${book.id}/continue`, { method: "POST" });
      setNotice(`《${book.title}》已派发续写任务`);
    } catch (caught) { setNotice(`续写失败：${String(caught)}`); } finally { setBusy(""); }
  };

  const startBatch = async (book: Book) => {
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<{ batch_id: string }>>(`/api/v1/novels/${book.id}/chapters/batch`, {
        method: "POST", body: JSON.stringify({ chapter_count: batchCount }),
      });
      setBatches(prev => ({ ...prev, [book.id]: { id: result.data.batch_id, status: "pending", completed_count: 0, requested_count: batchCount } }));
      pollBatch(book.id, result.data.batch_id);
    } catch (caught) { setNotice(`批量生成失败：${String(caught)}`); } finally { setBusy(""); }
  };

  const resumeBatch = async (book: Book, batch: Batch) => {
    setBusy(book.id); setNotice("");
    try {
      await api(`/api/v1/generation-batches/${batch.id}/resume`, { method: "POST" });
      setBatches(prev => ({ ...prev, [book.id]: { ...batch, status: "pending" } }));
      pollBatch(book.id, batch.id);
    } catch (caught) { setNotice(`恢复失败：${String(caught)}`); } finally { setBusy(""); }
  };

  const exportBook = async (book: Book, format: "txt" | "markdown") => {
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<{ status: string; content?: string; message?: string }>>(`/api/v1/novels/${book.id}/export/${format}`);
      if (result.data.status !== "ok" || !result.data.content) { setNotice(`导出失败：${result.data.message || "无内容"}`); return; }
      const blob = new Blob([result.data.content], { type: "text/plain;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${book.title}.${format === "txt" ? "txt" : "md"}`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (caught) { setNotice(`导出失败：${String(caught)}`); } finally { setBusy(""); }
  };

  return <section className="panel"><h2>统一书库</h2>{error && <div className="error">{error}</div>}
    {notice && <div className="muted">{notice}</div>}
    <label className="muted">批量章节数 <input type="number" min={1} max={50} value={batchCount}
      onChange={event => setBatchCount(Math.max(1, Math.min(50, Number(event.target.value) || 1)))} style={{ width: "4em" }} /></label>
    <div className="grid-cards">{books.map(book => {
      const batch = batches[book.id];
      return <article className="feature-card" key={book.id}>
        <strong>{book.title}</strong><small>{book.status} · {book.meta?.source_type || "inspiration"}</small>
        <p>{book.meta?.idea || "暂无简介"}</p>
        {batch && <p className="muted">批次 {batch.status}：{batch.completed_count}/{batch.requested_count}
          {batch.error ? ` — ${batch.error}` : ""}</p>}
        <div className="row-actions">
          <button onClick={() => void onOpen(book.id)}>打开小说</button>
          <button disabled={busy === book.id} onClick={() => void continueOne(book)}>续写一章</button>
          <button disabled={busy === book.id} onClick={() => void startBatch(book)}>批量生成</button>
          {batch && ["failed", "pending_provider"].includes(batch.status) &&
            <button disabled={busy === book.id} onClick={() => void resumeBatch(book, batch)}>恢复批次</button>}
          <button disabled={busy === book.id} onClick={() => void exportBook(book, "txt")}>导出TXT</button>
          <button disabled={busy === book.id} onClick={() => void exportBook(book, "markdown")}>导出MD</button>
        </div>
      </article>;
    })}</div>
    {!books.length && !error && <p className="muted">书库为空。可以从扫榜中心或灵感入口创建小说。</p>}
  </section>;
}
