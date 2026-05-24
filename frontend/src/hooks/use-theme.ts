import { useCallback, useEffect, useState } from "react";

/** Theme mode applied to the document root via the `dark` class. */
export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "booking-system:theme";

/**
 * Read the saved preference. Defaults to dark (post-Notion-theme swap)
 * when nothing is stored. Falls back to OS preference if the user has
 * never picked anything AND the saved key is absent — but only on the
 * first call; once anything is written via setTheme it sticks.
 */
function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  // Default: dark mode on (per design decision 2026-05-23). To respect
  // OS preference instead, swap this for window.matchMedia('(prefers-color-scheme: dark)').
  return "dark";
}

/** Apply the theme class to <html>. Synchronous so the next render
 * sees the right CSS variables. */
function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

/**
 * Tiny theme controller. Single source of truth for which theme is
 * active. Persists to localStorage, applies the `dark` class to <html>
 * so the `.dark { }` block in index.css takes effect.
 *
 * Apply once at app boot via `useTheme()` in the root layout (or
 * <ThemeBoot />). Toggle from anywhere via `useTheme().toggle()`.
 */
export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(getInitialTheme);

  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const toggle = useCallback(() => {
    setModeState((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { mode, setMode, toggle };
}

/**
 * One-time application of the saved theme as early as possible —
 * prevents a flash of the wrong theme on initial paint. Render once
 * near the React root.
 */
export function ThemeBoot(): null {
  useTheme();
  return null;
}
