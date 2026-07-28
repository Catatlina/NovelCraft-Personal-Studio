import { AlertTriangle, BookOpenCheck, CheckCircle2, CircleHelp, Route, Users } from "lucide-react";

type ReviewPayload = {
  score?: number;
  self_score?: number;
  dimensions?: Record<string, number>;
  issues?: unknown[];
  weaknesses?: unknown[];
  strengths?: unknown[];
  checks?: Record<string, { status?: string; issues?: unknown[] }>;
  overall_status?: string;
  warning_count?: number;
  final_consistency_check?: {
    checks?: Record<string, { status?: string; issues?: unknown[] }>;
    overall_status?: string;
    warning_count?: number;
  };
  final_continuity_audit?: {
    continuity?: { status?: string; gaps?: unknown[]; narrative_flow?: string };
  };
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
};

function cleanItems(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(item => typeof item === "string" ? item : JSON.stringify(item)).filter(Boolean);
}

function statusLabel(status?: string) {
  if (status === "pass" || status === "continuous") return "通过";
  if (status === "warning") return "需留意";
  if (status === "fail" || status === "broken") return "未通过";
  return "未检查";
}

export function Review({
  chapter,
  review = {},
  characters = [],
  timeline = [],
  arcs = [],
}: {
  chapter?: { title?: string } | null;
  review?: ReviewPayload;
  characters?: Array<{ id?: string; title?: string; name?: string; body?: string }>;
  timeline?: Array<{ event?: string; chapter_seq?: number }>;
  arcs?: Array<{ character?: string; stage?: string; goal?: string; status?: string }>;
}) {
  const consistency = review.final_consistency_check || review;
  const checks = consistency.checks || {};
  const dimensionScores = review.dimensions || Object.fromEntries(
    Object.entries(checks).map(([key, check]) => [key, check.status === "pass" ? 90 : check.status === "warning" ? 65 : check.status === "fail" ? 35 : 0]),
  );
  const score = Number(review.score ?? review.self_score ?? 0);
  const issues = [
    ...cleanItems(review.issues),
    ...cleanItems(review.weaknesses),
    ...Object.values(checks).flatMap(check => cleanItems(check.issues)),
  ];
  const strengths = cleanItems(review.strengths);
  const continuity = review.final_continuity_audit?.continuity;
  const hasEvidence = score > 0 || Object.keys(checks).length > 0 || issues.length > 0 || Boolean(continuity);

  return (
    <div className="review-page page-enter">
      <section className="review-heading">
        <div>
          <p className="eyebrow">QUALITY & CONTINUITY</p>
          <h2>审阅与一致性</h2>
          <p>{chapter?.title ? `正在查看《${chapter.title}》的真实审阅证据。` : "选择或创建一本小说后，这里会汇总质量与连续性结果。"}</p>
        </div>
        {hasEvidence && <span className={`review-state ${issues.length ? "warning" : "pass"}`}>{issues.length ? `${issues.length} 项需关注` : "当前检查通过"}</span>}
      </section>

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
              <div className="review-score-ring" style={{ "--score": `${Math.max(0, Math.min(100, score)) * 3.6}deg` } as React.CSSProperties}>
                <span><strong>{score || "—"}</strong><small>/ 100</small></span>
              </div>
              <div><p className="eyebrow">综合质量</p><h3>{score >= 80 ? "基础质量达标" : score > 0 ? "仍需继续打磨" : "暂无综合评分"}</h3><p>评分来自真实自审与七维一致性结果。</p></div>
            </article>
            <article className="review-continuity-card starlume-card">
              <span className={`review-card-icon ${continuity?.status || "unchecked"}`}><Route size={20} /></span>
              <p className="eyebrow">连续性审计</p>
              <h3>{statusLabel(continuity?.status)}</h3>
              <p>{continuity?.narrative_flow || "尚未返回叙事流检查说明。"}</p>
              {cleanItems(continuity?.gaps).length > 0 && <small>{cleanItems(continuity?.gaps).length} 处衔接缺口</small>}
            </article>
          </section>

          <section className="review-dimensions starlume-card">
            <div className="section-heading"><div><p className="eyebrow">SEVEN DIMENSIONS</p><h3>一致性维度</h3></div><span>{Object.keys(dimensionScores).length} 项有证据</span></div>
            <div className="dimension-grid">
              {Object.keys(dimensionScores).length ? Object.entries(dimensionScores).map(([key, value]) => {
                const numeric = Number(value) || 0;
                return (
                  <div className="dimension-row" key={key}>
                    <div><strong>{DIMENSION_LABELS[key] || key}</strong><span>{numeric}</span></div>
                    <div><span style={{ width: `${Math.max(0, Math.min(100, numeric))}%` }} /></div>
                  </div>
                );
              }) : <p className="muted-output">本次审阅未返回分维度分数。</p>}
            </div>
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
          <div className="review-list-heading"><span><Route size={18} /></span><div><p className="eyebrow">TIMELINE</p><h3>故事时间线</h3></div></div>
          {timeline.length ? <div className="narrative-list">{timeline.map((item, index) => <div key={`${item.chapter_seq}-${index}`}><span>{item.chapter_seq ? `第 ${item.chapter_seq} 章` : "未标章节"}</span><p>{item.event || "未记录事件"}</p></div>)}</div> : <p className="muted-output">尚未从章节中提取时间线事件。</p>}
        </article>
        <article className="starlume-card narrative-card">
          <div className="review-list-heading"><span><Users size={18} /></span><div><p className="eyebrow">CHARACTER ARCS</p><h3>人物弧线</h3></div></div>
          {arcs.length ? <div className="narrative-list">{arcs.map((item, index) => <div key={`${item.character}-${index}`}><span>{item.character || "未命名角色"} · {item.stage || "阶段未标"}</span><p>{item.goal || item.status || "暂无目标记录"}</p></div>)}</div> : characters.length ? <div className="narrative-list">{characters.map((item, index) => <div key={item.id || index}><span>{item.title || item.name || "未命名角色"}</span><p>{item.body || "人物资料已建立，弧线尚未提取。"}</p></div>)}</div> : <p className="muted-output">尚未建立人物弧线数据。</p>}
        </article>
      </section>
    </div>
  );
}
