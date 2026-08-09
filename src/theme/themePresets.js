// ──────────────────────────────────────────────────────────
// BOLD ENTERPRISE THEMES — Maximum contrast, high-impact designs
// No soft gradients. Pure power. Authoritative presence.
// ──────────────────────────────────────────────────────────

export const THEME_PRESETS = {
  // ---- DARK POWER: Jet black + electric blue — commanding boardroom ----
  dark_power: {
    name: "Dark Power",
    description: "Jet black with electric blue. Maximum contrast. Pure authority.",
    backgroundColor: "#000000",           // Pure jet black (maximum darkness)
    primaryColor: "#00d4ff",              // Electric cyan/blue (maximum saturation & brightness)
    accentColor: "#ff0080",               // Hot magenta (high visibility CTAs)
    textColor: "#ffffff",                 // Pure white (maximum contrast)
    fontDisplay: '"IBM Plex Mono", monospace',              // Bold, technical
    fontBody: '"IBM Plex Sans", Arial, sans-serif',        // Corporate strength
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@600;700;800&family=IBM+Plex+Mono:wght@600;700&display=swap",
    headerHeightPx: 80,                  // Tall, commanding
    contentMaxWidthPx: 1400,
    cornerRadiusPx: 0,                   // NO rounding — sharp, brutal
    heroAutoAdvanceSeconds: 5,
  },

  // ---- CORPORATE STEEL: Deep navy + gold — institutional powerhouse ----
  corporate_steel: {
    name: "Corporate Steel",
    description: "Deep navy foundation with bold gold highlights. Institutional strength.",
    backgroundColor: "#0a1428",          // Deep navy-black (intense, authority)
    primaryColor: "#ffd700",             // Bold gold (high visibility, wealth signal)
    accentColor: "#ff4444",              // Bold red (emergency CTAs, demands attention)
    textColor: "#ffffff",                // Pure white text (maximum readability)
    fontDisplay: '"Playfair Display", Georgia, serif',     // Bold serif authority
    fontBody: '"Open Sans", Arial, sans-serif',            // Strong sans-serif
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800;900&family=Open+Sans:wght@600;700;800&display=swap",
    headerHeightPx: 78,
    contentMaxWidthPx: 1380,
    cornerRadiusPx: 2,                   // Minimal rounding (sharp, professional)
    heroAutoAdvanceSeconds: 6,
  },

  // ---- TECH NEON: White + cyberpunk magenta/cyan — disruptive bold ----
  tech_neon: {
    name: "Tech Neon",
    description: "Pure white with neon magenta & cyan. Modern, aggressive, disruptive.",
    backgroundColor: "#ffffff",          // Pure white (maximum brightness)
    primaryColor: "#ff006e",             // Hot magenta (aggressive, attention-grabbing)
    accentColor: "#00f5ff",              // Neon cyan (electric, high-energy)
    textColor: "#000000",                // Pure black (maximum contrast)
    fontDisplay: '"Space Mono", monospace',               // Bold monospace (tech)
    fontBody: '"Roboto", Arial, sans-serif',              // Strong, modern sans
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=Space+Mono:wght@700&family=Roboto:wght@700;800;900&display=swap",
    headerHeightPx: 76,
    contentMaxWidthPx: 1360,
    cornerRadiusPx: 4,                   // Slightly sharp
    heroAutoAdvanceSeconds: 4,
  },

  // ---- MINIMAL BOLD: Charcoal + red — no-nonsense enterprise ----
  minimal_bold: {
    name: "Minimal Bold",
    description: "Charcoal + bold red. No frills. Maximum legibility. Enterprise steel.",
    backgroundColor: "#1a1a1a",          // Deep charcoal (strong, serious)
    primaryColor: "#ff0000",             // Pure bold red (cannot be ignored)
    accentColor: "#ffaa00",              // Bright orange-gold (secondary CTA)
    textColor: "#ffffff",                // Pure white (crystal clear)
    fontDisplay: '"Roboto Condensed", Arial, sans-serif',  // Condensed bold
    fontBody: '"Roboto", Arial, sans-serif',              // Strong, trustworthy
    fontAr: '"Noto Kufi Arabic", "Arial Unicode MS", sans-serif',
    googleFontsUrl: "https://fonts.googleapis.com/css2?family=Roboto+Condensed:wght@700;800;900&family=Roboto:wght@600;700;800&display=swap",
    headerHeightPx: 74,
    contentMaxWidthPx: 1340,
    cornerRadiusPx: 0,                   // No rounding
    heroAutoAdvanceSeconds: 7,
  },
};

export const DEFAULT_THEME = "dark_power";

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
