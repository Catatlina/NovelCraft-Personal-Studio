/**
 * 品类管理页面
 *
 * 专业级品类库管理页面，达到 V7 Dashboard 设计水准：
 * - 三栏布局（品类树 / 详情 / 规则对比）
 * - 深色 indigo 主题
 * - 卡片式布局
 * - 视觉层次分明
 * - 数据饱满无空白
 */
import { useCallback, useMemo, useState } from 'react';
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
} from 'lucide-react';

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
  rule_count?: number;
  knowledge_count?: number;
  prompt_count?: number;
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
  title: string;
  category: string;
  summary: string;
}

interface GenreManagerProps {
  novelId?: string | null;
}

type DetailTab = 'style' | 'quality' | 'forbidden';

// ============ Mock 数据 ============

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

const MOCK_GENRES: GenrePack[] = [
  {
    id: 'base',
    name: '通用网文',
    slug: 'base',
    description: '所有网文品类的基础规则集，包含通用质量门禁、AI味检测阈值和基础写作规范。',
    scope: 'webnovel',
    is_builtin: true,
    is_active: true,
    parent_id: null,
    icon_url: null,
    rule_count: 30,
    knowledge_count: 10,
    prompt_count: 5,
  },
  {
    id: 'tomato',
    name: '番茄爽文',
    slug: 'tomato',
    description: '番茄小说平台爽文专属规则，强化爽点密度、节奏把控和读者留存优化。',
    scope: 'fanqie',
    is_builtin: true,
    is_active: true,
    parent_id: 'base',
    icon_url: null,
    rule_count: 20,
    knowledge_count: 8,
    prompt_count: 3,
  },
  {
    id: 'qidian',
    name: '起点玄幻',
    slug: 'qidian',
    description: '起点中文网玄幻品类规则，侧重世界观构建、升级体系和长篇布局。',
    scope: 'qidian',
    is_builtin: true,
    is_active: true,
    parent_id: 'base',
    icon_url: null,
    rule_count: 15,
    knowledge_count: 12,
    prompt_count: 2,
  },
  {
    id: 'jjwxc',
    name: '晋江言情',
    slug: 'jjwxc',
    description: '晋江文学城言情品类规则，注重情感细腻度、人物关系和情节张力。',
    scope: 'jjwxc',
    is_builtin: true,
    is_active: true,
    parent_id: 'base',
    icon_url: null,
    rule_count: 18,
    knowledge_count: 10,
    prompt_count: 4,
  },
  {
    id: 'fengshen',
    name: '封神举国',
    slug: 'fengshen',
    description: '封神题材举国流专属规则，包含封神世界观硬约束、阵营设定和举国流爽点模式。',
    scope: 'fanqie',
    is_builtin: true,
    is_active: true,
    parent_id: 'tomato',
    icon_url: null,
    rule_count: 8,
    knowledge_count: 15,
    prompt_count: 2,
  },
  {
    id: 'datang',
    name: '大唐后台',
    slug: 'datang',
    description: '大唐背景官场文专属规则，包含历史考据、官场逻辑和时代特色语言。',
    scope: 'fanqie',
    is_builtin: true,
    is_active: true,
    parent_id: 'tomato',
    icon_url: null,
    rule_count: 10,
    knowledge_count: 20,
    prompt_count: 2,
  },
];

const MOCK_STYLE_CARD = {
  keywords: ['快节奏', '爽点密集', '打脸爽快', '金手指强', '升级清晰'],
  pacing: '每 3000 字一个小爽点，每 10000 字一个大爽点',
  language: '直白易懂，少用生僻词，对话占比 40% 以上',
  tone: '轻松幽默，主角性格鲜明，冲突直接',
  structure: '开局即高潮，三章内见金手指，十章内第一次打脸',
};

