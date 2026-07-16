import React from "react";
import { ReviewRadar } from "./ReviewRadar";
import { CharacterCard, OutlineTree } from "./CharacterOutline";

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
  const continuity = review?.final_continuity_audit?.continuity;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel">
        <h3>七维审查 {chapter ? `— 总分 ${Math.round(totalScore)}` : ""}</h3>
        <ReviewRadar data={dims} />
        {issues.length > 0 && (
          <div className="chips">
            {issues.map((issue, index) => <span key={index}>{issue}</span>)}
          </div>
        )}
        {continuity?.narrative_flow && <p className="muted">连续性：{continuity.narrative_flow}</p>}
      </div>

      {characters?.length > 0 && (
        <div className="panel">
          <h3>人物卡</h3>
          {characters.map((c, i) => (
            <CharacterCard key={i} char={c} />
          ))}
        </div>
      )}

      {timeline?.length > 0 && (
        <div className="panel">
          <h3>时间线</h3>
          {timeline.map((e: any, i: number) => (
            <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", fontSize: 13, borderBottom: "1px solid var(--border-subtle)" }}>
              <span style={{ color: "var(--text-muted)", minWidth: 60 }}>第{e.chapter_seq}章</span>
              <span>{e.event}</span>
            </div>
          ))}
        </div>
      )}

      {arcs?.length > 0 && (
        <div className="panel">
          <h3>人物弧线</h3>
          {arcs.map((a: any, i: number) => (
            <div key={i} style={{ padding: "4px 0", fontSize: 13 }}>
              <strong>{a.character}</strong>
              <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>{a.stage}</span>
              <span style={{ marginLeft: 8 }}>{a.goal}</span>
            </div>
          ))}
        </div>
      )}

      {chapter && (
        <div className="panel">
          <h3>大纲</h3>
          <OutlineTree nodes={(meta as any).outline || (meta as any).chapter_outlines || []} />
        </div>
      )}
    </div>
  );
}
