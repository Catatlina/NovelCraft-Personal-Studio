import { useState } from "react";
import { AlertTriangle, BookOpenCheck, CheckCircle2, CircleHelp, Route, Sparkles, Users } from "lucide-react";
import { ApiError, api } from "../lib/api";

type ReviewPayload = {
  score?: number;
  self_score?: number;
  overall_score?: number;
  computed_score?: number;
  dimensions?: Record<string, number>;
  dimension_scores?: Record<string, number>;
  issues?: unknown[];
  weaknesses?: unknown[];
  strengths?: unknown[];
  checks?: Record<string, { status?: string; issues?: unknown[] }>;
  overall_status?: string;
  warning_count?: number;
  audit_report?: AuditReport;
  reader_experience?: Record<string, number>;
  canonical_engine?: string;
  review_evidence?: ReviewEvidence;
  continuity?: { status?: string; checked?: boolean; gaps?: unknown[]; narrative_flow?: string; source?: string; model_score?: number | null };
  provenance?: {
    engine?: string;
    audit_source?: string;
    prompt_name?: string;
    prompt_version?: string;
    provider?: string;
    model?: string;
    text_hash?: string;
    cache_hit?: boolean;
    source?: string;
    scored_at?: string;
  };
  final_consistency_check?: {
    checks?: Record<string, { status?: string; issues?: unknown[] }>;
    overall_score?: number;
    dimension_scores?: Record<string, number>;
    audit_report?: AuditReport;
    overall_status?: string;
    warning_count?: number;
  };
  final_continuity_audit?: {
    continuity?: { status?: string; gaps?: unknown[]; narrative_flow?: string };
  };
};

type ReviewEvidence = {
  status?: string;
  complete?: boolean;
  missing?: string[];
  audit_33?: { status?: string; complete?: boolean; scored?: number; required?: number; coverage?: number; issues?: string[] };
  continuity?: { status?: string; checked?: boolean; complete?: boolean; narrative_flow?: string; gaps?: unknown[] };
  timeline?: { status?: string; complete?: boolean; score?: number | null; evidence?: string };
  character_arcs?: { status?: string; complete?: boolean; score?: number | null; evidence?: string };
};

type AuditItem = {
  key?: string;
  group?: string;
  label?: string;
  score?: number | null;
  evidence?: string;
  repair?: string;
  source?: string;
  status?: string;
  hard_gate?: boolean;
};

type AuditReport = {
  count?: number;
  scored_count?: number;
  llm_scored_count?: number;
  coverage?: number;
  complete?: boolean;
  source?: string;
  groups?: Record<string, string[]>;
  items?: Record<string, AuditItem>;
};

const DIMENSION_LABELS: Record<string, string> = {
  source_fidelity: "原始设定",
  characters: "人物一致性",
  locations: "地点一致性",
  timeline: "时间线",
  objects: "关键物件",
  settings: "世界设定",
  foreshadowing: "伏笔呼应",
  plot: "情节",
  style: "文风",
  pacing: "节奏",
  consistency: "设定一致性",
  character_voice: "人物声音",
  plot_logic: "情节逻辑",
  writing_quality: "文字质量",
  emotional_impact: "情感冲击",
  constraint_compliance: "约束遵守",
};

const AUDIT_GROUP_LABELS: Record<string, string> = {
  plot: "情节与因果",
  character: "人物一致性",
  world: "世界与连续性",
  reader: "读者体验",
  style: "文风与去 AI 味",
};

const AUDIT_SOURCE_LABELS: Record<string, string> = {
  llm: "模型逐项审计",
  macro_projection: "七维分数折算",
  projected: "兼容折算",
  scored: "已评分",
  not_scored: "未评分",
};

function readableItem(item: unknown): string {
  if (typeof item === "string") return item;
  if (!item || typeof item !== "object") return String(item ?? "");
  const record = item as Record<string, unknown>;
  const description = record.description || record.issue || record.message || record.reason || record.title;
  const suggestion = record.suggestion || record.recommendation || record.fix;
  if (description && suggestion) return `${String(description)}（建议：${String(suggestion)}）`;
  if (description) return String(description);
  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key}：${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
    .join("；");
}

function cleanItems(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(readableItem).map(item => item.trim()).filter(Boolean);
}

function statusLabel(status?: string) {
  if (status === "pass" || status === "continuous") return "通过";
  if (status === "warning") return "需留意";
  if (status === "fail" || status === "broken") return "未通过";
  return "未检查";
}

function scoreValue(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, value));
}

