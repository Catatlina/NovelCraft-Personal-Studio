import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen, Check, ChevronDown, CircleDollarSign, Code2, FileText,
  GitBranch, Layout as LayoutIcon, LayoutDashboard, Layers, Library,
  Lightbulb, LogOut, PenTool, Radio, Rocket, Search, Send, Settings,
  Sparkles, Sun, Moon, Terminal, TrendingUp, Users, Workflow, Wrench
} from "lucide-react";

type Tab = "dashboard" | "ranking" | "library" | "wizard" | "progress" | "review" | "editor" | "costs" | "prompts" | "dag" | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout" | "versions" | "foreshadowing" | "collaboration" | "agents";

interface SubItem {
  tab: Tab;
  label: string;
  icon: React.ReactNode;
}

interface Category {
  id: string;
  label: string;
  icon: React.ReactNode;
  items: SubItem[];
  /** If true, clicking the header itself navigates (no expand/collapse) */
  directLink?: Tab;
}

const CATEGORIES: Category[] = [
  {
    id: "overview",
    label: "概览",
    icon: <LayoutIcon size={18} />,
    items: [
      { tab: "dashboard", label: "工作台", icon: <LayoutDashboard size={16} /> },
    ],
  },
  {
    id: "writing",
    label: "小说创作",
    icon: <PenTool size={18} />,
    items: [
      { tab: "wizard", label: "灵感创作", icon: <Sparkles size={16} /> },
      { tab: "ranking", label: "扫榜选书", icon: <BookOpen size={16} /> },
      { tab: "library", label: "书库管理", icon: <Library size={16} /> },
      { tab: "editor", label: "编辑器", icon: <FileText size={16} /> },
      { tab: "progress", label: "创作进度", icon: <GitBranch size={16} /> },
      { tab: "review", label: "审阅", icon: <Check size={16} /> },
      { tab: "foreshadowing", label: "伏笔看板", icon: <Lightbulb size={16} /> },
    ],
  },
  {
    id: "media",
    label: "自媒体中心",
    icon: <Radio size={18} />,
    items: [
      { tab: "hotspot", label: "热点追踪", icon: <TrendingUp size={16} /> },
      { tab: "studio", label: "内容工作室", icon: <Layers size={16} /> },
      { tab: "fanout", label: "多平台分发", icon: <Send size={16} /> },
      { tab: "knowledge", label: "知识库", icon: <Search size={16} /> },
    ],
  },
  {
    id: "tools",
    label: "工具服务",
    icon: <Wrench size={18} />,
    items: [
      { tab: "publish", label: "发布看板", icon: <Rocket size={16} /> },
      { tab: "costs", label: "成本追踪", icon: <CircleDollarSign size={16} /> },
      { tab: "prompts", label: "Prompt管理", icon: <Code2 size={16} /> },
      { tab: "dag", label: "工作流编排", icon: <Workflow size={16} /> },
      { tab: "versions", label: "版本树", icon: <GitBranch size={16} /> },
      { tab: "collaboration", label: "协作管理", icon: <Users size={16} /> },
      { tab: "agents", label: "智能体", icon: <Terminal size={16} /> },
    ],
  },
  {
    id: "settings",
    label: "设置",
    icon: <Settings size={18} />,
    items: [],
    directLink: "settings",
  },
];

/** Map each tab to its parent category id */
function findCategoryForTab(tab: Tab): string {
  for (const cat of CATEGORIES) {
    if (cat.items.some((item) => item.tab === tab)) return cat.id;
    if (cat.directLink === tab) return cat.id;
  }
  return "";
}

export function Layout({ tab, setTab, title, runStatus, children }: {
  tab: Tab; setTab: (t: Tab) => void; title: string;
  runStatus?: string; children: React.ReactNode;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const workspaceRef = useRef<HTMLElement>(null);

  // Initialize expanded categories: the one containing the active tab is open
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const s = new Set<string>();
    const cat = findCategoryForTab(tab);
    if (cat) s.add(cat);
    return s;
  });

  // When active tab changes, auto-expand its parent category
  useEffect(() => {
    const cat = findCategoryForTab(tab);
    if (cat) {
      setExpanded((prev) => {
        if (prev.has(cat)) return prev;
        const next = new Set(prev);
        next.add(cat);
        return next;
      });
    }
  }, [tab]);

  // Scroll to top on tab change
  useEffect(() => { workspaceRef.current?.scrollTo(0, 0); window.scrollTo(0, 0); }, [tab]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next); document.documentElement.setAttribute("data-theme", next);
  }

  function toggleCategory(catId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) next.delete(catId);
      else next.add(catId);
      return next;
    });
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><span>N</span> NovelCraft</div>
        <nav className="sidebar-nav">
          {CATEGORIES.map((cat) => (
            <SidebarCategory
              key={cat.id}
              category={cat}
              activeTab={tab}
              expanded={expanded.has(cat.id)}
              onToggle={() => {
                if (cat.directLink) {
                  setTab(cat.directLink);
                } else {
                  toggleCategory(cat.id);
                }
              }}
              onSelectTab={(t) => setTab(t)}
            />
          ))}
        </nav>
        <div className="theme-toggle">
          <button onClick={toggleTheme}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}{theme === "dark" ? "亮色" : "暗色"}</button>
          <button onClick={() => { (window as any).__ncLogout?.() }} style={{ marginLeft: 8 }} title="登出">
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <section className="workspace" ref={workspaceRef}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>{title}</h1>
          {runStatus && <span className={`pill ${runStatus}`}>{runStatus}</span>}
        </div>
        {children}
      </section>
    </div>
  );
}

function SidebarCategory({
  category,
  activeTab,
  expanded,
  onToggle,
  onSelectTab,
}: {
  category: Category;
  activeTab: Tab;
  expanded: boolean;
  onToggle: () => void;
  onSelectTab: (t: Tab) => void;
}) {
  const hasActive = category.items.some((item) => item.tab === activeTab) ||
    category.directLink === activeTab;
  const isDirect = !!category.directLink;

  return (
    <div className={`sidebar-category${hasActive && !isDirect ? " has-active" : ""}`}>
      <button
        className={`sidebar-cat-header${hasActive ? " active" : ""}`}
        onClick={onToggle}
        title={category.label}
      >
        <span className="sidebar-cat-icon">{category.icon}</span>
        <span className="sidebar-cat-label">{category.label}</span>
        {!isDirect && (
          <ChevronDown
            size={14}
            className={`sidebar-cat-chevron${expanded ? " open" : ""}`}
          />
        )}
      </button>
      {!isDirect && (
        <div className={`sidebar-cat-items${expanded ? " expanded" : ""}`}>
          {category.items.map((item) => (
            <button
              key={item.tab}
              className={`sidebar-sub-item${activeTab === item.tab ? " active" : ""}`}
              onClick={() => onSelectTab(item.tab)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
