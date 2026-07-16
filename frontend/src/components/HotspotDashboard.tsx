import React, { useState, useEffect } from "react";
import { TrendingUp, Zap, Target, Plus } from "lucide-react";
import { api } from "../lib/api";

export function HotspotDashboard() {
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [notice, setNotice] = useState("");
  // NC-HM-002/003: per-topic toolbox — platform match, title variants, video script, materials
  const [toolTopic, setToolTopic] = useState<any | null>(null);
  const [toolBusy, setToolBusy] = useState("");
  const [matches, setMatches] = useState<any[]>([]);
  const [titles, setTitles] = useState<string[]>([]);
  const [videoScript, setVideoScript] = useState<any | null>(null);
  const [materials, setMaterials] = useState<any | null>(null);

  const applyResult = (response: any) => {
    const data = response?.data || {};
    setHotspots(data.hotspots || []);
    setError("");
  };

  const loadHotspots = async () => {
    setLoading(true);
    try {
      applyResult(await api("/api/v1/hotspots"));
    } catch (caught) {
      setError(`热点获取失败：${String(caught)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadHotspots();
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

  const openToolbox = async (h: any) => {
    setToolTopic(h); setMatches([]); setTitles([]); setVideoScript(null); setMaterials(null); setError("");
    setToolBusy("match");
    try {
      const result = await api(`/api/v1/hotspots/platform-match?topic=${encodeURIComponent(h.title)}&category=${encodeURIComponent(h.category || "")}`);
      setMatches(result.data?.matches || []);
    } catch (caught) { setError(`平台匹配失败：${String(caught)}`); } finally { setToolBusy(""); }
  };

  const runTool = async (tool: "titles" | "video" | "materials") => {
    if (!toolTopic) return;
    setToolBusy(tool); setError("");
    try {
      const projects = await api("/api/v1/projects");
      const body = { project_id: projects.data?.[0]?.id, topic: toolTopic.title, count: 5, platform: "douyin", content: "" };
      if (tool === "titles") {
        const result = await api("/api/v1/hotspots/title-variants", { method: "POST", body: JSON.stringify(body) });
        setTitles(result.data?.titles || []);
      } else if (tool === "video") {
        const result = await api("/api/v1/hotspots/video-script", { method: "POST", body: JSON.stringify(body) });
        setVideoScript(result.data || null);
      } else {
        const result = await api("/api/v1/hotspots/material-suggestions", { method: "POST", body: JSON.stringify(body) });
        setMaterials(result.data || null);
      }
    } catch (caught) { setError(`AI 生成失败：${String(caught)}`); } finally { setToolBusy(""); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="panel">
        <h3><TrendingUp size={14} /> 热点看板</h3>
        <button disabled={loading} onClick={() => void loadHotspots()}><Zap size={12} /> {loading ? "正在采集…" : "刷新"}</button>
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
            <button style={{ marginTop: 4 }} onClick={() => void openToolbox(h)}>
              <Target size={12} />选题工具箱
            </button>
          </div>
        ))}
      </div>

      {toolTopic && (
        <div className="panel" data-testid="hm-toolbox">
          <h3><Target size={14} /> 选题工具箱：{toolTopic.title?.slice(0, 40)}</h3>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <button disabled={toolBusy === "titles"} onClick={() => void runTool("titles")}>AI 标题变体</button>
            <button disabled={toolBusy === "video"} onClick={() => void runTool("video")}>AI 短视频脚本</button>
            <button disabled={toolBusy === "materials"} onClick={() => void runTool("materials")}>AI 素材建议</button>
            <button onClick={() => setToolTopic(null)}>关闭</button>
          </div>
          {matches.length > 0 && (
            <div style={{ fontSize: 12, marginBottom: 8 }}>
              <strong>平台匹配</strong>
              {matches.slice(0, 5).map((m, i) => (
                <div key={i}>{m.platform} 适配度 {m.suitability}{m.risks?.length ? `（风险：${m.risks.join("、")}）` : ""}</div>
              ))}
            </div>
          )}
          {titles.length > 0 && (
            <div style={{ fontSize: 12, marginBottom: 8 }}>
              <strong>标题变体</strong>
              {titles.map((t, i) => <div key={i}>{i + 1}. {t}</div>)}
            </div>
          )}
          {videoScript && (
            <div style={{ fontSize: 12, marginBottom: 8 }}>
              <strong>短视频脚本：{videoScript.title || ""}</strong>
              {(videoScript.scenes || []).map((s: any, i: number) => <div key={i}>{s.time}｜{s.action}｜{s.text}</div>)}
            </div>
          )}
          {materials && (
            <div style={{ fontSize: 12 }}>
              <strong>素材建议</strong>
              <div>封面：{materials.cover_image_prompt || ""}</div>
              <div>图表：{(materials.suggested_charts || []).join("、")}</div>
              <div>数据源：{(materials.data_sources || []).join("、")}</div>
            </div>
          )}
        </div>
      )}

    </div>
  );
}
