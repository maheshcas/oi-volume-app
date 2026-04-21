import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import LandingPage from "./LandingPage";
import "./styles.css";

const container = document.getElementById("app");

if (!container) {
  throw new Error("App container not found");
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<App />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .getRegistrations()
      .then((registrations) =>
        Promise.all(registrations.map((registration) => registration.unregister()))
      )
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
