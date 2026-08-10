import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import brainApi from "../api/client";

type MetricState = {
  data: any | null;
  loading: boolean;
  error: string;
};

const emptyMetric: MetricState = { data: null, loading: false, error: "" };

function display(value: unknown, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;
}

function metricText(metric: MetricState, emptyText: string) {
  if (metric.loading) return "分析中…";
  if (metric.error) return `加载失败：${metric.error}`;
  if (!metric.data || metric.data.has_data === false) return emptyText;
  return "已返回真实分析结果";
}

export function QualityAuxiliaryMetrics({
  novelId,
  chapterId,
}: {
  novelId?: string | null;
  chapterId?: string | null;
}) {
  const [aiSmell, setAiSmell] = useState<MetricState>(emptyMetric);
  const [emotion, setEmotion] = useState<MetricState>(emptyMetric);
  const [characters, setCharacters] = useState<MetricState>(emptyMetric);

  const refresh = useCallback(async () => {
    const chapter = chapterId || "";
    const novel = novelId || "";
    setAiSmell(metric => ({ ...metric, loading: Boolean(chapter), error: "" }));
    setEmotion(metric => ({ ...metric, loading: Boolean(novel), error: "" }));
    setCharacters(metric => ({ ...metric, loading: Boolean(chapter || novel), error: "" }));

    const [aiResult, emotionResult, characterResult] = await Promise.allSettled([
      chapter ? brainApi.getAiSmell(chapter) : Promise.resolve(null),
      novel ? brainApi.getEmotionalArc(novel) : Promise.resolve(null),
      chapter ? brainApi.getChapterCharacterStats(chapter) : novel ? brainApi.getCharacterStats(novel) : Promise.resolve(null),
    ]);

    if (aiResult.status === "fulfilled") setAiSmell({ data: aiResult.value, loading: false, error: "" });
    else setAiSmell({ data: null, loading: false, error: aiResult.reason?.message || "AI 味分析不可用" });
    if (emotionResult.status === "fulfilled") setEmotion({ data: emotionResult.value, loading: false, error: "" });
    else setEmotion({ data: null, loading: false, error: emotionResult.reason?.message || "情感弧线不可用" });
    if (characterResult.status === "fulfilled") setCharacters({ data: characterResult.value, loading: false, error: "" });
    else setCharacters({ data: null, loading: false, error: characterResult.reason?.message || "角色统计不可用" });
  }, [chapterId, novelId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="review-auxiliary starlume-card" aria-labelledby="review-auxiliary-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AUXILIARY SIGNALS</p>
          <h3 id="review-auxiliary-title">辅助指标</h3>
          <p className="muted-output">AI 味、情感和角色数据只用于定位问题，不参与 V7 主分。</p>
        </div>
        <button className="btn-sm" onClick={() => void refresh()} disabled={aiSmell.loading || emotion.loading || characters.loading}>
          <RefreshCw size={14} /> 刷新辅助分析
        </button>
      </div>
      <div className="review-auxiliary-grid">
        <article>
          <span className="eyebrow">AI 味</span>
          <strong>{aiSmell.data?.has_data === false ? "—" : display(aiSmell.data?.overall_score)}</strong>
          <p>{metricText(aiSmell, "暂无章节 AI 味分析")}{aiSmell.data?.grade ? ` · ${aiSmell.data.grade}` : ""}</p>
        </article>
        <article>
          <span className="eyebrow">情感弧线</span>
          <strong>{emotion.data?.has_data === false ? "—" : display(emotion.data?.overall_score)}</strong>
          <p>{metricText(emotion, "暂无情感弧线")}{emotion.data?.arc_type ? ` · ${emotion.data.arc_type}` : ""}</p>
          {emotion.data?.has_data && <small>峰值第 {emotion.data.peak_chapter || "—"} 章 · 波动 {display(emotion.data.volatility)}</small>}
        </article>
        <article>
          <span className="eyebrow">角色出场</span>
          <strong>{characters.data?.has_data === false ? "—" : display(characters.data?.balance_score)}</strong>
          <p>{metricText(characters, "暂无角色统计")}{characters.data?.total_characters != null ? ` · ${characters.data.total_characters} 个角色` : ""}</p>
          {characters.data?.has_warnings && <small>存在角色出场风险，请查看辅助分析结果。</small>}
        </article>
      </div>
    </section>
  );
}
