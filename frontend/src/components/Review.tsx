import React from "react";
import { ReviewRadar } from "./ReviewRadar";
import { CharacterCard, OutlineTree } from "./CharacterOutline";

type Content = { id: string; title: string; meta: Record<string, unknown> };

export function Review({ chapter, review, characters, timeline, arcs }: {
  chapter: Content | null;
  review?: { score?: number; dimensions?: Record<string, number>; issues?: string[] };
  characters: any[];
  timeline: any[];
  arcs: any[];
}) {
  const meta = chapter?.meta || {};
  const review7dim = (meta as any).review_7dim;
  const dims = review7dim?.dimensions
    ? Object.entries(review7dim.dimensions as Record<string, number>).map(([name, score]) => ({ name, score: score as number }))
    : [
      { name: "文学性", score: (meta as any).review_literary || 0 },
      { name: "逻辑", score: (meta as any).review_logic || 0 },
      { name: "节奏", score: (meta as any).review_rhythm || meta.review_rhythm_score || 0 },
      { name: "角色", score: (meta as any).review_character || 0 },
      { name: "对话", score: (meta as any).review_dialogue || 0 },
      { name: "描写", score: (meta as any).review_description || 0 },
      { name: "创新", score: (meta as any).review_innovation || 0 },
    ];
  const totalScore = dims.reduce((s, d) => s + d.score, 0) / dims.length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel">
        <h3>七维审查 {chapter ? `— 总分 ${Math.round(totalScore)}` : ""}</h3>
        <ReviewRadar data={dims} />
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
