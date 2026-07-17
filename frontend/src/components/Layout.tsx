import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Bot,
  ChevronDown,
  Code2,
  DollarSign,
  FileText,
  GitBranch,
  Layers,
  Layout as LayoutIcon,
  LayoutDashboard,
  Library,
  LogOut,
  PanelLeft,
  PanelLeftClose,
  PenTool,
  Radio,
  Search,
  Send,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Moon,
  Target,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import "../styles/proto.css";

type Tab =
  | "dashboard"
  | "ranking"
  | "library"
  | "wizard"
  | "progress"
  | "review"
  | "editor"
  | "costs"
  | "prompts"
  | "dag"
  | "settings"
  | "studio"
  | "publish"
  | "hotspot"
  | "knowledge"
  | "fanout"
  | "versions"
  | "foreshadowing"
  | "collaboration"
  | "agents";

interface NavItem {
  tab: Tab;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
  /** true = collapsible with chevron, false = flat items always visible */
  collapsible: boolean;
}

/** ── Sidebar nav groups matching prototype structure ── */
const NAV_GROUPS: NavGroup[] = [
  {
    id: "overview",
    label: "",
    collapsible: false,
    items: [
      { tab: "dashboard", label: "概览", icon: <LayoutDashboard size={17} /> },
      { tab: "dashboard", label: "工作台", icon: <LayoutIcon size={17} /> },
    ],
  },
  {
    id: "writing",
    label: "小说创作",
    collapsible: true,
    items: [
      { tab: "wizard", label: "灵感创作", icon: <Sparkles size={17} /> },
      { tab: "ranking", label: "扫榜选书", icon: <TrendingUp size={17} /> },
      { tab: "library", label: "书库管理", icon: <Library size={17} /> },
      { tab: "editor", label: "编辑器", icon: <FileText size={17} /> },
      { tab: "progress", label: "创作进度", icon: <GitBranch size={17} /> },
      { tab: "review", label: "审阅", icon: <BookOpen size={17} /> },
      { tab: "foreshadowing", label: "伏笔看板", icon: <Target size={17} /> },
    ],
  },
  {
    id: "media",
    label: "自媒体中心",
    collapsible: true,
    items: [
      { tab: "hotspot", label: "热点追踪", icon: <TrendingUp size={17} /> },
      { tab: "studio", label: "内容工作室", icon: <Layers size={17} /> },
      { tab: "fanout", label: "多平台分发", icon: <Send size={17} /> },
      { tab: "knowledge", label: "知识库", icon: <Search size={17} /> },
    ],
  },
  {
    id: "tools",
    label: "工具服务",
    collapsible: true,
    items: [
      { tab: "publish", label: "发布看板", icon: <Send size={17} /> },
      { tab: "costs", label: "成本追踪", icon: <DollarSign size={17} /> },
      { tab: "prompts", label: "Prompt 管理", icon: <Code2 size={17} /> },
      { tab: "dag", label: "工作流编排", icon: <Share2 size={17} /> },
      { tab: "versions", label: "版本树", icon: <GitBranch size={17} /> },
      { tab: "collaboration", label: "协作管理", icon: <Users size={17} /> },
      { tab: "agents", label: "智能体", icon: <Bot size={17} /> },
    ],
  },
  {
    id: "settings",
    label: "",
    collapsible: false,
    items: [
      { tab: "settings", label: "设置", icon: <Settings size={17} /> },
    ],
  },
];

/** Find which group contains the active tab */
function findGroupForTab(tab: Tab): string {
  for (const g of NAV_GROUPS) {
    if (g.items.some((item) => item.tab === tab)) return g.id;
  }
  return "";
}

