import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { buildFallbackSite, dirFor, loadSiteContent } from "../data/siteContent.js";
import { applyTheme } from "../theme/applyTheme.js";

const LangContext = createContext(null);

function detectInitialLang(supportedLanguages, defaultLanguage) {
  if (typeof navigator === "undefined") return defaultLanguage;
  const nav = (navigator.language || navigator.languages?.[0] || "").toLowerCase();
  const match = supportedLanguages.find((code) => nav.startsWith(code));
  return match ?? defaultLanguage;
}

function resolveBranding(branding, lang, defaultLanguage) {
  const pick = (byLang) => byLang[lang] ?? byLang[defaultLanguage] ?? Object.values(byLang)[0] ?? "";
  return {
    siteName: pick(branding.siteNameByLang),
    logoUrl: branding.logoUrl,
    faviconUrl: branding.faviconUrl,
    metaDescription: pick(branding.metaDescriptionByLang),
  };
}

// Built once, synchronously, at module load — this is what the very
// first render uses, so there's no loading spinner and no flash of
// empty UI while the backend request (kicked off in the effect below)
// is still in flight.
const FALLBACK_SITE = buildFallbackSite();

export function LangProvider({ children }) {
  const [site, setSite] = useState(FALLBACK_SITE);
  const [lang, setLang] = useState(() => detectInitialLang(FALLBACK_SITE.supportedLanguages, FALLBACK_SITE.defaultLanguage));

  // Silently upgrades from bundled fallback content to live backend
  // content once the fetch resolves. If the backend is unreachable,
  // loadSiteContent() itself already resolves to fallback data, so
  // this either upgrades seamlessly or is a harmless no-op.
  useEffect(() => {
    let cancelled = false;
    loadSiteContent().then((loaded) => {
      if (cancelled) return;
      setSite(loaded);
      // Only re-pick the language if the language the visitor is
      // currently on isn't actually supported by the live config —
      // never yank someone back to a "detected" language mid-session.
      setLang((current) => (loaded.supportedLanguages.includes(current) ? current : loaded.defaultLanguage));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const resolvedBranding = useMemo(
    () => resolveBranding(site.branding, lang, site.defaultLanguage),
    [site, lang]
  );

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dirFor(lang);
    applyTheme(site.theme, resolvedBranding);
  }, [lang, site, resolvedBranding]);

  const value = useMemo(() => {
    const langs = site.supportedLanguages;
    const idx = Math.max(0, langs.indexOf(lang));
    return {
      lang,
      dir: dirFor(lang),
      copy: site.copy[lang],
      faq: site.faq[lang],
      nav: site.nav[lang],
      sections: site.sections[lang],
      pages: site.pages[lang],
      branding: resolvedBranding,
      theme: site.theme,
      supportedLanguages: langs,
      toggleLang: () => setLang(langs[(idx + 1) % langs.length]),
      setLang,
    };
  }, [site, lang, resolvedBranding]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within LangProvider");
  return ctx;
}
