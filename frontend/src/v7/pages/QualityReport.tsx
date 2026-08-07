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
  if (score >= 90) return { label: 'S级', tone: 'indigo' as const };
  if (score >= 80) return { label: 'A级', tone: 'green' as const };
  if (score >= 70) return { label: 'B级', tone: 'amber' as const };
  if (score >= 60) return { label: 'C级', tone: 'amber' as const };
  return { label: 'D级', tone: 'danger' as const };
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

// ============ 组件 ============

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

    if (qualityReview?.has_data && qualityReview.dimensions) {
      overallScore = qualityReview.overall_score || 0;
      dimensionCount = qualityReview.dimensions.length;
      qualityReview.dimensions.forEach((dim: any) => {
        if (dim.score >= 80) advantageCount++;
        if (dim.score < 70) improvementCount++;
      });
    }

    return {
      overallScore,
      advantageCount,
      improvementCount,
      dimensionCount,
    };
  }, [qualityReview]);

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

  // ── 空状态渲染 ──────────────────────────────────────────────────────

  const renderEmptyState = (title: string, description: string) => (
    <div className="v7-empty-state">
      <div className="v7-empty-icon">
        <BookOpen size={32} />
      </div>
      <h4>{title}</h4>
      <p>{description}</p>
    </div>
  );

  // ── 加载状态渲染 ────────────────────────────────────────────────────

  const renderLoading = (text: string = '加载中...') => (
    <div className="v7-loading-state">
      <Loader2 className="v7-spinner" size={24} />
      <p>{text}</p>
    </div>
  );

  // ── 错误状态渲染 ────────────────────────────────────────────────────

  const renderError = (message: string, onRetry: () => void) => (
    <div className="v7-error-state">
      <p>加载失败：{message}</p>
      <button className="v7-btn v7-btn-secondary" onClick={onRetry}>
        重试
      </button>
    </div>
  );

  // ── 主渲染 ──────────────────────────────────────────────────────────

  return (
    <div className="v7-page">
      <div className="v7-page-head">
        <div>
          <p className="v7-kicker">质量审查</p>
          <h2>质量分析看板</h2>
          <p className="v7-page-desc">多维度质量分析与可视化报告</p>
        </div>
        <div className="v7-page-actions" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {/* 章节选择器 */}
          {chapters.length > 0 && (
            <select
              className="v7-select"
              value={currentChapterId || ''}
              onChange={(e) => setCurrentChapterId(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '8px',
                border: '1px solid rgba(99, 102, 241, 0.2)',
                background: 'rgba(30, 27, 75, 0.6)',
                color: '#e0e7ff',
                fontSize: '14px',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              {chapters.map((ch: any) => (
                <option key={ch.id} value={ch.id}>
                  {ch.title || `第${ch.seq || 1}章`}
                </option>
              ))}
            </select>
          )}
          <button className="v7-btn v7-btn-secondary" onClick={refreshCurrent}>
            <RefreshCw size={16} />
            刷新
          </button>
          <button className="v7-btn v7-btn-primary">
            <Brain size={16} />
            运行审查
          </button>
        </div>
      </div>

      {/* 总览指标 */}
      <div className="v7-metric-grid v7-metric-grid-4">
        <div className="v7-metric-card">
          <div className="v7-metric-label">综合评分</div>
          <div className="v7-metric-value">
            {qualityReview?.has_data ? overview.overallScore.toFixed(1) : '--'}
          </div>
          <div className="v7-metric-sub">
            {qualityReview?.has_data ? getScoreLevel(overview.overallScore).label : '暂无数据'}
          </div>
        </div>
        <div className="v7-metric-card v7-tone-green">
          <div className="v7-metric-label">优势维度</div>
          <div className="v7-metric-value">{qualityReview?.has_data ? overview.advantageCount : '--'}</div>
          <div className="v7-metric-sub">80分以上</div>
        </div>
        <div className="v7-metric-card v7-tone-amber">
          <div className="v7-metric-label">待提升</div>
          <div className="v7-metric-value">{qualityReview?.has_data ? overview.improvementCount : '--'}</div>
          <div className="v7-metric-sub">70分以下</div>
        </div>
        <div className="v7-metric-card v7-tone-gray">
          <div className="v7-metric-label">检测维度</div>
          <div className="v7-metric-value">{qualityReview?.has_data ? overview.dimensionCount : '--'}</div>
          <div className="v7-metric-sub">已分析维度</div>
        </div>
      </div>

      {/* 视图切换 */}
      <div className="v7-view-nav">
        {VIEW_ITEMS.map(item => (
          <button
            key={item.key}
            className={`v7-view-tab ${activeView === item.key ? 'active' : ''}`}
            onClick={() => setActiveView(item.key)}
          >
            <item.icon size={16} />
            {item.label}
          </button>
        ))}
      </div>

      {/* ── 深度审查 ── */}
      {activeView === 'depth' && (
        <div className="v7-monitor-grid">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>五维雷达图</h3>
            </div>
            <div className="v7-chart-container" style={{ height: 360 }}>
              {loadingReview && renderLoading('加载中...')}
              {reviewError && renderError(reviewError, loadQualityReview)}
              {!loadingReview && !reviewError && (!qualityReview?.has_data || qualityReview.dimensions?.length === 0) && (
                renderEmptyState('暂无审查数据', '请先运行质量审查生成报告')
              )}
              {!loadingReview && !reviewError && qualityReview?.has_data && qualityReview.dimensions?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={qualityReview.dimensions}>
                    <PolarGrid stroke="#e5e7eb" />
                    <PolarAngleAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 12 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#9ca3af', fontSize: 10 }} />
                    <Radar
                      name="得分"
                      dataKey="score"
                      stroke="#6366f1"
                      fill="#6366f1"
                      fillOpacity={0.25}
                      strokeWidth={2}
                    />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>维度详情</h3>
            </div>
            <div className="v7-dimension-list">
              {loadingReview && renderLoading('加载中...')}
              {reviewError && renderError(reviewError, loadQualityReview)}
              {!loadingReview && !reviewError && (!qualityReview?.has_data || qualityReview.dimensions?.length === 0) && (
                renderEmptyState('暂无审查数据', '请先运行质量审查生成报告')
              )}
              {!loadingReview && !reviewError && qualityReview?.has_data && qualityReview.dimensions?.map((dim: any) => {
                const level = getScoreLevel(dim.score);
                return (
                  <div key={dim.key} className="v7-dimension-row">
                    <div className="v7-dimension-header">
                      <span className="v7-dimension-name">{dim.name}</span>
                      <span className={`v7-dimension-score v7-tone-${level.tone}`}>
                        {dim.score}分
                      </span>
                    </div>
                    <div className="v7-progress-bar">
                      <div
                        className={`v7-progress-fill v7-tone-${level.tone}`}
                        style={{ width: `${dim.score}%` }}
                      />
                    </div>
                    <p className="v7-dimension-comment">{dim.comment}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── AI 味检测 ── */}
      {activeView === 'ai_smell' && (
        <div className="v7-monitor-stack">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>七维检测结果</h3>
              <span className={`v7-risk-badge v7-tone-${aiSmell?.overall_risk ? getRiskTone(aiSmell.overall_risk) : 'gray'}`}>
                整体风险：{aiSmell?.overall_risk ? getRiskLabel(aiSmell.overall_risk) : '暂无数据'}
              </span>
            </div>
            <div className="v7-chart-container" style={{ height: 300 }}>
              {loadingAiSmell && renderLoading('加载中...')}
              {aiSmellError && renderError(aiSmellError, loadAiSmell)}
              {!loadingAiSmell && !aiSmellError && (!aiSmell?.has_data || aiSmell.dimensions?.length === 0) && (
                renderEmptyState('暂无检测数据', '请先运行 AI 味检测')
              )}
              {!loadingAiSmell && !aiSmellError && aiSmell?.has_data && aiSmell.dimensions?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={aiSmell.dimensions} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} width={100} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                      {aiSmell.dimensions.map((entry: any, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={getRiskTone(entry.risk) === 'danger' ? '#ef4444' :
                                getRiskTone(entry.risk) === 'amber' ? '#f59e0b' : '#22c55e'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>风险详情</h3>
              <span className="v7-panel-count">{aiSmell?.dimensions?.length || 0} 个维度</span>
            </div>
            <div className="v7-ai-smell-list">
              {loadingAiSmell && renderLoading('加载中...')}
              {aiSmellError && renderError(aiSmellError, loadAiSmell)}
              {!loadingAiSmell && !aiSmellError && (!aiSmell?.has_data || aiSmell.dimensions?.length === 0) && (
                renderEmptyState('暂无检测数据', '请先运行 AI 味检测')
              )}
              {!loadingAiSmell && !aiSmellError && aiSmell?.has_data && aiSmell.dimensions?.map((dim: any) => (
                <div key={dim.key} className="v7-ai-smell-row">
                  <div className="v7-ai-smell-info">
                    <span className="v7-ai-smell-name">{dim.name}</span>
                    <span className={`v7-risk-badge v7-tone-${getRiskTone(dim.risk)}`}>
                      {getRiskLabel(dim.risk)}
                    </span>
                  </div>
                  <span className="v7-ai-smell-score">{dim.score}分</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 情感弧线 ── */}
      {activeView === 'emotion' && (
        <div className="v7-monitor-stack">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>全卷情感曲线</h3>
            </div>
            <div className="v7-chart-container" style={{ height: 320 }}>
              {loadingEmotion && renderLoading('加载中...')}
              {emotionError && renderError(emotionError, loadEmotionalArc)}
              {!loadingEmotion && !emotionError && (!emotionalArc?.has_data || emotionalArc.arc?.length === 0) && (
                renderEmptyState('暂无情感数据', '请先生成章节内容后再分析')
              )}
              {!loadingEmotion && !emotionError && emotionalArc?.has_data && emotionalArc.arc?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={emotionalArc.arc}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="chapter" tick={{ fill: '#6b7280', fontSize: 11 }} label={{ value: '章节', position: 'insideBottom', offset: -5, fill: '#9ca3af', fontSize: 11 }} />
                    <YAxis domain={[0, 10]} tick={{ fill: '#6b7280', fontSize: 11 }} label={{ value: '情感强度', angle: -90, position: 'insideLeft', fill: '#9ca3af', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(value: any) => [Number(value).toFixed(1), '情感强度']}
                    />
                    <Line
                      type="monotone"
                      dataKey="emotion_score"
                      stroke="#6366f1"
                      strokeWidth={2.5}
                      dot={{ fill: '#6366f1', r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>异常检测</h3>
              <span className="v7-panel-count">{emotionalArc?.anomalies?.length || 0} 个异常点</span>
            </div>
            <div className="v7-anomaly-list">
              {loadingEmotion && renderLoading('加载中...')}
              {emotionError && renderError(emotionError, loadEmotionalArc)}
              {!loadingEmotion && !emotionError && (!emotionalArc?.has_data || emotionalArc.anomalies?.length === 0) && (
                renderEmptyState('暂无异常', '情感曲线正常，未检测到异常点')
              )}
              {!loadingEmotion && !emotionError && emotionalArc?.has_data && emotionalArc.anomalies?.map((anomaly: any, idx: number) => (
                <div key={idx} className="v7-anomaly-row">
                  <div className="v7-anomaly-header">
                    <span className="v7-anomaly-chapter">第 {anomaly.chapter} 章</span>
                    <span className={`v7-anomaly-type v7-tone-${getRiskTone(anomaly.severity)}`}>
                      {getAnomalyTypeLabel(anomaly.type)}
                    </span>
                  </div>
                  <p className="v7-anomaly-desc">{anomaly.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 角色出场 ── */}
      {activeView === 'characters' && (
        <div className="v7-monitor-stack">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>角色出场统计</h3>
              <span className="v7-panel-count">{characterStats?.characters?.length || 0} 个角色</span>
            </div>
            <div className="v7-chart-container" style={{ height: 300 }}>
              {loadingCharacters && renderLoading('加载中...')}
              {charactersError && renderError(charactersError, loadCharacterStats)}
              {!loadingCharacters && !charactersError && (!characterStats?.has_data || characterStats.characters?.length === 0) && (
                renderEmptyState('暂无角色数据', '请先生成章节内容后再分析')
              )}
              {!loadingCharacters && !charactersError && characterStats?.has_data && characterStats.characters?.length > 0 && (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={characterStats.characters.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} label={{ value: '出场次数', angle: -90, position: 'insideLeft', fill: '#9ca3af', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="appearance_count" fill="#6366f1" radius={[4, 4, 0, 0]} name="出场次数" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>角色详情</h3>
            </div>
            <div className="v7-character-table">
              <div className="v7-character-header">
                <span>角色名</span>
                <span>出场次数</span>
                <span>字数占比</span>
                <span>最近出场</span>
                <span>遗忘风险</span>
              </div>
              {loadingCharacters && renderLoading('加载中...')}
              {charactersError && renderError(charactersError, loadCharacterStats)}
              {!loadingCharacters && !charactersError && (!characterStats?.has_data || characterStats.characters?.length === 0) && (
                renderEmptyState('暂无角色数据', '请先生成章节内容后再分析')
              )}
              {!loadingCharacters && !charactersError && characterStats?.has_data && characterStats.characters?.map((char: any, idx: number) => (
                <div key={idx} className="v7-character-row">
                  <span className="v7-character-name">{char.name}</span>
                  <span>{char.appearance_count}</span>
                  <span>{(char.word_ratio * 100).toFixed(1)}%</span>
                  <span>第 {char.last_appearance_chapter} 章</span>
                  <span className={`v7-risk-badge v7-tone-${getRiskTone(char.forget_risk)}`}>
                    {getRiskLabel(char.forget_risk)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
