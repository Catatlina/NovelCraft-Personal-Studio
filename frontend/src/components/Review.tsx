import React from "react";
import { ReviewRadar } from "./ReviewRadar";
import { CharacterCard, OutlineTree } from "./CharacterOutline";
import "../styles/proto.css";

type Content = { id: string; title: string; meta: Record<string, unknown> };
type ReviewPayload = {
  score?: number;
  self_score?: number;
  dimensions?: Record<string, number>;
  issues?: string[];
  weaknesses?: string[];
  strengths?: string[];
  final_consistency_check?: { checks?: Record<string, { status?: string; issues?: unknown[] }> };
  final_continuity_audit?: { continuity?: { status?: string; gaps?: unknown[]; narrative_flow?: string } };
};

const DIMENSION_LABELS: Record<string, string> = {
  prose: "文学性",
  plot: "剧情",
  character_ooc: "角色",
  world_conflict: "世界观",
  logic_consistency: "逻辑",
  pace: "节奏",
  foreshadowing: "伏笔",
  characters: "角色",
  locations: "地点",
  timeline: "时间线",
  objects: "物品",
  settings: "设定",
};

function statusToScore(status?: string): number {
  if (status === "pass" || status === "continuous") return 90;
  if (status === "warning" || status === "flagged") return 65;
  if (status === "fail" || status === "broken") return 35;
  return 0;
}

function statusBadge(status?: string): string {
  if (status === "pass" || status === "continuous") return "green";
  if (status === "warning" || status === "flagged") return "orange";
  if (status === "fail" || status === "broken") return "red";
  return "gray";
}

function scoreBadgeColor(score: number): string {
  if (score >= 80) return "green";
  if (score >= 60) return "orange";
  return "red";
}

