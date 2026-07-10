import React from "react";

type Content = { id: string; title: string; meta: Record<string, unknown> };
type Knowledge = { id: string; kind: string; title: string; body: string };

export function Review({ novel, knowledge, review }: {
  novel: Content | null; knowledge: Knowledge[];
  review?: { score?: number; dimensions?: Record<string, number>; issues?: string[] };
}) {
  const sellingPoints = (novel?.meta?.selling_points as string[]) ?? [];
  const outline = (novel?.meta?.outline as string[]) ?? [];

  return (
    <div className="review-grid">
      <div className="panel">
        <h2>{novel?.title ?? "小说审阅"}</h2>
        <p style={{lineHeight:1.7,color:"var(--text-secondary)"}}>{String(novel?.meta?.synopsis ?? "等待简介...")}</p>
        <div className="chips">{sellingPoints.map(p => <span key={p}>{p}</span>)}</div>
        <h3>总纲</h3>
        <ol style={{paddingLeft:20,lineHeight:1.8}}>{outline.map((item,i) => <li key={i}>{item}</li>)}</ol>
      </div>
      <div className="panel">
        <h2>人物与世界观</h2>
        <div className="card-list">
          {knowledge.map(item => (
            <article key={item.id}>
              <small>{item.kind}</small>
              <strong>{item.title}</strong>
              <p style={{color:"var(--text-secondary)",lineHeight:1.6,margin:0}}>{item.body}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>七维审核</h2>
        <div className="score">{review?.score ?? "--"}</div>
        <div className="bars">
          {Object.entries(review?.dimensions ?? {}).map(([name, value]) => (
            <label key={name}><span>{name}</span><meter min={0} max={100} value={Number(value)} /><em>{value}</em></label>
          ))}
        </div>
        <ul style={{lineHeight:1.7,paddingLeft:18,color:"var(--text-secondary)",marginTop:12}}>
          {(review?.issues ?? []).map((item,i) => <li key={i}>{item}</li>)}
        </ul>
      </div>
    </div>
  );
}
