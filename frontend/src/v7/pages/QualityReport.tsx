/**
 * 审查报告可视化页面
 *
 * 展示质量审查的各种可视化图表：
 * - 深度审查5维雷达图
 * - AI味7维评分柱状图
 * - 情感弧线折线图
 * - 角色出场时间热力图
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart3,
  LineChart,
  PieChart,
  Radar,
  Sparkles,
  Users,
} from 'lucide-react';

interface QualityReportProps {
  novelId?: string | null;
  chapterNumber?: number;
}

type ReportTab = 'radar' | 'ai_smell' | 'emotion' | 'characters';

// 模拟数据
const MOCK_DIMENSION_SCORES = {
  爽感: 85,
  节奏: 78,
  剧情: 82,
  人物: 75,
  文笔: 80,
};

const MOCK_AI_SMELL_SCORES = {
  转折词密度: 72,
  段落首句雷同: 85,
  抽象副词密度: 68,
  '了'字密度: 78,
  总结句密度: 82,
  对话省略比例: 75,
  段落节奏变异: 70,
};

const MOCK_EMOTIONAL_ARC = [
  { chapter: 1, score: 6.5 },
  { chapter: 2, score: 7.2 },
  { chapter: 3, score: 5.8 },
  { chapter: 4, score: 8.1 },
  { chapter: 5, score: 7.5 },
  { chapter: 6, score: 9.0 },
  { chapter: 7, score: 8.2 },
  { chapter: 8, score: 7.8 },
  { chapter: 9, score: 8.5 },
  { chapter: 10, score: 9.2 },
];

const MOCK_CHARACTER_APPEARANCES = [
  { name: '主角', chapters: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], wordRatio: 0.35 },
  { name: '女主角', chapters: [1, 2, 4, 5, 7, 8, 10], wordRatio: 0.20 },
  { name: '反派', chapters: [2, 3, 5, 6, 8, 9], wordRatio: 0.15 },
  { name: '导师', chapters: [1, 3, 6, 9], wordRatio: 0.10 },
  { name: '朋友A', chapters: [2, 4, 7, 10], wordRatio: 0.08 },
  { name: '朋友B', chapters: [3, 5, 8], wordRatio: 0.06 },
  { name: '路人甲', chapters: [1, 6], wordRatio: 0.03 },
  { name: '神秘人', chapters: [5, 10], wordRatio: 0.03 },
];

const TAB_ITEMS: Array<{ key: ReportTab; label: string; icon: typeof Radar }> = [
  { key: 'radar', label: '深度审查', icon: Radar },
  { key: 'ai_smell', label: 'AI味检测', icon: Sparkles },
  { key: 'emotion', label: '情感弧线', icon: LineChart },
  { key: 'characters', label: '角色出场', icon: Users },
];

export default function QualityReport({ novelId, chapterNumber }: QualityReportProps) {
  const [activeTab, setActiveTab] = useState<ReportTab>('radar');
  const [loading, setLoading] = useState(false);

  // 计算总体评分
  const overallScore = useMemo(() => {
    const scores = Object.values(MOCK_DIMENSION_SCORES);
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  }, []);

  // 获取评分等级
  const getScoreLevel = (score: number) => {
    if (score >= 90) return { label: 'S级', color: 'text-purple-600', bg: 'bg-purple-50' };
    if (score >= 80) return { label: 'A级', color: 'text-green-600', bg: 'bg-green-50' };
    if (score >= 70) return { label: 'B级', color: 'text-blue-600', bg: 'bg-blue-50' };
    if (score >= 60) return { label: 'C级', color: 'text-yellow-600', bg: 'bg-yellow-50' };
    return { label: 'D级', color: 'text-red-600', bg: 'bg-red-50' };
  };

  const level = getScoreLevel(overallScore);

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-600" />
          <h2 className="font-semibold text-gray-800">质量审查报告</h2>
          {chapterNumber && (
            <span className="text-sm text-gray-500">第 {chapterNumber} 章</span>
          )}
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-semibold ${level.bg} ${level.color}`}>
          {overallScore}分 · {level.label}
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="flex border-b overflow-x-auto">
        {TAB_ITEMS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.key
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
              onClick={() => setActiveTab(tab.key)}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-4">
        {/* 深度审查雷达图 */}
        {activeTab === 'radar' && (
          <div>
            <div className="mb-4">
              <h3 className="font-medium text-gray-800 mb-1">五维深度审查</h3>
              <p className="text-sm text-gray-500">从爽感、节奏、剧情、人物、文笔五个维度综合评估</p>
            </div>

            {/* 简易雷达图（用 CSS 实现） */}
            <div className="flex justify-center mb-6">
              <div className="relative w-64 h-64">
                {/* 背景同心圆 */}
                {[1, 0.75, 0.5, 0.25].map((scale, i) => (
                  <div
                    key={i}
                    className="absolute border border-gray-200 rounded-full"
                    style={{
                      width: `${scale * 100}%`,
                      height: `${scale * 100}%`,
                      left: `${(1 - scale) * 50}%`,
                      top: `${(1 - scale) * 50}%`,
                    }}
                  />
                ))}
                {/* 五边形网格线 */}
                {Object.keys(MOCK_DIMENSION_SCORES).map((_, i) => {
                  const angle = (i * 72 - 90) * (Math.PI / 180);
                  const x = 50 + 50 * Math.cos(angle);
                  const y = 50 + 50 * Math.sin(angle);
                  return (
                    <div
                      key={i}
                      className="absolute bg-gray-200"
                      style={{
                        width: '1px',
                        height: '50%',
                        left: '50%',
                        top: '50%',
                        transformOrigin: 'top center',
                        transform: `rotate(${i * 72}deg)`,
                      }}
                    />
                  );
                })}
                {/* 数据多边形（简化版） */}
                <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100">
                  <polygon
                    points={Object.entries(MOCK_DIMENSION_SCORES).map(([_, score], i) => {
                      const angle = (i * 72 - 90) * (Math.PI / 180);
                      const r = (score / 100) * 45;
                      const x = 50 + r * Math.cos(angle);
                      const y = 50 + r * Math.sin(angle);
                      return `${x},${y}`;
                    }).join(' ')}
                    fill="rgba(59, 130, 246, 0.2)"
                    stroke="rgb(59, 130, 246)"
                    strokeWidth="1"
                  />
                </svg>
                {/* 维度标签 */}
                {Object.entries(MOCK_DIMENSION_SCORES).map(([name, score], i) => {
                  const angle = (i * 72 - 90) * (Math.PI / 180);
                  const r = 55;
                  const x = 50 + r * Math.cos(angle);
                  const y = 50 + r * Math.sin(angle);
                  return (
                    <div
                      key={name}
                      className="absolute text-xs font-medium text-gray-600 -translate-x-1/2 -translate-y-1/2"
                      style={{ left: `${x}%`, top: `${y}%` }}
                    >
                      {name}
                      <div className="text-center text-blue-600 font-semibold">{score}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 各维度详情 */}
            <div className="space-y-3">
              {Object.entries(MOCK_DIMENSION_SCORES).map(([name, score]) => {
                const dimLevel = getScoreLevel(score);
                return (
                  <div key={name} className="flex items-center gap-3">
                    <div className="w-16 text-sm text-gray-600">{name}</div>
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          score >= 80 ? 'bg-green-500' :
                          score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    <div className={`w-12 text-right text-sm font-semibold ${dimLevel.color}`}>
                      {score}分
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AI味检测柱状图 */}
        {activeTab === 'ai_smell' && (
          <div>
            <div className="mb-4">
              <h3 className="font-medium text-gray-800 mb-1">7维AI味检测</h3>
              <p className="text-sm text-gray-500">检测文本的AI生成痕迹，分数越高越像人类写作</p>
            </div>

            <div className="mb-4 p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">AI味综合评分</span>
                <span className="text-lg font-bold text-blue-600">76分</span>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                总体表现良好，部分维度仍有优化空间
              </div>
            </div>

            {/* 柱状图 */}
            <div className="space-y-4">
              {Object.entries(MOCK_AI_SMELL_SCORES).map(([name, score], i) => (
                <div key={name}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-700">{name}</span>
                    <span className={`text-sm font-semibold ${
                      score >= 80 ? 'text-green-600' :
                      score >= 60 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {score}分
                    </span>
                  </div>
                  <div className="h-6 bg-gray-100 rounded overflow-hidden">
                    <div
                      className={`h-full rounded transition-all flex items-center justify-end pr-2 ${
                        score >= 80 ? 'bg-green-500' :
                        score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${score}%` }}
                    >
                      {score >= 30 && (
                        <span className="text-xs text-white font-medium">{score}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* 阈值说明 */}
            <div className="mt-6 p-3 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-green-500 rounded" />
                  <span>≥80分：优秀，基本无AI痕迹</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-yellow-500 rounded" />
                  <span>60-79分：良好，轻微AI痕迹</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-red-500 rounded" />
                  <span>＜60分：较差，明显AI痕迹</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 情感弧线折线图 */}
        {activeTab === 'emotion' && (
          <div>
            <div className="mb-4">
              <h3 className="font-medium text-gray-800 mb-1">情感弧线</h3>
              <p className="text-sm text-gray-500">各章节情感强度变化曲线</p>
            </div>

            {/* 弧线统计 */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="p-3 bg-green-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 mb-1">最高峰</div>
                <div className="text-lg font-bold text-green-600">9.2</div>
                <div className="text-xs text-gray-500">第10章</div>
              </div>
              <div className="p-3 bg-red-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 mb-1">最低谷</div>
                <div className="text-lg font-bold text-red-600">5.8</div>
                <div className="text-xs text-gray-500">第3章</div>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 mb-1">平均分</div>
                <div className="text-lg font-bold text-blue-600">7.8</div>
                <div className="text-xs text-gray-500">10章</div>
              </div>
            </div>

            {/* 折线图（SVG 实现） */}
            <div className="bg-white border rounded-lg p-4 mb-4">
              <svg viewBox="0 0 400 200" className="w-full h-48">
                {/* 网格线 */}
                {[0, 25, 50, 75, 100].map(y => (
                  <line
                    key={y}
                    x1="40"
                    y1={20 + (1 - y / 100) * 160}
                    x2="380"
                    y2={20 + (1 - y / 100) * 160}
                    stroke="#f3f4f6"
                    strokeWidth="1"
                  />
                ))}
                {/* Y轴标签 */}
                {[10, 7.5, 5, 2.5, 0].map((val, i) => (
                  <text
                    key={val}
                    x="35"
                    y={25 + i * 40}
                    textAnchor="end"
                    className="text-xs fill-gray-400"
                  >
                    {val}
                  </text>
                ))}
                {/* X轴标签 */}
                {MOCK_EMOTIONAL_ARC.filter((_, i) => i % 2 === 0).map((d) => (
                  <text
                    key={d.chapter}
                    x={40 + (d.chapter - 1) / 9 * 340}
                    y="195"
                    textAnchor="middle"
                    className="text-xs fill-gray-400"
                  >
                    第{d.chapter}章
                  </text>
                ))}
                {/* 折线 */}
                <polyline
                  points={MOCK_EMOTIONAL_ARC.map((d, i) => {
                    const x = 40 + i / 9 * 340;
                    const y = 20 + (1 - d.score / 10) * 160;
                    return `${x},${y}`;
                  }).join(' ')}
                  fill="none"
                  stroke="rgb(59, 130, 246)"
                  strokeWidth="2"
                />
                {/* 数据点 */}
                {MOCK_EMOTIONAL_ARC.map((d, i) => {
                  const x = 40 + i / 9 * 340;
                  const y = 20 + (1 - d.score / 10) * 160;
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r="4"
                      fill="white"
                      stroke="rgb(59, 130, 246)"
                      strokeWidth="2"
                    />
                  );
                })}
              </svg>
            </div>

            {/* 异常检测 */}
            <div className="p-3 bg-yellow-50 rounded-lg">
              <div className="text-sm font-medium text-yellow-800 mb-2">异常检测</div>
              <div className="space-y-2 text-xs text-yellow-700">
                <div className="flex items-start gap-2">
                  <span className="text-yellow-500">⚠</span>
                  <span>第3章情感强度偏低（5.8），建议增加冲突或爽点</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-yellow-500">⚠</span>
                  <span>第6章高潮前蓄力不足，建议提前铺垫</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 角色出场热力图 */}
        {activeTab === 'characters' && (
          <div>
            <div className="mb-4">
              <h3 className="font-medium text-gray-800 mb-1">角色出场分布</h3>
              <p className="text-sm text-gray-500">各角色在不同章节的出场情况</p>
            </div>

            {/* 热力图 */}
            <div className="overflow-x-auto mb-4">
              <div className="min-w-max">
                {/* 表头 */}
                <div className="flex border-b">
                  <div className="w-24 py-2 text-xs text-gray-500 font-medium">角色</div>
                  {Array.from({ length: 10 }, (_, i) => (
                    <div key={i} className="w-10 py-2 text-center text-xs text-gray-500">
                      {i + 1}
                    </div>
                  ))}
                  <div className="w-16 py-2 text-center text-xs text-gray-500">占比</div>
                </div>
                {/* 数据行 */}
                {MOCK_CHARACTER_APPEARANCES.map(char => (
                  <div key={char.name} className="flex border-b hover:bg-gray-50">
                    <div className="w-24 py-2 text-sm text-gray-700 truncate px-2">
                      {char.name}
                    </div>
                    {Array.from({ length: 10 }, (_, i) => {
                      const appeared = char.chapters.includes(i + 1);
                      return (
                        <div key={i} className="w-10 py-2 flex justify-center items-center">
                          <div
                            className={`w-6 h-6 rounded ${
                              appeared
                                ? 'bg-blue-500'
                                : 'bg-gray-100'
                            }`}
                            title={appeared ? `第${i + 1}章出场` : '未出场'}
                          />
                        </div>
                      );
                    })}
                    <div className="w-16 py-2 text-center text-sm text-gray-600">
                      {(char.wordRatio * 100).toFixed(0)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 遗忘风险 */}
            <div className="p-3 bg-orange-50 rounded-lg">
              <div className="text-sm font-medium text-orange-800 mb-2">遗忘风险提示</div>
              <div className="space-y-2 text-xs text-orange-700">
                <div className="flex items-start gap-2">
                  <span className="text-orange-500">⚠</span>
                  <span>「神秘人」已连续4章未出场（第6-9章），有被读者遗忘的风险</span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-orange-500">⚠</span>
                  <span>「路人甲」出场过少，建议增加戏份或合并角色</span>
                </div>
              </div>
            </div>

            {/* 角色平衡 */}
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <div className="text-sm font-medium text-gray-700 mb-2">出场平衡度</div>
              <div className="text-xs text-gray-500">
                主角占比 35%，略偏高。建议适当增加配角戏份，丰富群像描写。
              </div>
              <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden flex">
                <div className="bg-blue-500" style={{ width: '35%' }} title="主角" />
                <div className="bg-purple-500" style={{ width: '20%' }} title="女主角" />
                <div className="bg-red-500" style={{ width: '15%' }} title="反派" />
                <div className="bg-green-500" style={{ width: '30%' }} title="其他" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
