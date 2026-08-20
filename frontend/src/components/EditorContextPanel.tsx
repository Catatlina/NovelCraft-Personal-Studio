import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, CircleAlert, Compass, UsersRound } from "lucide-react";
import { api } from "../lib/api";

type ContextPayload = {
  source?: string;
  chapter?: { title?: string; seq?: number; text?: string } | null;
  previous_chapter?: { title?: string; seq?: number } | null;
  next_chapter?: { title?: string; seq?: number } | null;
  characters?: Array<{ title?: string; body?: string; approved?: boolean }>;
  plot?: Array<{ title?: string; body?: string; approved?: boolean }>;
  worldview?: Array<{ title?: string; body?: string; approved?: boolean }>;
  foreshadowing?: Array<{ title?: string; body?: string; approved?: boolean }>;
};

function ContextGroup({ title, items, icon }: { title: string; items: ContextPayload["characters"]; icon: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="editor-context-group">
      <button type="button" className="editor-context-group-title" onClick={() => setOpen(value => !value)}>
        <span>{icon}{title}</span>
        <span className="editor-context-count">{items?.length || 0}{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
      </button>
      {open && items?.length ? (
        <div className="editor-context-items">
          {items.slice(0, 5).map((item, index) => (
            <div className="editor-context-item" key={`${item.title}-${index}`}>
              <strong>{item.title || "未命名条目"}</strong>
              <p>{String(item.body || "").slice(0, 140) || "已建立条目，正文摘要暂未填写。"}</p>
              {item.approved ? <small>已确认</small> : <small className="pending">待确认</small>}
            </div>
          ))}
          {items.length > 5 ? <small className="editor-context-more">还有 {items.length - 5} 条，去故事 Bible 查看</small> : null}
        </div>
      ) : open ? <div className="editor-context-empty">暂未建立</div> : null}
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
          <span className="editor-context-kicker">NOW WRITING</span>
          <strong>当前剧情上下文</strong>
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
            <div className="editor-context-neighbors">
              <span>{context.previous_chapter ? `上一章：${context.previous_chapter.title || "未命名"}` : "上一章：无"}</span>
              <span>{context.next_chapter ? `下一章：${context.next_chapter.title || "未命名"}` : "下一章：尚未建立"}</span>
            </div>
          </div>
          <ContextGroup title="人物" items={context.characters} icon={<UsersRound size={13} />} />
          <ContextGroup title="剧情与主线" items={context.plot} icon={<Compass size={13} />} />
          <ContextGroup title="伏笔" items={context.foreshadowing} icon={<CircleAlert size={13} />} />
          <ContextGroup title="世界观" items={context.worldview} icon={<Compass size={13} />} />
        </>
      ) : null}
    </section>
  );
}
