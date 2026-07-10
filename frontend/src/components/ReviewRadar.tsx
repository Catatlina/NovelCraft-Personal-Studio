import React from "react";

type Dim = { name: string; score: number };

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function polygonPoints(cx: number, cy: number, r: number, sides: number) {
  return Array.from({ length: sides }, (_, i) => {
    const pt = polarToCartesian(cx, cy, r, (360 / sides) * i);
    return `${pt.x},${pt.y}`;
  }).join(" ");
}

export function ReviewRadar({ data }: { data: Dim[] }) {
  if (!data?.length) return <p style={{ color: "var(--text-muted)" }}>暂无审查数据</p>;
  const cx = 120, cy = 110, maxR = 85;
  const sides = data.length;
  const angleStep = 360 / sides;

  // Data polygon
  const dataPts = data.map((d, i) => {
    const r = (d.score / 100) * maxR;
    const pt = polarToCartesian(cx, cy, r, angleStep * i);
    return `${pt.x},${pt.y}`;
  }).join(" ");

  return (
    <svg width="100%" viewBox="0 0 240 220" style={{ maxWidth: 300 }}>
      {/* Grid rings */}
      {[0.5, 1].map(pct => (
        <polygon key={pct} points={polygonPoints(cx, cy, maxR * pct, sides)}
          fill="none" stroke="var(--border-subtle)" strokeWidth="1" />
      ))}
      {/* Axes */}
      {data.map((_, i) => {
        const pt = polarToCartesian(cx, cy, maxR, angleStep * i);
        return <line key={i} x1={cx} y1={cy} x2={pt.x} y2={pt.y} stroke="var(--border-subtle)" strokeWidth="1" />;
      })}
      {/* Data area */}
      <polygon points={dataPts} fill="var(--primary)" fillOpacity="0.15" stroke="var(--primary)" strokeWidth="1.5" />
      {/* Labels */}
      {data.map((d, i) => {
        const pt = polarToCartesian(cx, cy, maxR + 16, angleStep * i);
        return <text key={i} x={pt.x} y={pt.y} textAnchor="middle" fontSize="11" fill="var(--text-secondary)">{d.name}</text>;
      })}
      {/* Dots with scores */}
      {data.map((d, i) => {
        const r = (d.score / 100) * maxR;
        const pt = polarToCartesian(cx, cy, r, angleStep * i);
        return (
          <g key={i}>
            <circle cx={pt.x} cy={pt.y} r="3" fill="var(--primary)" />
            <text x={pt.x} y={pt.y - 8} textAnchor="middle" fontSize="9" fill="var(--text-secondary)">{d.score}</text>
          </g>
        );
      })}
    </svg>
  );
}
