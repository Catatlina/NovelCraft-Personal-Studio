import React from "react";

type RunNode = { node_key: string; kind: string; agent: string | null; title: string; status: string };
type Run = { id: string; nodes: RunNode[]; context: Record<string, unknown> };

export function Progress({ run, onConfirm }: { run: Run | null; onConfirm: (title: string) => void }) {
  const nodes = run?.nodes ?? [];
  const human = nodes.find(n => n.node_key === "n2");
  const titles = (run?.context?.title_candidates as string[]) ?? [];

  return (
    <div className="review-grid">
      <div className="panel">
        <div className="timeline">
          {nodes.map(n => (
            <div key={n.node_key} className={`node ${n.status}`}>
              <span>{n.node_key}</span>
              <div><strong>{n.title}</strong><br /><small style={{color:"var(--text-muted)"}}>{n.agent ?? n.kind}</small></div>
              <em>{n.status}</em>
            </div>
          ))}
        </div>
      </div>
      <div className="panel human-gate">
        <h2>人工确认</h2>
        {human?.status === "waiting_human" ? (
          <div className="title-choices">
            {titles.map(t => <button key={t} onClick={() => onConfirm(t)}>{t}</button>)}
          </div>
        ) : (
          <p style={{color:"var(--text-muted)"}}>
            {human?.status === "succeeded" ? "书名已确认，继续执行..." : "等待书名候选生成..."}
          </p>
        )}
      </div>
    </div>
  );
}
