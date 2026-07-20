import React from "react";
import { Accordion, EmptyState } from "./ui";
import type { AccordionItem } from "./ui";

/**
 * Per-section content for the novel analysis report.
 *
 * Callers pass ONLY the data they actually possess. Any section left
 * `undefined` renders a "暂无数据" placeholder instead of fabricated content
 * (requirement: 复用现有分析数据，缺失则占位，不编造).
 */
export type NovelAnalysisData = {
  /** 基础信息：书名 / 类型 / 状态 / 题材 / 核心设定 / 综合评分 等 */
  basicInfo?: React.ReactNode;
  /** 爆款原因：差异化卖点 / 市场依据 / 优点 等 */
  hitReason?: React.ReactNode;
  /** 黄金三章：开篇三章大纲或计划 */
  goldenThree?: React.ReactNode;
  /** 人物分析：角色卡与人物弧线 */
  characterAnalysis?: React.ReactNode;
  /** 世界观设定 */
  worldview?: React.ReactNode;
  /** 文风分析：文学性 / 描写 / 对话 / 创新 等维度 */
  styleAnalysis?: React.ReactNode;
  /** 读者分析：目标受众与需求 */
  readerAnalysis?: React.ReactNode;
  /** AI 建议：问题 / 弱点 / 连续性缺口 等 */
  aiSuggestion?: React.ReactNode;
};

/** Fixed 8-section order mandated by the spec. */
const SECTION_ORDER: { key: string; title: string; field: keyof NovelAnalysisData }[] = [
  { key: "basic", title: "基础信息", field: "basicInfo" },
  { key: "hit", title: "爆款原因", field: "hitReason" },
  { key: "golden", title: "黄金三章", field: "goldenThree" },
  { key: "character", title: "人物分析", field: "characterAnalysis" },
  { key: "world", title: "世界观", field: "worldview" },
  { key: "style", title: "文风分析", field: "styleAnalysis" },
  { key: "reader", title: "读者分析", field: "readerAnalysis" },
  { key: "ai", title: "AI建议", field: "aiSuggestion" },
];

/**
 * Renders a single "暂无数据" placeholder. Returned fresh each call so the
 * same element instance is never shared across multiple Accordion bodies.
 */
function emptySection(): React.ReactNode {
  return (
    <EmptyState
      title="暂无数据"
      description="当前作品尚未生成该维度的分析内容，请先运行生成工作流或市场分析。"
    />
  );
}

/**
 * NovelAnalysisReport — a consolidated 8-section analysis view rendered as a
 * Wave A Accordion. All sections are collapsed by default; expanding one
 * reveals the caller-provided content or a "暂无数据" placeholder.
 */
export function NovelAnalysisReport(data: NovelAnalysisData): React.ReactElement {
  const items: AccordionItem[] = SECTION_ORDER.map((section) => ({
    key: section.key,
    title: section.title,
    defaultOpen: false,
    content: data[section.field] ?? emptySection(),
  }));

  return <Accordion items={items} />;
}

export default NovelAnalysisReport;
