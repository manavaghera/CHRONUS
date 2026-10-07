// Light / dark / follow-the-system, remembered in this browser.
// html[data-theme] forces a theme (dark.css); no attribute = follow the system.
const KEY = 'chronus_theme'
export const THEME_EVENT = 'chronus:theme'

export function storedTheme() {
  try { return localStorage.getItem(KEY) || 'auto' } catch { return 'auto' }
}

export function applyTheme(theme) {
  const root = document.documentElement
  if (theme === 'light' || theme === 'dark') root.dataset.theme = theme
  else delete root.dataset.theme
  try { theme === 'auto' ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, theme) } catch { /* storage blocked */ }
  window.dispatchEvent(new Event(THEME_EVENT))
}

export function isDark() {
  const forced = document.documentElement.dataset.theme
  if (forced) return forced === 'dark'
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}
