/**
 * 品类管理页面
 *
 * 专业级品类库管理页面，达到 V7 Dashboard 设计水准：
 * - 三栏布局（品类树 / 详情 / 规则对比）
 * - 深色 indigo 主题
 * - 卡片式布局
 * - 视觉层次分明
 * - 真实 API 数据，无 mock
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Download,
  GitCompare,
  Layers,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Upload,
  Loader2,
} from 'lucide-react';
import brainApi from '../api/client';

interface GenrePack {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  scope: string;
  is_builtin: boolean;
  is_active: boolean;
  parent_id: string | null;
  icon_url: string | null;
  extra_metadata?: any;
  created_at?: string;
  updated_at?: string;
  children?: GenrePack[];
}

interface GenreRule {
  id: string;
  genre_id: string;
  rule_type: string;
  rule_key: string;
  rule_value: any;
  severity: string;
  priority: number;
  description: string | null;
  is_active: boolean;
  inherited_from: string | null;
}

interface GenreKnowledge {
  id: string;
  genre_id: string;
  knowledge_type: string;
  title: string;
  content: string;
  tags: string[];
  priority: number;
  is_active: boolean;
  inherited_from: string | null;
}

interface GenreManagerProps {
  novelId?: string | null;
}

type DetailTab = 'style' | 'quality' | 'forbidden';

// ============ 常量 ============

const SCOPE_LABELS: Record<string, string> = {
  webnovel: '通用网文',
  fanqie: '番茄小说',
  qidian: '起点中文网',
  jjwxc: '晋江文学城',
  custom: '自定义',
};

const RULE_TYPE_LABELS: Record<string, string> = {
  style: '风格',
  forbidden: '禁止',
  required: '要求',
  quality_threshold: '质量阈值',
  ai_smell_threshold: 'AI味阈值',
  payoff: '爽点',
  pacing: '节奏',
  chapter_basic: '章节基础',
  style_card: '风格卡',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  warning: '#eab308',
  info: '#3b82f6',
};

// ============ 风格卡字段映射 ============

const STYLE_FIELD_LABELS: Record<string, string> = {
  tone: '基调',
  pacing: '节奏',
  dialogue_ratio: '对话占比',
  payoff_density: '爽点密度',
  conflict_intensity: '冲突强度',
  narrative_style: '叙事风格',
  perspective: '视角',
  tense: '时态',
  sentence_length: '句长',
  vocabulary_level: '词汇难度',
};

const STYLE_VALUE_LABELS: Record<string, Record<string, string>> = {
  tone: {
    strong: '强',
    medium: '中',
    soft: '弱',
    passionate: '激昂',
    calm: '平静',
    humorous: '幽默',
    serious: '严肃',
  },
  pacing: {
    fast: '快',
    medium: '中',
    slow: '慢',
  },
  payoff_density: {
    high: '高',
    medium: '中',
    low: '低',
  },
  conflict_intensity: {
    high: '强',
    medium: '中',
    low: '弱',
  },
  narrative_style: {
    straightforward: '直白',
    literary: '文艺',
    colloquial: '口语化',
  },
  perspective: {
    first_person: '第一人称',
    third_person_limited: '第三人称有限',
    third_person_omniscient: '第三人称全知',
  },
  tense: {
    past: '过去时',
    present: '现在时',
  },
  sentence_length: {
    short: '短句',
    medium: '中句',
    long: '长句',
    mixed: '混合',
  },
  vocabulary_level: {
    simple: '简单',
    medium: '中等',
    advanced: '高级',
  },
};

// ============ 质量门禁字段映射 ============

const QUALITY_FIELD_LABELS: Record<string, string> = {
  ai_smell_score: 'AI味得分',
  overall_score: '综合得分',
  paragraph_rhythm_cv: '段落节奏变异',
  transition_word_density: '转折词密度',
  paragraph_opening_repeat: '段落首句雷同',
  le_word_density: '"了"字密度',
  summary_sentence_density: '总结句密度',
  dialogue_omit_ratio: '对话省略比例',
  abstract_adverb_density: '抽象副词密度',
  min_chapter_words: '最小章节字数',
  max_chapter_words: '最大章节字数',
  min_characters: '最少角色数',
  max_characters: '最多角色数',
};

// ============ 辅助函数 ============

function formatStyleValue(value: any): React.ReactNode {
  if (typeof value !== 'object' || value === null) {
    return String(value);
  }

  const entries = Object.entries(value);
  if (entries.length === 0) {
    return '无';
  }

  return (
    <div className="v7-style-card-fields">
      {entries.map(([key, val]) => {
        const label = STYLE_FIELD_LABELS[key] || key;
        let displayValue: React.ReactNode = String(val);
        
        // 检查是否有预设的文本标签
        if (typeof val === 'string' && STYLE_VALUE_LABELS[key]?.[val]) {
          displayValue = STYLE_VALUE_LABELS[key][val];
        }
        
        // 百分比处理
        if (key.includes('ratio') || key.includes('density')) {
          if (typeof val === 'number') {
            displayValue = `${Math.round(val * 100)}%`;
          } else if (typeof val === 'string' && !isNaN(parseFloat(val))) {
            displayValue = `${Math.round(parseFloat(val) * 100)}%`;
          }
        }

        return (
          <div key={key} className="v7-style-field">
            <span className="v7-style-field-label">{label}</span>
            <span className="v7-style-field-value">{displayValue}</span>
          </div>
        );
      })}
    </div>
  );
}

function formatQualityValue(value: any): React.ReactNode {
  if (typeof value !== 'object' || value === null) {
    return String(value);
  }

  const entries = Object.entries(value);
  if (entries.length === 0) {
    return '无';
  }

  return (
    <div className="v7-quality-fields">
      {entries.map(([key, val]) => {
        const label = QUALITY_FIELD_LABELS[key] || key;
        return (
          <div key={key} className="v7-quality-field">
            <span className="v7-quality-field-label">{label}</span>
            <span className="v7-quality-field-value">{String(val)}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function GenreManager({ novelId }: GenreManagerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenreId, setSelectedGenreId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('style');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // 数据状态
  const [genreTree, setGenreTree] = useState<any[]>([]);
  const [allGenres, setAllGenres] = useState<GenrePack[]>([]);
  const [selectedGenre, setSelectedGenre] = useState<GenrePack | null>(null);
  const [parentGenre, setParentGenre] = useState<GenrePack | null>(null);
  const [styleRules, setStyleRules] = useState<GenreRule[]>([]);
  const [qualityRules, setQualityRules] = useState<GenreRule[]>([]);
  const [forbiddenRules, setForbiddenRules] = useState<GenreRule[]>([]);
  const [knowledgeList, setKnowledgeList] = useState<GenreKnowledge[]>([]);
  const [inheritanceChain, setInheritanceChain] = useState<GenrePack[]>([]);

  // 加载状态
  const [loadingTree, setLoadingTree] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  // ── 加载品类树 ──────────────────────────────────────────────────────

  const loadGenreTree = useCallback(async () => {
    setLoadingTree(true);
    setTreeError(null);
    try {
      const result = await brainApi.getGenreTree();
      setGenreTree(result.tree || []);

      // 扁平化所有品类
      const flatten = (nodes: any[]): GenrePack[] => {
        let result: GenrePack[] = [];
        nodes.forEach(node => {
          result.push(node);
          if (node.children && node.children.length > 0) {
            result = result.concat(flatten(node.children));
          }
        });
        return result;
      };
      const flat = flatten(result.tree || []);
      setAllGenres(flat);

      // 默认选中第一个根节点
      if (flat.length > 0 && !selectedGenreId) {
        const firstRoot = result.tree?.[0];
        if (firstRoot) {
          setSelectedGenreId(firstRoot.id);
          setExpandedNodes(prev => new Set(prev).add(firstRoot.id));
        }
      }
    } catch (err: any) {
      setTreeError(err.message || '加载品类树失败');
    } finally {
      setLoadingTree(false);
    }
  }, [selectedGenreId]);

  useEffect(() => {
    loadGenreTree();
  }, [loadGenreTree]);

  // ── 加载品类详情 ────────────────────────────────────────────────────

  const loadGenreDetail = useCallback(async (genreId: string) => {
    if (!genreId) return;

    setLoadingDetail(true);
    setDetailError(null);

    try {
      // 并行加载所有数据
      const [packResult, styleResult, qualityResult, forbiddenResult, knowledgeResult, chainResult] = await Promise.all([
        brainApi.getGenrePack(genreId),
        brainApi.listGenreRules(genreId, { rule_type: 'style', include_inherited: true }),
        brainApi.listGenreRules(genreId, { rule_type: 'quality_threshold', include_inherited: true }),
        brainApi.listGenreRules(genreId, { rule_type: 'forbidden', include_inherited: true }),
        brainApi.listGenreKnowledge(genreId, { include_inherited: true }),
        brainApi.getGenreInheritanceChain(genreId),
      ]);

      setSelectedGenre(packResult.pack);
      setStyleRules(styleResult.rules || []);
      setQualityRules(qualityResult.rules || []);
      setForbiddenRules(forbiddenResult.rules || []);
      setKnowledgeList(knowledgeResult.knowledge || []);
      setInheritanceChain(chainResult.chain || []);

      // 查找父品类
      if (packResult.pack?.parent_id) {
        const parent = allGenres.find(g => g.id === packResult.pack.parent_id);
        setParentGenre(parent || null);
      } else {
        setParentGenre(null);
      }
    } catch (err: any) {
      setDetailError(err.message || '加载品类详情失败');
    } finally {
      setLoadingDetail(false);
    }
  }, [allGenres]);

  useEffect(() => {
    if (selectedGenreId) {
      loadGenreDetail(selectedGenreId);
    }
  }, [selectedGenreId, loadGenreDetail]);

  // ── 品类树过滤 ──────────────────────────────────────────────────────

  const filteredTree = useMemo(() => {
    if (!searchQuery.trim()) return genreTree;

    const query = searchQuery.toLowerCase();
    const filterNodes = (nodes: any[]): any[] => {
      return nodes
        .map(node => {
          const children = node.children ? filterNodes(node.children) : [];
          const matches = node.name.toLowerCase().includes(query) ||
            node.slug.toLowerCase().includes(query);
          if (matches || children.length > 0) {
            return { ...node, children };
          }
          return null;
        })
        .filter(Boolean);
    };

    return filterNodes(genreTree);
  }, [genreTree, searchQuery]);

  // ── 展开/收起 ───────────────────────────────────────────────────────

  const toggleNode = useCallback((id: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // ── 统计数据 ────────────────────────────────────────────────────────

  const stats = useMemo(() => {
    if (!selectedGenre) return null;

    const totalRules = styleRules.length + qualityRules.length + forbiddenRules.length;
    const inheritedRules = [...styleRules, ...qualityRules, ...forbiddenRules].filter(r => r.inherited_from).length;
    const ownRules = totalRules - inheritedRules;

    return {
      totalRules,
      ownRules,
      inheritedRules,
      knowledgeCount: knowledgeList.length,
      inheritanceDepth: inheritanceChain.length,
    };
  }, [selectedGenre, styleRules, qualityRules, forbiddenRules, knowledgeList, inheritanceChain]);

  // ── 渲染品类树节点 ──────────────────────────────────────────────────

  const renderTreeNode = (node: any, level: number = 0) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(node.id);
    const isSelected = selectedGenreId === node.id;

    return (
      <div key={node.id}>
        <div
          className={`v7-genre-tree-node ${isSelected ? 'selected' : ''}`}
          style={{ paddingLeft: `${12 + level * 16}px` }}
          onClick={() => {
            setSelectedGenreId(node.id);
            if (hasChildren && !isExpanded) {
              toggleNode(node.id);
            }
          }}
        >
          {hasChildren ? (
            <button
              className="v7-genre-tree-toggle"
              onClick={(e) => {
                e.stopPropagation();
                toggleNode(node.id);
              }}
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
          ) : (
            <span className="v7-genre-tree-spacer" />
          )}
          <span className={`v7-genre-tree-icon ${node.is_builtin ? 'builtin' : 'custom'}`}>
            {node.is_builtin ? <Layers size={14} /> : <Sparkles size={14} />}
          </span>
          <div className="v7-genre-tree-info">
            <span className="v7-genre-tree-name">{node.name}</span>
            <span className="v7-genre-tree-meta">
              <span className="v7-genre-tree-count">{node.children?.length || 0} 子品类</span>
            </span>
          </div>
        </div>
        {hasChildren && isExpanded && (
          <div className="v7-genre-tree-children">
            {node.children.map((child: any) => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

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

  // ── 主渲染 ──────────────────────────────────────────────────────────

  return (
    <div className="v7-page">
      <div className="v7-page-head">
        <div>
          <p className="v7-kicker">品类库</p>
          <h2>品类管理</h2>
          <p className="v7-page-desc">管理小说品类规则、风格卡和知识库</p>
        </div>
        <div className="v7-page-actions">
          <button className="v7-btn v7-btn-secondary">
            <Upload size={16} />
            导入
          </button>
          <button className="v7-btn v7-btn-secondary">
            <Download size={16} />
            导出
          </button>
          <button className="v7-btn v7-btn-primary">
            <Plus size={16} />
            新建品类
          </button>
        </div>
      </div>

      <div className="v7-genre-layout">
        {/* ── 左侧：品类树 ── */}
        <div className="v7-genre-sidebar">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3>品类树</h3>
              <button className="v7-icon-btn" onClick={loadGenreTree} title="刷新">
                <RefreshCw size={14} />
              </button>
            </div>

            <div className="v7-genre-search">
              <Search size={14} />
              <input
                type="text"
                placeholder="搜索品类..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="v7-genre-tree">
              {loadingTree && renderLoading('加载品类树...')}
              {treeError && (
                <div className="v7-error-state">
                  <p>加载失败：{treeError}</p>
                  <button className="v7-btn v7-btn-secondary" onClick={loadGenreTree}>
                    重试
                  </button>
                </div>
              )}
              {!loadingTree && !treeError && filteredTree.length === 0 && renderEmptyState(
                '暂无品类',
                '点击右上角"新建品类"创建第一个品类'
              )}
              {!loadingTree && !treeError && filteredTree.length > 0 && (
                filteredTree.map(node => renderTreeNode(node))
              )}
            </div>

            <div className="v7-genre-sidebar-footer">
              <button className="v7-btn v7-btn-primary v7-btn-block">
                <Plus size={14} />
                新建品类
              </button>
            </div>
          </div>
        </div>

        {/* ── 中间：品类详情 ── */}
        <div className="v7-genre-detail">
          {loadingDetail && renderLoading('加载品类详情...')}
          {detailError && (
            <div className="v7-panel">
              <div className="v7-error-state">
                <p>加载失败：{detailError}</p>
                <button className="v7-btn v7-btn-secondary" onClick={() => selectedGenreId && loadGenreDetail(selectedGenreId)}>
                  重试
                </button>
              </div>
            </div>
          )}

          {!loadingDetail && !detailError && selectedGenre && stats && (
            <>
              {/* 头部信息 */}
              <div className="v7-panel">
                <div className="v7-genre-detail-head">
                  <div className="v7-genre-detail-icon">
                    <Layers size={24} />
                  </div>
                  <div className="v7-genre-detail-title">
                    <div className="v7-genre-detail-name-row">
                      <h3>{selectedGenre.name}</h3>
                      {selectedGenre.is_builtin && (
                        <span className="v7-badge v7-badge-info">内置</span>
                      )}
                      {!selectedGenre.is_active && (
                        <span className="v7-badge v7-badge-gray">已停用</span>
                      )}
                    </div>
                    <p className="v7-genre-detail-desc">
                      {selectedGenre.description || '暂无描述'}
                    </p>
                    <div className="v7-genre-detail-meta">
                      <span>slug: {selectedGenre.slug}</span>
                      <span>范围: {SCOPE_LABELS[selectedGenre.scope] || selectedGenre.scope}</span>
                      {parentGenre && <span>继承自: {parentGenre.name}</span>}
                    </div>
                  </div>
                  <div className="v7-genre-detail-actions">
                    <button className="v7-btn v7-btn-secondary">
                      <RefreshCw size={14} />
                      刷新
                    </button>
                    <button className="v7-btn v7-btn-secondary">
                      编辑
                    </button>
                  </div>
                </div>

                {/* 指标卡片 */}
                <div className="v7-metric-grid v7-metric-grid-4">
                  <div className="v7-metric-card">
                    <div className="v7-metric-label">规则总数</div>
                    <div className="v7-metric-value">{stats.totalRules}</div>
                    <div className="v7-metric-sub">自有 {stats.ownRules} · 继承 {stats.inheritedRules}</div>
                  </div>
                  <div className="v7-metric-card">
                    <div className="v7-metric-label">风格规则</div>
                    <div className="v7-metric-value">{styleRules.length}</div>
                    <div className="v7-metric-sub">写作风格约束</div>
                  </div>
                  <div className="v7-metric-card">
                    <div className="v7-metric-label">质量门禁</div>
                    <div className="v7-metric-value">{qualityRules.length}</div>
                    <div className="v7-metric-sub">质量阈值规则</div>
                  </div>
                  <div className="v7-metric-card">
                    <div className="v7-metric-label">知识条目</div>
                    <div className="v7-metric-value">{knowledgeList.length}</div>
                    <div className="v7-metric-sub">知识库条目数</div>
                  </div>
                </div>
              </div>

              {/* 标签页导航 */}
              <div className="v7-view-nav">
                <button
                  className={`v7-view-tab ${detailTab === 'style' ? 'active' : ''}`}
                  onClick={() => setDetailTab('style')}
                >
                  <Sparkles size={14} />
                  风格卡
                  <span className="v7-tab-count">{styleRules.length}</span>
                </button>
                <button
                  className={`v7-view-tab ${detailTab === 'quality' ? 'active' : ''}`}
                  onClick={() => setDetailTab('quality')}
                >
                  <Shield size={14} />
                  质量门禁
                  <span className="v7-tab-count">{qualityRules.length}</span>
                </button>
                <button
                  className={`v7-view-tab ${detailTab === 'forbidden' ? 'active' : ''}`}
                  onClick={() => setDetailTab('forbidden')}
                >
                  <XCircle size={14} />
                  禁止规则
                  <span className="v7-tab-count">{forbiddenRules.length}</span>
                </button>
              </div>

              {/* 风格卡 */}
              {detailTab === 'style' && (
                <div className="v7-panel">
                  <div className="v7-panel-head">
                    <h3>风格规则</h3>
                    <span className="v7-panel-count">{styleRules.length} 条</span>
                  </div>
                  {styleRules.length === 0 ? (
                    renderEmptyState('暂无风格规则', '该品类还没有配置风格规则')
                  ) : (
                    <div className="v7-rule-list">
                      {styleRules.map(rule => (
                        <div key={rule.id} className="v7-rule-row">
                          <div className="v7-rule-info">
                            <div className="v7-rule-name">
                              {rule.rule_key}
                              {rule.inherited_from && (
                                <span className="v7-rule-badge v7-badge v7-badge-gray">继承</span>
                              )}
                            </div>
                            {rule.description && (
                              <div className="v7-rule-desc">{rule.description}</div>
                            )}
                          </div>
                          <div className="v7-rule-value">
                            {typeof rule.rule_value === 'object'
                              ? formatStyleValue(rule.rule_value)
                              : String(rule.rule_value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 质量门禁 */}
              {detailTab === 'quality' && (
                <div className="v7-panel">
                  <div className="v7-panel-head">
                    <h3>质量门禁规则</h3>
                    <span className="v7-panel-count">{qualityRules.length} 条</span>
                  </div>
                  {qualityRules.length === 0 ? (
                    renderEmptyState('暂无质量门禁规则', '该品类还没有配置质量门禁阈值')
                  ) : (
                    <div className="v7-rule-list">
                      {qualityRules.map(rule => (
                        <div key={rule.id} className="v7-rule-row">
                          <div className="v7-rule-info">
                            <div className="v7-rule-name">
                              {rule.rule_key}
                              {rule.inherited_from && (
                                <span className="v7-rule-badge v7-badge v7-badge-gray">继承</span>
                              )}
                            </div>
                            {rule.description && (
                              <div className="v7-rule-desc">{rule.description}</div>
                            )}
                          </div>
                          <div className="v7-rule-value">
                            <span
                              className="v7-rule-badge"
                              style={{
                                backgroundColor: `${SEVERITY_COLORS[rule.severity] || '#6b7280'}20`,
                                color: SEVERITY_COLORS[rule.severity] || '#6b7280',
                              }}
                            >
                              {rule.severity}
                            </span>
                            {typeof rule.rule_value === 'object'
                              ? formatQualityValue(rule.rule_value)
                              : String(rule.rule_value)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 禁止规则 */}
              {detailTab === 'forbidden' && (
                <div className="v7-panel">
                  <div className="v7-panel-head">
                    <h3>禁止规则</h3>
                    <span className="v7-panel-count">{forbiddenRules.length} 条</span>
                  </div>
                  {forbiddenRules.length === 0 ? (
                    renderEmptyState('暂无禁止规则', '该品类还没有配置禁止规则')
                  ) : (
                    <div className="v7-forbidden-groups">
                      <div className="v7-forbidden-group">
                        <div className="v7-forbidden-category">违禁词/句</div>
                        <div className="v7-forbidden-list">
                          {forbiddenRules.map(rule => (
                            <div key={rule.id} className="v7-forbidden-item">
                              <span className="v7-forbidden-text">{rule.rule_key}</span>
                              {rule.inherited_from && (
                                <span className="v7-badge v7-badge-gray">继承</span>
                              )}
                              {rule.description && (
                                <span className="v7-forbidden-desc">{rule.description}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {!loadingDetail && !detailError && !selectedGenre && !loadingTree && (
            <div className="v7-panel">
              {renderEmptyState('请选择品类', '从左侧品类树中选择一个品类查看详情')}
            </div>
          )}
        </div>

        {/* ── 右侧：规则对比 + 知识库 ── */}
        <div className="v7-genre-rightbar">
          {/* 规则对比 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3><GitCompare size={16} /> 规则对比</h3>
            </div>
            {loadingDetail && renderLoading('加载中...')}
            {!loadingDetail && inheritanceChain.length <= 1 && (
              <div className="v7-compare-summary">
                <div className="v7-compare-item">
                  <span className="v7-compare-label">继承层级</span>
                  <span className="v7-compare-value">根品类</span>
                </div>
                <div className="v7-compare-note">
                  这是根品类，没有父品类
                </div>
              </div>
            )}
            {!loadingDetail && inheritanceChain.length > 1 && (
              <div className="v7-compare-summary">
                <div className="v7-compare-item">
                  <span className="v7-compare-label">继承深度</span>
                  <span className="v7-compare-value">{inheritanceChain.length} 层</span>
                </div>
                <div className="v7-compare-item">
                  <span className="v7-compare-label">自有规则</span>
                  <span className="v7-compare-value">{stats?.ownRules || 0} 条</span>
                </div>
                <div className="v7-compare-item">
                  <span className="v7-compare-label">继承规则</span>
                  <span className="v7-compare-value">{stats?.inheritedRules || 0} 条</span>
                </div>
                <div className="v7-compare-detail">
                  <div className="v7-compare-chain">
                    {inheritanceChain.map((g, i) => (
                      <div key={g.id} className="v7-compare-chain-item">
                        <span className="v7-compare-chain-name">{g.name}</span>
                        {i < inheritanceChain.length - 1 && (
                          <ChevronRight size={12} className="v7-compare-chain-arrow" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 知识库 */}
          <div className="v7-panel">
            <div className="v7-panel-head">
              <h3><BookOpen size={16} /> 知识库</h3>
              <span className="v7-panel-count">{knowledgeList.length} 条</span>
            </div>
            {loadingDetail && renderLoading('加载中...')}
            {!loadingDetail && knowledgeList.length === 0 && (
              renderEmptyState('暂无知识条目', '该品类还没有添加知识条目')
            )}
            {!loadingDetail && knowledgeList.length > 0 && (
              <div className="v7-knowledge-list">
                {knowledgeList.slice(0, 6).map(item => (
                  <div key={item.id} className="v7-knowledge-item">
                    <div className="v7-knowledge-header">
                      <span className="v7-knowledge-title">{item.title}</span>
                      <span className="v7-knowledge-category">{item.knowledge_type}</span>
                    </div>
                    <p className="v7-knowledge-summary">
                      {item.content?.substring(0, 80)}{item.content?.length > 80 ? '...' : ''}
                    </p>
                    {item.inherited_from && (
                      <span className="v7-badge v7-badge-gray">继承</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// 缺少的图标组件
function XCircle({ size = 16 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="m15 9-6 6" />
      <path d="m9 9 6 6" />
    </svg>
  );
}
