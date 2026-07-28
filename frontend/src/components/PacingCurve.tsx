import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

/** V3 §11.2 Pacing Engine curve — inline SVG, no chart deps.
 *  Renders per-chapter rhythm signals (review pace / pacing gate score /
 *  reader-experience average) from GET /novels/{id}/pacing-series. */

type PacingPoint = {
  chapter_id: string; seq: number | null; title: string;
  review_score: number | null; pace: number | null;
  pacing_status: string | null; pacing_score: number | null;
  reader_experience: Record<string, number | null> | null;
};

const RX_KEYS = ["expectation", "conflict", "payoff", "emotion_shift", "worth_continuing"];

function rxAvg(rx: PacingPoint["reader_experience"]): number | null {
  if (!rx) return null;
  const vals = RX_KEYS.map(k => rx[k]).filter((v): v is number => typeof v === "number");
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

function polyline(points: PacingPoint[], pick: (p: PacingPoint) => number | null,
                  w: number, h: number, pad: number): string {
  const n = points.length;
  if (n === 0) return "";
  const step = n > 1 ? (w - pad * 2) / (n - 1) : 0;
  return points.map((p, i) => {
    const v = pick(p);
    if (v == null) return null;
    const x = pad + i * step;
    const y = h - pad - (Math.max(0, Math.min(100, v)) / 100) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).filter(Boolean).join(" ");
}

export function PacingCurve({ novelId }: { novelId: string }) {
  const [series, setSeries] = useState<PacingPoint[]>([]);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!novelId || !open) return;
    let cancelled = false;
    api<{ novel_id: string; count: number; series: PacingPoint[] }>(`/api/v1/novels/${novelId}/pacing-series`)
      .then(data => { if (!cancelled) { setSeries(data.series || []); setError(""); } })
      .catch(caught => { if (!cancelled) setError(String(caught)); });
    return () => { cancelled = true; };
  }, [novelId, open]);

  const W = 220, H = 90, PAD = 8;
  const paceLine = polyline(series, p => p.pace ?? p.pacing_score, W, H, PAD);
  const rxLine = polyline(series, p => rxAvg(p.reader_experience), W, H, PAD);
  const scoreLine = polyline(series, p => p.review_score, W, H, PAD);
  const hasData = !!(paceLine || rxLine || scoreLine);

  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
      <button className="btn-sm btn-ghost" style={{ width: "100%", textAlign: "left", fontSize: 12 }}
              onClick={() => setOpen(v => !v)} data-testid="pacing-curve-toggle">
        {open ? "▾" : "▸"} 节奏曲线
      </button>
      {open && (
        <div style={{ padding: "6px 2px" }}>
          {error ? <div style={{ fontSize: 11, color: "var(--orange)" }}>加载失败：{error}</div> : null}
          {!error && !hasData ? (
            <div style={{ fontSize: 11, color: "var(--text-3)" }}>暂无节奏数据（章节完成审核后生成）</div>
          ) : null}
          {hasData ? (
            <>
              <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="节奏曲线"
                   style={{ display: "block", background: "var(--bg-muted)", borderRadius: 6 }}>
                {[25, 50, 75].map(y => (
                  <line key={y} x1={PAD} x2={W - PAD}
                        y1={H - PAD - (y / 100) * (H - PAD * 2)} y2={H - PAD - (y / 100) * (H - PAD * 2)}
                        stroke="var(--border)" strokeWidth="0.5" />
                ))}
                {scoreLine ? <polyline points={scoreLine} fill="none" stroke="var(--text-3)" strokeWidth="1" strokeDasharray="3 2" /> : null}
                {paceLine ? <polyline points={paceLine} fill="none" stroke="var(--primary-light)" strokeWidth="1.5" /> : null}
                {rxLine ? <polyline points={rxLine} fill="none" stroke="var(--orange)" strokeWidth="1.5" /> : null}
              </svg>
              <div style={{ display: "flex", gap: 10, fontSize: 10, color: "var(--text-3)", marginTop: 4, flexWrap: "wrap" }}>
                {paceLine ? <span style={{ color: "var(--primary-light)" }}>— 节奏</span> : null}
                {rxLine ? <span style={{ color: "var(--orange)" }}>— 读者体验</span> : null}
                {scoreLine ? <span>┄ 评分</span> : null}
                <span>{series.length} 章</span>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
