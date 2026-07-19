import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Search, BookOpen, ArrowLeft, Trash2 } from "lucide-react";

type Book = { id: string; title: string; status: string; meta: Record<string, any>; created_at: string; updated_at: string; synopsis?: string; genre?: string; latest_chapter_title?: string; latest_chapter_seq?: number; total_words?: number; chapter_count?: number };
type BookDetail = { book: Book; synopsis: string; genre: string; outline: unknown; latest_chapter?: any; chapters: any[]; total_words: number };
type Batch = { id: string; status: string; completed_count: number; requested_count: number; error?: string; blocker_code?: string; cancel_requested?: boolean; updated_at?: string };
type Completion = { total_chapters: number; reviewed_chapters: number; total_words: number; average_review_score: number; generation_percent?: number | null; review_percent?: number; continuity_flagged?: number; continuity_unchecked?: number; needs_rewrite_chapters?: number; quality_warnings?: string[]; ready_for_release?: boolean; exportable: boolean };
type ImportPreview = { seq: string; title: string; raw: string };
type Wrapped<T> = { data: T };

function formatBookOutline(outline: unknown): string {
  if (typeof outline === "string") return outline.trim();
  if (!outline || typeof outline !== "object") return "";

  const blueprint = outline as { volume_plan?: any[]; chapter_outlines?: any[] };
  const sections: string[] = [];
  if (Array.isArray(blueprint.volume_plan) && blueprint.volume_plan.length) {
    const volumes = blueprint.volume_plan.map((volume, index) => {
      const number = volume.number ?? index + 1;
      const chapterRange = volume.start_chapter && volume.end_chapter
        ? `（第${volume.start_chapter}-${volume.end_chapter}章）`
        : "";
      return [
        `第${number}卷 ${volume.title || "未命名"}${chapterRange}`,
        volume.arc ? `主线：${volume.arc}` : "",
        volume.climax ? `高潮：${volume.climax}` : "",
        volume.hook ? `卷末钩子：${volume.hook}` : "",
      ].filter(Boolean).join("\n");
    });
    sections.push(`【分卷规划】\n${volumes.join("\n\n")}`);
  }
  if (Array.isArray(blueprint.chapter_outlines) && blueprint.chapter_outlines.length) {
    const chapters = blueprint.chapter_outlines.map((chapter, index) => {
      const seq = chapter.seq ?? index + 1;
      const beats = Array.isArray(chapter.beats) && chapter.beats.length
        ? `\n节拍：${chapter.beats.join(" → ")}`
        : "";
      return `第${seq}章 ${chapter.title || "未命名"}\n${chapter.outline || ""}${beats}`.trim();
    });
    sections.push(`【逐章细纲】\n${chapters.join("\n\n")}`);
  }
  return sections.join("\n\n") || JSON.stringify(outline, null, 2);
}

