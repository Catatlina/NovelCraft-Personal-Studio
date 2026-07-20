import React, { useEffect, useState } from "react";
import { api as baseApi } from "../lib/api";
import { Download, Trash2, Power, PowerOff, Package, Globe, GitBranch } from "lucide-react";

type ModuleInfo = {
  id: string; name: string; description: string; icon: string;
  version: string; source: string; source_url: string;
  enabled: boolean; installed: boolean; route: string; category: string;
};

const api = baseApi as any;

export function Marketplace() {
  const [modules, setModules] = useState<Record<string, ModuleInfo[]>>({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");

  const fetchModules = async () => {
    try {
      const r = await api("/modules");
      setModules(r.data?.categories || {});
    } catch (e) { /* offline */ }
    setLoading(false);
  };

  useEffect(() => { fetchModules(); }, []);

  const toggle = async (id: string, enabled: boolean) => {
    await api(`/modules/${id}/toggle?enabled=${enabled}`, {method: "POST"});
    fetchModules();
  };

  const install = async (id: string) => {
    await api(`/modules/${id}/install`, {method: "POST"});
    fetchModules();
  };

  const uninstall = async (id: string) => {
    await api(`/modules/${id}/uninstall`, {method: "POST"});
    fetchModules();
  };

  if (loading) return <div className="panel">加载中…</div>;

  const CAT_NAMES: Record<string, string> = {
    novel: "📖 小说创作", content: "🔥 内容中心", ai: "🤖 AI 平台",
    system: "⚙️ 系统", community: "🌐 社区",
  };

  return (
    <div className="marketplace">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>🧩 模块市场</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {["all", "novel", "content", "ai", "system", "community"].map(t => (
            <button key={t} className={`btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setTab(t)}>
              {t === "all" ? "全部" : CAT_NAMES[t] || t}
            </button>
          ))}
        </div>
      </div>

      {Object.entries(modules).map(([cat, mods]) => {
        const filtered = tab === "all" ? mods : mods.filter(m => m.category === tab);
        if (!filtered.length) return null;
        return (
          <div key={cat} style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, color: "var(--text-muted)", marginBottom: 12, textTransform: "uppercase", letterSpacing: ".5px" }}>
              {CAT_NAMES[cat] || cat}
            </h3>
            <div className="module-grid">
              {filtered.map(m => (
                <div key={m.id} className={`module-card${!m.installed ? ' uninstalled' : ''}${!m.enabled ? ' disabled' : ''}`}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 24 }}>{m.icon}</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{m.name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        v{m.version}
                        {m.source === "github" && <><GitBranch size={10} style={{ marginLeft: 4, verticalAlign: "middle" }} /> GitHub</>}
                        {m.source === "marketplace" && <><Globe size={10} style={{ marginLeft: 4, verticalAlign: "middle" }} /> Market</>}
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "8px 0" }}>{m.description}</p>
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    {!m.installed ? (
                      <button className="btn-sm btn-primary" onClick={() => install(m.id)}>
                        <Download size={12} /> 安装
                      </button>
                    ) : (
                      <>
                        <button className={`btn-sm ${m.enabled ? "btn-ghost" : "btn-primary"}`}
                                onClick={() => toggle(m.id, !m.enabled)}>
                          {m.enabled ? <><PowerOff size={12} /> 禁用</> : <><Power size={12} /> 启用</>}
                        </button>
                        {m.source !== "builtin" && (
                          <button className="btn-sm btn-danger" onClick={() => uninstall(m.id)}>
                            <Trash2 size={12} /> 卸载
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      <div style={{ marginTop: 32, padding: 16, background: "var(--bg-hover)", borderRadius: 8, fontSize: 13 }}>
        <strong>🔌 从 GitHub 安装插件：</strong>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <input placeholder="https://github.com/user/repo" style={{ flex: 1 }} />
          <button className="btn-primary">安装</button>
        </div>
      </div>
    </div>
  );
}
