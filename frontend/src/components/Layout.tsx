import React, { useState } from "react";
import { Check, CircleDollarSign, Code2, FileText, GitBranch, Settings, Sparkles, Sun, Moon, Workflow } from "lucide-react";

type Tab = "wizard" | "progress" | "review" | "editor" | "costs" | "prompts" | "dag" | "settings";

export function Layout({ tab, setTab, title, runStatus, children }: {
  tab: Tab; setTab: (t: Tab) => void; title: string;
  runStatus?: string; children: React.ReactNode;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next); document.documentElement.setAttribute("data-theme", next);
  }
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><span>N</span> NovelCraft</div>
        <nav>
          <TabBtn icon={<Sparkles size={18} />} active={tab==="wizard"} label="创作向导" onClick={()=>setTab("wizard")} />
          <TabBtn icon={<GitBranch size={18} />} active={tab==="progress"} label="生成进度" onClick={()=>setTab("progress")} />
          <TabBtn icon={<Check size={18} />} active={tab==="review"} label="审阅" onClick={()=>setTab("review")} />
          <TabBtn icon={<FileText size={18} />} active={tab==="editor"} label="编辑器" onClick={()=>setTab("editor")} />
          <TabBtn icon={<CircleDollarSign size={18} />} active={tab==="costs"} label="成本追踪" onClick={()=>setTab("costs")} />
          <TabBtn icon={<Code2 size={18} />} active={tab==="prompts"} label="Prompt" onClick={()=>setTab("prompts")} />
          <TabBtn icon={<Workflow size={18} />} active={tab==="dag"} label="工作流" onClick={()=>setTab("dag")} />
          <TabBtn icon={<Settings size={18} />} active={tab==="settings"} label="设置" onClick={()=>setTab("settings")} />
        </nav>
        <div className="theme-toggle">
          <button onClick={toggleTheme}>{theme==="dark"?<Sun size={16}/>:<Moon size={16}/>}{theme==="dark"?"亮色":"暗色"}</button>
        </div>
      </aside>
      <section className="workspace">
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
