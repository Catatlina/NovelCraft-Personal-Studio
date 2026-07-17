import React from "react";
import "../styles/proto.css";

// ── Static sample data ───────────────────────────────────────────────────────

const stats = [
  {
    label: "本周 AI 生成字数",
    value: "48.2k",
    trend: "↑ 23%",
    trendClass: "up",
    subtitle: "较上周",
    icColor: "ic-purple",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
      </svg>
    ),
  },
  {
    label: "活跃项目",
    value: "5",
    trend: "持平",
    trendClass: "flat",
    subtitle: "",
    icColor: "ic-cyan",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      </svg>
    ),
  },
  {
    label: "AI 调用次数",
    value: "1,284",
    trend: "↑ 12%",
    trendClass: "up",
    subtitle: "",
    icColor: "ic-orange",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    label: "本月成本",
    value: "¥312",
    trend: "↓ 8%",
    trendClass: "down",
    subtitle: "预算内",
    icColor: "ic-green",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
  },
];

// 14-day trend bars (height % → representing daily word count)
const bars = [
  { day: 1, height: 40 },
  { day: 2, height: 55 },
  { day: 3, height: 35 },
  { day: 4, height: 70 },
  { day: 5, height: 60 },
  { day: 6, height: 85 },
  { day: 7, height: 50 },
  { day: 8, height: 90 },
  { day: 9, height: 65 },
  { day: 10, height: 75 },
  { day: 11, height: 55 },
  { day: 12, height: 80 },
  { day: 13, height: 95 },
  { day: 14, height: 70 },
];

// Donut segments: category, pct, color
const donutSegments = [
  { label: "玄幻", pct: 45, color: "#6366F1" },
  { label: "都市", pct: 25, color: "#22D3EE" },
  { label: "科幻", pct: 20, color: "#FB923C" },
  { label: "其他", pct: 10, color: "#34D399" },
];

// ── More sample data ──────────────────────────────────────────────────────────

const topSubjects = [
  { rank: 1, name: "玄幻·东方仙侠", count: 12.4, unit: "万字" },
  { rank: 2, name: "都市·职场商战", count: 9.8, unit: "万字" },
  { rank: 3, name: "科幻·赛博朋克", count: 7.6, unit: "万字" },
  { rank: 4, name: "悬疑·推理探案", count: 5.2, unit: "万字" },
  { rank: 5, name: "历史·架空王朝", count: 3.1, unit: "万字" },
];

const activities = [
  {
    text: "《星渊纪元》第 12 章由 AI 续写完成（3,200 字）",
    time: "10 分钟前",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
      </svg>
    ),
    iconStyle: {} as React.CSSProperties,
  },
  {
    text: "扫榜完成：捕获 3 个上升题材热点",
    time: "1 小时前",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" /><path d="M7 14l4-4 3 3 5-6" />
      </svg>
    ),
    iconStyle: { color: "var(--cyan)", background: "rgba(34,211,238,.12)" } as React.CSSProperties,
  },
  {
    text: "知乎专栏已同步《论 AI 写作的边界》",
    time: "昨天",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" />
      </svg>
    ),
    iconStyle: { color: "var(--orange)", background: "rgba(251,146,60,.12)" } as React.CSSProperties,
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

const Overview: React.FC = () => {
  const handleExport = () => {
    // Placeholder — will be wired to real export logic later
    console.log("Export weekly report");
  };

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <b>NovelCraft</b> › 概览
      </div>

      {/* Page head */}
      <div className="page-head">
        <div>
          <h1>概览</h1>
          <p>你的创作全景与 AI 效能总览</p>
        </div>
        <div className="head-actions">
          <button className="btn-sm btn-ghost" onClick={handleExport}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            导出周报
          </button>
        </div>
      </div>

      {/* 4 stat cards */}
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        {stats.map((s, i) => (
          <div className="stat" key={i}>
            <div className="stat-top">
              <span className="stat-label">{s.label}</span>
              <div className={`stat-ic ${s.icColor}`}>{s.icon}</div>
            </div>
            <div className="stat-val">{s.value}</div>
            <div className="stat-trend">
              <span className={s.trendClass}>{s.trend}</span>
              {s.subtitle && ` ${s.subtitle}`}
            </div>
          </div>
        ))}
      </div>

      {/* Two-column: trend chart + donut */}
      <div className="layout-2">
        {/* Left: 14-day trend */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "var(--primary-light)" }}>
                <path d="M3 3v18h18" /><path d="M7 14l4-4 3 3 5-6" />
              </svg>
              近 14 天生成趋势
            </div>
            <span className="badge green">● 稳定产出</span>
          </div>
          <div className="bars">
            {bars.map((b) => (
              <div className="bar" style={{ height: `${b.height}%` }} key={b.day}>
                <span>{b.day}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Donut + legend */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "var(--primary-light)" }}>
                <path d="M21.21 15.89A10 10 0 1 1 8 2.83" /><path d="M22 12A10 10 0 0 0 12 2v10z" />
              </svg>
              创作类型分布
            </div>
          </div>
          <div className="chart-row">
            <svg className="donut" viewBox="0 0 42 42">
              <circle cx="21" cy="21" r="15.9" fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="6" />
              {(() => {
                // Cumulative stroke-dashoffset to chain segments
                let cumulativeOffset = 25; // start at 25 (top)
                return donutSegments.map((seg) => {
                  const circumference = 2 * Math.PI * 15.9;
                  const dashLength = (seg.pct / 100) * circumference;
                  const circle = (
                    <circle
                      key={seg.label}
                      cx="21" cy="21" r="15.9"
                      fill="none"
                      stroke={seg.color}
                      strokeWidth="6"
                      strokeDasharray={`${dashLength} ${circumference}`}
                      strokeDashoffset={cumulativeOffset}
                    />
                  );
                  cumulativeOffset -= dashLength;
                  return circle;
                });
              })()}
            </svg>
            <div className="legend">
              {donutSegments.map((seg) => (
                <div className="legend-item" key={seg.label}>
                  <span className="sw" style={{ background: seg.color }} />
                  {seg.label} · {seg.pct}%
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Two columns below: TOP5 + Activity */}
      <div className="layout-2" style={{ marginTop: 16 }}>
        {/* Left: 本周热门题材 TOP5 */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "var(--primary-light)" }}>
                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
                <path d="M4 9h16" /><rect x="2" y="4" width="20" height="6" rx="2" />
                <path d="M12 10v11" /><path d="M8 14h8" />
              </svg>
              本周热门题材 TOP5
            </div>
            <span className="card-sub">按生成字数排序</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>题材</th>
                  <th>生成量</th>
                </tr>
              </thead>
              <tbody>
                {topSubjects.map((item) => (
                  <tr key={item.rank}>
                    <td>
                      <span className={`rank${item.rank <= 3 ? " top" : ""}`}>
                        {item.rank}
                      </span>
                    </td>
                    <td><b>{item.name}</b></td>
                    <td>{item.count} {item.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: 最近动态 */}
        <div className="card">
          <div className="card-head">
            <div className="card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "var(--primary-light)" }}>
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              最近动态
            </div>
          </div>
          {activities.map((a, i) => (
            <div className="activity" key={i}>
              <div className="av-sm" style={a.iconStyle}>
                {a.icon}
              </div>
              <div>
                <p>{a.text}</p>
                <time>{a.time}</time>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Overview;