const MOCK_QUALITY_RULES = [
  { key: 'ai_smell_score', name: 'AI 味综合评分', value: '≥ 75 分', severity: 'error', inherited: false },
  { key: 'transition_density', name: '转折词密度', value: '≤ 5 次/千字', severity: 'warning', inherited: true },
  { key: 'payoff_density', name: '爽点密度', value: '≥ 1 个/千字', severity: 'error', inherited: false },
  { key: 'chapter_word_count', name: '章节字数', value: '2000-5000 字', severity: 'info', inherited: true },
  { key: 'dialogue_ratio', name: '对话占比', value: '≥ 35%', severity: 'warning', inherited: false },
  { key: 'pacing_variance', name: '节奏变异度', value: '≤ 30%', severity: 'warning', inherited: true },
];

const MOCK_FORBIDDEN_RULES = [
  { category: '高级违规', items: [
    { name: '政治敏感内容', desc: '禁止涉及现实政治敏感话题' },
    { name: '色情低俗描写', desc: '禁止露骨性描写和低俗内容' },
    { name: '违法犯罪教唆', desc: '禁止教唆违法犯罪行为' },
  ]},
  { category: '中级违规', items: [
    { name: '负面价值观', desc: '禁止传播错误价值观' },
    { name: '人身攻击', desc: '禁止针对特定群体的人身攻击' },
    { name: '封建迷信', desc: '禁止宣扬封建迷信思想' },
  ]},
  { category: '低级违规', items: [
    { name: '错别字过多', desc: '每千字错别字不超过 3 个' },
    { name: '标点不规范', desc: '规范使用中文标点符号' },
    { name: '段落过长', desc: '单段不超过 200 字' },
  ]},
];

const MOCK_KNOWLEDGE: GenreKnowledge[] = [
  { id: '1', title: '番茄爽文黄金三章', category: '开篇技巧', summary: '第一章：钩子+金手指；第二章：第一次小冲突；第三章：第一次打脸。' },
  { id: '2', title: '举国流核心爽点', category: '爽点模式', summary: '从弱到强的国家建设、科技碾压、文化输出、万国来朝。' },
  { id: '3', title: '封神世界观设定', category: '世界观', summary: '阐截两教、封神榜、三十六路伐西岐、诛仙阵等核心设定。' },
  { id: '4', title: '读者留存优化技巧', category: '留存策略', summary: '章末钩子、悬念设置、节奏控制、期待感管理。' },
  { id: '5', title: '打脸情节设计公式', category: '情节设计', summary: '铺垫-冲突-爆发-余韵四步法，确保打脸爽快不憋屈。' },
  { id: '6', title: '角色人设塑造要点', category: '人物塑造', summary: '主角辨识度、配角记忆点、反派立体感、群像平衡。' },
];

// ============ 工具函数 ============

function getSeverityTone(severity: string) {
  if (severity === 'error') return 'danger';
  if (severity === 'warning') return 'amber';
  return 'green';
}

