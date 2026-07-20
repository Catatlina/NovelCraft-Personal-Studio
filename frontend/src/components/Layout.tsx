import React, { useState } from "react";
import { Search, Bell, Sun, Moon, LogOut, ChevronDown, PanelLeftClose, PanelLeft } from "lucide-react";
import { useTheme } from "./ThemeProvider";

type Tab = "dashboard" | "overview" | "workspace" | "ranking" | "library" | "wizard" | "progress" | "review" | "editor" | "costs" | "billing" | "prompts" | "dag" | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout" | "versions" | "foreshadowing" | "collaboration" | "agents" | "plugins";

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active?: boolean; onClick: () => void }) {
  return (
    <div className={`nav-item${active ? ' active' : ''}`} onClick={onClick} style={{ cursor: 'pointer' }}>
      {icon}
      <span className="nav-label">{label}</span>
    </div>
  );
}

function NavGroup({ title, icon, defaultOpen, children }: { title: string; icon?: React.ReactNode; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen ?? true);
  return (
    <div className={`nav-group${open ? '' : ' collapsed'}`}>
      <div className="nav-group-title" onClick={() => setOpen(!open)}>
        {title}
        <ChevronDown className="nav-chevron" size={14} />
      </div>
      <div className="nav-sub">{children}</div>
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

  const isActive = (t: Tab) => tab === t;

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          </div>
          <span className="brand-text">NovelCraft</span>
        </div>

        {/* 概览 */}
        <div className="nav-group">
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>}
            label="概览" active={isActive('overview')} onClick={() => setTab('overview')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>}
            label="工作台" active={isActive('dashboard')} onClick={() => setTab('dashboard')} />
        </div>

        {/* 小说创作 */}
        <NavGroup title="小说创作" defaultOpen={['wizard','ranking','library','editor','progress','review','foreshadowing'].includes(tab)}>
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg>}
            label="灵感创作" active={isActive('wizard')} onClick={() => setTab('wizard')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg>}
            label="扫榜选书" active={isActive('ranking')} onClick={() => setTab('ranking')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>}
            label="书库管理" active={isActive('library')} onClick={() => setTab('library')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>}
            label="编辑器" active={isActive('editor')} onClick={() => setTab('editor')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>}
            label="创作进度" active={isActive('progress')} onClick={() => setTab('progress')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>}
            label="审阅" active={isActive('review')} onClick={() => setTab('review')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 7l3 3M17 7l-3 3M7 17l3-3M17 17l-3-3"/></svg>}
            label="伏笔看板" active={isActive('foreshadowing')} onClick={() => setTab('foreshadowing')} />
        </NavGroup>

        {/* 自媒体中心 */}
        <NavGroup title="自媒体中心" defaultOpen={['hotspot','studio','fanout','knowledge'].includes(tab)}>
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 6v6l4 2"/></svg>}
            label="热点追踪" active={isActive('hotspot')} onClick={() => setTab('hotspot')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>}
            label="内容工作室" active={isActive('studio')} onClick={() => setTab('studio')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg>}
            label="多平台分发" active={isActive('fanout')} onClick={() => setTab('fanout')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>}
            label="知识库" active={isActive('knowledge')} onClick={() => setTab('knowledge')} />
        </NavGroup>

        {/* 工具服务 */}
        <NavGroup title="工具服务" defaultOpen={['publish','costs','billing','prompts','dag','versions'].includes(tab)}>
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>}
            label="发布看板" active={isActive('publish')} onClick={() => setTab('publish')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>}
            label="成本追踪" active={isActive('costs')} onClick={() => setTab('costs')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>}
            label="订阅套餐" active={isActive('billing')} onClick={() => setTab('billing')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
            label="Prompt管理" active={isActive('prompts')} onClick={() => setTab('prompts')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4v7a2 2 0 0 1-2 2H6"/></svg>}
            label="工作流编排" active={isActive('dag')} onClick={() => setTab('dag')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>}
            label="版本树" active={isActive('versions')} onClick={() => setTab('versions')} />
        </NavGroup>

        {/* 实验室 — 低频/实验性入口，默认折叠（P1-T6） */}
        <NavGroup title="实验室" defaultOpen={['agents','plugins','collaboration'].includes(tab)}>
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>}
            label="插件管理" active={isActive('plugins')} onClick={() => setTab('plugins')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4M8 16h.01M16 16h.01"/></svg>}
            label="智能体" active={isActive('agents')} onClick={() => setTab('agents')} />
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
            label="协作管理" active={isActive('collaboration')} onClick={() => setTab('collaboration')} />
        </NavGroup>

        {/* 设置 */}
        <div className="nav-group">
          <NavItem icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>}
            label="设置" active={isActive('settings')} onClick={() => setTab('settings')} />
        </div>

        {/* Bottom */}
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={toggleTheme} title="切换主题">
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            <span className="label">{theme === "dark" ? "暗色" : "亮色"}</span>
          </button>
          <button className="nav-item" title="退出" onClick={() => {
            sessionStorage.removeItem('nc_token');
            window.location.reload();
          }}>
            <LogOut size={17} />
            <span className="label">退出</span>
          </button>
          <button className="nav-item collapse-btn" onClick={() => setCollapsed(!collapsed)} title="收起">
            {collapsed ? <PanelLeft size={17} /> : <PanelLeftClose size={17} />}
            <span className="label">{collapsed ? '展开' : '收起侧栏'}</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="app-main">
        <header className="topbar">
          <div className="search-box">
            <Search size={16} />
            <input placeholder="搜索项目、章节或命令… (Ctrl+K)" />
          </div>
          <div className="topbar-right">
            <button className="icon-btn" title="通知"><Bell size={18} /></button>
            <div className="avatar">A</div>
          </div>
        </header>
        <div className="content">
          {children}
        </div>
      </main>
    </div>
  );
}
