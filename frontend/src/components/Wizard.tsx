import React from "react";
import { Loader2, Play } from "lucide-react";

export function Wizard({ idea, setIdea, genre, setGenre, style, setStyle, targetWords, setTargetWords, busy, startBootstrap }: {
  idea: string; setIdea: (v: string) => void;
  genre: string; setGenre: (v: string) => void;
  style: string; setStyle: (v: string) => void;
  targetWords: number; setTargetWords: (v: number) => void;
  busy: boolean; startBootstrap: () => void;
}) {
  return (
    <div className="panel" style={{ maxWidth: 720 }}>
      <label style={{ display: "flex", flexDirection: "column", gap: 8, fontWeight: 600, marginBottom: 16 }}>
        灵感
        <textarea value={idea} onChange={e => setIdea(e.target.value)} rows={4} />
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          题材 <input value={genre} onChange={e => setGenre(e.target.value)} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          风格 <input value={style} onChange={e => setStyle(e.target.value)} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontWeight: 600, fontSize: 14 }}>
          目标字数 <input type="number" value={targetWords} onChange={e => setTargetWords(Number(e.target.value))} />
        </label>
      </div>
      <button className="primary" onClick={startBootstrap} disabled={busy}>
        {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        启动 Bootstrap
      </button>
    </div>
  );
}
