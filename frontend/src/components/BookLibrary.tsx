import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

type Book = { id: string; title: string; status: string; meta: Record<string, any>; updated_at: string };

export function BookLibrary({ projectId, onOpen }: { projectId: string; onOpen: (bookId: string) => Promise<void> }) {
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    setBooks([]); setError("");
    api<{ data: Book[] }>(`/api/v1/ranking/library/books?project_id=${projectId}`).then(result => { setBooks(result.data); setError(""); }).catch(caught => setError(String(caught)));
  }, [projectId]);
  return <section className="panel"><h2>统一书库</h2>{error && <div className="error">{error}</div>}
    <div className="grid-cards">{books.map(book => <article className="feature-card" key={book.id}>
      <strong>{book.title}</strong><small>{book.status} · {book.meta?.source_type || "inspiration"}</small>
      <p>{book.meta?.idea || "暂无简介"}</p><button onClick={() => void onOpen(book.id)}>打开小说</button>
    </article>)}</div>
    {!books.length && !error && <p className="muted">书库为空。可以从扫榜中心或灵感入口创建小说。</p>}
  </section>;
}
