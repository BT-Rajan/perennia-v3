// ──────────────────────────────────────────────────────────
// Applies theme + branding settings to the live document. This is
// what turns the *static* fallback values baked into tokens.css and
// index.html into genuinely runtime-configurable ones: every value
// here can come from the backend (theme.* / branding.* in
// backend/app/settings_registry.py) and, when it does, silently
// overrides the CSS/HTML defaults with no rebuild required.
// ──────────────────────────────────────────────────────────

const CSS_VAR_MAP = {
  backgroundColor: "--brand-bg",
  primaryColor: "--brand-primary",
  accentColor: "--brand-accent",
  textColor: "--brand-text",
  fontDisplay: "--font-display",
  fontBody: "--font-body",
  fontAr: "--font-ar",
};

const PX_VAR_MAP = {
  headerHeightPx: "--header-h",
  contentMaxWidthPx: "--content-max",
  cornerRadiusPx: "--radius-md",
};

/**
 * @param {object} theme - camelCase theme fields (see siteContent.js)
 * @param {{siteName: string, faviconUrl: string, metaDescription: string}} branding - already resolved to the current language
 */
export function applyTheme(theme, branding) {
  const root = document.documentElement.style;

  for (const [key, cssVar] of Object.entries(CSS_VAR_MAP)) {
    if (theme[key]) root.setProperty(cssVar, theme[key]);
  }
  for (const [key, cssVar] of Object.entries(PX_VAR_MAP)) {
    if (theme[key] != null) root.setProperty(cssVar, `${theme[key]}px`);
  }

  if (theme.googleFontsUrl) {
    const link = document.getElementById("google-fonts-link");
    if (link && link.href !== theme.googleFontsUrl) link.href = theme.googleFontsUrl;
  }

  if (branding.siteName) document.title = branding.siteName;

  if (branding.faviconUrl) {
    const favicon = document.getElementById("favicon-link");
    if (favicon) favicon.href = branding.faviconUrl;
  }

  if (branding.metaDescription) {
    const meta = document.getElementById("meta-description");
    if (meta) meta.content = branding.metaDescription;
  }

  const themeColorMeta = document.getElementById("theme-color-meta");
  if (themeColorMeta && theme.backgroundColor) themeColorMeta.content = theme.backgroundColor;
}
