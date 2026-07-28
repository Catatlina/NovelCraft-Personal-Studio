import React from "react";
import { AlertTriangle, RefreshCw, Sparkles } from "lucide-react";

type Props = { children: React.ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fatal-page">
        <div className="fatal-brand"><Sparkles size={19} /> Starlume AI</div>
        <section className="fatal-card">
          <span className="fatal-icon"><AlertTriangle size={24} /></span>
          <p className="eyebrow">页面没有正常完成</p>
          <h1>这次停笔不是你的错。</h1>
          <p>页面遇到了意外，但你的创作内容不会因此被主动覆盖。刷新后可以继续。</p>
          <details><summary>查看错误信息</summary><code>{this.state.error.message}</code></details>
          <button type="button" onClick={() => window.location.reload()}><RefreshCw size={17} /> 刷新页面</button>
        </section>
      </main>
    );
  }
}
