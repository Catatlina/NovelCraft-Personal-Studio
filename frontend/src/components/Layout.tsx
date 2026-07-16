import React, { useEffect, useRef, useState } from "react";
import { BookOpen, Check, CircleDollarSign, Code2, FileText, GitBranch, Library, Layers, LogOut, Rocket, Settings, Sparkles, Sun, Moon, Workflow, TrendingUp, Search, Send, Lightbulb, Users, Terminal } from "lucide-react";

type Tab = "ranking" | "library" | "wizard" | "progress" | "review" | "editor" | "costs" | "prompts" | "dag" | "settings" | "studio" | "publish" | "hotspot" | "knowledge" | "fanout" | "versions" | "foreshadowing" | "collaboration" | "agents";

export function Layout({ tab, setTab, title, runStatus, children }: {
  tab: Tab; setTab: (t: Tab) => void; title: string;
  runStatus?: string; children: React.ReactNode;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const workspaceRef = useRef<HTMLElement>(null);
  // 切换页面时回到顶部，避免沿用上一页的滚动位置导致内容看似空白。
  // 实际滚动容器是 document（.workspace 未产生内部滚动），两者都归零以兼容布局变化。
  useEffect(() => { workspaceRef.current?.scrollTo(0, 0); window.scrollTo(0, 0); }, [tab]);
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next); document.documentElement.setAttribute("data-theme", next);
  }
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><span>N</span> NovelCraft</div>
        <nav>
          <TabBtn icon={<BookOpen size={18} />} active={tab==="ranking"} label="扫榜中心" onClick={()=>setTab("ranking")} />
          <TabBtn icon={<Library size={18} />} active={tab==="library"} label="书库" onClick={()=>setTab("library")} />
          <TabBtn icon={<Sparkles size={18} />} active={tab==="wizard"} label="创作向导" onClick={()=>setTab("wizard")} />
          <TabBtn icon={<GitBranch size={18} />} active={tab==="progress"} label="生成进度" onClick={()=>setTab("progress")} />
          <TabBtn icon={<Check size={18} />} active={tab==="review"} label="审阅" onClick={()=>setTab("review")} />
          <TabBtn icon={<FileText size={18} />} active={tab==="editor"} label="编辑器" onClick={()=>setTab("editor")} />
          <TabBtn icon={<CircleDollarSign size={18} />} active={tab==="costs"} label="成本追踪" onClick={()=>setTab("costs")} />
          <TabBtn icon={<Code2 size={18} />} active={tab==="prompts"} label="Prompt" onClick={()=>setTab("prompts")} />
          <TabBtn icon={<Workflow size={18} />} active={tab==="dag"} label="工作流" onClick={()=>setTab("dag")} />
          <TabBtn icon={<Settings size={18} />} active={tab==="settings"} label="设置" onClick={()=>setTab("settings")} />
          <TabBtn icon={<Layers size={18} />} active={tab==="studio"} label="工作室" onClick={()=>setTab("studio")} />
          <TabBtn icon={<Rocket size={18} />} active={tab==="publish"} label="发布" onClick={()=>setTab("publish")} />
          <TabBtn icon={<TrendingUp size={18} />} active={tab==="hotspot"} label="热点" onClick={()=>setTab("hotspot")} />
          <TabBtn icon={<Search size={18} />} active={tab==="knowledge"} label="知识库" onClick={()=>setTab("knowledge")} />
          <TabBtn icon={<Send size={18} />} active={tab==="fanout"} label="分发" onClick={()=>setTab("fanout")} />
          <TabBtn icon={<GitBranch size={18} />} active={tab==="versions"} label="版本树" onClick={()=>setTab("versions")} />
          <TabBtn icon={<Lightbulb size={18} />} active={tab==="foreshadowing"} label="伏笔" onClick={()=>setTab("foreshadowing")} />
          <TabBtn icon={<Users size={18} />} active={tab==="collaboration"} label="协作" onClick={()=>setTab("collaboration")} />
          <TabBtn icon={<Terminal size={18} />} active={tab==="agents"} label="智能体" onClick={()=>setTab("agents")} />
        </nav>
        <div className="theme-toggle">
          <button onClick={toggleTheme}>{theme==="dark"?<Sun size={16}/>:<Moon size={16}/>}{theme==="dark"?"亮色":"暗色"}</button>
          <button onClick={() => { (window as any).__ncLogout?.() }} style={{ marginLeft: 8 }} title="登出">
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <section className="workspace" ref={workspaceRef}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:18}}>
          <h1 style={{fontSize:24,margin:0}}>{title}</h1>
          {runStatus&&<span className={`pill ${runStatus}`}>{runStatus}</span>}
        </div>
        {children}
      </section>
    </div>
  );
}

function TabBtn({ icon, active, label, onClick }: { icon: React.ReactNode; active: boolean; label: string; onClick: () => void }) {
  return <button className={active?"active":""} onClick={onClick}>{icon}{label}</button>;
}
