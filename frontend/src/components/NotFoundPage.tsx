import { ArrowLeft, Compass, Sparkles } from "lucide-react";
import type { AppTab } from "./Layout";

export function NotFoundPage({ onNavigate }: { onNavigate: (tab: AppTab) => void }) {
  return (
    <section className="not-found-page page-enter">
      <span className="not-found-icon"><Compass size={25} /></span>
      <p className="eyebrow">404 · LOST PAGE</p>
      <h2>这一页没有写进故事里。</h2>
      <p>链接可能已经迁移，或对应功能已从小说主线中隐藏。你的原有数据不会因此被删除。</p>
      <button type="button" onClick={() => onNavigate("dashboard")}><ArrowLeft size={17} /> 返回小说首页</button>
      <small><Sparkles size={13} /> Starlume AI</small>
    </section>
  );
}
