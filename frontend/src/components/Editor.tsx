import React from "react";
import { Bot, Wand2, Sparkles, Save, RotateCcw } from "lucide-react";
import { RichEditor } from "./RichEditor";

type Content = { id: string; title: string; body: { content?: { text?: string }[] }; meta: Record<string, unknown> };
type Version = { id: string; label: string; snapshot: Record<string, unknown>; created_at: string };
type AiCall = { id: string; provider: string; model: string; prompt_name: string; task_type: string; prompt_tokens: number; completion_tokens: number; cost_cny: number; latency_ms: number; status: string };

export function Editor({ chapter, editorText, setEditorText, selection, setSelection, saveChapter, runEditorOp, versions, restoreVersion }: {
  chapter: Content | null; editorText: string; setEditorText: (t: string) => void;
  selection: string; setSelection: (s: string) => void;
  saveChapter: () => void; runEditorOp: (op: string) => void;
  versions: Version[]; restoreVersion: (id: string) => void;
}) {
  return (
    <div className="editor-grid">
      <div className="panel">
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <input value={chapter?.title ?? ""} readOnly style={{ flex: 1, background: "transparent", border: "none", fontSize: 18, fontWeight: 600 }} />
          <button onClick={saveChapter} disabled={!chapter}><Save size={16} />保存</button>
        </div>
        <RichEditor value={editorText} onChange={setEditorText} />
        <div className="ai-bar">
          <button onClick={() => runEditorOp("polish")} disabled={!selection}><Wand2 size={15} />润色</button>
          <button onClick={() => runEditorOp("rewrite")} disabled={!selection}><Bot size={15} />改写</button>
          <button onClick={() => runEditorOp("continue")} disabled={!selection}><Sparkles size={15} />续写</button>
        </div>
      </div>
      <div className="panel versions">
        <h2>版本历史</h2>
        {versions.map(v => (
          <button key={v.id} onClick={() => restoreVersion(v.id)}>
            <RotateCcw size={14} />{v.label}
            <small>{new Date(v.created_at).toLocaleString()}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
