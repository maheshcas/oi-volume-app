import { useState, useEffect, useCallback } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "optionlens_theme";
const DEFAULT_THEME: Theme = "dark";

function getSystemTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return DEFAULT_THEME;
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    return stored ?? getSystemTheme();
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Apply immediately on mount to prevent flash.
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    const initial = stored ?? getSystemTheme();
    applyTheme(initial);
    setThemeState(initial);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggleTheme, isDark: theme === "dark" };
}
