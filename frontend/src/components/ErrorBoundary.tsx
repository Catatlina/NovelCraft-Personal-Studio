import React from "react";
import { AlertTriangle } from "lucide-react";

type Props = { children: React.ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) { return { error }; }

  render() {
    if (this.state.error) {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
          <div className="panel" style={{ maxWidth: 480, textAlign: "center" }}>
            <AlertTriangle size={48} style={{ color: "var(--warning)", marginBottom: 16 }} />
            <h2>出错了</h2>
            <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>{this.state.error.message}</p>
            <button className="primary" onClick={() => window.location.reload()}>刷新页面</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
