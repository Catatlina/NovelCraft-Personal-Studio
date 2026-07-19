import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
// Design-system foundation: canonical doc12 tokens first, then the legacy
// alias layer so existing components resolve old token names. The legacy
// stylesheets (styles.css / proto.css) are kept because they still hold
// component-layout classes not yet migrated to tokens (B8 will remove them).
import "./design/tokens.css";
import "./design/compat.css";
import "./styles.css";
import "./styles/proto.css";
import "./styles/novel-prose.css";

// SW registration lives here (not an inline <script>) so a strict CSP can use
// script-src 'self' without an inline-script hash/nonce.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
