import React, { useState, useCallback } from "react";
import { Search, Bell, Sun, Moon, LogOut, ChevronDown, PanelLeftClose, PanelLeft, Sparkles, BookOpen, Zap, LayoutDashboard, Settings, Bot, PlugZap, Wrench } from "lucide-react";
import { useTheme } from "./ThemeProvider";

type Tab = "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard" | "progress" | "review" | "editor" | "costs" | "billing" | "prompts" | "dag" | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout" | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins" | "skills" | "chat" | "marketplace";

type NavSection = {
  id: string;
  label: string;
  icon: React.ReactNode;
  items: { id: Tab; label: string; icon?: React.ReactNode }[];
};

const NAV_SECTIONS: NavSection[] = [
  { id: "home", label: "首页", icon: <LayoutDashboard size={16} />, items: [
    { id: "dashboard", label: "工作台" },
  ]},
  { id: "novel", label: "小说创作", icon: <BookOpen size={16} />, items: [
    { id: "ranking", label: "扫榜选书" },
    { id: "library", label: "书库" },
    { id: "wizard", label: "灵感创作" },
    { id: "editor", label: "编辑器" },
    { id: "progress", label: "创作进度" },
    { id: "review", label: "审阅" },
    { id: "foreshadowing", label: "伏笔" },
    { id: "versions", label: "版本" },
    { id: "publish", label: "发布" },
  ]},
  { id: "content", label: "内容中心", icon: <Sparkles size={16} />, items: [
    { id: "hotspot", label: "热点追踪" },
    { id: "studio", label: "内容工作室" },
    { id: "knowledge", label: "知识库" },
    { id: "fanout", label: "多平台分发" },
  ]},
  { id: "ai", label: "AI 平台", icon: <Bot size={16} />, items: [
    { id: "chat", label: "AI 对话" },
    { id: "prompts", label: "Prompt" },
    { id: "dag", label: "工作流" },
    { id: "agents", label: "Agent" },
    { id: "skills", label: "Skill" },
    { id: "marketplace", label: "模块市场" },
  ]},
  { id: "system", label: "系统", icon: <Settings size={16} />, items: [
    { id: "settings", label: "设置" },
    { id: "costs", label: "成本" },
    { id: "billing", label: "套餐" },
  ]},
];

function NavSection({ section, tab, setTab }: { section: NavSection; tab: Tab; setTab: (t: Tab) => void }) {
  const [open, setOpen] = useState(true);
  return (
    <div className={`nav-section${open ? '' : ' collapsed'}`}>
      <div className="nav-section-title" onClick={() => setOpen(!open)}>
        {section.icon}
        <span>{section.label}</span>
        <ChevronDown size={12} className={`nav-chevron${open ? '' : ' rotated'}`} />
      </div>
      {open && (
        <div className="nav-items">
          {section.items.map(item => (
            <div
              key={item.id}
              className={`nav-item${tab === item.id ? ' active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Layout({ tab, setTab, title, children }: {
  tab: Tab; setTab: (t: Tab) => void; title: string;
  runStatus?: string; children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const { theme, setTheme } = useTheme();
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className={`app-sidebar${collapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-header">
          {!collapsed && <><Sparkles size={18} /><span className="logo">星禾AI</span></>}
          <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <PanelLeft size={14} /> : <PanelLeftClose size={14} />}
          </button>
        </div>
        <nav className="sidebar-nav">
          {NAV_SECTIONS.map(section => (
            <NavSection key={section.id} section={section} tab={tab} setTab={setTab} />
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item" onClick={toggleTheme}>
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
            {!collapsed && <span style={{ marginLeft: 8 }}>{theme === "dark" ? "浅色" : "深色"}</span>}
          </button>
          <button className="nav-item" onClick={() => { localStorage.clear(); window.location.reload(); }}>
            <LogOut size={14} />
            {!collapsed && <span style={{ marginLeft: 8 }}>退出</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="app-main">
        <header className="app-header">
          <h2 className="app-title">{title}</h2>
          <div className="header-actions">
            <Search size={16} className="header-icon" />
            <Bell size={16} className="header-icon" />
            <div className="user-avatar">G</div>
          </div>
        </header>
        <div className="app-content">
          {children}
        </div>
      </main>
    </div>
  );
}
