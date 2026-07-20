import React from "react";
import { FileText } from "lucide-react";
import { ReviewRadar } from "./ReviewRadar";
import { CharacterCard, OutlineTree } from "./CharacterOutline";
import { Pagination } from "./ui";
import { NovelAnalysisReport } from "./NovelAnalysisReport";
import { usePagination } from "../hooks/usePagination";

type Content = { id: string; title: string; type?: string; status?: string; meta: Record<string, unknown> };
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

  // ── Build NovelAnalysisReport sections from EXISTING review data ──
  // Only data we actually possess is passed; missing sections fall back to
  // the "暂无数据" placeholder inside NovelAnalysisReport (no fabrication).
  const metaAny = meta as Record<string, unknown>;

  const basicInfoNode: React.ReactNode = (
    <div style={{ fontSize: 13, lineHeight: 1.9, color: "var(--text-2)" }}>
      <div><b>书名：</b>{chapter?.title || "未命名作品"}</div>
      <div><b>类型：</b>{chapter?.type || "—"}</div>
      <div><b>状态：</b>{chapter?.status || "—"}</div>
      {metaAny.genre ? <div><b>题材：</b>{String(metaAny.genre)}</div> : null}
      {metaAny.premise ? <div><b>核心设定：</b>{String(metaAny.premise)}</div> : null}
      {metaAny.idea ? <div><b>创作灵感：</b>{String(metaAny.idea)}</div> : null}
      {hasScoreEvidence ? <div><b>综合评分：</b>{Math.round(totalScore)}</div> : null}
    </div>
  );

  const hitReasonNode: React.ReactNode | undefined = (() => {
    const reasons: React.ReactNode[] = [];
    strengths.forEach((s, i) => reasons.push(<span key={`st-${i}`} className="badge purple">{s}</span>));
    if (Array.isArray(metaAny.differentiators)) {
      (metaAny.differentiators as unknown[]).forEach((d, i) => reasons.push(<span key={`df-${i}`} className="badge cyan">{String(d)}</span>));
    }
    if (Array.isArray(metaAny.market_evidence)) {
      (metaAny.market_evidence as unknown[]).forEach((e, i) => reasons.push(<span key={`me-${i}`} className="badge gray">{String(e)}</span>));
    }
    if (!reasons.length) return undefined;
    return <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{reasons}</div>;
  })();

  const goldenThreeNode: React.ReactNode | undefined = (() => {
    const outline = metaAny.outline || metaAny.chapter_outlines;
    if (Array.isArray(outline) && outline.length) return <OutlineTree nodes={outline as any[]} />;
    return undefined;
  })();

  const characterAnalysisNode: React.ReactNode | undefined = (() => {
    if (!characters?.length) return undefined;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {characters.map((c: any, i: number) => (
          <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
            <strong>{c.name || c.character || `角色 ${i + 1}`}</strong>
            {c.role ? <span style={{ color: "var(--text-3)", marginLeft: 8 }}>{c.role}</span> : null}
            {c.description ? <div style={{ color: "var(--text-2)", marginTop: 4 }}>{c.description}</div> : null}
          </div>
        ))}
        {arcs?.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <strong style={{ fontSize: 13 }}>人物弧线</strong>
            {arcs.map((a: any, i: number) => (
              <div key={i} style={{ fontSize: 13, padding: "4px 0" }}>
                <strong>{a.character}</strong>
                {a.stage ? <span style={{ color: "var(--text-3)", marginLeft: 8 }}>{a.stage}</span> : null}
                {a.goal ? <span style={{ marginLeft: 8 }}>{a.goal}</span> : null}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  })();

  const worldviewNode: React.ReactNode | undefined = (() => {
    const world = metaAny.worldview || metaAny.world_building || metaAny.world_setting;
    if (world) return <div style={{ fontSize: 13, lineHeight: 1.8, color: "var(--text-2)" }}>{String(world)}</div>;
    return undefined;
  })();

  const styleAnalysisNode: React.ReactNode | undefined = (() => {
    if (!dims.length) return undefined;
    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {dims.map((d, i) => (
          <span key={i} className={`badge ${scoreBadgeColor(d.score)}`}>{d.name} {d.score}</span>
        ))}
      </div>
    );
  })();

  const readerAnalysisNode: React.ReactNode | undefined = (() => {
    const reader = metaAny.target_audience || metaAny.audience;
    if (reader) return <div style={{ fontSize: 13, lineHeight: 1.8, color: "var(--text-2)" }}>{String(reader)}</div>;
    return undefined;
  })();

  const aiSuggestionNode: React.ReactNode | undefined = (() => {
    const suggestions: React.ReactNode[] = [];
    issues.forEach((s, i) => suggestions.push(<span key={`is-${i}`} className="badge orange">{s}</span>));
    if (continuity?.gaps && Array.isArray(continuity.gaps)) {
      (continuity.gaps as unknown[]).forEach((g, i) =>
        suggestions.push(<span key={`gp-${i}`} className="badge orange">{typeof g === "string" ? g : JSON.stringify(g)}</span>));
    }
    if (!suggestions.length) return undefined;
    return <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{suggestions}</div>;
  })();

  // Paginate the read-only data lists so long reviews stay scannable.
  const charactersPager = usePagination({ items: characters, pageSize: 10, mode: "client" });
  const timelinePager = usePagination({ items: timeline, pageSize: 10, mode: "client" });
  const arcsPager = usePagination({ items: arcs, pageSize: 10, mode: "client" });

  // ── Export the rendered review data as a downloadable Markdown report ──
  // Assembles the SAME source data already shown on this page (the 8-section
  // report, consistency checks, issues, strengths, continuity, characters,
  // timeline, outline) into a Markdown string and triggers a browser download.
  // No backend endpoint required — purely client-side serialization.
  function exportReport(): void {
    const lines: string[] = [];
    lines.push(`# 七维审查报告：${chapter?.title || "未命名作品"}`);
    lines.push("");
    lines.push(`- 类型：${chapter?.type || "—"}`);
    lines.push(`- 状态：${chapter?.status || "—"}`);
    if (hasScoreEvidence) lines.push(`- 综合评分：${Math.round(totalScore)}`);
    if (metaAny.genre) lines.push(`- 题材：${String(metaAny.genre)}`);
    if (metaAny.premise) lines.push(`- 核心设定：${String(metaAny.premise)}`);
    if (metaAny.idea) lines.push(`- 创作灵感：${String(metaAny.idea)}`);
    lines.push("");

    if (dims.length) {
      lines.push("## 文风分析（七维）");
      dims.forEach((d) => lines.push(`- ${d.name}：${d.score}`));
      lines.push("");
    }

    const checkEntries = Object.entries(consistencyChecks);
    if (checkEntries.length) {
      lines.push("## 一致性检查");
      checkEntries.forEach(([name, check]) => lines.push(`- ${DIMENSION_LABELS[name] || name}：${check?.status || "—"}`));
      lines.push("");
    }

    if (issues.length) {
      lines.push("## 问题与弱点");
      issues.forEach((s) => lines.push(`- ${s}`));
      lines.push("");
    }

    if (strengths.length) {
      lines.push("## 优点");
      strengths.forEach((s) => lines.push(`- ${s}`));
      lines.push("");
    }

    if (continuity) {
      lines.push("## 连续性审计");
      if (continuity.status) lines.push(`- 状态：${continuity.status}`);
      if (continuity.narrative_flow) lines.push(`- 叙事流：${continuity.narrative_flow}`);
      if (Array.isArray(continuity.gaps) && continuity.gaps.length) {
        lines.push("- 连续性缺口：");
        (continuity.gaps as unknown[]).forEach((g) => lines.push(`  - ${typeof g === "string" ? g : JSON.stringify(g)}`));
      }
      lines.push("");
    }

    if (characters?.length) {
      lines.push("## 人物卡");
      characters.forEach((c: any) => {
        const name = c.name || c.character || "角色";
        lines.push(`- **${name}**${c.role ? `（${c.role}）` : ""}`);
        if (c.description) lines.push(`  - ${c.description}`);
      });
      lines.push("");
    }

    if (timeline?.length) {
      lines.push("## 时间线");
      timeline.forEach((e: any) => lines.push(`- 第${e.chapter_seq}章：${e.event}`));
      lines.push("");
    }

    const outline = metaAny.outline || metaAny.chapter_outlines;
    if (Array.isArray(outline) && outline.length) {
      lines.push("## 大纲");
      outline.forEach((n: any, i: number) => lines.push(`${i + 1}. ${typeof n === "string" ? n : (n.title || n.label || JSON.stringify(n))}`));
      lines.push("");
    }

    const md = lines.join("\n");
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeTitle = (chapter?.title || "review").replace(/[\\/:*?"<>|]/g, "_");
    a.download = `novelcraft-review-${safeTitle}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

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
          {/* 「重新审查」依赖后端 final_consistency_check 工作流节点，超出纯前端范围，已移除（见审计 P1-1）。
              「导出报告」为真实功能：将本页已渲染的审查数据拼装为 Markdown 并触发浏览器下载。 */}
          <button
            className="btn-sm"
            style={{ background: "var(--bg-hover)", color: "var(--text-2)" }}
            onClick={exportReport}
            disabled={!chapter}
            title={chapter ? "导出当前审查数据为 Markdown" : "请先选择章节"}
          >
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

      {/* ── Consolidated novel analysis report (8-section Accordion) ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <div className="card-title">
            <FileText size={18} /> 小说分析报告
          </div>
        </div>
        <NovelAnalysisReport
          basicInfo={basicInfoNode}
          hitReason={hitReasonNode}
          goldenThree={goldenThreeNode}
          characterAnalysis={characterAnalysisNode}
          worldview={worldviewNode}
          styleAnalysis={styleAnalysisNode}
          readerAnalysis={readerAnalysisNode}
          aiSuggestion={aiSuggestionNode}
        />
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
          {charactersPager.pageData.map((c, i) => (
            <CharacterCard key={i} char={c} />
          ))}
          <Pagination
            page={charactersPager.page}
            pageSize={charactersPager.pageSize}
            total={characters.length}
            onPageChange={charactersPager.setPage}
            onPageSizeChange={charactersPager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
        </div>
      )}

      {/* ── Timeline ── */}
      {timeline?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">时间线</div>
            <span className="badge cyan">{timeline.length} 项</span>
          </div>
          {timelinePager.pageData.map((e: any, i: number) => (
            <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", fontSize: 13, borderBottom: "1px solid var(--border)" }}>
              <span style={{ color: "var(--text-3)", minWidth: 60 }}>第{e.chapter_seq}章</span>
              <span>{e.event}</span>
            </div>
          ))}
          <Pagination
            page={timelinePager.page}
            pageSize={timelinePager.pageSize}
            total={timeline.length}
            onPageChange={timelinePager.setPage}
            onPageSizeChange={timelinePager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
        </div>
      )}

      {/* ── Arcs ── */}
      {arcs?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <div className="card-title">人物弧线</div>
          </div>
          {arcsPager.pageData.map((a: any, i: number) => (
            <div key={i} style={{ padding: "4px 0", fontSize: 13 }}>
              <strong>{a.character}</strong>
              <span style={{ color: "var(--text-3)", marginLeft: 8 }}>{a.stage}</span>
              <span style={{ marginLeft: 8 }}>{a.goal}</span>
            </div>
          ))}
          <Pagination
            page={arcsPager.page}
            pageSize={arcsPager.pageSize}
            total={arcs.length}
            onPageChange={arcsPager.setPage}
            onPageSizeChange={arcsPager.setPageSize}
            pageSizeOptions={[10, 20, 50, 100]}
          />
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
