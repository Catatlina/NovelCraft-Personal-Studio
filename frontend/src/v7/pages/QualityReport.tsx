/**
 * 质量分析看板
 *
 * 专业级质量审查可视化页面，达到 V7 Dashboard 设计水准：
 * - 深色 indigo 主题
 * - 卡片式布局
 * - 专业图表（recharts）
 * - 视觉层次分明
 * - 真实 API 数据，无 mock
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  GitBranch,
  LineChart as LineChartIcon,
  Radar as RadarIcon,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
  XCircle,
  Loader2,
  BookOpen,
  Zap,
  Clock,
  BookMarked,
  UserCheck,
  Award,
  ArrowUpRight,
  ArrowDownRight,
  Lightbulb,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import brainApi from '../api/client';

interface QualityReportProps {
  novelId?: string | null;
  chapters?: any[];
  selectedChapterId?: string | null;
}

type ReportView = 'depth' | 'ai_smell' | 'emotion' | 'characters';

// ============ 常量 ============

const VIEW_ITEMS: Array<{ key: ReportView; label: string; description: string; icon: typeof RadarIcon }> = [
  { key: 'depth', label: '深度审查', description: '五维质量雷达图', icon: RadarIcon },
  { key: 'ai_smell', label: 'AI 味检测', description: '七维模式级检测', icon: Sparkles },
  { key: 'emotion', label: '情感弧线', description: '全卷情感曲线', icon: LineChartIcon },
  { key: 'characters', label: '角色出场', description: '出场平衡与遗忘风险', icon: Users },
];

// ============ 工具函数 ============

function getScoreLevel(score: number) {
  if (score >= 90) return { label: 'S级', tone: 'indigo' as const, fullLabel: '卓越' };
  if (score >= 80) return { label: 'A级', tone: 'green' as const, fullLabel: '优秀' };
  if (score >= 70) return { label: 'B级', tone: 'amber' as const, fullLabel: '良好' };
  if (score >= 60) return { label: 'C级', tone: 'amber' as const, fullLabel: '一般' };
  return { label: 'D级', tone: 'danger' as const, fullLabel: '待改进' };
}

function getRiskTone(risk: string) {
  switch (risk) {
    case 'high': return 'danger' as const;
    case 'medium': return 'amber' as const;
    case 'low': return 'green' as const;
    default: return 'gray' as const;
  }
}

function getRiskLabel(risk: string) {
  switch (risk) {
    case 'high': return '高风险';
    case 'medium': return '中风险';
    case 'low': return '低风险';
    case 'none': return '正常';
    default: return '未知';
  }
}

function getAnomalyTypeLabel(type: string) {
  switch (type) {
    case 'fatigue': return '读者疲劳';
    case 'abrupt': return '转折突兀';
    case 'depression': return '情绪压抑';
    default: return type;
  }
}

function getAnomalyTone(type: string) {
  switch (type) {
    case 'fatigue': return 'amber' as const;
    case 'abrupt': return 'danger' as const;
    case 'depression': return 'indigo' as const;
    default: return 'gray' as const;
  }
}

// ============ 子组件 ============

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'indigo',
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  tone?: 'indigo' | 'green' | 'amber' | 'gray' | 'danger';
}) {
  return (
    <div className="v7-metric-card">
      <div className={`v7-metric-icon ${tone}`}><Icon size={18} /></div>
      <div className="v7-metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function EmptyBlock({ children }: { children: string }) {
  return <div className="v7-empty-block">{children}</div>;
}

function LoadingBlock({ text }: { text: string }) {
  return (
    <div className="v7-empty-block" style={{ flexDirection: 'column', gap: 12 }}>
      <Loader2 className="v7-spinner" size={24} style={{ color: 'var(--brand-500)' }} />
      <span>{text}</span>
    </div>
  );
}

function ErrorBlock({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="v7-empty-block" style={{ flexDirection: 'column', gap: 12 }}>
      <AlertTriangle size={24} style={{ color: 'var(--warning)' }} />
      <span>{message}</span>
      <button className="v7-link-button" onClick={onRetry}>重试</button>
    </div>
  );
}

// ============ 主组件 ============

export default function QualityReport({ novelId, chapters = [], selectedChapterId }: QualityReportProps) {
  const [activeView, setActiveView] = useState<ReportView>('depth');

  // 当前选中的章节
  const [currentChapterId, setCurrentChapterId] = useState<string | null>(selectedChapterId || null);

  // 数据状态
  const [qualityReview, setQualityReview] = useState<any>(null);
  const [aiSmell, setAiSmell] = useState<any>(null);
  const [characterStats, setCharacterStats] = useState<any>(null);
  const [emotionalArc, setEmotionalArc] = useState<any>(null);

  // 加载状态
  const [loadingReview, setLoadingReview] = useState(false);
  const [loadingAiSmell, setLoadingAiSmell] = useState(false);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  const [loadingEmotion, setLoadingEmotion] = useState(false);

  // 错误状态
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [aiSmellError, setAiSmellError] = useState<string | null>(null);
  const [charactersError, setCharactersError] = useState<string | null>(null);
  const [emotionError, setEmotionError] = useState<string | null>(null);

  // 当选中的章节变化时更新当前章节
  useEffect(() => {
    if (selectedChapterId) {
      setCurrentChapterId(selectedChapterId);
    }
  }, [selectedChapterId]);

  // 当章节列表变化时，如果没有选中章节，默认选第一个
  useEffect(() => {
    if (!currentChapterId && chapters.length > 0) {
      setCurrentChapterId(chapters[0].id);
    }
  }, [chapters, currentChapterId]);

  // ── 加载质量审查 ────────────────────────────────────────────────────

  const loadQualityReview = useCallback(async () => {
    if (!currentChapterId) return;

    setLoadingReview(true);
    setReviewError(null);
    try {
      const result = await brainApi.getQualityReview(currentChapterId);
      setQualityReview(result);
    } catch (err: any) {
      setReviewError(err.message || '加载质量审查失败');
    } finally {
      setLoadingReview(false);
    }
  }, [currentChapterId]);

  // ── 加载 AI 味检测 ──────────────────────────────────────────────────

  const loadAiSmell = useCallback(async () => {
    if (!currentChapterId) return;

    setLoadingAiSmell(true);
    setAiSmellError(null);
    try {
      const result = await brainApi.getAiSmell(currentChapterId);
      setAiSmell(result);
    } catch (err: any) {
      setAiSmellError(err.message || '加载 AI 味检测失败');
    } finally {
      setLoadingAiSmell(false);
    }
  }, [currentChapterId]);

  // ── 加载角色统计 ────────────────────────────────────────────────────

  const loadCharacterStats = useCallback(async () => {
    if (!novelId) return;

    setLoadingCharacters(true);
    setCharactersError(null);
    try {
      const result = await brainApi.getCharacterStats(novelId);
      setCharacterStats(result);
    } catch (err: any) {
      setCharactersError(err.message || '加载角色统计失败');
    } finally {
      setLoadingCharacters(false);
    }
  }, [novelId]);

  // ── 加载情感弧线 ────────────────────────────────────────────────────

  const loadEmotionalArc = useCallback(async () => {
    if (!novelId) return;

    setLoadingEmotion(true);
    setEmotionError(null);
    try {
      const result = await brainApi.getEmotionalArc(novelId);
      setEmotionalArc(result);
    } catch (err: any) {
      setEmotionError(err.message || '加载情感弧线失败');
    } finally {
      setLoadingEmotion(false);
    }
  }, [novelId]);

  // ── 初始加载 ────────────────────────────────────────────────────────

  useEffect(() => {
    if (activeView === 'depth') {
      loadQualityReview();
    } else if (activeView === 'ai_smell') {
      loadAiSmell();
    } else if (activeView === 'characters') {
      loadCharacterStats();
    } else if (activeView === 'emotion') {
      loadEmotionalArc();
    }
  }, [activeView, currentChapterId, loadQualityReview, loadAiSmell, loadCharacterStats, loadEmotionalArc]);

  // ── 计算总览指标 ────────────────────────────────────────────────────

  const overview = useMemo(() => {
    let overallScore = 0;
    let advantageCount = 0;
    let improvementCount = 0;
    let dimensionCount = 0;
    let aiSmellScore = 0;

    if (qualityReview?.has_data && qualityReview.dimensions) {
      overallScore = qualityReview.overall_score || 0;
      dimensionCount = qualityReview.dimensions.length;
      qualityReview.dimensions.forEach((dim: any) => {
        if (dim.score >= 85) advantageCount++;
        if (dim.score < 70) improvementCount++;
      });
    }

    if (aiSmell?.has_data) {
      aiSmellScore = aiSmell.overall_score || 0;
    }

    return {
      overallScore,
      advantageCount,
      improvementCount,
      dimensionCount,
      aiSmellScore,
    };
  }, [qualityReview, aiSmell]);

  // ── 刷新当前视图 ────────────────────────────────────────────────────

  const refreshCurrent = useCallback(() => {
    if (activeView === 'depth') {
      loadQualityReview();
    } else if (activeView === 'ai_smell') {
      loadAiSmell();
    } else if (activeView === 'characters') {
      loadCharacterStats();
    } else if (activeView === 'emotion') {
      loadEmotionalArc();
    }
  }, [activeView, currentChapterId, loadQualityReview, loadAiSmell, loadCharacterStats, loadEmotionalArc]);

  // ── 主渲染 ──────────────────────────────────────────────────────────

  const scoreLevel = getScoreLevel(overview.overallScore);
  const hasReviewData = qualityReview?.has_data && qualityReview.dimensions?.length > 0;

  return (
    <div className="v7-monitor">
      {/* 头部 */}
      <div className="v7-monitor-head">
        <div>
          <p className="v7-kicker">质量审查</p>
          <h2>质量分析看板</h2>
          <p>多维度质量分析与可视化报告，基于真实文本统计计算</p>
        </div>
        <div className="v7-monitor-head-actions">
          {/* 章节选择器 */}
          {chapters.length > 0 && (
            <select
              className="v7-refresh-button"
              value={currentChapterId || ''}
              onChange={(e) => setCurrentChapterId(e.target.value)}
              style={{ minWidth: 160, cursor: 'pointer' }}
            >
              {chapters.map((ch: any) => (
                <option key={ch.id} value={ch.id}>
                  {ch.title || `第${ch.seq || 1}章`}
                </option>
              ))}
            </select>
          )}
          <button className="v7-refresh-button" onClick={refreshCurrent}>
            <RefreshCw size={14} />
            刷新
          </button>
        </div>
      </div>

      {/* 总览指标 */}
      <div className="v7-metric-grid">
        {/* 综合评分 - 大卡片 */}
        <div className="v7-metric-card" style={{ gridColumn: 'span 1', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%', background: `color-mix(in srgb, var(--brand-500) 12%, transparent)`, pointerEvents: 'none' }} />
          <div className={`v7-metric-icon ${scoreLevel.tone}`} style={{ width: 44, height: 44 }}>
            <Award size={22} />
          </div>
          <div className="v7-metric-copy" style={{ gap: 6 }}>
            <span>综合评分</span>
            <strong style={{ fontSize: 36, lineHeight: 1, letterSpacing: '-.04em' }}>
              {hasReviewData ? overview.overallScore.toFixed(1) : '--'}
            </strong>
            <small>
              {hasReviewData ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span className={`v7-chain-badge`} style={{ padding: '2px 8px', fontSize: 10 }}>
                    {scoreLevel.label}
                  </span>
                  {scoreLevel.fullLabel}
                </span>
              ) : '暂无数据'}
            </small>
          </div>
        </div>

        <MetricCard
          icon={ArrowUpRight}
          label="优势维度"
          value={hasReviewData ? String(overview.advantageCount) : '--'}
          detail="≥85分"
          tone="green"
        />
        <MetricCard
          icon={ArrowDownRight}
          label="待提升"
          value={hasReviewData ? String(overview.improvementCount) : '--'}
          detail="<70分"
          tone="amber"
        />
        <MetricCard
          icon={Sparkles}
          label="AI 味得分"
          value={aiSmell?.has_data ? overview.aiSmellScore.toFixed(1) : '--'}
          detail="越低越好"
          tone="indigo"
        />
      </div>

      {/* 视图切换 */}
      <div className="v7-view-nav">
        {VIEW_ITEMS.map(item => (
          <button
            key={item.key}
            className={activeView === item.key ? 'active' : ''}
            onClick={() => setActiveView(item.key)}
          >
            <item.icon size={16} />
            <span>
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </span>
          </button>
        ))}
      </div>

      {/* ── 深度审查 ── */}
      {activeView === 'depth' && (
        <div className="v7-monitor-stack">
          <div className="v7-monitor-grid">
            {/* 雷达图 */}
            <div className="v7-panel">
              <div className="v7-panel-head">
                <div>
                  <h3>五维质量雷达</h3>
                  <p style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
                    爽感 · 节奏 · 剧情 · 人物 · 文笔
                  </p>
                </div>
                <span className="v7-panel-count">
                  {hasReviewData ? `${qualityReview.dimensions.length} 个维度` : '暂无数据'}
                </span>
              </div>
              <div style={{ height: 340, padding: '0 8px' }}>
                {loadingReview && <LoadingBlock text="加载质量数据..." />}
                {reviewError && <ErrorBlock message={reviewError} onRetry={loadQualityReview} />}
                {!loadingReview && !reviewError && !hasReviewData && (
                  <EmptyBlock>暂无审查数据</EmptyBlock>
                )}
                {!loadingReview && !reviewError && hasReviewData && (
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={qualityReview.dimensions} outerRadius="72%">
                      <PolarGrid stroke="var(--border-subtle)" />
                      <PolarAngleAxis
                        dataKey="name"
                        tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontWeight: 500 }}
                      />
                      <PolarRadiusAxis
                        angle={90}
                        domain={[0, 100]}
                        tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                        axisLine={false}
                        tickCount={5}
                      />
                      <Radar
                        name="得分"
                        dataKey="score"
                        stroke="var(--brand-500)"
                        fill="var(--brand-500)"
                        fillOpacity={0.2}
                        strokeWidth={2.5}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 10,
                          fontSize: 12,
                          color: 'var(--text-primary)',
                          boxShadow: 'var(--shadow-card)',
                        }}
                        formatter={(value: any) => [`${Number(value).toFixed(1)}分`, '得分']}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* 维度详情 */}
            <div className="v7-panel">
              <div className="v7-panel-head">
                <h3>维度详情</h3>
                <span className="v7-panel-count">
                  {hasReviewData ? `${qualityReview.dimensions.length} 项` : '--'}
                </span>
              </div>
              <div style={{ padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 16 }}>
                {loadingReview && <LoadingBlock text="加载中..." />}
                {reviewError && <ErrorBlock message={reviewError} onRetry={loadQualityReview} />}
                {!loadingReview && !reviewError && !hasReviewData && (
                  <EmptyBlock>暂无审查数据</EmptyBlock>
                )}
                {!loadingReview && !reviewError && hasReviewData && qualityReview.dimensions.map((dim: any) => {
                  const level = getScoreLevel(dim.score);
                  return (
                    <div key={dim.key} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                          {dim.name}
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className={`v7-chain-badge`} style={{
                            padding: '2px 8px',
                            fontSize: 10,
                            color: level.tone === 'indigo' ? 'var(--brand-500)' :
                                   level.tone === 'green' ? 'var(--success)' :
                                   level.tone === 'amber' ? 'var(--warning)' :
                                   'var(--danger)',
                            background: level.tone === 'indigo' ? 'var(--brand-50)' :
                                        level.tone === 'green' ? 'var(--success-soft)' :
                                        level.tone === 'amber' ? 'var(--warning-soft)' :
                                        'var(--danger-soft)',
                          }}>
                            {level.label}
                          </span>
                          <strong style={{ fontSize: 16, color: 'var(--text-primary)', minWidth: 42, textAlign: 'right' }}>
                            {dim.score}
                          </strong>
                        </span>
                      </div>
                      <div style={{
                        height: 6,
                        borderRadius: 999,
                        background: 'var(--bg-hover)',
                        overflow: 'hidden',
                      }}>
                        <div
                          style={{
                            height: '100%',
                            borderRadius: 999,
                            width: `${dim.score}%`,
                            background: level.tone === 'indigo' ? 'var(--brand-500)' :
                                        level.tone === 'green' ? 'var(--success)' :
                                        level.tone === 'amber' ? 'var(--warning)' :
                                        'var(--danger)',
                            transition: 'width .4s ease',
                          }}
                        />
                      </div>
                      <p style={{ margin: 0, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        {dim.comment}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* 总体评价与建议 */}
          {hasReviewData && (
            <div className="v7-panel">
              <div className="v7-panel-head">
                <div>
                  <h3>总体评价与改进建议</h3>
                  <p style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
                    基于文本统计的自动化分析结果
                  </p>
                </div>
                <span className="v7-panel-count">
                  {qualityReview.suggestions?.length || 0} 条建议
                </span>
              </div>
              <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* 总体评价 */}
                <div style={{
                  padding: '14px 16px',
                  borderRadius: 12,
                  background: `color-mix(in srgb, var(--brand-50) 50%, var(--bg-surface))`,
                  border: '1px solid color-mix(in srgb, var(--brand-500) 15%, transparent)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                    <Lightbulb size={16} style={{ color: 'var(--brand-500)' }} />
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>总体评价</strong>
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {qualityReview.summary}
                  </p>
                </div>

                {/* 改进建议 */}
                {qualityReview.suggestions?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <TrendingUp size={16} style={{ color: 'var(--warning)' }} />
                      <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>改进建议</strong>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {qualityReview.suggestions.slice(0, 5).map((sugg: string, idx: number) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 10,
                            padding: '10px 12px',
                            borderRadius: 10,
                            background: 'var(--bg-hover)',
                          }}
                        >
                          <span style={{
                            flex: '0 0 auto',
                            width: 20,
                            height: 20,
                            borderRadius: '50%',
                            background: 'var(--warning-soft)',
                            color: 'var(--warning)',
                            display: 'grid',
                            placeItems: 'center',
                            fontSize: 11,
                            fontWeight: 600,
                          }}>
                            {idx + 1}
                          </span>
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                            {sugg}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── AI 味检测 ── */}
      {activeView === 'ai_smell' && (
        <div className="v7-monitor-stack">
          <div className="v7-monitor-grid">
            {/* 柱状图 */}
            <div className="v7-panel">
              <div className="v7-panel-head">
                <div>
                  <h3>七维检测结果</h3>
                  <p style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
                    模式级 AI 味检测，基于文本统计特征
                  </p>
                </div>
                <span className={`v7-chain-badge`} style={{
                  padding: '4px 10px',
                  fontSize: 11,
                  color: aiSmell?.overall_risk === 'high' ? 'var(--danger)' :
                         aiSmell?.overall_risk === 'medium' ? 'var(--warning)' :
                         'var(--success)',
                  background: aiSmell?.overall_risk === 'high' ? 'var(--danger-soft)' :
                              aiSmell?.overall_risk === 'medium' ? 'var(--warning-soft)' :
                              'var(--success-soft)',
                }}>
                  整体：{aiSmell?.overall_risk ? getRiskLabel(aiSmell.overall_risk) : '暂无数据'}
                </span>
              </div>
              <div style={{ height: 340, padding: '0 8px' }}>
                {loadingAiSmell && <LoadingBlock text="加载检测数据..." />}
                {aiSmellError && <ErrorBlock message={aiSmellError} onRetry={loadAiSmell} />}
                {!loadingAiSmell && !aiSmellError && (!aiSmell?.has_data || aiSmell.dimensions?.length === 0) && (
                  <EmptyBlock>暂无检测数据</EmptyBlock>
                )}
                {!loadingAiSmell && !aiSmellError && aiSmell?.has_data && aiSmell.dimensions?.length > 0 && (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={aiSmell.dimensions} layout="vertical" margin={{ left: 10, right: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
                      <XAxis
                        type="number"
                        domain={[0, 100]}
                        tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                        width={90}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 10,
                          fontSize: 12,
                          color: 'var(--text-primary)',
                          boxShadow: 'var(--shadow-card)',
                        }}
                        formatter={(value: any) => [`${Number(value).toFixed(1)}分`, '得分']}
                      />
                      <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={18}>
                        {aiSmell.dimensions.map((entry: any, index: number) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={getRiskTone(entry.risk) === 'danger' ? 'var(--danger)' :
                                  getRiskTone(entry.risk) === 'amber' ? 'var(--warning)' : 'var(--success)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* 风险详情 */}
            <div className="v7-panel">
              <div className="v7-panel-head">
                <h3>风险详情</h3>
                <span className="v7-panel-count">
                  {aiSmell?.dimensions?.length || 0} 个维度
                </span>
              </div>
              <div style={{ padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {loadingAiSmell && <LoadingBlock text="加载中..." />}
                {aiSmellError && <ErrorBlock message={aiSmellError} onRetry={loadAiSmell} />}
                {!loadingAiSmell && !aiSmellError && (!aiSmell?.has_data || aiSmell.dimensions?.length === 0) && (
                  <EmptyBlock>暂无检测数据</EmptyBlock>
                )}
                {!loadingAiSmell && !aiSmellError && aiSmell?.has_data && aiSmell.dimensions?.map((dim: any) => {
                  const tone = getRiskTone(dim.risk);
                  return (
                    <div
                      key={dim.key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 14px',
                        borderRadius: 10,
                        transition: 'background .15s ease',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                          {dim.name}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          实际值：{dim.actual?.toFixed?.(1) ?? dim.actual} {dim.unit || ''}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className={`v7-chain-badge`} style={{
                          padding: '3px 8px',
                          fontSize: 10,
                          color: tone === 'danger' ? 'var(--danger)' :
                                 tone === 'amber' ? 'var(--warning)' :
                                 'var(--success)',
                          background: tone === 'danger' ? 'var(--danger-soft)' :
                                      tone === 'amber' ? 'var(--warning-soft)' :
                                      'var(--success-soft)',
                        }}>
                          {getRiskLabel(dim.risk)}
                        </span>
                        <strong style={{ fontSize: 15, color: 'var(--text-primary)', minWidth: 40, textAlign: 'right' }}>
                          {dim.score}
                        </strong>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 情感弧线 ── */}
      {activeView === 'emotion' && (
        <div className="v7-monitor-stack">
          {/* 情感曲线 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <div>
                <h3>全卷情感曲线</h3>
                <p style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
                  基于文本情感强度的连续变化曲线
                </p>
              </div>
              <span className="v7-panel-count">
                {emotionalArc?.arc?.length || 0} 章
              </span>
            </div>
            <div style={{ height: 320, padding: '0 8px' }}>
              {loadingEmotion && <LoadingBlock text="加载情感数据..." />}
              {emotionError && <ErrorBlock message={emotionError} onRetry={loadEmotionalArc} />}
              {!loadingEmotion && !emotionError && (!emotionalArc?.has_data || emotionalArc.arc?.length === 0) && (
                <EmptyBlock>暂无情感数据</EmptyBlock>
              )}
              {!loadingEmotion && !emotionError && emotionalArc?.has_data && emotionalArc.arc?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={emotionalArc.arc} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="emotionGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--brand-500)" stopOpacity={0.24} />
                        <stop offset="95%" stopColor="var(--brand-500)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis
                      dataKey="chapter"
                      tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                      label={{ value: '章节', position: 'insideBottom', offset: -5, fill: 'var(--text-muted)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 10]}
                      tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                      label={{ value: '情感强度', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 10,
                        fontSize: 12,
                        color: 'var(--text-primary)',
                        boxShadow: 'var(--shadow-card)',
                      }}
                      formatter={(value: any) => [Number(value).toFixed(1), '情感强度']}
                      labelFormatter={(label) => `第 ${label} 章`}
                    />
                    <Line
                      type="monotone"
                      dataKey="emotion_score"
                      stroke="var(--brand-500)"
                      strokeWidth={2.5}
                      dot={{ fill: 'var(--brand-500)', r: 3, strokeWidth: 2, stroke: 'var(--bg-surface)' }}
                      activeDot={{ r: 6, strokeWidth: 2, stroke: 'var(--bg-surface)' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* 异常检测 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>异常检测</h3>
              <span className="v7-panel-count">
                {emotionalArc?.anomalies?.length || 0} 个异常点
              </span>
            </div>
            <div style={{ padding: '4px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {loadingEmotion && <LoadingBlock text="加载中..." />}
              {emotionError && <ErrorBlock message={emotionError} onRetry={loadEmotionalArc} />}
              {!loadingEmotion && !emotionError && (!emotionalArc?.has_data || emotionalArc.anomalies?.length === 0) && (
                <EmptyBlock>情感曲线正常，未检测到异常点</EmptyBlock>
              )}
              {!loadingEmotion && !emotionError && emotionalArc?.has_data && emotionalArc.anomalies?.map((anomaly: any, idx: number) => {
                const tone = getAnomalyTone(anomaly.type);
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                      padding: '14px 16px',
                      borderRadius: 12,
                      background: 'var(--bg-hover)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                        第 {anomaly.chapter} 章
                      </span>
                      <span className={`v7-chain-badge`} style={{
                        padding: '3px 10px',
                        fontSize: 11,
                        color: tone === 'danger' ? 'var(--danger)' :
                               tone === 'amber' ? 'var(--warning)' :
                               'var(--brand-500)',
                        background: tone === 'danger' ? 'var(--danger-soft)' :
                                    tone === 'amber' ? 'var(--warning-soft)' :
                                    'var(--brand-50)',
                      }}>
                        {getAnomalyTypeLabel(anomaly.type)}
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {anomaly.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── 角色出场 ── */}
      {activeView === 'characters' && (
        <div className="v7-monitor-stack">
          {/* 出场统计柱状图 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <div>
                <h3>角色出场统计</h3>
                <p style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
                  Top 10 角色出场次数
                </p>
              </div>
              <span className="v7-panel-count">
                {characterStats?.characters?.length || 0} 个角色
              </span>
            </div>
            <div style={{ height: 300, padding: '0 8px' }}>
              {loadingCharacters && <LoadingBlock text="加载角色数据..." />}
              {charactersError && <ErrorBlock message={charactersError} onRetry={loadCharacterStats} />}
              {!loadingCharacters && !charactersError && (!characterStats?.has_data || characterStats.characters?.length === 0) && (
                <EmptyBlock>暂无角色数据</EmptyBlock>
              )}
              {!loadingCharacters && !charactersError && characterStats?.has_data && characterStats.characters?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={characterStats.characters.slice(0, 10)} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                      height={60}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                      label={{ value: '出场次数', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 10,
                        fontSize: 12,
                        color: 'var(--text-primary)',
                        boxShadow: 'var(--shadow-card)',
                      }}
                    />
                    <Bar
                      dataKey="appearance_count"
                      fill="var(--brand-500)"
                      radius={[6, 6, 0, 0]}
                      name="出场次数"
                      barSize={28}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* 角色详情表格 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>角色详情</h3>
              <span className="v7-panel-count">
                {characterStats?.characters?.length || 0} 个角色
              </span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <th style={{ textAlign: 'left', padding: '12px 16px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>角色名</th>
                    <th style={{ textAlign: 'right', padding: '12px 16px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>出场次数</th>
                    <th style={{ textAlign: 'right', padding: '12px 16px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>字数占比</th>
                    <th style={{ textAlign: 'right', padding: '12px 16px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>最近出场</th>
                    <th style={{ textAlign: 'right', padding: '12px 16px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>遗忘风险</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCharacters && (
                    <tr>
                      <td colSpan={5} style={{ padding: '40px 16px' }}>
                        <LoadingBlock text="加载中..." />
                      </td>
                    </tr>
                  )}
                  {charactersError && (
                    <tr>
                      <td colSpan={5} style={{ padding: '40px 16px' }}>
                        <ErrorBlock message={charactersError} onRetry={loadCharacterStats} />
                      </td>
                    </tr>
                  )}
                  {!loadingCharacters && !charactersError && (!characterStats?.has_data || characterStats.characters?.length === 0) && (
                    <tr>
                      <td colSpan={5} style={{ padding: '40px 16px' }}>
                        <EmptyBlock>暂无角色数据</EmptyBlock>
                      </td>
                    </tr>
                  )}
                  {!loadingCharacters && !charactersError && characterStats?.has_data && characterStats.characters?.map((char: any, idx: number) => {
                    const tone = getRiskTone(char.forget_risk);
                    return (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: '1px solid var(--border-subtle)',
                          transition: 'background .15s ease',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                        <td style={{ padding: '12px 16px', fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                          {char.name}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)', textAlign: 'right' }}>
                          {char.appearance_count}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)', textAlign: 'right' }}>
                          {(char.word_ratio * 100).toFixed(1)}%
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)', textAlign: 'right' }}>
                          第 {char.last_appearance_chapter} 章
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          <span className={`v7-chain-badge`} style={{
                            padding: '3px 8px',
                            fontSize: 10,
                            color: tone === 'danger' ? 'var(--danger)' :
                                   tone === 'amber' ? 'var(--warning)' :
                                   'var(--success)',
                            background: tone === 'danger' ? 'var(--danger-soft)' :
                                        tone === 'amber' ? 'var(--warning-soft)' :
                                        'var(--success-soft)',
                          }}>
                            {getRiskLabel(char.forget_risk)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
