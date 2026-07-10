import React from "react";

type Character = { name: string; role: string; arc: string; traits: string[] };

export function CharacterCard({ char }: { char: Character }) {
  return (
    <div style={{ padding: 12, border: "1px solid var(--border-subtle)", borderRadius: 8, marginBottom: 8 }}>
      <h4 style={{ margin: 0 }}>{char.name} <small style={{ color: "var(--text-muted)" }}>{char.role}</small></h4>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "4px 0" }}>{char.arc}</p>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {(char.traits || []).map((t, i) => <span key={i} style={{
          padding: "2px 8px", borderRadius: 12, fontSize: 11,
          background: "var(--bg-secondary)", color: "var(--text-secondary)",
        }}>{t}</span>)}
      </div>
    </div>
  );
}

type OutlineNode = { title: string; chapters?: OutlineNode[]; seq?: number };
export function OutlineTree({ nodes }: { nodes: OutlineNode[] }) {
  if (!nodes?.length) return <p style={{color:"var(--text-muted)"}}>暂未生成大纲</p>;
  return (
    <ul style={{ listStyle: "none", paddingLeft: 0 }}>
      {nodes.map((n, i) => (
        <li key={i} style={{ marginLeft: 16, borderLeft: "1px solid var(--border-subtle)", paddingLeft: 12, paddingBottom: 4 }}>
          <span style={{ fontWeight: 600 }}>{n.seq ? `第${n.seq}章 ` : ""}{n.title}</span>
          {n.chapters && <OutlineTree nodes={n.chapters} />}
        </li>
      ))}
    </ul>
  );
}
