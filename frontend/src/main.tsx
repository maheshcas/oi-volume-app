import { Component, lazy, StrictMode, Suspense, type ErrorInfo, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import LandingPage from "./LandingPage";
import "./styles.css";

const LocalAnalytics = import.meta.env.DEV
  ? lazy(() => import("./pages/LocalAnalytics"))
  : null;

type RootErrorBoundaryState = {
  error: Error | null;
};

class RootErrorBoundary extends Component<{ children: ReactNode }, RootErrorBoundaryState> {
  state: RootErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): RootErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Root render error:", error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: "100vh",
            background: "#080f18",
            color: "#ffd2d2",
            padding: "24px",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            whiteSpace: "pre-wrap",
          }}
        >
          <h2 style={{ marginTop: 0, color: "#ff7f7f" }}>Frontend runtime error</h2>
          <div>{String(this.state.error.message || this.state.error)}</div>
        </div>
      );
    }
    return this.props.children;
  }
}

function ensureRuntimeErrorPanel(message: string) {
  const existing = document.getElementById("runtime-error-panel");
  if (existing) {
    existing.textContent = message;
    return;
  }
  const panel = document.createElement("pre");
  panel.id = "runtime-error-panel";
  panel.style.position = "fixed";
  panel.style.left = "12px";
  panel.style.right = "12px";
  panel.style.bottom = "12px";
  panel.style.maxHeight = "45vh";
  panel.style.overflow = "auto";
  panel.style.margin = "0";
  panel.style.padding = "12px";
  panel.style.borderRadius = "10px";
  panel.style.border = "1px solid rgba(255,127,127,0.5)";
  panel.style.background = "rgba(32,8,12,0.95)";
  panel.style.color = "#ffd2d2";
  panel.style.fontFamily = "ui-monospace, SFMono-Regular, Menlo, monospace";
  panel.style.fontSize = "12px";
  panel.style.whiteSpace = "pre-wrap";
  panel.style.zIndex = "2147483647";
  panel.textContent = message;
  document.body.appendChild(panel);
}

window.addEventListener("error", (event) => {
  const message = `Uncaught error: ${event.message}\n${event.filename}:${event.lineno}:${event.colno}`;
  ensureRuntimeErrorPanel(message);
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason instanceof Error ? event.reason.stack || event.reason.message : String(event.reason);
  ensureRuntimeErrorPanel(`Unhandled rejection:\n${reason}`);
});

const container = document.getElementById("app");

if (!container) {
  throw new Error("App container not found");
}

createRoot(container).render(
  <StrictMode>
    <RootErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/app" element={<App />} />
          {LocalAnalytics && (
            <Route
              path="/local-analytics"
              element={<Suspense fallback={null}><LocalAnalytics /></Suspense>}
            />
          )}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </RootErrorBoundary>
  </StrictMode>
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    const RELOAD_KEY = "optionlens:sw-cleaned-reload";
    navigator.serviceWorker
      .getRegistrations()
      .then((registrations) => {
        const hadRegistrations = registrations.length > 0;
        return Promise.all(registrations.map((registration) => registration.unregister())).then(
          () => hadRegistrations
        );
      })
      .then((hadRegistrations) => {
        if (!hadRegistrations) return;
        if (window.sessionStorage.getItem(RELOAD_KEY) === "1") return;
        window.sessionStorage.setItem(RELOAD_KEY, "1");
        window.location.reload();
      })
      .catch((error) => {
        console.error("Service worker cleanup failed", error);
      });

    if ("caches" in window) {
      caches
        .keys()
        .then((keys) =>
          Promise.all(
            keys
              .filter((key) => key.startsWith("optionlens-shell"))
              .map((key) => caches.delete(key))
          )
        )
        .catch((error) => {
          console.error("Cache cleanup failed", error);
        });
    }
  });
}
