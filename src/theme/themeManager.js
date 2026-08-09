import { THEME_PRESETS, DEFAULT_THEME } from "./themePresets.js";
import { applyTheme } from "./applyTheme.js";

/**
 * Store for persisting selected theme across sessions
 */
const THEME_STORAGE_KEY = "perennia-theme-preset";

/**
 * Get the currently active theme preset key
 * @returns {string} Active preset key
 */
export function getActiveTheme() {
  // First check localStorage
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored && THEME_PRESETS[stored]) {
    return stored;
  }
  // Fall back to default
  return DEFAULT_THEME;
}

/**
 * Set active theme by preset key
 * @param {string} presetKey - Key from THEME_PRESETS
 * @returns {boolean} Success flag
 */
export function setActiveTheme(presetKey) {
  if (!THEME_PRESETS[presetKey]) {
    console.warn(`Theme preset "${presetKey}" not found`);
    return false;
  }

  const theme = THEME_PRESETS[presetKey];
  localStorage.setItem(THEME_STORAGE_KEY, presetKey);
  
  // Apply the theme via applyTheme (existing function)
  applyTheme(theme, { siteName: "", faviconUrl: "", metaDescription: "" });
  
  return true;
}

/**
 * Initialize theme on app load
 * Applies persisted theme or default
 */
export function initializeTheme() {
  const activeTheme = getActiveTheme();
  const theme = THEME_PRESETS[activeTheme];
  
  if (theme) {
    applyTheme(theme, { siteName: "", faviconUrl: "", metaDescription: "" });
  }
}

/**
 * Get all available theme presets with metadata
 * @returns {object[]} Array of {key, name, description}
 */
export function getThemePresets() {
  return Object.entries(THEME_PRESETS).map(([key, preset]) => ({
    key,
    name: preset.name,
    description: preset.description,
  }));
}
