import React, { useState } from "react";
import {
  BookOpen,
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

export type AppTab =
  | "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard"
  | "progress" | "review" | "editor" | "costs" | "billing" | "prompts" | "dag"
  | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout"
  | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins"
  | "skills" | "chat" | "marketplace";

const NAV_ITEMS: Array<{ id: AppTab; label: string; icon: React.ReactNode }> = [
  { id: "dashboard", label: "小说首页", icon: <Sparkles size={19} /> },
  { id: "wizard", label: "创作向导", icon: <WandSparkles size={19} /> },
  { id: "ranking", label: "扫榜选书", icon: <Search size={19} /> },
  { id: "library", label: "我的书库", icon: <Library size={19} /> },
  { id: "progress", label: "创作进度", icon: <CircleCheckBig size={19} /> },
  { id: "editor", label: "章节编辑器", icon: <FilePenLine size={19} /> },
  { id: "review", label: "审阅与一致性", icon: <BookOpen size={19} /> },
  { id: "settings", label: "小说设置", icon: <Settings size={19} /> },
];

const RUN_LABELS: Record<string, string> = {
  pending: "等待开始",
  running: "AI 创作中",
  waiting_human: "等待确认",
  succeeded: "创作完成",
  failed: "需要处理",
};

export function Layout({
  tab,
  setTab,
  title,
  runStatus,
  userEmail,
  children,
}: {
  tab: AppTab;
  setTab: (tab: AppTab) => void;
  title: string;
  runStatus?: string;
  userEmail?: string;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(true);
  const [hovered, setHovered] = useState(false);
  const { theme, setTheme } = useTheme();
  const expanded = !collapsed || hovered;
  const initials = (userEmail?.trim()[0] || "S").toUpperCase();

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
          <div className="app-header-title">
            <h1>{title}</h1>
            {runStatus && <span className={`run-state ${runStatus}`}>{RUN_LABELS[runStatus] || runStatus}</span>}
          </div>
          <div className="header-actions">
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
