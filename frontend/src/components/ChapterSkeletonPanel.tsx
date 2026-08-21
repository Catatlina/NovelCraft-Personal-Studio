import React, { useEffect, useMemo, useState } from "react";
import { BookOpenText, Check, ChevronDown, ChevronRight, Loader2, Save, Sparkles } from "lucide-react";
import { api } from "../lib/api";

type SkeletonScene = {
  title?: string;
  purpose?: string;
  trigger?: string;
  action?: string;
  choice?: string;
  conflict?: string;
  cost?: string;
  outcome?: string;
  visible_change?: string;
  characters?: string[];
};

type ReaderExperiencePlan = {
  opening_anchor?: string;
  reader_discovery?: string;
  interest_change?: string;
  aftertaste?: string;
  continuation_question?: string;
};

type ChapterSkeleton = {
  title?: string;
  chapter_goal?: string;
  current_state?: string;
  main_conflict?: string;
  scenes?: SkeletonScene[];
  character_moves?: string[];
  mainline_progress?: string;
  payoff?: string;
  foreshadowing?: string[];
  continuity_warnings?: string[];
  next_hook?: string;
  reader_experience_plan?: ReaderExperiencePlan;
  skeleton_text?: string;
};

type SkeletonVersion = {
  id: string;
  label?: string;
  version_no?: number;
  char_count?: number;
  author_intent?: string;
  skeleton?: ChapterSkeleton;
  created_at?: string;
};

function visibleChars(value: string): number {
  return value.replace(/\s/g, "").length;
}