export function Layout({
  tab,
  setTab,
  title,
  runStatus,
  children,
}: {
  tab: Tab;
  setTab: (t: Tab) => void;
  title: string;
  runStatus?: string;
  children: React.ReactNode;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const workspaceRef = useRef<HTMLElement>(null);

  // ── Collapsible group state: expanded set ──
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const s = new Set<string>();
    const gid = findGroupForTab(tab);
    if (gid) s.add(gid);
    // Expand all collapsible groups by default
    for (const g of NAV_GROUPS) {
      if (g.collapsible) s.add(g.id);
    }
    return s;
  });

  // Auto-expand parent group when tab changes
  useEffect(() => {
    const gid = findGroupForTab(tab);
    if (gid) {
      setExpanded((prev) => {
        if (prev.has(gid)) return prev;
        const next = new Set(prev);
        next.add(gid);
        return next;
      });
    }
  }, [tab]);

  // Scroll to top on tab change
  useEffect(() => {
    workspaceRef.current?.scrollTo(0, 0);
    window.scrollTo(0, 0);
  }, [tab]);

  // ── Theme ──
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  }

  // ── Sidebar collapse ──
  function toggleSidebar() {
    setSidebarCollapsed((prev) => !prev);
  }

  // ── Group expand/collapse ──
  function toggleGroup(groupId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  return (
    <div className="layout">
      {/* ══════════ SIDEBAR ══════════ */}
      <aside className={`sidebar${sidebarCollapsed ? " collapsed" : ""}`}>
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="brand-icon">
            <LayoutIcon size={18} />
          </div>
          <span className="brand-text">NovelCraft</span>
        </div>

        {/* Navigation groups */}
        {NAV_GROUPS.map((group) => {
          const isExpanded = expanded.has(group.id);
          const hasActive = group.items.some((item) => item.tab === tab);

          if (group.collapsible) {
            // Collapsible group: title + chevron + sub-items
            return (
              <div
                key={group.id}
                className={`nav-group${isExpanded ? "" : " collapsed"}`}
              >
                <button
                  className="nav-group-title"
                  onClick={() => toggleGroup(group.id)}
                >
                  {group.label}
                  <ChevronDown size={14} className="nav-chevron" />
                </button>
                <div className="nav-sub">
                  {group.items.map((item) => (
                    <button
                      key={item.tab}
                      className={`nav-item${
                        tab === item.tab ? " active" : ""
                      }`}
                      onClick={() => setTab(item.tab)}
                    >
                      {item.icon}
                      <span className="nav-label">{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          }

          // Flat group: items always visible
          return (
            <div key={group.id} className="nav-group">
              {group.items.map((item) => (
                <button
                  key={item.tab + "-" + item.label}
                  className={`nav-item${tab === item.tab ? " active" : ""}`}
                  onClick={() => setTab(item.tab)}
                >
                  {item.icon}
                  <span className="nav-label">{item.label}</span>
                </button>
              ))}
            </div>
          );
        })}

        {/* Bottom section */}
        <div className="sidebar-bottom">
          <div className="theme-row">
            <button
              className="nav-item"
              onClick={toggleTheme}
              title="切换主题"
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              <span className="label">
                {theme === "dark" ? "亮色" : "暗色"}
              </span>
            </button>
            <button
              className="nav-item"
              onClick={() => (window as any).__ncLogout?.()}
              title="退出"
            >
              <LogOut size={17} />
              <span className="label">退出</span>
            </button>
          </div>
          <button
            className="nav-item collapse-btn"
            onClick={toggleSidebar}
            title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          >
            {sidebarCollapsed ? (
              <PanelLeft size={17} />
            ) : (
              <PanelLeftClose size={17} />
            )}
            <span className="label">
              {sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
            </span>
          </button>
        </div>
      </aside>

      {/* ══════════ MAIN ══════════ */}
      <section className="workspace" ref={workspaceRef}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 18,
          }}
        >
          <h1 style={{ fontSize: 24, margin: 0 }}>{title}</h1>
          {runStatus && (
            <span className={`pill ${runStatus}`}>{runStatus}</span>
          )}
        </div>
        {children}
      </section>
    </div>
  );
}
