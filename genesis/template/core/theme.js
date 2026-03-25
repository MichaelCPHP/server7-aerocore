// Theme Management Helper
// Handles switching between light and dark themes

const THEME_KEY = 'genesis-theme';
const DARK_MODE_CLASS = 'dark-mode';

/**
 * Initialize theme from localStorage or system preference
 */
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const isDark = saved === 'dark' || (!saved && prefersReducedMotion());

  setTheme(isDark ? 'dark' : 'light');
  updateThemeButton();
}

/**
 * Set theme to 'light' or 'dark'
 */
function setTheme(mode) {
  if (mode === 'dark') {
    document.body.classList.add(DARK_MODE_CLASS);
    localStorage.setItem(THEME_KEY, 'dark');
  } else {
    document.body.classList.remove(DARK_MODE_CLASS);
    localStorage.setItem(THEME_KEY, 'light');
  }
}

/**
 * Get current theme
 */
function getTheme() {
  return document.body.classList.contains(DARK_MODE_CLASS) ? 'dark' : 'light';
}

/**
 * Toggle between light and dark themes
 */
function toggleTheme() {
  const current = getTheme();
  const next = current === 'dark' ? 'light' : 'dark';
  setTheme(next);
  updateThemeButton();
}

/**
 * Update theme toggle button text/icon
 */
function updateThemeButton() {
  const btn = document.getElementById('theme-toggle-btn');
  if (!btn) return;

  const isDark = getTheme() === 'dark';
  btn.textContent = isDark ? '☀️ Light' : '🌙 Dark';
}

/**
 * Check if system prefers reduced motion (use dark mode as default in that case)
 */
function prefersReducedMotion() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

// Auto-initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}