function average(values: number[]): number | null {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function statusScore(status?: string): number | null {
  if (status === "pass" || status === "continuous" || status === "completed" || status === "succeeded") return 100;
  if (status === "warning") return 70;
  if (status === "fail" || status === "broken" || status === "failed") return 0;
  return null;
}

function displayScore(value: number | null): string {
  if (value === null) return "—";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function uniqueItems(items: string[]): string[] {
  return Array.from(new Set(items));
}

export function Review({
  chapter,
  review = {},
  characters = [],
  timeline = [],
  arcs = [],
  narrativeEvidence,
  onOpenEditor,
  onRepairApplied,
}: {
  chapter?: { id?: string; title?: string; body?: unknown; meta?: Record<string, unknown>; updated_at?: string } | null;
  review?: ReviewPayload;
  characters?: Array<{ id?: string; title?: string; name?: string; body?: string }>;
  timeline?: Array<{ event?: string; chapter_seq?: number }>;
  arcs?: Array<{ character?: string; stage?: string; goal?: string; status?: string }>;
  narrativeEvidence?: { timeline_source?: string; arcs_source?: string };
  onOpenEditor?: (chapterId?: string) => void;
  onRepairApplied?: (updated: { body?: unknown; meta?: Record<string, unknown>; status?: string; updated_at?: string }) => void;
}) {
  const [repairBusy, setRepairBusy] = useState(false);
  const [repairError, setRepairError] = useState("");
  const [repairPreview, setRepairPreview] = useState<null | {
    action: "repair_local" | "rewrite_chapter" | "replan_chapter";
    base_updated_at: string;
    current_body: unknown;
    proposal: Record<string, unknown>;
    signature: string;
  }>(null);
  const consistency = review.final_consistency_check || review;
  const checks = consistency.checks || {};
  const auditReport = review.audit_report || consistency.audit_report;
  const reviewEvidence = review.review_evidence;
  const auditItems = auditReport?.items || {};
  const dimensionScores = review.dimension_scores || review.dimensions || consistency.dimension_scores || {};
  const numericDimensionScores = Object.values(dimensionScores).map(scoreValue).filter((value): value is number => value !== null);
  const auditScores = Object.values(auditItems).map(item => scoreValue(item.score)).filter((value): value is number => value !== null);
  const checkScores = Object.values(checks).map(check => statusScore(check.status)).filter((value): value is number => value !== null);
  const directScore = [review.overall_score, review.score, review.self_score, consistency.overall_score]
    .map(scoreValue)
    .find((value): value is number => value !== null) ?? null;
  const score = directScore ?? average(numericDimensionScores) ?? average(auditScores) ?? average(checkScores);
  const scoreSource = directScore !== null
    ? "provider"
    : numericDimensionScores.length
      ? "dimension_scores"
      : auditScores.length
        ? (auditReport?.source === "macro_projection" ? "projected_audit" : "audit_report")
        : checkScores.length ? "checks" : "none";
  const scoreEvidence = directScore !== null
    ? Math.max(numericDimensionScores.length, auditScores.length, Object.keys(checks).length)
    : numericDimensionScores.length || auditScores.length || checkScores.length;
  const continuity = review.final_continuity_audit?.continuity ?? review.continuity;
  const issues = uniqueItems([
    ...cleanItems(review.issues),
    ...cleanItems(review.weaknesses),
    ...Object.values(checks).flatMap(check => cleanItems(check.issues)),
    ...cleanItems(continuity?.gaps),
  ]);
  const strengths = cleanItems(review.strengths);
  const hasEvidence = score !== null || Object.keys(dimensionScores).length > 0 || Object.keys(auditItems).length > 0 || Object.keys(checks).length > 0 || issues.length > 0 || Boolean(continuity) || Boolean(reviewEvidence);
  const recommendation = chapter?.meta?.repair_recommendation as {
    action?: "repair_local" | "rewrite_chapter" | "replan_chapter";
    level?: string;
    reason?: string;
  } | undefined;

  function bodyText(value: unknown): string {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(bodyText).filter(Boolean).join("\n\n");
    if (value && typeof value === "object") {
      const item = value as { text?: unknown; content?: unknown };
      if (typeof item.text === "string") return item.text;
      return bodyText(item.content);
    }
    return "";
  }

  function repairErrorMessage(error: unknown, fallback: string): string {
    if (error instanceof ApiError) {
      const payload = error.payload as { message?: string; detail?: string | { message?: string } } | null;
      if (typeof payload?.detail === "string") return payload.detail;
      if (payload?.detail && typeof payload.detail === "object" && payload.detail.message) return payload.detail.message;
      if (payload?.message) return payload.message;
    }
    return error instanceof Error && error.message ? error.message : fallback;
  }

  async function generateRepairPreview() {
    if (!chapter?.id || !recommendation?.action || !issues.length) return;
    setRepairBusy(true);
    setRepairError("");
    try {
      const preview = await api<NonNullable<typeof repairPreview>>(
        `/api/v1/chapters/${chapter.id}/repair-preview`,
        {
          method: "POST",
          body: JSON.stringify({
            action: recommendation.action,
            issues,
            client_mutation_id: crypto.randomUUID(),
          }),
        },
      );
      setRepairPreview(preview);
    } catch (error) {
      setRepairError(repairErrorMessage(error, "修复预览生成失败"));
    } finally {
      setRepairBusy(false);
    }
  }

  async function applyRepairPreview() {
    if (!chapter?.id || !repairPreview) return;
    setRepairBusy(true);
    setRepairError("");
    try {
      const updated = await api<{ body?: unknown; meta?: Record<string, unknown>; status?: string; updated_at?: string }>(
        `/api/v1/chapters/${chapter.id}/repair-apply`,
        {
          method: "POST",
          body: JSON.stringify({
            action: repairPreview.action,
            base_updated_at: repairPreview.base_updated_at,
            proposal: repairPreview.proposal,
            signature: repairPreview.signature,
          }),
        },
      );
      onRepairApplied?.(updated);
      setRepairPreview(null);
    } catch (error) {
      setRepairError(repairErrorMessage(error, "应用失败，请重新生成预览"));
    } finally {
      setRepairBusy(false);
    }
  }

  return (
    <div className="review-page page-enter">
      <section className="review-heading">
        <div>
          <p className="eyebrow">QUALITY & CONTINUITY</p>
          <h2>审阅与一致性</h2>
          <p>{chapter?.title ? `正在查看《${chapter.title}》的真实审阅证据。` : "选择或创建一本小说后，这里会汇总质量与连续性结果。"}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {hasEvidence && (
            <span className={`review-state ${issues.length ? "warning" : "pass"}`}>{issues.length ? `${issues.length} 项需关注` : "当前检查通过"}</span>
          )}
          {onOpenEditor && chapter?.id && (
            <button className="btn-sm btn-primary" onClick={() => onOpenEditor(chapter.id)}>
              <BookOpenCheck size={14} /> 打开编辑器修改
            </button>
          )}
          {recommendation?.action && issues.length > 0 && (
            <button className="btn-sm" disabled={repairBusy} onClick={() => void generateRepairPreview()}>
              <Sparkles size={14} /> {repairBusy ? "生成预览中…" : "按审阅建议生成修复预览"}
            </button>
          )}
        </div>
      </section>

      {repairError && <section className="error">{repairError}</section>}
      {repairPreview && (
        <section className="repair-preview starlume-card">
          <div className="section-heading">
            <div><p className="eyebrow">REPAIR PREVIEW</p><h3>修复预览 · 尚未应用</h3></div>
            <span>{repairPreview.action === "repair_local" ? "局部修复" : repairPreview.action === "replan_chapter" ? "重新规划" : "整章重写"}</span>
          </div>
          {repairPreview.action === "replan_chapter" ? (
            <div className="repair-preview-grid">
              <div><strong>当前细纲</strong><pre>{JSON.stringify(chapter?.meta?.outline || {}, null, 2)}</pre></div>
              <div><strong>建议细纲</strong><pre>{JSON.stringify(repairPreview.proposal.revised_outline || {}, null, 2)}</pre></div>
            </div>
          ) : (
            <div className="repair-preview-grid">
              <div><strong>当前正文</strong><pre>{bodyText(repairPreview.current_body)}</pre></div>
              <div><strong>建议正文</strong><pre>{bodyText(repairPreview.proposal.proposed_body)}</pre></div>
            </div>
          )}
          <div className="ai-edit-preview-actions">
            <button type="button" className="btn-primary" disabled={repairBusy} onClick={() => void applyRepairPreview()}>
              {repairBusy ? "应用中…" : "确认应用"}
            </button>
            <button type="button" disabled={repairBusy} onClick={() => setRepairPreview(null)}>放弃建议</button>
          </div>
        </section>
      )}

      {!hasEvidence ? (
        <section className="review-empty starlume-card">
          <span><CircleHelp size={24} /></span>
          <h3>还没有可用的审阅结果</h3>
          <p>完成首章生成或在编辑器中运行质量审阅后，真实评分、问题与一致性证据会出现在这里；不会用默认高分填充。</p>
        </section>
      ) : (
        <>
          <section className="review-summary-grid">
            <article className="review-score-card starlume-card">
              <div className="review-score-ring" style={{ "--score": `${(score ?? 0) * 3.6}deg` } as React.CSSProperties}>
                <span><strong>{displayScore(score)}</strong><small>/ 100</small></span>
              </div>
              <div>
                <p className="eyebrow">综合质量</p>
                <h3>{score === null ? "暂无综合评分" : score >= 80 ? "基础质量达标" : "仍需继续打磨"}</h3>
                <p>{scoreSource === "provider" ? "来自 V7 审阅器返回的 overall_score。" : scoreSource === "none" ? "审阅尚未返回可计算的评分证据。" : `按${scoreSource === "checks" ? "检查状态" : "现有审计证据"}折算，非人工评分。`}</p>
                {scoreEvidence > 0 && <small className="review-evidence-note">已纳入 {scoreEvidence} 项证据</small>}
              </div>
            </article>
            <article className="review-continuity-card starlume-card">
              <span className={`review-card-icon ${continuity?.status || "unchecked"}`}><Route size={20} /></span>
              <p className="eyebrow">连续性审计</p>
              <h3>{statusLabel(continuity?.status)}</h3>
              <p>{continuity?.narrative_flow || "尚未返回叙事流检查说明。"}</p>
              {cleanItems(continuity?.gaps).length > 0 && <small>{cleanItems(continuity?.gaps).length} 处衔接缺口</small>}
            </article>
          </section>

          {review.provenance && (
            <section className="review-provenance starlume-card">
              <div className="section-heading">
                <div><p className="eyebrow">AUDIT PROVENANCE</p><h3>本次评分来源</h3></div>
                <span>{review.provenance.cache_hit ? "命中同正文缓存" : "实时 V7 审计"}</span>
              </div>
              <div className="review-provenance-grid">
                <div><span>审核引擎</span><strong>{review.provenance.engine || review.canonical_engine || "v7"}</strong></div>
                <div><span>实际模型</span><strong>{[review.provenance.provider, review.provenance.model].filter(Boolean).join(" · ") || "未返回"}</strong></div>
                <div><span>Prompt</span><strong>{review.provenance.prompt_name || "未返回"}</strong></div>
                <div><span>Prompt 版本</span><strong>{review.provenance.prompt_version || "未返回"}</strong></div>
                <div><span>审计来源</span><strong>{review.provenance.audit_source || review.provenance.source || "未返回"}</strong></div>
                <div><span>正文指纹</span><strong>{review.provenance.text_hash ? `${review.provenance.text_hash.slice(0, 12)}…` : "未返回"}</strong></div>
              </div>
            </section>
          )}

          {reviewEvidence && reviewEvidence.complete === false && (
            <section className="review-evidence-warning starlume-card">
              <strong>V7 证据链尚未完整</strong>
              <span>
                {reviewEvidence.missing?.length
                  ? `缺少：${reviewEvidence.missing.join("、")}`
                  : "本次结果只能作为待复核结果，页面不会把缺失证据补成通过。"}
              </span>
            </section>
          )}

          <section className="review-dimensions starlume-card">
            <div className="section-heading"><div><p className="eyebrow">SEVEN DIMENSIONS</p><h3>核心质量维度</h3></div><span>{numericDimensionScores.length} 项有分数</span></div>
            <div className="dimension-grid">
              {Object.keys(dimensionScores).length ? Object.entries(dimensionScores).map(([key, value]) => {
                const numeric = scoreValue(value);
                return (
                  <div className="dimension-row" key={key}>
                    <div><strong>{DIMENSION_LABELS[key] || key}</strong><span>{displayScore(numeric)}</span></div>
                    <div><span style={{ width: `${numeric ?? 0}%` }} /></div>
                  </div>
                );
              }) : <p className="muted-output">本次审阅未返回分维度分数。</p>}
            </div>
          </section>

          <section className="review-audit-card starlume-card">
            <div className="section-heading">
              <div><p className="eyebrow">33-DIMENSION EVIDENCE</p><h3>细项审计证据</h3></div>
              <span>{auditReport ? `${auditReport.scored_count ?? auditScores.length}/${auditReport.count ?? 33} 项有分数` : `${Object.keys(checks).length} 项检查`}</span>
            </div>
            <div className="review-audit-summary">
              <div><strong>{auditReport ? `${Math.round((auditReport.coverage ?? 0) * 100)}%` : "—"}</strong><span>模型逐项覆盖</span></div>
              <div><strong>{auditReport?.complete ? "完整" : auditReport ? "兼容" : "未返回"}</strong><span>{auditReport?.source === "macro_projection" ? "部分由七维分数折算" : "审计契约状态"}</span></div>
              <div><strong>{statusLabel(continuity?.status)}</strong><span>跨章连续性</span></div>
              <div><strong>{reviewEvidence ? (reviewEvidence.complete ? "完整" : "待补齐") : "未返回"}</strong><span>V7 证据链</span></div>
            </div>
            {Object.keys(auditItems).length > 0 ? (
              <div className="review-audit-groups">
                {Object.entries(
                  Object.entries(auditItems).reduce<Record<string, AuditItem[]>>((groups, [, item]) => {
                    const group = item.group || "other";
                    (groups[group] ||= []).push(item);
                    return groups;
                  }, {}),
                ).map(([group, items]) => (
                  <details className="review-audit-group" key={group}>
                    <summary><strong>{AUDIT_GROUP_LABELS[group] || group}</strong><span>{items.filter(item => scoreValue(item.score) !== null).length}/{items.length} 项有分数</span></summary>
                    <div className="review-audit-items">
                      {items.map((item, index) => {
                        const numeric = scoreValue(item.score);
                        return <div className="review-audit-item" key={`${item.key || item.label || group}-${index}`}>
                          <div><strong>{item.label || item.key || "未命名审计"}</strong><span>{numeric === null ? "未评分" : displayScore(numeric)} · {AUDIT_SOURCE_LABELS[item.source || item.status || ""] || item.source || "未标来源"}</span></div>
                          {item.evidence && <p>{item.evidence}</p>}
                        </div>;
                      })}
                    </div>
                  </details>
                ))}
              </div>
            ) : Object.keys(checks).length > 0 ? (
              <div className="review-check-grid">
                {Object.entries(checks).map(([key, check]) => <div className="review-check-row" key={key}><span className={`review-check-status ${check.status || ""}`}>{statusLabel(check.status)}</span><strong>{DIMENSION_LABELS[key] || key}</strong><small>{cleanItems(check.issues).length ? `${cleanItems(check.issues).length} 项问题` : "无附带问题"}</small></div>)}
              </div>
            ) : <p className="muted-output">本次审阅没有返回细项审计或检查证据，页面不会自行补造分数。</p>}
          </section>

          <section className="review-detail-grid">
            <article className="review-list-card starlume-card">
              <div className="review-list-heading"><span className={issues.length ? "warning" : "pass"}>{issues.length ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}</span><div><p className="eyebrow">ISSUES</p><h3>需要处理</h3></div></div>
              {issues.length ? <ul>{issues.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="muted-output">当前审阅没有返回明确问题。</p>}
            </article>
            <article className="review-list-card starlume-card">
              <div className="review-list-heading"><span className="pass"><BookOpenCheck size={18} /></span><div><p className="eyebrow">STRENGTHS</p><h3>保留优势</h3></div></div>
              {strengths.length ? <ul>{strengths.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="muted-output">本次审阅未单独列出优势。</p>}
            </article>
          </section>
        </>
      )}

      <section className="narrative-grid">
        <article className="starlume-card narrative-card">
          <div className="review-list-heading"><span><Route size={18} /></span><div><p className="eyebrow">TIMELINE</p><h3>故事时间线</h3>{narrativeEvidence?.timeline_source && <small className="narrative-source">来源：{narrativeEvidence.timeline_source}</small>}</div></div>
          {timeline.length ? <div className="narrative-list">{timeline.map((item, index) => <div key={`${item.chapter_seq}-${index}`}><span>{item.chapter_seq ? `第 ${item.chapter_seq} 章` : "未标章节"}</span><p>{item.event || "未记录事件"}</p></div>)}</div> : <p className="muted-output">尚未从章节中提取时间线事件。</p>}
        </article>
        <article className="starlume-card narrative-card">
          <div className="review-list-heading"><span><Users size={18} /></span><div><p className="eyebrow">CHARACTER ARCS</p><h3>人物弧线</h3>{narrativeEvidence?.arcs_source && <small className="narrative-source">来源：{narrativeEvidence.arcs_source}</small>}</div></div>
          {arcs.length ? <div className="narrative-list">{arcs.map((item, index) => <div key={`${item.character}-${index}`}><span>{item.character || "未命名角色"} · {item.stage || "阶段未标"}</span><p>{item.goal || item.status || "暂无目标记录"}</p></div>)}</div> : characters.length ? <div className="narrative-list">{characters.map((item, index) => <div key={item.id || index}><span>{item.title || item.name || "未命名角色"}</span><p>{item.body || "人物资料已建立，弧线尚未提取。"}</p></div>)}</div> : <p className="muted-output">尚未建立人物弧线数据。</p>}
        </article>
      </section>
    </div>
  );
}
