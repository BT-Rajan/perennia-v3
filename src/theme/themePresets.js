// ──────────────────────────────────────────────────────────
// Enterprise theme presets — three professional, high-visibility designs
// Replace soft pastels with authoritative typography and bold contrast.
// ──────────────────────────────────────────────────────────

export const THEME_PRESETS = {
  // ---- PROFESSIONAL DARK: Sophisticated, executive boardroom aesthetic ----
  professional_dark: {
    name: "Professional Dark",
    description: "Authoritative dark theme with steel blue accents",
    backgroundColor: "#0f1419",      // Deeper charcoal (less playful than #0a0e27)
    primaryColor: "#1e40af",         // Bold steel blue (replaces soft gold)
    accentColor: "#0369a1",          // Deep cyan (sharp, not playful)
    textColor: "#f8fafc",            // Clean white text
    fontDisplay: '"Lora", Georgia, serif',                               // More serious serif
    fontBody: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',        // Corporate sans-serif
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=Lora:wght@500;600;700&display=swap",
    headerHeightPx: 72,              // Taller, more commanding
    contentMaxWidthPx: 1280,
    cornerRadiusPx: 8,               // Sharper corners (less rounded/playful)
    heroAutoAdvanceSeconds: 6,
  },

  // ---- CORPORATE BLUE: Trustworthy, institutional, high-impact ----
  corporate_blue: {
    name: "Corporate Blue",
    description: "Trust-focused design with strong contrast and institutional authority",
    backgroundColor: "#ffffff",      // Pure white (maximum clarity)
    primaryColor: "#003d82",         // Deep corporate blue
    accentColor: "#d73027",          // Bold accent for CTAs (high visibility)
    textColor: "#1a1a1a",            // Near-black text (strong contrast)
    fontDisplay: '"IBM Plex Sans", Arial, sans-serif',                  // IBM corporate aesthetic
    fontBody: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap",
    headerHeightPx: 68,
    contentMaxWidthPx: 1200,
    cornerRadiusPx: 6,               // Minimal rounding (business-like)
    heroAutoAdvanceSeconds: 8,
  },

  // ---- MODERN MINIMAL: Clean, minimalist, confidence through clarity ----
  modern_minimal: {
    name: "Modern Minimal",
    description: "Bold typography, clean lines, maximum readability",
    backgroundColor: "#fafbfc",      // Nearly white with subtle warmth
    primaryColor: "#e11d48",         // Striking rose (confident, bold)
    accentColor: "#475569",          // Dark slate (grounded, professional)
    textColor: "#0f172a",            // Deep navy text (high contrast)
    fontDisplay: '"Poppins", "Segoe UI", sans-serif',                  // Modern, clean display
    fontBody: '"Inter", system-ui, -apple-system, sans-serif',         // Industry standard
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@300;400;500;600;700&display=swap",
    headerHeightPx: 70,
    contentMaxWidthPx: 1260,
    cornerRadiusPx: 12,              // Balanced, not excessive
    heroAutoAdvanceSeconds: 7,
  },
};

export const DEFAULT_THEME = "professional_dark";

/**
 * Get a specific preset by key
 * @param {string} presetKey - Key from THEME_PRESETS
 * @returns {object} Theme configuration object
 */
export function getThemePreset(presetKey = DEFAULT_THEME) {
  return THEME_PRESETS[presetKey] || THEME_PRESETS[DEFAULT_THEME];
}

/**
 * Get all available theme keys
 * @returns {string[]} Array of preset keys
 */
export function getThemePresetKeys() {
  return Object.keys(THEME_PRESETS);
}
