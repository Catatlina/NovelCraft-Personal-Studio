import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, CircleAlert, Compass, UsersRound } from "lucide-react";
import { api } from "../lib/api";

type ContextPayload = {
  source?: string;
  chapter?: { title?: string; seq?: number; text?: string } | null;
  previous_chapter?: { title?: string; seq?: number } | null;
  next_chapter?: { title?: string; seq?: number } | null;
  characters?: Array<{ id?: string; title?: string; body?: string; approved?: boolean; source?: string }>;
  plot?: Array<{ id?: string; title?: string; body?: string; approved?: boolean; source?: string }>;
  worldview?: Array<{ id?: string; title?: string; body?: string; approved?: boolean; source?: string }>;
  foreshadowing?: Array<{ id?: string; title?: string; body?: string; approved?: boolean; source?: string }>;
};

function ContextGroup({ title, items = [], icon, emptyMessage, defaultOpen = true }: { title: string; items?: ContextPayload["characters"]; icon: React.ReactNode; emptyMessage: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="editor-context-group">
      <button type="button" className="editor-context-group-title" onClick={() => setOpen(value => !value)}>
        <span>{icon}{title}</span>
        <span className="editor-context-count">{items.length}{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
      </button>
      {open && items.length ? (
        <div className="editor-context-items">
          {items.slice(0, 6).map((item, index) => (
            <div className="editor-context-item" key={item.id || `${item.title}-${index}`}>
              <strong>{item.title || "未命名条目"}</strong>
              <p>{String(item.body || "").slice(0, 140) || "已建立条目，正文摘要暂未填写。"}</p>
              <small className={item.approved ? "" : "pending"}>{item.approved ? "已进入当前上下文" : "待人工确认"}{item.source ? ` · ${item.source}` : ""}</small>
            </div>
          ))}
          {items.length > 6 ? <small className="editor-context-more">还有 {items.length - 6} 条，可在故事 Bible 查看</small> : null}
        </div>
      ) : open ? <div className="editor-context-empty"><span>{emptyMessage}</span></div> : null}
    </div>
  );
}

export function EditorContextPanel({ chapterId }: { chapterId: string }) {
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<ContextPayload>(`/api/v1/authoring/context/${chapterId}`, { method: "POST" })
      .then(value => { if (active) setContext(value); })
      .catch(caught => { if (active) setError(caught instanceof Error ? caught.message : "上下文暂时不可用"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [chapterId]);

  return (
    <section className="editor-context-panel" aria-label="当前创作上下文">
      <div className="editor-context-header">
        <div>
          <span className="editor-context-kicker">WRITING CONTEXT</span>
          <strong>本章写作上下文</strong>
        </div>
        <Compass size={16} />
      </div>
      {loading ? <div className="editor-context-loading">正在读取本章人物与剧情…</div> : null}
      {error ? <div className="editor-context-error" role="alert"><CircleAlert size={13} />{error}</div> : null}
      {!loading && !error && context ? (
        <>
          <div className="editor-context-chapter">
            <span>第 {context.chapter?.seq || "-"} 章</span>
            <strong>{context.chapter?.title || "未命名章节"}</strong>
            {context.chapter?.text ? <p className="editor-context-chapter-excerpt">{context.chapter.text.slice(0, 120)}{context.chapter.text.length > 120 ? "…" : ""}</p> : null}
            <div className="editor-context-neighbors">
              <span>{context.previous_chapter ? `上一章：${context.previous_chapter.title || "未命名"}` : "上一章：无"}</span>
              <span>{context.next_chapter ? `下一章：${context.next_chapter.title || "未命名"}` : "下一章：尚未建立"}</span>
            </div>
          </div>
          <ContextGroup title="人物" items={context.characters} icon={<UsersRound size={13} />} emptyMessage="暂无本章已记录人物。可先在创作圣经建立角色卡。" />
          <ContextGroup title="剧情与主线" items={context.plot} icon={<Compass size={13} />} emptyMessage="暂无主线记录。先在 AI 共创助手里说明本章目标。" />
          <ContextGroup title="伏笔" items={context.foreshadowing} icon={<CircleAlert size={13} />} emptyMessage="本章暂未记录伏笔。需要时可让 AI 提议并由你确认。" />
          <ContextGroup title="世界观" items={context.worldview} icon={<Compass size={13} />} emptyMessage="暂无已确认世界观事实。请先建立或确认创作圣经。" defaultOpen={false} />
        </>
      ) : null}
    </section>
  );
}