export function Review({ chapter, review, characters, timeline, arcs }: {
  chapter: Content | null;
  review?: ReviewPayload;
  characters: any[];
  timeline: any[];
  arcs: any[];
}) {
  const meta = chapter?.meta || {};
  const review7dim = (meta as any).review_7dim;
  const consistencyChecks = review?.final_consistency_check?.checks || {};
  const hasLegacyDimensions = !!(review7dim?.dimensions || review?.dimensions);
  const hasScoreEvidence = hasLegacyDimensions
    || Object.keys(consistencyChecks).length > 0
    || review7dim?.score != null
    || review?.score != null
    || review?.self_score != null
    || ["review_literary", "review_logic", "review_rhythm", "review_rhythm_score", "review_character", "review_dialogue", "review_description", "review_innovation"]
      .some(key => (meta as any)[key] != null);
  const dims = hasLegacyDimensions
    ? Object.entries((review7dim?.dimensions || review?.dimensions) as Record<string, number>).map(([name, score]) => ({ name: DIMENSION_LABELS[name] || name, score: Number(score) || 0 }))
    : Object.keys(consistencyChecks).length
      ? Object.entries(consistencyChecks).map(([name, check]) => ({ name: DIMENSION_LABELS[name] || name, score: statusToScore(check?.status) }))
      : [
        { name: "文学性", score: Number((meta as any).review_literary || review?.self_score || review?.score || 0) },
        { name: "逻辑", score: Number((meta as any).review_logic || 0) },
        { name: "节奏", score: Number((meta as any).review_rhythm || meta.review_rhythm_score || 0) },
        { name: "角色", score: Number((meta as any).review_character || 0) },
        { name: "对话", score: Number((meta as any).review_dialogue || 0) },
        { name: "描写", score: Number((meta as any).review_description || 0) },
        { name: "创新", score: Number((meta as any).review_innovation || 0) },
      ];
  const totalScore = Number(review7dim?.score || review?.score || review?.self_score || (dims.reduce((s, d) => s + d.score, 0) / Math.max(1, dims.length)));
  const issues = review?.issues || review?.weaknesses || [];
  const strengths = review?.strengths || [];
  const continuity = review?.final_continuity_audit?.continuity;

  return (
    <div>
      {/* ── Page head ── */}
      <div className="page-head">
        <div>
          <h1>七维审查</h1>
          <p>
            {chapter
              ? hasScoreEvidence
                ? `${chapter.title} · 总分 ${Math.round(totalScore)}`
                : `${chapter.title} · 尚未评分`
              : "选择章节以查看审查结果"}
          </p>
        </div>
        <div className="head-actions">
          <button className="btn-sm" style={{ background: "var(--primary-dim)", color: "var(--primary-light)" }}>
            重新审查
          </button>
          <button className="btn-sm" style={{ background: "var(--bg-hover)", color: "var(--text-2)" }}>
            导出报告
          </button>
        </div>
      </div>

      {/* ── Chapter info / radar card ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <div className="card-title">{chapter?.title || "未选择章节"}</div>
          {hasScoreEvidence && (
            <span className={`badge ${scoreBadgeColor(totalScore)}`}>
              总分 {Math.round(totalScore)}
            </span>
          )}
        </div>
        {hasScoreEvidence ? (
          <ReviewRadar data={dims} />
        ) : (
          <div className="empty">
            <div className="empty-ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <p>本章没有可验证的七维评分记录。请在编辑器执行改写、润色或整章重写，或等待生成工作流完成自动审查。</p>
          </div>
        )}
      </div>

      {/* ── Dimensions detail (consistency checks) ── */}
      {Object.keys(consistencyChecks).length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">一致性检查</div>
            <span className="badge cyan">{Object.keys(consistencyChecks).length} 项</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Object.entries(consistencyChecks).map(([name, check]) => (
              <span key={name} className={`badge ${statusBadge(check?.status)}`}>
                {DIMENSION_LABELS[name] || name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Issues / weaknesses ── */}
      {issues.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">问题与弱点</div>
            <span className="badge orange">{issues.length} 项</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {issues.map((issue, index) => (
              <span key={index} className="badge gray">{issue}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── Strengths ── */}
      {strengths.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">优点</div>
            <span className="badge green">{strengths.length} 项</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {strengths.map((s, i) => (
              <span key={i} className="badge purple">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── Continuity audit ── */}
      {continuity && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">连续性审计</div>
            <span className={`badge ${statusBadge(continuity.status)}`}>
              {continuity.status || "—"}
            </span>
          </div>
          {continuity.narrative_flow && (
            <p style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.7 }}>{continuity.narrative_flow}</p>
          )}
          {continuity.gaps && (continuity.gaps as any[]).length > 0 && (
            <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
              {(continuity.gaps as any[]).map((g, i) => (
                <span key={i} className="badge orange">
                  {typeof g === "string" ? g : JSON.stringify(g)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Characters ── */}
      {characters?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">人物卡</div>
            <span className="badge cyan">{characters.length}</span>
          </div>
          {characters.map((c, i) => (
            <CharacterCard key={i} char={c} />
          ))}
        </div>
      )}

      {/* ── Timeline ── */}
      {timeline?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">时间线</div>
            <span className="badge cyan">{timeline.length} 项</span>
          </div>
          {timeline.map((e: any, i: number) => (
            <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", fontSize: 13, borderBottom: "1px solid var(--border)" }}>
              <span style={{ color: "var(--text-3)", minWidth: 60 }}>第{e.chapter_seq}章</span>
              <span>{e.event}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Arcs ── */}
      {arcs?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">人物弧线</div>
          </div>
          {arcs.map((a: any, i: number) => (
            <div key={i} style={{ padding: "4px 0", fontSize: 13 }}>
              <strong>{a.character}</strong>
              <span style={{ color: "var(--text-3)", marginLeft: 8 }}>{a.stage}</span>
              <span style={{ marginLeft: 8 }}>{a.goal}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Outline ── */}
      {chapter && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">大纲</div>
          </div>
          <OutlineTree nodes={(meta as any).outline || (meta as any).chapter_outlines || []} />
        </div>
      )}
    </div>
  );
}
