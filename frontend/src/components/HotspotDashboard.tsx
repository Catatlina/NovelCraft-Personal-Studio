import React, { useState, useEffect } from "react";
import { TrendingUp, Zap, Target, Plus } from "lucide-react";
import { api } from "../lib/api";

export function HotspotDashboard() {
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [angles, setAngles] = useState<string[]>([]);

  useEffect(() => {
    api<{ hotspots: any[]; creative_angles: any[] }>("/api/v1/hotspots").then(d => {
      if (d) { setHotspots(d.hotspots || []); setAngles(d.creative_angles?.map((a: any) => a.angle) || []); }
    }).catch(() => {});
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="panel">
        <h3><TrendingUp size={14} /> 热点看板</h3>
        <button onClick={() => {
          api("/api/v1/hotspots").then(d => {
            if (d) { setHotspots(d.hotspots || []); setAngles(d.creative_angles || []); }
          });
        }}><Zap size={12} /> 刷新</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
        {hotspots.slice(0, 12).map((h, i) => (
          <div key={i} className="panel" style={{ fontSize: 13, padding: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{h.title?.slice(0, 50)}</div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)" }}>
              <span>{h.source}</span>
              <span>{h.score}</span>
            </div>
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