export function ChapterSkeletonPanel({ chapterId }: { chapterId: string }) {
  const [open, setOpen] = useState(true);
  const [intent, setIntent] = useState("");
  const [version, setVersion] = useState<SkeletonVersion | null>(null);
  const [draft, setDraft] = useState<ChapterSkeleton | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const text = draft?.skeleton_text || "";
  const count = useMemo(() => visibleChars(text), [text]);
  const countClass = count >= 700 && count <= 1000 ? "ok" : "warn";

  useEffect(() => {
    let active = true;
    setVersion(null);
    setDraft(null);
    setIntent("");
    setError("");
    setNotice("");
    api<SkeletonVersion[]>(`/api/v1/authoring/chapters/${chapterId}/skeletons`)
      .then(items => {
        if (!active || !items.length) return;
        const latest = items[0];
        setVersion(latest);
        setDraft(latest.skeleton || null);
        setIntent(latest.author_intent || "");
      })
      .catch(() => {
        // An empty history is a valid first-use state; generation surfaces real errors.
      });
    return () => { active = false; };
  }, [chapterId]);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ version: SkeletonVersion }>(`/api/v1/authoring/chapters/${chapterId}/skeleton`, {
        method: "POST",
        body: JSON.stringify({ author_intent: intent, target_chars: 850, client_mutation_id: crypto.randomUUID() }),
      });
      setVersion(result.version);
      setDraft(result.version.skeleton || null);
      setNotice("章节骨架已生成，正文没有被修改");
      setOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "章节骨架生成失败，正文没有被修改");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ version: SkeletonVersion }>(`/api/v1/authoring/chapters/${chapterId}/skeletons/save`, {
        method: "POST",
        body: JSON.stringify({ skeleton: draft, base_version_id: version?.id || null }),
      });
      setVersion(result.version);
      setDraft(result.version.skeleton || draft);
      setNotice("人工修改已保存为新版本，正文仍需你自己完成");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "骨架保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="chapter-skeleton-panel" aria-label="章节骨架工作区">
      <button type="button" className="chapter-skeleton-header" onClick={() => setOpen(value => !value)}>
        <span className="chapter-skeleton-title"><BookOpenText size={15} /><span><strong>章节骨架</strong><small>AI 规划 · 人工成稿</small></span></span>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open ? (
        <div className="chapter-skeleton-body">
          <div className="chapter-skeleton-boundary"><Sparkles size={13} /> AI只生成700–1000字骨架，不会写入正文</div>
          <label className="chapter-skeleton-field">
            <span>本章灵感 / 想写什么</span>
            <textarea value={intent} onChange={event => setIntent(event.target.value)} rows={3} maxLength={6000} placeholder="例如：主角必须在今晚拿到证据，但不能暴露金手指；结尾让反派先一步认出他。" />
          </label>
          <button type="button" className="btn-primary chapter-skeleton-generate" onClick={() => void generate()} disabled={busy}>
            {busy ? <Loader2 size={14} className="nc-animate-pulse" /> : <Sparkles size={14} />}
            {busy ? "正在生成骨架…" : version ? "重新生成骨架" : "生成本章骨架"}
          </button>
          {error ? <div className="chapter-skeleton-error" role="alert">{error}</div> : null}
          {notice ? <div className="chapter-skeleton-notice" role="status"><Check size={13} />{notice}</div> : null}
          {draft ? (
            <>
              <div className="chapter-skeleton-meta">
                <strong>{draft.title || "本章工作标题"}</strong>
                <span className={countClass}>{count}/1000 字{count < 700 ? `，还需 ${700 - count} 字` : count > 1000 ? `，超出 ${count - 1000} 字` : "，符合范围"}</span>
              </div>
              <div className="chapter-skeleton-facts">
                {[["本章目标", draft.chapter_goal], ["主压力", draft.main_conflict], ["主线推进", draft.mainline_progress], ["本章结果", draft.payoff], ["下一章钩子", draft.next_hook]].map(([label, value]) => (
                  <div key={label} className="chapter-skeleton-fact"><small>{label}</small><p>{String(value || "待补充")}</p></div>
                ))}
              </div>
              {draft.reader_experience_plan ? (
                <div className="chapter-skeleton-reader-plan">
                  <div className="chapter-skeleton-subtitle">读者体验目标 <small>写作靶点，不是检测分数</small></div>
                  {[["开场抓手", draft.reader_experience_plan.opening_anchor], ["读者发现", draft.reader_experience_plan.reader_discovery], ["期待变化", draft.reader_experience_plan.interest_change], ["章末余波", draft.reader_experience_plan.aftertaste], ["带入下一章的问题", draft.reader_experience_plan.continuation_question]].map(([label, value]) => (
                    <div key={label} className="chapter-skeleton-reader-item"><small>{label}</small><p>{String(value || "待补充")}</p></div>
                  ))}
                </div>
              ) : null}
              {draft.scenes?.length ? (
                <div className="chapter-skeleton-scenes">
                  <div className="chapter-skeleton-subtitle">场景链 <small>触发 → 选择 → 代价 → 可见变化</small></div>
                  {draft.scenes.map((scene, index) => (
                    <div key={`${scene.title || "scene"}-${index}`} className="chapter-skeleton-scene">
                      <div className="chapter-skeleton-scene-head"><strong>{index + 1}. {scene.title || "未命名场景"}</strong><span>{scene.characters?.join("、") || "人物待确认"}</span></div>
                      <p>{scene.purpose || ""}</p>
                      <div className="chapter-skeleton-scene-grid">
                        <span><b>触发</b>{scene.trigger || "待补充"}</span>
                        <span><b>行动</b>{scene.action || "待补充"}</span>
                        <span><b>选择</b>{scene.choice || "待补充"}</span>
                        <span><b>代价</b>{scene.cost || "待补充"}</span>
                        <span><b>结果</b>{scene.outcome || "待补充"}</span>
                        <span><b>变化</b>{scene.visible_change || "待补充"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              {(draft.character_moves?.length || draft.foreshadowing?.length || draft.continuity_warnings?.length) ? (
                <div className="chapter-skeleton-supporting-facts">
                  {draft.character_moves?.length ? <div><small>人物变化</small><p>{draft.character_moves.join("；")}</p></div> : null}
                  {draft.foreshadowing?.length ? <div><small>伏笔动作</small><p>{draft.foreshadowing.join("；")}</p></div> : null}
                  {draft.continuity_warnings?.length ? <div className="warning"><small>待人工确认</small><p>{draft.continuity_warnings.join("；")}</p></div> : null}
                </div>
              ) : null}
              <label className="chapter-skeleton-field">
                <span>可写骨架（可人工修改）</span>
                <textarea value={text} onChange={event => setDraft(current => current ? { ...current, skeleton_text: event.target.value } : current)} rows={12} />
              </label>
              <button type="button" className="btn-sm btn-ghost chapter-skeleton-save" onClick={() => void save()} disabled={saving || count < 700 || count > 1000}>
                {saving ? <Loader2 size={13} className="nc-animate-pulse" /> : <Save size={13} />}
                {saving ? "保存中…" : "保存人工修改"}
              </button>
              <p className="chapter-skeleton-footnote">保存骨架不会改变正文。完成骨架后，在中间编辑区人工写作。</p>
            </>
          ) : <p className="chapter-skeleton-empty">先输入本章灵感，AI会结合人物、主线、伏笔和世界观生成可执行骨架。</p>}
        </div>
      ) : null}
    </section>
  );
}
