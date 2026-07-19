import React, { useEffect, useState } from "react";
import { Loader2, Play, AlertTriangle } from "lucide-react";
import { api, getApiKey } from "../lib/api";

const GENRES = ["都市","科幻","玄幻","仙侠","悬疑","历史","游戏","轻小说","短篇","其他"];

export function Wizard({ idea, setIdea, genre, setGenre, style, setStyle, targetWords, setTargetWords, busy, startBootstrap }: {
  idea: string; setIdea: (v: string) => void;
  genre: string; setGenre: (v: string) => void;
  style: string; setStyle: (v: string) => void;
  targetWords: number; setTargetWords: (v: number) => void;
  busy: boolean; startBootstrap: () => void;
}) {
  const [errors, setErrors] = useState<Record<string,string>>({});
  const [keyMissing, setKeyMissing] = useState(false);

  // BUG-07: warn before a keyless bootstrap dies at the first AI node.
  useEffect(() => {
    if (getApiKey()) { setKeyMissing(false); return; }
    api<{ data?: { ai_key_configured?: boolean } }>("/api/v1/healthz")
      .then(h => setKeyMissing(!(h?.data?.ai_key_configured)))
      .catch(() => setKeyMissing(false));
  }, []);

  function validate() {
    const e: Record<string,string> = {};
    if (idea.trim().length < 4) e.idea = "灵感至少4个字";
    if (!genre.trim()) e.genre = "请选择题材";
    if (!style.trim()) e.style = "请填写风格";
    if (targetWords < 5000) e.targetWords = "目标字数至少5000";
    if (targetWords > 5000000) e.targetWords = "目标字数不超过500万";
    setErrors(e);
    if (Object.keys(e).length > 0) return;
    startBootstrap();
  }

  return (
    <div style={{ maxWidth: 720 }}>
      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>启动 Bootstrap</h1>
          <p>输入你的故事灵感，AI 将为你生成完整的小说大纲与章节规划</p>
        </div>
      </div>

      {/* Key missing warning */}
      {keyMissing && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "12px 16px", marginBottom: 20,
          borderRadius: "var(--r-sm)",
          background: "var(--warning-bg)",
          border: "1px solid var(--warning)",
          color: "var(--yellow)", fontSize: 13
        }}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>尚未配置 AI API Key（服务器也未配置全局 Key）。生成会在第一个 AI 节点失败——请先到「系统设置」填入 DeepSeek API Key。</span>
        </div>
      )}

      {/* Main card */}
      <div className="card">
        {/* 灵感 field */}
        <div className="field">
          <label>灵感 <span style={{ color: "var(--red)" }}>*</span></label>
          <textarea
            className={`form-input${errors.idea ? " has-error" : ""}`}
            value={idea}
            onChange={e => { setIdea(e.target.value); if (errors.idea) setErrors({...errors, idea:""}); }}
            rows={4}
            placeholder="用几句话描述你的故事创意..."
            style={errors.idea ? { borderColor: "var(--red)" } : {}}
          />
          {errors.idea && (
            <span className="hint" style={{ color: "var(--red)", display: "flex", alignItems: "center", gap: 4 }}>
              <AlertTriangle size={12} />{errors.idea}
            </span>
          )}
        </div>

        {/* 题材 — segmented control */}
        <div className="field">
          <label>题材 <span style={{ color: "var(--red)" }}>*</span></label>
          <div className="seg" style={{ flexWrap: "wrap" }}>
            {GENRES.map(g => (
              <button
                key={g}
                type="button"
                className={genre === g ? "on" : ""}
                onClick={() => { setGenre(g); if (errors.genre) setErrors({...errors, genre:""}); }}
              >
                {g}
              </button>
            ))}
          </div>
          {errors.genre && (
            <span className="hint" style={{ color: "var(--red)" }}>{errors.genre}</span>
          )}
        </div>

        {/* 风格 + 目标字数 — 2-column grid */}
        <div className="grid grid-2">
          <div className="field">
            <label>风格 <span style={{ color: "var(--red)" }}>*</span></label>
            <input
              className={`form-input${errors.style ? " has-error" : ""}`}
              value={style}
              onChange={e => { setStyle(e.target.value); if (errors.style) setErrors({...errors, style:""}); }}
              placeholder="例如：克制、悬疑"
              style={errors.style ? { borderColor: "var(--red)" } : {}}
            />
            {errors.style && (
              <span className="hint" style={{ color: "var(--red)" }}>{errors.style}</span>
            )}
          </div>
          <div className="field">
            <label>目标字数 <span style={{ color: "var(--red)" }}>*</span></label>
            <input
              className={`form-input${errors.targetWords ? " has-error" : ""}`}
              type="number"
              value={targetWords}
              min={5000}
              max={5000000}
              step={10000}
              onChange={e => { setTargetWords(Number(e.target.value)); if (errors.targetWords) setErrors({...errors, targetWords:""}); }}
              style={errors.targetWords ? { borderColor: "var(--red)" } : {}}
            />
            {errors.targetWords && (
              <span className="hint" style={{ color: "var(--red)" }}>{errors.targetWords}</span>
            )}
          </div>
        </div>

        {/* Submit */}
        <button className="btn-primary" onClick={validate} disabled={busy} style={{ marginTop: 8 }}>
          {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          启动 Bootstrap
        </button>
      </div>
    </div>
  );
}
