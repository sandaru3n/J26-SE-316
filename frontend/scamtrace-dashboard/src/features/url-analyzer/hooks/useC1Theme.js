/**
 * Theme State Management Hook & Context for Component C1 (URL Analyzer).
 *
 * ============================================================================
 * COMPONENT 1: FRONTEND UI - SOC THEME SWITCHER HOOK (useC1Theme)
 * ============================================================================
 * This module provides dark/light theme switching specifically calibrated for
 * the Security Operations Center (SOC) dashboard of Component C1.
 *
 * How it works:
 * 1. Persistent Storage: Saves the user's selected theme ('dark' or 'light')
 *    in the browser's localStorage under the key 'c1.theme'.
 * 2. System Preference Detection: On first visit, checks the operating system's
 *    preferred color scheme via window.matchMedia('(prefers-color-scheme: light)').
 * 3. DOM Syncing: Sets 'data-c1-theme' and toggles the '.dark' CSS class on the
 *    root <html> element (document.documentElement), ensuring all Tailwind styles
 *    and custom cyber-glow borders immediately adapt.
 * 4. React Context Provider: Exports <C1ThemeProvider> so any nested card, tab,
 *    or chart can read the current theme without prop-drilling.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// Browser localStorage key for theme persistence
const STORAGE_KEY = 'c1.theme';

/**
 * Read initial theme from localStorage or OS preferences.
 * Defaults to 'dark' (the classic SOC cybersecurity operational palette).
 */
function readInitialTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }
    // Respect OS preference on first visit if no explicit setting was saved
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark'; // Default to SOC dark theme
  } catch {
    return 'dark';
  }
}

export function useC1Theme() {
  const [theme, setThemeState] = useState(readInitialTheme);

  const setTheme = useCallback((newTheme) => {
    setThemeState((prev) => {
      const resolved = typeof newTheme === 'function' ? newTheme(prev) : newTheme;
      try {
        localStorage.setItem(STORAGE_KEY, resolved);
      } catch {
        // Private browsing fallback
      }
      return resolved;
    });
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, [setTheme]);

  // Sync with document root so global elements (nav, shell, modals) adapt seamlessly
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-c1-theme', theme);
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  }, [theme]);

  // Sync with OS preference changes if user hasn't explicitly set a preference
  useEffect(() => {
    try {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
      const handleChange = (e) => {
        if (!localStorage.getItem(STORAGE_KEY)) {
          setThemeState(e.matches ? 'light' : 'dark');
        }
      };
      mediaQuery.addEventListener?.('change', handleChange);
      return () => mediaQuery.removeEventListener?.('change', handleChange);
    } catch {
      return undefined;
    }
  }, []);

  return { theme, setTheme, toggleTheme, isDark: theme === 'dark' };
}

export const C1ThemeContext = createContext({
  theme: 'dark',
  isDark: true,
  setTheme: () => {},
  toggleTheme: () => {},
});

export function C1ThemeProvider({ children }) {
  const themeState = useC1Theme();
  return React.createElement(C1ThemeContext.Provider, { value: themeState }, children);
}

export function useC1ThemeContext() {
  return useContext(C1ThemeContext);
}

