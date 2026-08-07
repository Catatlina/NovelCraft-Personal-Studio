/**
 * 质量分析看板
 *
 * 专业级质量审查可视化页面，达到 V7 Dashboard 设计水准：
 * - 深色 indigo 主题
 * - 卡片式布局
 * - 专业图表（recharts）
 * - 视觉层次分明
 * - 数据饱满无空白
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

interface QualityReportProps {
  novelId?: string | null;
  chapterNumber?: number;
}

type ReportView = 'depth' | 'ai_smell' | 'emotion' | 'characters';

// ============ Mock 数据 ============

const DEPTH_DIMENSIONS = [
  { key: 'consistency', name: '一致性', score: 85, comment: '跨章事实一致性良好，无明显矛盾' },
  { key: 'character_voice', name: '角色声线', score: 78, comment: '主角辨识度高，配角声线有待加强' },
  { key: 'plot_logic', name: '剧情逻辑', score: 82, comment: '主线逻辑自洽，部分支线转折稍显突兀' },
  { key: 'pacing', name: '节奏把控', score: 75, comment: '爽点分布合理，部分章节节奏偏慢' },
  { key: 'writing_quality', name: '文笔质量', score: 80, comment: '语言流畅，描写生动，偶有AI痕迹' },
];

const AI_SMELL_DIMENSIONS = [
  { key: 'transition_density', name: '转折词密度', score: 72, risk: 'medium' },
  { key: 'opening_repetition', name: '段落首句雷同', score: 85, risk: 'low' },
  { key: 'adverb_density', name: '抽象副词密度', score: 68, risk: 'medium' },
  { key: 'le_density', name: '"了"字密度', score: 78, risk: 'low' },
  { key: 'summary_density', name: '总结句密度', score: 82, risk: 'low' },
  { key: 'dialogue_ellipsis', name: '对话省略比例', score: 75, risk: 'medium' },
  { key: 'rhythm_variance', name: '段落节奏变异', score: 70, risk: 'medium' },
];

const EMOTIONAL_ARC = [
  { chapter: 1, score: 6.5, label: '开局' },
  { chapter: 2, score: 7.2, label: '金手指' },
  { chapter: 3, score: 5.8, label: '低谷' },
  { chapter: 4, score: 8.1, label: '第一次打脸' },
  { chapter: 5, score: 7.5, label: '蓄力' },
  { chapter: 6, score: 9.0, label: '小高潮' },
  { chapter: 7, score: 8.2, label: '余韵' },
  { chapter: 8, score: 7.8, label: '新地图' },
  { chapter: 9, score: 8.5, label: '冲突升级' },
  { chapter: 10, score: 9.2, label: '大高潮' },
];

const EMOTION_ANOMALIES = [
  { type: 'fatigue', chapter: 3, severity: 'medium', description: '情感强度偏低，读者可能产生疲劳感' },
  { type: 'abrupt', chapter: 6, severity: 'low', description: '高潮前蓄力不足，转折稍显突兀' },
  { type: 'depression', chapter: 3, severity: 'low', description: '连续低情绪章节，建议穿插小爽点' },
];

const CHARACTER_DATA = [
  { name: '主角', appearances: 10, wordRatio: 0.35, lastChapter: 10, risk: 'none' },
  { name: '女主角', appearances: 7, wordRatio: 0.20, lastChapter: 10, risk: 'none' },
  { name: '反派', appearances: 6, wordRatio: 0.15, lastChapter: 9, risk: 'low' },
  { name: '导师', appearances: 4, wordRatio: 0.10, lastChapter: 9, risk: 'medium' },
  { name: '朋友A', appearances: 4, wordRatio: 0.08, lastChapter: 10, risk: 'low' },
  { name: '朋友B', appearances: 3, wordRatio: 0.06, lastChapter: 8, risk: 'medium' },
  { name: '路人甲', appearances: 2, wordRatio: 0.03, lastChapter: 6, risk: 'high' },
  { name: '神秘人', appearances: 2, wordRatio: 0.03, lastChapter: 10, risk: 'none' },
];

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
  if (risk === 'high') return 'danger';
  if (risk === 'medium') return 'amber';
  if (risk === 'low') return 'green';
  return 'gray';
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(0)}%`;
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

// ============ 视图组件 ============

function DepthReviewView() {
  const overallScore = Math.round(DEPTH_DIMENSIONS.reduce((sum, d) => sum + d.score, 0) / DEPTH_DIMENSIONS.length);
  const level = getScoreLevel(overallScore);

  const radarData = DEPTH_DIMENSIONS.map(d => ({
    name: d.name,
    score: d.score,
    fullMark: 100,
  }));

  return (
    <div className="v7-monitor-stack">
      <div className="v7-metric-grid">
        <MetricCard
          icon={TrendingUp}
          label="综合评分"
          value={`${overallScore}分`}
          detail={`${level.label} · 五维加权平均`}
          tone={level.tone}
        />
        <MetricCard
          icon={CheckCircle2}
          label="优势维度"
          value="一致性"
          detail="85分 · 跨章事实无矛盾"
          tone="green"
        />
        <MetricCard
          icon={AlertTriangle}
          label="待提升"
          value="节奏把控"
          detail="75分 · 部分章节偏慢"
          tone="amber"
        />
        <MetricCard
          icon={Brain}
          label="检测维度"
          value="5维"
          detail="深度审查全覆盖"
          tone="gray"
        />
      </div>

      <div className="v7-monitor-grid">
        <section className="v7-panel">
          <div className="v7-panel-head">
            <div><p className="v7-kicker">雷达图</p><h3>五维深度审查</h3></div>
            <span className="v7-panel-count">满分 100</span>
          </div>
          <div className="v7-chart-container">
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e0e7ff" />
                <PolarAngleAxis dataKey="name" tick={{ fill: '#6366f1', fontSize: 12 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Radar
                  name="得分"
                  dataKey="score"
                  stroke="#6366f1"
                  fill="#6366f1"
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e0e7ff',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="v7-panel">
          <div className="v7-panel-head">
            <div><p className="v7-kicker">维度详情</p><h3>各维度得分与评语</h3></div>
            <span className="v7-panel-count">{DEPTH_DIMENSIONS.length} 项</span>
          </div>
          <div className="v7-dimension-list">
            {DEPTH_DIMENSIONS.map(dim => {
              const dimLevel = getScoreLevel(dim.score);
              return (
                <div key={dim.key} className="v7-dimension-row">
                  <div className="v7-dimension-header">
                    <span className="v7-dimension-name">{dim.name}</span>
                    <span className={`v7-dimension-score v7-tone-${dimLevel.tone}`}>
                      {dim.score}分
                    </span>
                  </div>
                  <div className="v7-progress-bar">
                    <div
                      className={`v7-progress-fill v7-tone-${dimLevel.tone}`}
                      style={{ width: `${dim.score}%` }}
                    />
                  </div>
                  <p className="v7-dimension-comment">{dim.comment}</p>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

function AiSmellView() {
  const overallScore = Math.round(AI_SMELL_DIMENSIONS.reduce((sum, d) => sum + d.score, 0) / AI_SMELL_DIMENSIONS.length);
  const level = getScoreLevel(overallScore);

  const barData = AI_SMELL_DIMENSIONS.map(d => ({
    name: d.name,
    score: d.score,
    risk: d.risk,
  }));

  const getBarColor = (risk: string) => {
    if (risk === 'high') return '#ef4444';
    if (risk === 'medium') return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="v7-monitor-stack">
      <div className="v7-metric-grid">
        <MetricCard
          icon={Sparkles}
          label="AI 味综合评分"
          value={`${overallScore}分`}
          detail={`${level.label} · 分数越高越像人类`}
          tone={level.tone}
        />
        <MetricCard
          icon={CheckCircle2}
          label="低风险维度"
          value="4项"
          detail="无明显AI痕迹"
          tone="green"
        />
        <MetricCard
          icon={AlertTriangle}
          label="中风险维度"
          value="3项"
          detail="建议针对性优化"
          tone="amber"
        />
        <MetricCard
          icon={XCircle}
          label="高风险维度"
          value="0项"
          detail="无严重AI痕迹"
          tone="gray"
        />
      </div>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">柱状图</p><h3>七维 AI 味检测</h3></div>
          <span className="v7-panel-count">分数越高越好</span>
        </div>
        <div className="v7-chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#6366f1', fontSize: 12 }}
                width={100}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e0e7ff',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value: any) => [`${value}分`, '得分']}
              />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {barData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getBarColor(entry.risk)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">风险等级</p><h3>各维度详情</h3></div>
          <span className="v7-panel-count">7 项检测</span>
        </div>
        <div className="v7-ai-smell-list">
          {AI_SMELL_DIMENSIONS.map(dim => (
            <div key={dim.key} className="v7-ai-smell-row">
              <div className="v7-ai-smell-info">
                <span className="v7-ai-smell-name">{dim.name}</span>
                <span className={`v7-risk-badge v7-tone-${getRiskTone(dim.risk)}`}>
                  {dim.risk === 'high' ? '高风险' : dim.risk === 'medium' ? '中风险' : '低风险'}
                </span>
              </div>
              <div className="v7-ai-smell-score">
                <strong>{dim.score}</strong>
                <span>分</span>
              </div>
            </div>
          ))}
        </div>
        <p className="v7-panel-note">
          <Sparkles size={14} /> 检测基于统计模式识别，仅供参考；最终质量以人工审阅为准。
        </p>
      </section>
    </div>
  );
}

function EmotionArcView() {
  const peak = EMOTIONAL_ARC.reduce((max, d) => d.score > max.score ? d : max, EMOTIONAL_ARC[0]);
  const valley = EMOTIONAL_ARC.reduce((min, d) => d.score < min.score ? d : min, EMOTIONAL_ARC[0]);
  const avg = Math.round(EMOTIONAL_ARC.reduce((sum, d) => sum + d.score, 0) / EMOTIONAL_ARC.length * 10) / 10;

  return (
    <div className="v7-monitor-stack">
      <div className="v7-metric-grid">
        <MetricCard
          icon={TrendingUp}
          label="情感峰值"
          value={String(peak.score)}
          detail={`第${peak.chapter}章 · ${peak.label}`}
          tone="green"
        />
        <MetricCard
          icon={AlertTriangle}
          label="情感低谷"
          value={String(valley.score)}
          detail={`第${valley.chapter}章 · ${valley.label}`}
          tone="amber"
        />
        <MetricCard
          icon={Activity}
          label="平均强度"
          value={String(avg)}
          detail={`${EMOTIONAL_ARC.length}章平均`}
          tone="indigo"
        />
        <MetricCard
          icon={GitBranch}
          label="异常检测"
          value={`${EMOTION_ANOMALIES.length}处`}
          detail="需要关注的波动点"
          tone="amber"
        />
      </div>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">折线图</p><h3>全卷情感弧线</h3></div>
          <span className="v7-panel-count">强度 1-10</span>
        </div>
        <div className="v7-chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={EMOTIONAL_ARC}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
              <XAxis
                dataKey="chapter"
                tick={{ fill: '#6366f1', fontSize: 12 }}
                label={{ value: '章节', position: 'insideBottom', offset: -5, fill: '#94a3b8' }}
              />
              <YAxis
                domain={[0, 10]}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                label={{ value: '情感强度', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e0e7ff',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value: any, _name: any, props: any) => [
                  `${value} · ${props.payload.label}`,
                  '情感强度'
                ]}
                labelFormatter={(label: any) => `第${label}章`}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#6366f1"
                strokeWidth={3}
                dot={{ fill: '#6366f1', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, fill: '#4f46e5' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">异常检测</p><h3>需要关注的波动点</h3></div>
          <span className="v7-panel-count">{EMOTION_ANOMALIES.length} 处</span>
        </div>
        {!EMOTION_ANOMALIES.length ? (
          <EmptyBlock>未检测到明显异常</EmptyBlock>
        ) : (
          <div className="v7-anomaly-list">
            {EMOTION_ANOMALIES.map((anomaly, i) => (
              <div key={i} className={`v7-anomaly-row v7-tone-${getRiskTone(anomaly.severity)}`}>
                <div className="v7-anomaly-header">
                  <span className="v7-anomaly-chapter">第 {anomaly.chapter} 章</span>
                  <span className="v7-anomaly-type">
                    {anomaly.type === 'fatigue' ? '读者疲劳' :
                     anomaly.type === 'abrupt' ? '转折突兀' : '情绪压抑'}
                  </span>
                </div>
                <p className="v7-anomaly-desc">{anomaly.description}</p>
              </div>
            ))}
          </div>
        )}
        <p className="v7-panel-note">
          <Activity size={14} /> 情感弧线基于读者体验模型计算，用于辅助节奏调整。
        </p>
      </section>
    </div>
  );
}

function CharacterBalanceView() {
  const totalWords = CHARACTER_DATA.reduce((sum, c) => sum + c.wordRatio, 0);
  const mainCharRatio = CHARACTER_DATA[0].wordRatio;
  const atRiskCount = CHARACTER_DATA.filter(c => c.risk !== 'none').length;

  const barData = CHARACTER_DATA.map(c => ({
    name: c.name,
    出场次数: c.appearances,
    字数占比: Math.round(c.wordRatio * 100),
  }));

  return (
    <div className="v7-monitor-stack">
      <div className="v7-metric-grid">
        <MetricCard
          icon={Users}
          label="角色总数"
          value={String(CHARACTER_DATA.length)}
          detail="有出场记录的角色"
          tone="indigo"
        />
        <MetricCard
          icon={TrendingUp}
          label="主角占比"
          value={formatPercent(mainCharRatio)}
          detail={mainCharRatio > 0.4 ? '偏高，建议增加配角戏份' : '比例合理'}
          tone={mainCharRatio > 0.4 ? 'amber' : 'green'}
        />
        <MetricCard
          icon={AlertTriangle}
          label="遗忘风险"
          value={`${atRiskCount}个`}
          detail="中高风险角色"
          tone="amber"
        />
        <MetricCard
          icon={CheckCircle2}
          label="平衡度"
          value="良好"
          detail="群像结构基本合理"
          tone="green"
        />
      </div>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">柱状图</p><h3>角色出场次数统计</h3></div>
          <span className="v7-panel-count">共 {CHARACTER_DATA.length} 个角色</span>
        </div>
        <div className="v7-chart-container">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e7ff" />
              <XAxis dataKey="name" tick={{ fill: '#6366f1', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e0e7ff',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Bar dataKey="出场次数" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="字数占比" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="v7-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">角色详情</p><h3>出场统计与遗忘风险</h3></div>
          <span className="v7-panel-count">按出场次数排序</span>
        </div>
        <div className="v7-character-table">
          <div className="v7-character-header">
            <span>角色</span>
            <span>出场次数</span>
            <span>字数占比</span>
            <span>最近出场</span>
            <span>遗忘风险</span>
          </div>
          {CHARACTER_DATA.map(char => (
            <div key={char.name} className="v7-character-row">
              <span className="v7-character-name">{char.name}</span>
              <span>{char.appearances} 章</span>
              <span>{formatPercent(char.wordRatio)}</span>
              <span>第 {char.lastChapter} 章</span>
              <span className={`v7-risk-badge v7-tone-${getRiskTone(char.risk)}`}>
                {char.risk === 'high' ? '高风险' :
                 char.risk === 'medium' ? '中风险' :
                 char.risk === 'low' ? '低风险' : '无'}
              </span>
            </div>
          ))}
        </div>
        <p className="v7-panel-note">
          <Users size={14} /> 遗忘风险基于连续未出场章数和角色重要性综合评估。
        </p>
      </section>
    </div>
  );
}

// ============ 主组件 ============

export default function QualityReport({ novelId, chapterNumber }: QualityReportProps) {
  const [view, setView] = useState<ReportView>('depth');
  const [loading, setLoading] = useState(false);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    setTimeout(() => setLoading(false), 800);
  }, []);

  const viewTitle = useMemo(
    () => VIEW_ITEMS.find(item => item.key === view)?.label || '深度审查',
    [view]
  );

  return (
    <div className="v7-monitor page-enter">
      <header className="v7-monitor-head">
        <div>
          <p className="v7-kicker">质量分析 · {viewTitle}</p>
          <h2>质量分析看板</h2>
          <p>
            多维度可视化质量审查报告，包含深度审查、AI 味检测、情感弧线和角色出场平衡。
            {chapterNumber && ` 当前查看：第 ${chapterNumber} 章`}
          </p>
        </div>
        <div className="v7-monitor-head-actions">
          <span className="v7-chain-badge"><BarChart3 size={14} /> 可视化报告</span>
          <button
            type="button"
            className="v7-refresh-button"
            onClick={handleRefresh}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'v7-spin' : undefined} /> 刷新
          </button>
        </div>
      </header>

      <nav className="v7-view-nav" aria-label="质量分析视图">
        {VIEW_ITEMS.map(item => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              key={item.key}
              className={view === item.key ? 'active' : ''}
              aria-selected={view === item.key}
              role="tab"
              onClick={() => setView(item.key)}
            >
              <Icon size={16} />
              <span><strong>{item.label}</strong><small>{item.description}</small></span>
            </button>
          );
        })}
      </nav>

      {!novelId ? (
        <section className="v7-panel v7-empty-panel">
          <div className="v7-access-icon"><BarChart3 size={22} /></div>
          <h3>先选择一本小说</h3>
          <p>质量分析数据按作品隔离。请先在书库选择作品，再查看可视化报告。</p>
        </section>
      ) : loading ? (
        <section className="v7-panel v7-loading-panel"><span className="spinner" /> 正在加载质量数据…</section>
      ) : (
        <>
          {view === 'depth' && <DepthReviewView />}
          {view === 'ai_smell' && <AiSmellView />}
          {view === 'emotion' && <EmotionArcView />}
          {view === 'characters' && <CharacterBalanceView />}
        </>
      )}
    </div>
  );
}
