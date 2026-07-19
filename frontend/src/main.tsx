import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
// Design-system foundation: canonical doc12 tokens first, then the legacy
// alias layer so existing components resolve old token names. styles.css and
// components.css (the tokenized twin of the retired proto.css) hold the
// component-layout classes; components.css loads after styles.css so its
// :focus-visible / reduced-motion rules win over legacy outline killers.
import "./design/tokens.css";
import "./design/compat.css";
import "./styles.css";
import "./design/components.css";
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
