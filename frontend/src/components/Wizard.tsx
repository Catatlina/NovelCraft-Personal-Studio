import React, { useState } from "react";
import { Loader2, Play, AlertTriangle } from "lucide-react";

const GENRES = ["都市","科幻","玄幻","仙侠","悬疑","历史","游戏","轻小说","短篇","其他"];

export function Wizard({ idea, setIdea, genre, setGenre, style, setStyle, targetWords, setTargetWords, busy, startBootstrap }: {
  idea: string; setIdea: (v: string) => void;
  genre: string; setGenre: (v: string) => void;
  style: string; setStyle: (v: string) => void;
  targetWords: number; setTargetWords: (v: number) => void;
  busy: boolean; startBootstrap: () => void;
}) {
  const [errors, setErrors] = useState<Record<string,string>>({});

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
    <div className="panel" style={{ maxWidth: 720 }}>
      <label style={{ display: "flex", flexDirection: "column", gap: 8, fontWeight: 600, marginBottom: 16 }}>
        灵感 *
        <textarea
          value={idea} onChange={e => { setIdea(e.target.value); if (errors.idea) setErrors({...errors, idea:""}); }}
          rows={4} placeholder="用几句话描述你的故事创意..."
          style={errors.idea ? { borderColor: "var(--warning)" } : {}}
        />
        {errors.idea && <small style={{color:"var(--warning)",display:"flex",alignItems:"center",gap:4}}><AlertTriangle size={12}/>{errors.idea}</small>}
      </label>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          题材 *
          <select
            value={genre} onChange={e => { setGenre(e.target.value); if (errors.genre) setErrors({...errors, genre:""}); }}
            style={errors.genre ? { borderColor: "var(--warning)" } : {}}
          >
            <option value="">选择题材</option>
            {GENRES.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
          {errors.genre && <small style={{color:"var(--warning)"}}>{errors.genre}</small>}
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          风格 *
          <input
            value={style} onChange={e => { setStyle(e.target.value); if (errors.style) setErrors({...errors, style:""}); }}
            placeholder="例如：克制、悬疑"
            style={errors.style ? { borderColor: "var(--warning)" } : {}}
          />
          {errors.style && <small style={{color:"var(--warning)"}}>{errors.style}</small>}
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          目标字数 *
          <input
            type="number" value={targetWords} min={5000} max={5000000} step={10000}
            onChange={e => { setTargetWords(Number(e.target.value)); if (errors.targetWords) setErrors({...errors, targetWords:""}); }}
            style={errors.targetWords ? { borderColor: "var(--warning)" } : {}}
          />
          {errors.targetWords && <small style={{color:"var(--warning)"}}>{errors.targetWords}</small>}
        </label>
      </div>

      <button className="primary" onClick={validate} disabled={busy}>
        {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        启动 Bootstrap
      </button>
    </div>
  );
}
