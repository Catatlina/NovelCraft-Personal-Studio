import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Brain,
  CircleCheckBig,
  FilePenLine,
  Library,
  LogOut,
  Moon,
  PanelLeft,
  PanelLeftClose,
  Search,
  Settings,
  Sparkles,
  Sun,
  WandSparkles,
} from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { cleanNovelTitle } from "../lib/titleDisplay";

export type AppTab =
  | "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard"
  | "progress" | "review" | "editor" | "costs" | "billing" | "prompts" | "dag"
  | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout"
  | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins"
  | "skills" | "chat" | "marketplace" | "v7" | "genre-manager" | "quality-analysis";

const NAV_ITEMS: Array<{ id: AppTab; label: string; icon: React.ReactNode }> = [
  { id: "dashboard", label: "小说首页", icon: <Sparkles size={19} /> },
  { id: "wizard", label: "创作向导", icon: <WandSparkles size={19} /> },
  { id: "ranking", label: "扫榜选书", icon: <Search size={19} /> },
  { id: "library", label: "我的书库", icon: <Library size={19} /> },
  { id: "progress", label: "创作进度", icon: <CircleCheckBig size={19} /> },
  { id: "editor", label: "章节编辑器", icon: <FilePenLine size={19} /> },
  { id: "review", label: "审阅与一致性", icon: <BookOpen size={19} /> },
  { id: "v7", label: "V7 智能体", icon: <Brain size={19} /> },
  { id: "settings", label: "小说设置", icon: <Settings size={19} /> },
];

const RUN_LABELS: Record<string, string> = {
  pending: "等待开始",
  queued: "已排队",
  running: "AI 创作中",
  waiting_human: "等待确认",
  pending_approval: "等待生成确认",
  succeeded: "创作完成",
  failed: "需要处理",
  pending_provider: "需要处理",
  pending_budget: "需要处理",
  needs_review: "质量待处理",
  dispatch_failed: "派发失败",
};

export function Layout({
  tab,
  setTab,
  title,
  runStatus,
  userEmail,
  projects,
  currentProjectId,
  onProjectChange,
  novels,
  currentNovelId,
  onNovelChange,
  showSelector,
  children,
}: {
  tab: AppTab;
  setTab: (tab: AppTab) => void;
  title: string;
  runStatus?: string;
  userEmail?: string;
  projects?: Array<{ id: string; name: string }>;
  currentProjectId?: string | null;
  onProjectChange?: (projectId: string) => void;
  novels?: Array<{ id: string; title: string }>;
  currentNovelId?: string | null;
  onNovelChange?: (novelId: string) => void;
  showSelector?: boolean;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(true);
  const [hovered, setHovered] = useState(false);
  const { theme, setTheme } = useTheme();
  const [selectedId, setSelectedId] = useState(currentNovelId);
  const expanded = !collapsed || hovered;
  const initials = (userEmail?.trim()[0] || "S").toUpperCase();

  useEffect(() => {
    setSelectedId(currentNovelId);
  }, [currentNovelId]);

  return (
    <div className="app-shell">
      <aside
        className={`app-sidebar${expanded ? " expanded" : " collapsed"}`}
        onMouseEnter={() => collapsed && setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div className="sidebar-header">
          <button
            type="button"
            className="brand-mark"
            aria-label="返回小说首页"
            onClick={() => { setTab("dashboard"); setHovered(false); }}
          >
            <Sparkles size={20} />
          </button>
          <span className="logo">Starlume AI</span>
          <button
            type="button"
            className="sidebar-toggle"
            aria-label={collapsed ? "固定展开导航" : "收起导航"}
            onClick={() => { setCollapsed(value => !value); setHovered(false); }}
          >
            {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="小说创作主导航">
          {NAV_ITEMS.map(item => (
            <button
              type="button"
              key={item.id}
              className={`nav-item${tab === item.id ? " active" : ""}`}
              aria-current={tab === item.id ? "page" : undefined}
              aria-label={item.label}
              title={!expanded ? item.label : undefined}
              onClick={() => { setTab(item.id); setHovered(false); }}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button
            type="button"
            className="nav-item"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? "切换浅色模式" : "切换深色模式"}
          >
            {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
            <span>{theme === "dark" ? "浅色模式" : "深色模式"}</span>
          </button>
          <button
            type="button"
            className="nav-item"
            aria-label="退出登录"
            onClick={() => void (window as Window & { __ncLogout?: () => Promise<void> }).__ncLogout?.()}
          >
            <LogOut size={19} />
            <span>退出登录</span>
          </button>
        </div>
      </aside>

      <main className={`app-main${collapsed ? "" : " sidebar-pinned"}`}>
        <header className="app-header">
          <div className="app-header-left">
            <div className="header-brand" aria-label="Starlume AI 工作台">Starlume AI</div>
            <span className="header-breadcrumb-divider" aria-hidden="true">/</span>
            <div className="app-header-title">
              <h1>{title}</h1>
              {runStatus && <span className={`run-state ${runStatus}`}>{RUN_LABELS[runStatus] || runStatus}</span>}
            </div>
          </div>
          <div className="header-actions">
            {projects && projects.length > 1 && (
              <select
                className="project-selector"
                value={currentProjectId || ""}
                onChange={event => onProjectChange?.(event.target.value)}
                aria-label="选择项目"
                title="切换项目，查看对应书库和历史记录"
              >
                {projects.map(project => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            )}
            {showSelector && novels && novels.length > 0 && (
              <select
                className="novel-selector"
                value={selectedId || ""}
                onChange={e => {
                  const id = e.target.value;
                  setSelectedId(id);
                  onNovelChange?.(id);
                }}
                aria-label="切换作品"
              >
                {novels.map(n => (
                  <option key={n.id} value={n.id}>{cleanNovelTitle(n.title, "待命名作品")}</option>
                ))}
              </select>
            )}
            <button
              type="button"
              className="command-trigger"
              onClick={() => window.dispatchEvent(new Event("starlume:open-command-palette"))}
              aria-label="打开全局搜索"
            >
              <Search size={16} />
              <span>搜索</span>
              <kbd>⌘ K</kbd>
            </button>
            <div className="user-avatar" title={userEmail || "Starlume 用户"}>{initials}</div>
          </div>
        </header>
        <div className="app-content">
          <div className="content-frame">{children}</div>
        </div>
      </main>

      <nav className="mobile-tabbar" aria-label="移动端小说创作主导航">
        {NAV_ITEMS.map(item => (
          <button
            type="button"
            key={item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
            aria-label={item.label}
          >
            {item.icon}
            <span>{item.label.replace("章节", "").replace("小说", "")}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
