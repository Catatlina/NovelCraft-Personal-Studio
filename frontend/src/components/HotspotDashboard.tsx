import React, { useState, useEffect } from "react";
import { TrendingUp, Zap, Target, Plus } from "lucide-react";
import { api } from "../lib/api";

export function HotspotDashboard() {
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [angles, setAngles] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [notice, setNotice] = useState("");

  const applyResult = (response: any) => {
    const data = response?.data || {};
    setHotspots(data.hotspots || []);
    setAngles((data.creative_angles || []).map((item: any) => typeof item === "string" ? item : item.angle));
    setError("");
  };

  useEffect(() => {
    api("/api/v1/hotspots").then(applyResult).catch(caught => setError(`热点获取失败：${String(caught)}`));
  }, []);

  const generate = async (h: any) => {
    setBusyKey(`${h.source}:${h.title}`); setNotice("");
    try {
      const projects = await api("/api/v1/projects");
      const projectId = projects.data?.[0]?.id;
      const result = await api("/api/v1/hotspots/generate", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          title: h.title,
          source: h.source,
          url: h.url || "",
          platforms: ["wechat", "toutiao", "baijia", "dayu", "xiaohongshu", "douyin"],
        }),
      });
      setNotice(`已生成 ${result.data?.items?.length || 0} 篇/条平台内容草稿。`);
    } catch (caught) {
      setError(`内容生成失败：${String(caught)}`);
    } finally {
      setBusyKey("");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="panel">
        <h3><TrendingUp size={14} /> 热点看板</h3>
        <button onClick={() => {
          api("/api/v1/hotspots").then(applyResult).catch(caught => setError(`热点获取失败：${String(caught)}`));
        }}><Zap size={12} /> 刷新</button>
        {error && <div className="error">{error}</div>}
        {notice && <div className="muted">{notice}</div>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
        {hotspots.slice(0, 12).map((h, i) => (
          <div key={i} className="panel" style={{ fontSize: 13, padding: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{h.title?.slice(0, 50)}</div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)" }}>
              <span>{h.source}</span>
              <span>{h.score}</span>
            </div>
            <button style={{ marginTop: 8 }} disabled={busyKey === `${h.source}:${h.title}`} onClick={() => void generate(h)}>
              <Plus size={12} />按此热点生成
            </button>
          </div>
        ))}
      </div>

      {angles.length > 0 && (
        <div className="panel">
          <h3><Target size={14} /> 创作选题</h3>
          {angles.slice(0, 10).map((a, i) => (
            <div key={i} style={{ fontSize: 13, padding: "4px 0", borderBottom: "1px solid var(--border-subtle)" }}>
              <Plus size={10} /> {a}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