// ============ 子组件 ============

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'indigo',
}: {
  icon: typeof Layers;
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

// ============ 主组件 ============

export default function GenreManager({ novelId }: GenreManagerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenreId, setSelectedGenreId] = useState<string>('tomato');
  const [expandedGenres, setExpandedGenres] = useState<Set<string>>(new Set(['base', 'tomato']));
  const [detailTab, setDetailTab] = useState<DetailTab>('style');
  const [loading, setLoading] = useState(false);

  // 构建品类树
  const genreTree = useMemo(() => {
    const map = new Map<string, GenrePack>();
    MOCK_GENRES.forEach(g => map.set(g.id, { ...g, children: [] }));

    const roots: GenrePack[] = [];
    map.forEach(genre => {
      if (genre.parent_id && map.has(genre.parent_id)) {
        map.get(genre.parent_id)!.children!.push(genre);
      } else {
        roots.push(genre);
      }
    });

    return roots;
  }, []);

  // 选中的品类
  const selectedGenre = useMemo(() => {
    return MOCK_GENRES.find(g => g.id === selectedGenreId) || null;
  }, [selectedGenreId]);

  // 父品类
  const parentGenre = useMemo(() => {
    if (!selectedGenre?.parent_id) return null;
    return MOCK_GENRES.find(g => g.id === selectedGenre.parent_id) || null;
  }, [selectedGenre]);

  // 过滤品类
  const filteredGenres = useMemo(() => {
    if (!searchQuery) return genreTree;

    const query = searchQuery.toLowerCase();
    const filterTree = (genres: GenrePack[]): GenrePack[] => {
      return genres
        .map(g => {
          const children = g.children ? filterTree(g.children) : [];
          const match = g.name.toLowerCase().includes(query) ||
            g.slug.toLowerCase().includes(query) ||
            (g.description && g.description.toLowerCase().includes(query));
          if (match || children.length > 0) {
            return { ...g, children };
          }
          return null;
        })
        .filter(Boolean) as GenrePack[];
    };

    return filterTree(genreTree);
  }, [genreTree, searchQuery]);

  const toggleGenre = useCallback((id: string) => {
    setExpandedGenres(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    setTimeout(() => setLoading(false), 800);
  }, []);

  const renderGenreNode = (genre: GenrePack, depth: number = 0) => {
    const hasChildren = genre.children && genre.children.length > 0;
    const isExpanded = expandedGenres.has(genre.id);
    const isSelected = selectedGenreId === genre.id;

    return (
      <div key={genre.id}>
        <div
          className={`v7-genre-tree-node ${isSelected ? 'active' : ''}`}
          style={{ paddingLeft: `${depth * 16 + 12}px` }}
          onClick={() => setSelectedGenreId(genre.id)}
        >
          {hasChildren ? (
            <button
              className="v7-genre-tree-toggle"
              onClick={(e) => {
                e.stopPropagation();
                toggleGenre(genre.id);
              }}
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
          ) : (
            <span className="v7-genre-tree-spacer" />
          )}

          <BookOpen
            size={16}
            className={genre.is_builtin ? 'v7-genre-icon-builtin' : 'v7-genre-icon-custom'}
          />

          <div className="v7-genre-tree-info">
            <span className="v7-genre-tree-name">{genre.name}</span>
            <span className="v7-genre-tree-meta">
              {SCOPE_LABELS[genre.scope] || genre.scope}
              {genre.is_builtin && ' · 内置'}
            </span>
          </div>

          <span className="v7-genre-tree-count">{genre.rule_count || 0}</span>
        </div>

        {hasChildren && isExpanded && (
          <div className="v7-genre-tree-children">
            {genre.children!.map(child => renderGenreNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const DETAIL_TABS: Array<{ key: DetailTab; label: string; icon: typeof Sparkles }> = [
    { key: 'style', label: '风格卡', icon: Sparkles },
    { key: 'quality', label: '质量门禁', icon: Shield },
    { key: 'forbidden', label: '禁止规则', icon: Shield },
  ];

  return (
    <div className="v7-monitor page-enter">
      <header className="v7-monitor-head">
        <div>
          <p className="v7-kicker">品类工厂 · 规则库</p>
          <h2>品类管理</h2>
          <p>
            管理网文品类规则包，支持继承、覆盖和蒸馏。内置品类经过实战验证，可直接使用或二次定制。
          </p>
        </div>
        <div className="v7-monitor-head-actions">
          <span className="v7-chain-badge"><Layers size={14} /> 继承引擎</span>
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

      <div className="v7-genre-layout">
        {/* 左侧：品类树 */}
        <aside className="v7-genre-sidebar">
          <div className="v7-panel">
            <div className="v7-panel-head">
              <div><p className="v7-kicker">品类树</p><h3>全部品类</h3></div>
              <span className="v7-panel-count">{MOCK_GENRES.length} 个</span>
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
              {filteredGenres.map(genre => renderGenreNode(genre))}
            </div>

            <div className="v7-genre-sidebar-footer">
              <button type="button" className="v7-primary-button">
                <Plus size={14} /> 新建品类
              </button>
            </div>
          </div>
        </aside>

        {/* 中间：品类详情 */}
        <main className="v7-genre-main">
          {selectedGenre ? (
            <div className="v7-monitor-stack">
              {/* 品类头部 */}
              <section className="v7-panel">
                <div className="v7-genre-detail-head">
                  <div className="v7-genre-detail-title">
                    <div className="v7-genre-detail-icon">
                      <BookOpen size={24} />
                    </div>
                    <div>
                      <div className="v7-genre-detail-name-row">
                        <h2>{selectedGenre.name}</h2>
                        {selectedGenre.is_builtin ? (
                          <span className="v7-mini-badge indigo">内置</span>
                        ) : (
                          <span className="v7-mini-badge green">自建</span>
                        )}
                      </div>
                      <p className="v7-genre-detail-desc">{selectedGenre.description}</p>
                    </div>
                  </div>
                  <div className="v7-genre-detail-actions">
                    <button className="v7-link-button">
                      <Upload size={14} /> 导入
                    </button>
                    <button className="v7-link-button">
                      <Download size={14} /> 导出
                    </button>
                  </div>
                </div>

                <div className="v7-metric-grid">
                  <MetricCard
                    icon={Shield}
                    label="规则总数"
                    value={String(selectedGenre.rule_count || 0)}
                    detail={`继承 ${parentGenre?.rule_count || 0} + 新增 ${(selectedGenre.rule_count || 0) - (parentGenre?.rule_count || 0)}`}
                    tone="indigo"
                  />
                  <MetricCard
                    icon={BookOpen}
                    label="知识条目"
                    value={String(selectedGenre.knowledge_count || 0)}
                    detail="品类专属知识库"
                    tone="green"
                  />
                  <MetricCard
                    icon={Sparkles}
                    label="Prompt 模板"
                    value={String(selectedGenre.prompt_count || 0)}
                    detail="生成专用模板"
                    tone="amber"
                  />
                  <MetricCard
                    icon={Layers}
                    label="继承层级"
                    value={parentGenre ? '2 层' : '1 层'}
                    detail={parentGenre ? `父类：${parentGenre.name}` : '根品类'}
                    tone="gray"
                  />
                </div>
              </section>

              {/* Tab 导航 */}
              <nav className="v7-view-nav" aria-label="品类详情视图">
                {DETAIL_TABS.map(item => {
                  const Icon = item.icon;
                  return (
                    <button
                      type="button"
                      key={item.key}
                      className={detailTab === item.key ? 'active' : ''}
                      aria-selected={detailTab === item.key}
                      role="tab"
                      onClick={() => setDetailTab(item.key)}
                    >
                      <Icon size={16} />
                      <span><strong>{item.label}</strong><small>查看{item.label}详情</small></span>
                    </button>
                  );
                })}
              </nav>

              {/* 风格卡 */}
              {detailTab === 'style' && (
                <section className="v7-panel">
                  <div className="v7-panel-head">
                    <div><p className="v7-kicker">风格定义</p><h3>品类风格卡</h3></div>
                    <span className="v7-panel-count">5 项</span>
                  </div>
                  <div className="v7-style-card">
                    <div className="v7-style-keywords">
                      <h4>风格关键词</h4>
                      <div className="v7-keyword-list">
                        {MOCK_STYLE_CARD.keywords.map((kw, i) => (
                          <span key={i} className="v7-keyword-tag">{kw}</span>
                        ))}
                      </div>
                    </div>
                    <div className="v7-style-grid">
                      <div className="v7-style-item">
                        <h4>节奏特点</h4>
                        <p>{MOCK_STYLE_CARD.pacing}</p>
                      </div>
                      <div className="v7-style-item">
                        <h4>语言风格</h4>
                        <p>{MOCK_STYLE_CARD.language}</p>
                      </div>
                      <div className="v7-style-item">
                        <h4>整体调性</h4>
                        <p>{MOCK_STYLE_CARD.tone}</p>
                      </div>
                      <div className="v7-style-item">
                        <h4>结构特征</h4>
                        <p>{MOCK_STYLE_CARD.structure}</p>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* 质量门禁 */}
              {detailTab === 'quality' && (
                <section className="v7-panel">
                  <div className="v7-panel-head">
                    <div><p className="v7-kicker">质量阈值</p><h3>质量门禁规则</h3></div>
                    <span className="v7-panel-count">{MOCK_QUALITY_RULES.length} 条</span>
                  </div>
                  <div className="v7-rule-list">
                    {MOCK_QUALITY_RULES.map(rule => (
                      <div key={rule.key} className="v7-rule-row">
                        <div className="v7-rule-info">
                          <span className="v7-rule-name">{rule.name}</span>
                          {rule.inherited && <span className="v7-rule-badge inherited">继承</span>}
                        </div>
                        <div className={`v7-rule-value v7-tone-${getSeverityTone(rule.severity)}`}>
                          {rule.value}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="v7-panel-note">
                    <Shield size={14} /> 质量门禁在生成前后自动执行，违规内容会触发重生成或人工审核。
                  </p>
                </section>
              )}

              {/* 禁止规则 */}
              {detailTab === 'forbidden' && (
                <section className="v7-panel">
                  <div className="v7-panel-head">
                    <div><p className="v7-kicker">违规分级</p><h3>禁止规则清单</h3></div>
                    <span className="v7-panel-count">三级分类</span>
                  </div>
                  <div className="v7-forbidden-groups">
                    {MOCK_FORBIDDEN_RULES.map(group => (
                      <div key={group.category} className="v7-forbidden-group">
                        <h4 className={`v7-forbidden-category v7-tone-${
                          group.category.includes('高级') ? 'danger' :
                          group.category.includes('中级') ? 'amber' : 'green'
                        }`}>
                          {group.category}
                        </h4>
                        <div className="v7-forbidden-list">
                          {group.items.map((item, i) => (
                            <div key={i} className="v7-forbidden-item">
                              <strong>{item.name}</strong>
                              <p>{item.desc}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <section className="v7-panel v7-empty-panel">
              <div className="v7-access-icon"><Layers size={22} /></div>
              <h3>选择一个品类</h3>
              <p>从左侧品类树选择一个品类，查看详细规则和知识条目。</p>
            </section>
          )}
        </main>

        {/* 右侧：规则对比 + 知识 */}
        <aside className="v7-genre-rightbar">
          {selectedGenre && parentGenre && (
            <section className="v7-panel">
              <div className="v7-panel-head">
                <div><p className="v7-kicker">继承对比</p><h3>与父品类差异</h3></div>
                <GitCompare size={16} />
              </div>
              <div className="v7-compare-summary">
                <div className="v7-compare-item">
                  <span className="v7-compare-label">继承规则</span>
                  <span className="v7-compare-value">{parentGenre.rule_count || 0} 条</span>
                </div>
                <div className="v7-compare-item">
                  <span className="v7-compare-label">新增规则</span>
                  <span className="v7-compare-value v7-tone-green">
                    +{(selectedGenre.rule_count || 0) - (parentGenre.rule_count || 0)} 条
                  </span>
                </div>
                <div className="v7-compare-item">
                  <span className="v7-compare-label">覆盖规则</span>
                  <span className="v7-compare-value v7-tone-amber">2 条</span>
                </div>
              </div>
              <div className="v7-compare-detail">
                <p className="v7-compare-note">
                  继承自 <strong>{parentGenre.name}</strong>，在此基础上针对番茄平台特性进行了优化。
                </p>
              </div>
            </section>
          )}

          {selectedGenre && (
            <section className="v7-panel">
              <div className="v7-panel-head">
                <div><p className="v7-kicker">知识条目</p><h3>品类知识库</h3></div>
                <span className="v7-panel-count">{MOCK_KNOWLEDGE.length} 条</span>
              </div>
              <div className="v7-knowledge-list">
                {MOCK_KNOWLEDGE.map(item => (
                  <div key={item.id} className="v7-knowledge-item">
                    <div className="v7-knowledge-header">
                      <span className="v7-knowledge-title">{item.title}</span>
                      <span className="v7-knowledge-category">{item.category}</span>
                    </div>
                    <p className="v7-knowledge-summary">{item.summary}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