export function BookLibrary({ projectId, onOpen }: { projectId: string; onOpen: (bookId: string) => Promise<void> }) {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [batchCount, setBatchCount] = useState(5);
  const [batches, setBatches] = useState<Record<string, Batch>>({});
  const [completions, setCompletions] = useState<Record<string, Completion>>({});
  const [importBookId, setImportBookId] = useState("");
  const [directoryText, setDirectoryText] = useState("");
  const [detail, setDetail] = useState<BookDetail | null>(null);
  const [rejectingChapterId, setRejectingChapterId] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  // NC-LIB-002: search, filter, sort, pagination
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState<"created" | "updated" | "title" | "chapters">("created");
  const [page, setPage] = useState(0);
  // V2.0: Delete functionality
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [selectedBooks, setSelectedBooks] = useState<Set<string>>(new Set());
  const PAGE_SIZE = 10;
  const pollers = useRef<Record<string, number>>({});

  const loadBookState = async (book: Book) => {
    const [completionResult, batchesResult] = await Promise.allSettled([
      api<Wrapped<Completion>>(`/api/v1/novels/${book.id}/completion`),
      api<Wrapped<Batch[] | { items?: Batch[]; data?: Batch[] }>>(`/api/v1/novels/${book.id}/generation-batches`),
    ]);
    if (completionResult.status === "fulfilled") setCompletions(previous => ({ ...previous, [book.id]: completionResult.value.data }));
    if (batchesResult.status === "fulfilled") {
      const payload = batchesResult.value.data;
      const items = Array.isArray(payload) ? payload : payload.items || payload.data || [];
      const latest = items[0];
      if (latest) {
        setBatches(previous => ({ ...previous, [book.id]: latest }));
        if (["pending", "running"].includes(latest.status)) pollBatch(book.id, latest.id);
      }
    }
  };

  const openDetail = async (book: Book) => {
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<BookDetail>>(`/api/v1/library/books/${book.id}`);
      setDetail(result.data);
    } catch (caught) {
      setNotice(`详情加载失败：${String(caught)}`);
    } finally {
      setBusy("");
    }
  };

  useEffect(() => {
    setBooks([]); setError(""); setLoading(true);
    api<Wrapped<Book[]>>(`/api/v1/library/books?project_id=${projectId}`).then(result => {
      setBooks(result.data); setError(""); result.data.forEach(book => void loadBookState(book));
    }).catch(caught => setError(String(caught))).finally(() => setLoading(false));
    return () => { Object.values(pollers.current).forEach(id => window.clearInterval(id)); pollers.current = {}; };
  }, [projectId]);

  const pollBatch = (bookId: string, batchId: string) => {
    if (pollers.current[batchId]) return;
    pollers.current[batchId] = window.setInterval(async () => {
      try {
        const result = await api<Wrapped<Batch>>(`/api/v1/generation-batches/${batchId}`);
        setBatches(prev => ({ ...prev, [bookId]: result.data }));
        if (["succeeded", "failed", "cancelled"].includes(result.data.status)) {
          window.clearInterval(pollers.current[batchId]); delete pollers.current[batchId];
          const book = books.find(item => item.id === bookId);
          if (book) void loadBookState(book);
        }
      } catch (caught) {
        window.clearInterval(pollers.current[batchId]); delete pollers.current[batchId];
        setNotice(`批次状态刷新失败：${String(caught)}。请刷新书库重试。`);
      }
    }, 3000);
  };

  const continueOne = async (book: Book) => {
    setBusy(book.id); setNotice("");
    try {
      await api(`/api/v1/novels/${book.id}/continue`, { method: "POST" });
      setNotice(`${book.title} 已派发续写任务`);
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

  const cancelBatch = async (book: Book, batch: Batch) => {
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<{ status: string }>>(`/api/v1/generation-batches/${batch.id}/cancel`, { method: "POST", body: "{}" });
      setBatches(previous => ({ ...previous, [book.id]: { ...batch, status: result.data.status, cancel_requested: true } }));
      if (pollers.current[batch.id]) { window.clearInterval(pollers.current[batch.id]); delete pollers.current[batch.id]; }
      setNotice(`《${book.title}》批次已请求取消。`);
    } catch (caught) { setNotice(`取消失败：${String(caught)}`); } finally { setBusy(""); }
  };

  const importPreview: ImportPreview[] = directoryText.split(/\r?\n/).flatMap(raw => {
    const line = raw.trim();
    const match = line.match(/^第([一二三四五六七八九十百千\d]+)章\s*(.+)$/i)
      || line.match(/^Chapter\s+(\d+)[:：]\s*(.+)$/i)
      || line.match(/^(\d+)[.、\s]+(.+)$/);
    return match ? [{ seq: match[1], title: match[2].trim(), raw: line }] : [];
  });

  const importDirectory = async (book: Book) => {
    if (!importPreview.length) { setNotice("没有识别到章节目录，请使用“第1章 标题”等格式。"); return; }
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<{ imported?: number; count?: number; skipped?: number }>>(`/api/v1/novels/${book.id}/import-chapters`, {
        method: "POST", body: JSON.stringify({ text: directoryText }),
      });
      setNotice(`目录导入完成：新增 ${result.data.imported ?? result.data.count ?? 0} 章，跳过 ${result.data.skipped ?? 0} 章。`);
      setDirectoryText(""); setImportBookId(""); await loadBookState(book);
    } catch (caught) { setNotice(`目录导入失败：${String(caught)}`); } finally { setBusy(""); }
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

  // V2.0: Delete book
  const deleteBook = async (book: Book) => {
    setBusy(book.id); setNotice("");
    try {
      const result = await api<Wrapped<{ deleted_book_id: string; deleted_chapters: number }>>(
        `/api/v1/library/books/${book.id}`, { method: "DELETE" });
      setNotice(`已删除《${book.title}》（含 ${result.data.deleted_chapters} 个章节）。`);
      setBooks(prev => prev.filter(b => b.id !== book.id));
      setSelectedBooks(prev => { const next = new Set(prev); next.delete(book.id); return next; });
    } catch (caught) { setNotice(`删除失败：${String(caught)}`); }
    finally { setBusy(""); setDeleteConfirm(null); }
  };

  const batchDelete = async () => {
    if (!selectedBooks.size) return;
    setBusy("batch"); setNotice("");
    try {
      const ids = [...selectedBooks];
      await api(`/api/v1/library/books/batch-delete`, {
        method: "POST", body: JSON.stringify({ ids }),
      });
      setNotice(`已批量删除 ${ids.length} 本书。`);
      setBooks(prev => prev.filter(b => !selectedBooks.has(b.id)));
      setSelectedBooks(new Set());
    } catch (caught) { setNotice(`批量删除失败：${String(caught)}`); }
    finally { setBusy(""); }
  };

  const manualReviewChapter = async (chapter: any, decision: "approve" | "reject", reason = "") => {
    if (!detail) return;
    if (decision === "reject" && !reason.trim()) return;
    setBusy(chapter.id); setNotice("");
    try {
      const result = await api<Wrapped<{ status: string; task_id?: string }>>(`/api/v1/chapters/${chapter.id}/manual-review`, {
        method: "POST",
        body: JSON.stringify({ decision, reason }),
      });
      setNotice(decision === "approve"
        ? `《${chapter.title}》已通过人工审核并入库。`
        : `《${chapter.title}》已拒绝，正在重新生成。任务 ${result.data.task_id || ""}`);
      if (decision === "reject") {
        setRejectingChapterId("");
        setRejectReason("");
      }
      await openDetail(detail.book);
      await loadBookState(detail.book);
    } catch (caught) {
      setNotice(`${decision === "approve" ? "通过" : "拒绝"}失败：${String(caught)}`);
    } finally {
      setBusy("");
    }
  };

  // NC-LIB-002: Apply filters client-side
  const filtered = books.filter(b => {
    if (search && !b.title.includes(search) && !(b.meta?.idea || "").includes(search)) return false;
    if (statusFilter && b.status !== statusFilter) return false;
    return true;
  }).sort((a, b) => {
    if (sortBy === "title") return a.title.localeCompare(b.title);
    if (sortBy === "updated") return new Date(b.updated_at || b.created_at || "").getTime() - new Date(a.updated_at || a.created_at || "").getTime();
    if (sortBy === "chapters") return (b.chapter_count || completions[b.id]?.total_chapters || 0) - (a.chapter_count || completions[a.id]?.total_chapters || 0);
    return new Date(b.created_at || "").getTime() - new Date(a.created_at || "").getTime();
  });
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  if (detail) {
    const book = detail.book;
    const outline = formatBookOutline(detail.outline || book.meta?.outline || {
      volume_plan: book.meta?.volume_plan,
      chapter_outlines: book.meta?.chapter_outlines,
    });
    return <section className="panel book-detail">
      <button onClick={() => setDetail(null)}><ArrowLeft size={14} />返回书库</button>
      {notice && <div className="muted" role="status">{notice}</div>}
      <div className="book-detail-head">
        <div>
          <h2>{book.title}</h2>
          <p className="muted">{detail.genre} · 创建于 {new Date(book.created_at).toLocaleString()} · {detail.total_words || 0} 字</p>
        </div>
        <button className="primary" onClick={() => void onOpen(book.id)}><BookOpen size={14} />进入编辑</button>
      </div>
      <div className="book-detail-grid">
        <section>
          <h3>简介</h3>
          <p>{detail.synopsis || "暂无简介"}</p>
        </section>
        <section>
          <h3>最新章节</h3>
          <p>{detail.latest_chapter?.title || "暂无章节"}</p>
        </section>
      </div>
      {(book.meta?.creative_bible || book.meta?.source_facts?.length) && <section>
        <h3>创作拆解</h3>
        {Array.isArray(book.meta?.source_facts) && book.meta.source_facts.length > 0 && <>
          <h4>不可变事实</h4>
          <ul>{book.meta.source_facts.map((fact: string, index: number) => <li key={index}>{fact}</li>)}</ul>
        </>}
        {book.meta?.creative_bible && <>
          <h4>创作圣经</h4>
          <pre className="outline-block">{book.meta.creative_bible}</pre>
        </>}
      </section>}
      <section>
        <h3>大纲</h3>
        <pre className="outline-block">{outline || "暂无大纲"}</pre>
      </section>
      <section>
        <h3>全部章节</h3>
        <div className="chapter-list">
          {detail.chapters.map(ch => <div key={ch.id}>
            <div className="chapter-review-row">
              <button onClick={() => void onOpen(book.id)}>
                第{ch.seq || ch.meta?.seq || "-"}章 {ch.title}
                <small>{ch.status}{ch.meta?.review_score ? ` · AI分 ${Math.round(ch.meta.review_score)}` : ""}</small>
              </button>
              <div className="chapter-review-actions">
                {ch.status !== "reviewed" && <button disabled={busy === ch.id} className="primary" onClick={() => void manualReviewChapter(ch, "approve")}>通过入库</button>}
                {ch.status !== "reviewed" && <button disabled={busy === ch.id} onClick={() => {
                  setRejectingChapterId(ch.id);
                  setRejectReason("质量不达标，请增强场景冲突、生活质感、人物连续性和章末钩子，重写后正文不得低于3000字。");
                }}>拒绝重写</button>}
                {ch.status === "reviewed" && <span className="pill succeeded">已入库</span>}
              </div>
            </div>
            {rejectingChapterId === ch.id && <div className="review-reject-form">
              <label htmlFor={`reject-reason-${ch.id}`}>拒绝原因（将原样交给 AI 重写）</label>
              <textarea id={`reject-reason-${ch.id}`} rows={4} maxLength={2000} value={rejectReason}
                onChange={event => setRejectReason(event.target.value)} />
              <small>{rejectReason.trim().length}/2000 字</small>
              <div className="row-actions">
                <button onClick={() => { setRejectingChapterId(""); setRejectReason(""); }}>取消</button>
                <button className="primary" disabled={busy === ch.id || !rejectReason.trim()}
                  onClick={() => void manualReviewChapter(ch, "reject", rejectReason)}>
                  {busy === ch.id ? "提交中…" : "确认拒绝并重写"}
                </button>
              </div>
            </div>}
          </div>)}
          {!detail.chapters.length && <p className="muted">暂无章节。</p>}
        </div>
      </section>
    </section>;
  }

  return <section className="panel">
    <div className="page-head">
      <div>
        <h1>统一书库</h1>
        <p>{filtered.length} 本 · {books.length} 本总计</p>
      </div>
      <div className="head-actions">
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-2)" }}>
          批次章节数
          <input type="number" min={1} max={50} value={batchCount}
            onChange={event => setBatchCount(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
            className="form-input" style={{ width: 64, height: 34, padding: "0 8px" }} />
        </label>
        {selectedBooks.size > 0 && <button className="btn-sm" style={{ background: "var(--red)", color: "var(--brand-foreground)" }} disabled={busy === "batch"} onClick={() => void batchDelete()}>
          <Trash2 size={14} />批量删除 ({selectedBooks.size})
        </button>}
      </div>
    </div>
    {error && <div className="badge red" style={{ marginBottom: 12 }}>{error}</div>}
    {notice && <div className="badge gray" style={{ marginBottom: 12 }}>{notice}</div>}
    {/* NC-LIB-002: Search + filter + sort toolbar */}
    <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
      <div className="search-box" style={{ flex: 1, maxWidth: 400 }}>
        <Search size={14} /><input placeholder="搜索书名或简介…" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} />
      </div>
      <select className="form-input" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(0); }} style={{ width: 120, height: 38 }}>
        <option value="">全部状态</option>
        <option value="draft">📄 draft</option>
        <option value="planning">📋 planning</option>
        <option value="generated">⚡ generated</option>
        <option value="completed">✅ completed</option>
      </select>
      <select className="form-input" value={sortBy} onChange={e => setSortBy(e.target.value as any)} style={{ width: 120, height: 38 }}>
        <option value="created">最新创建</option>
        <option value="updated">最近编辑</option>
        <option value="title">按书名</option>
        <option value="chapters">按章节数</option>
      </select>
    </div>
    {!loading && !books.length && !error ? <div className="empty">
      <div className="empty-ic"><BookOpen size={26} /></div>
      <h3>书库为空</h3>
      <p>可以从扫榜中心或灵感入口创建小说，开始你的创作之旅。</p>
    </div> : <>
      <div className="grid grid-3">{paged.map((book, index) => {
        const batch = batches[book.id];
        const completion = completions[book.id];
        const rank = page * PAGE_SIZE + index + 1;
        const badgeClass = book.status === "draft" ? "gray" : book.status === "planning" ? "cyan" : book.status === "generated" ? "purple" : book.status === "completed" ? "green" : "gray";
        return <div className="card" key={book.id}>
          <div className="card-head">
            <div className="card-title" style={{ gap: 6 }}>
              <input type="checkbox" checked={selectedBooks.has(book.id)}
                onChange={() => setSelectedBooks(prev => {
                  const next = new Set(prev);
                  next.has(book.id) ? next.delete(book.id) : next.add(book.id);
                  return next;
                })} title="选择批量删除" />
              <span>{rank}. {book.title}</span>
            </div>
            <span className={`badge ${badgeClass}`}>{book.status}</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 10, lineHeight: 1.5 }}>{book.synopsis || book.meta?.idea || "暂无简介"}</p>
          <div className="card-sub" style={{ marginBottom: 8 }}>
            {book.genre || book.meta?.genre || "未分类"} · 创建 {new Date(book.created_at).toLocaleDateString()} · {book.total_words ?? completion?.total_words ?? 0} 字
          </div>
          {completion ? <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8, lineHeight: 1.7 }}>
            <div>章节 {book.chapter_count ?? completion.total_chapters} · 已审核 {completion.reviewed_chapters}</div>
            <div>生成进度 {completion.generation_percent ?? "目标未设置"}{completion.generation_percent !== null && completion.generation_percent !== undefined ? "%" : ""} · 审核覆盖 {completion.review_percent ?? 0}% · 平均分 {completion.average_review_score || "暂无"}</div>
            {(completion.quality_warnings || []).length > 0 && <div style={{ color: "var(--red)", fontWeight: 500 }}>⚠ 质量警告：{completion.quality_warnings?.join("；")}</div>}
            {!completion.ready_for_release && completion.total_chapters > 0 && <div>当前仅表示章节已生成，不代表质量验收或整书完成。</div>}
          </div> : <div className="card-sub" style={{ marginBottom: 8 }}>正在加载章节完成度与质量状态…</div>}
          {batch && <div style={{ fontSize: 12, marginBottom: 8, lineHeight: 1.5 }}>
            {batch.status === "failed" ? <span className="badge red">批次失败</span> : batch.status === "succeeded" ? <span className="badge green">批次完成</span> : <span className="badge orange">批次 {batch.status}</span>}
            <span style={{ color: "var(--text-3)", marginLeft: 6 }}>{batch.completed_count}/{batch.requested_count}</span>
            {batch.cancel_requested ? <span style={{ color: "var(--orange)", marginLeft: 6 }}>· 已请求取消</span> : ""}
            {batch.blocker_code ? <span style={{ color: "var(--text-3)", marginLeft: 6 }}>· {batch.blocker_code}</span> : ""}
            {batch.error && <div style={{ color: "var(--red)", fontSize: 11, marginTop: 3 }}>{batch.error}</div>}
            {batch.status === "succeeded" && <div style={{ color: "var(--text-3)", fontSize: 11, marginTop: 3 }}>生成批次已结束，请继续核对审核覆盖和连续性风险。</div>}
          </div>}
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 4 }}>
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} onClick={() => void openDetail(book)}>查看详情</button>
            <button className="btn-sm" style={{ background: "var(--primary-dim)", color: "var(--primary-light)" }} onClick={() => void onOpen(book.id)}>进入编辑</button>
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} disabled={busy === book.id} onClick={() => void continueOne(book)}>续写一章</button>
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} disabled={busy === book.id} onClick={() => void startBatch(book)}>批量生成</button>
            {batch && ["pending", "running"].includes(batch.status) &&
              <button className="btn-sm" style={{ background: "var(--danger-bg)", color: "var(--red)" }} disabled={busy === book.id} onClick={() => void cancelBatch(book, batch)}>取消批次</button>}
            {batch && batch.status === "failed" &&
              <button className="btn-sm" style={{ background: "var(--warning-bg)", color: "var(--orange)" }} disabled={busy === book.id} onClick={() => void resumeBatch(book, batch)}>恢复批次</button>}
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} disabled={busy === book.id} onClick={() => { setImportBookId(importBookId === book.id ? "" : book.id); setDirectoryText(""); }}>导入目录</button>
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} disabled={busy === book.id || !completion?.exportable} title={!completion?.exportable ? "至少生成或导入一章后才能导出" : undefined} onClick={() => void exportBook(book, "txt")}>导出TXT</button>
            <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)", border: "1px solid var(--border)" }} disabled={busy === book.id || !completion?.exportable} title={!completion?.exportable ? "至少生成或导入一章后才能导出" : undefined} onClick={() => void exportBook(book, "markdown")}>导出MD</button>
            <button className="btn-sm" style={{ background: "var(--danger-bg)", color: "var(--red)" }} disabled={busy === book.id} onClick={() => setDeleteConfirm(book.id)} title="删除此书及全部章节">
              <Trash2 size={14} />
            </button>
          </div>
          {importBookId === book.id && <div style={{ marginTop: 14, padding: 14, background: "var(--bg)", borderRadius: "var(--r-sm)", border: "1px solid var(--border)" }}>
            <strong style={{ fontSize: 13 }}>章节目录预览</strong>
            <small style={{ display: "block", color: "var(--text-3)", marginTop: 4 }}>粘贴 TXT 目录；预览不会写入，点击确认后才创建空白计划章节。重复标题由后端跳过。</small>
            <textarea className="form-input" rows={5} value={directoryText} onChange={event => setDirectoryText(event.target.value)} placeholder={"第1章 初入异界\n第2章 规则觉醒"} style={{ marginTop: 8 }} />
            <small style={{ display: "block", color: "var(--text-3)", marginTop: 4 }}>识别 {importPreview.length} 条{directoryText.trim() && !importPreview.length ? "；当前格式无法识别" : ""}</small>
            {importPreview.length > 0 && <ol style={{ maxHeight: 120, overflow: "auto", margin: "6px 0", paddingLeft: 24, fontSize: 12, color: "var(--text-2)" }}>
              {importPreview.slice(0, 20).map((chapter, i) => <li key={`${chapter.raw}:${i}`}>第{chapter.seq}章 {chapter.title}</li>)}
            </ol>}
            {importPreview.length > 20 && <small style={{ display: "block", color: "var(--text-3)" }}>仅预览前 20 条，确认时提交全部 {importPreview.length} 条。</small>}
            <button className="btn-sm" style={{ background: "var(--primary-dim)", color: "var(--primary-light)", marginTop: 8 }} disabled={busy === book.id || !importPreview.length} onClick={() => void importDirectory(book)}>{busy === book.id ? "导入中…" : `确认导入 ${importPreview.length} 条`}</button>
          </div>}
        </div>;
      })}</div>
      {/* NC-LIB-002: Pagination */}
      {totalPages > 1 && <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "center", marginTop: 20 }}>
        <button className="btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>上一页</button>
        <span style={{ fontSize: 13, color: "var(--text-2)" }}>{page + 1} / {totalPages} (共 {filtered.length} 本)</span>
        <button className="btn-ghost" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>下一页</button>
      </div>}
    </>}
    {loading && <p style={{ color: "var(--text-3)", textAlign: "center", padding: 20 }}>正在加载书库…</p>}
    {/* V2.0: Delete confirmation modal */}
    {deleteConfirm && <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
      onClick={() => setDeleteConfirm(null)}>
      <div className="card" onClick={e => e.stopPropagation()} style={{ maxWidth: 400, width: "90%", padding: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>确认删除</h3>
        <p style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 16 }}>确定删除《{books.find(b => b.id === deleteConfirm)?.title || "未知"}》？此操作将同时删除该书所有章节和知识条目，不可撤销。</p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn-ghost" onClick={() => setDeleteConfirm(null)}>取消</button>
          <button className="btn-sm" style={{ background: "var(--red)", color: "var(--brand-foreground)" }} disabled={busy === deleteConfirm}
            onClick={() => { const book = books.find(b => b.id === deleteConfirm); if (book) deleteBook(book); }}>
            {busy === deleteConfirm ? "删除中…" : "确认删除"}
          </button>
        </div>
      </div>
    </div>}
  </section>;
}
