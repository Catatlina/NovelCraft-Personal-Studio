/**
 * 品类管理页面
 *
 * 展示品类库、规则对比、品类导入导出
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Download,
  Plus,
  Search,
  Settings,
  Shield,
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

interface GenreManagerProps {
  novelId?: string | null;
}

type ViewMode = 'tree' | 'rules' | 'knowledge';

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
  info: 'text-blue-600',
  warning: 'text-yellow-600',
  error: 'text-red-600',
  blocking: 'text-red-700',
};

// 模拟数据（实际应从 API 获取）
const MOCK_GENRES: GenrePack[] = [
  {
    id: 'base',
    name: '通用网文',
    slug: 'base',
    description: '所有网文品类的基础规则集',
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
    description: '番茄小说平台爽文专属规则',
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
    description: '起点中文网玄幻品类规则',
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
    description: '晋江文学城言情品类规则',
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
    description: '封神题材举国流专属规则',
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
    description: '大唐背景官场文专属规则',
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

const MOCK_RULES: GenreRule[] = [
  {
    id: '1',
    genre_id: 'tomato',
    rule_type: 'ai_smell_threshold',
    rule_key: 'abstract_adverb_density',
    rule_value: { max: 2.0, unit: '次/千字' },
    severity: 'warning',
    priority: 10,
    description: '抽象副词密度上限',
    is_active: true,
    inherited_from: null,
  },
  {
    id: '2',
    genre_id: 'tomato',
    rule_type: 'ai_smell_threshold',
    rule_key: 'transition_word_density',
    rule_value: { max: 5.0, unit: '次/千字' },
    severity: 'warning',
    priority: 9,
    description: '转折词密度上限',
    is_active: true,
    inherited_from: null,
  },
  {
    id: '3',
    genre_id: 'tomato',
    rule_type: 'payoff',
    rule_key: 'payoff_density',
    rule_value: { min: 1.0, unit: '个/千字' },
    severity: 'error',
    priority: 10,
    description: '爽点密度下限',
    is_active: true,
    inherited_from: null,
  },
  {
    id: '4',
    genre_id: 'tomato',
    rule_type: 'chapter_basic',
    rule_key: 'word_count',
    rule_value: { min: 2000, max: 5000, unit: '字' },
    severity: 'info',
    priority: 5,
    description: '章节字数范围',
    is_active: true,
    inherited_from: 'base',
  },
];

export default function GenreManager({ novelId }: GenreManagerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('tree');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenre, setSelectedGenre] = useState<GenrePack | null>(null);
  const [expandedGenres, setExpandedGenres] = useState<Set<string>>(new Set(['base', 'tomato']));
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

  const handleExport = useCallback(() => {
    if (!selectedGenre) return;
    const data = JSON.stringify(selectedGenre, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedGenre.slug}-genre-pack.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [selectedGenre]);

  const renderGenreNode = (genre: GenrePack, depth: number = 0) => {
    const hasChildren = genre.children && genre.children.length > 0;
    const isExpanded = expandedGenres.has(genre.id);
    const isSelected = selectedGenre?.id === genre.id;

    return (
      <div key={genre.id}>
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
            isSelected ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'
          }`}
          style={{ paddingLeft: `${depth * 16 + 12}px` }}
          onClick={() => setSelectedGenre(genre)}
        >
          {hasChildren ? (
            <button
              className="p-0.5 hover:bg-gray-200 rounded"
              onClick={(e) => {
                e.stopPropagation();
                toggleGenre(genre.id);
              }}
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )}
            </button>
          ) : (
            <span className="w-5" />
          )}

          <BookOpen className={`w-4 h-4 ${genre.is_builtin ? 'text-purple-500' : 'text-green-500'}`} />

          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm truncate">{genre.name}</div>
            <div className="text-xs text-gray-500 truncate">
              {SCOPE_LABELS[genre.scope] || genre.scope}
              {genre.is_builtin && ' · 内置'}
            </div>
          </div>

          <div className="text-xs text-gray-400">
            {genre.rule_count || 0} 规则
          </div>
        </div>

        {hasChildren && isExpanded && (
          <div>
            {genre.children!.map(child => renderGenreNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple-600" />
          <h2 className="font-semibold text-gray-800">品类库管理</h2>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-gray-100 rounded-lg text-gray-600" title="导入">
            <Upload className="w-4 h-4" />
          </button>
          <button className="p-2 hover:bg-gray-100 rounded-lg text-gray-600" title="导出" onClick={handleExport} disabled={!selectedGenre}>
            <Download className="w-4 h-4" />
          </button>
          <button className="p-2 hover:bg-gray-100 rounded-lg text-gray-600" title="设置">
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 搜索栏 */}
      <div className="px-4 py-2 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索品类..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* 视图切换 */}
      <div className="flex border-b">
        {[
          { key: 'tree' as ViewMode, label: '品类树' },
          { key: 'rules' as ViewMode, label: '规则对比' },
          { key: 'knowledge' as ViewMode, label: '知识库' },
        ].map(tab => (
          <button
            key={tab.key}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
              viewMode === tab.key
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-800'
            }`}
            onClick={() => setViewMode(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto">
        {viewMode === 'tree' && (
          <div className="p-2">
            {filteredGenres.map(genre => renderGenreNode(genre))}
          </div>
        )}

        {viewMode === 'rules' && selectedGenre && (
          <div className="p-4">
            <div className="mb-4">
              <h3 className="font-medium text-gray-800 mb-1">{selectedGenre.name} - 规则列表</h3>
              <p className="text-sm text-gray-500">共 {MOCK_RULES.length} 条规则</p>
            </div>
            <div className="space-y-2">
              {MOCK_RULES.map(rule => (
                <div key={rule.id} className="p-3 border rounded-lg hover:bg-gray-50">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 bg-gray-100 rounded text-gray-600">
                        {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
                      </span>
                      <span className="font-medium text-sm">{rule.rule_key}</span>
                      {rule.inherited_from && (
                        <span className="text-xs text-purple-600">继承</span>
                      )}
                    </div>
                    <span className={`text-xs font-medium ${SEVERITY_COLORS[rule.severity]}`}>
                      {rule.severity}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mb-2">{rule.description}</p>
                  <div className="text-xs text-gray-600">
                    值：{JSON.stringify(rule.rule_value)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {viewMode === 'rules' && !selectedGenre && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            请选择一个品类查看规则
          </div>
        )}

        {viewMode === 'knowledge' && (
          <div className="p-4">
            <div className="text-center text-gray-400 text-sm py-8">
              知识库功能开发中...
            </div>
          </div>
        )}
      </div>

      {/* 底部操作栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
        <div className="text-xs text-gray-500">
          共 {MOCK_GENRES.length} 个品类
        </div>
        <button className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" />
          新建品类
        </button>
      </div>
    </div>
  );
}
