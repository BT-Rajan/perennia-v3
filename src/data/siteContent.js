// ──────────────────────────────────────────────────────────
// Single place that knows how to turn (a) the backend's public config
// + content API responses, or (b) the bundled fallback data, into the
// exact shape LangContext hands to every component: { copy, nav,
// sections, faq, pages }, each keyed by language.
//
// Components never import COPY/FAQ/NAV/SECTIONS or PAGE_META/
// PAGE_CONTENT directly anymore — only useLang() — so swapping how
// content is sourced never touches component code again.
// ──────────────────────────────────────────────────────────
import { COPY, FAQ, NAV, SECTIONS } from "./content.js";
import { PAGE_CONTENT, PAGE_META } from "./pages.js";
import { fetchContentPages, fetchFaqItems, fetchPublicConfig } from "../api/publicContent.js";

const RTL_LANGS = new Set(["ar", "he", "fa", "ur"]);

function dirFor(lang) {
  return RTL_LANGS.has(lang) ? "rtl" : "ltr";
}

// Backend copy blobs use snake_case (matches Python convention);
// components use camelCase (matches this codebase's JS convention).
// One small recursive converter keeps both sides idiomatic instead of
// forcing one language's naming convention onto the other.
function toCamel(value) {
  if (Array.isArray(value)) return value.map(toCamel);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()), toCamel(v)])
    );
  }
  return value;
}

function fillTemplate(template, vars) {
  return Object.entries(vars).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, v), template ?? "");
}

// ---- Building the unified shape from the BUNDLED FALLBACK ----------

function localCopyForLang(lang) {
  const c = COPY[lang];
  return {
    home: c.home,
    chat: c.chat,
    booking: {
      ...c.booking,
      // already functions in the local fallback — used as-is.
    },
  };
}

function buildFromLocalFallback(supportedLanguages) {
  const copy = {}, nav = {}, sections = {}, faq = {}, pages = {};
  for (const lang of supportedLanguages) {
    copy[lang] = localCopyForLang(lang);
    nav[lang] = NAV[lang];
    sections[lang] = SECTIONS[lang];
    faq[lang] = FAQ[lang];
    pages[lang] = Object.fromEntries(
      Object.keys(PAGE_META[lang]).map((slug) => [
        slug,
        { ...PAGE_META[lang][slug], body: PAGE_CONTENT[lang][slug] },
      ])
    );
  }
  return { copy, nav, sections, faq, pages };
}

// ---- Building the unified shape from the BACKEND API ----------------

function apiCopyForLang(copyBlobs, lang) {
  const home = toCamel(copyBlobs["copy.home"]?.[lang] ?? {});
  const chat = toCamel(copyBlobs["copy.chat"]?.[lang] ?? {});
  const bookingRaw = toCamel(copyBlobs["copy.booking"]?.[lang] ?? {});

  return {
    home,
    chat,
    booking: {
      ...bookingRaw,
      // Backend stores these as {id}/{date}/{time} template strings
      // (functions aren't JSON-serializable); rehydrate them into the
      // callables every booking component already expects.
      successNew: (id) => fillTemplate(bookingRaw.successNew, { id }),
      successReschedule: (date, time) => fillTemplate(bookingRaw.successReschedule, { date, time }),
      successCancel: bookingRaw.successCancel,
    },
  };
}

function buildFromApi(publicConfig, contentPages, faqItems, supportedLanguages) {
  const visiblePages = [...contentPages].sort((a, b) => a.order - b.order);
  const navPages = visiblePages.filter((p) => p.show_in_nav);

  const copy = {}, nav = {}, sections = {}, faq = {}, pages = {};
  for (const lang of supportedLanguages) {
    copy[lang] = apiCopyForLang(publicConfig, lang);

    nav[lang] = navPages.map((p) => ({ id: p.slug, label: p.translations[lang]?.nav_label ?? p.slug }));

    sections[lang] = Object.fromEntries(
      navPages.map((p) => [p.slug, {
        title: p.translations[lang]?.section_title ?? "",
        body: p.translations[lang]?.section_body ?? "",
      }])
    );

    pages[lang] = Object.fromEntries(
      visiblePages.map((p) => [p.slug, {
        line1: p.translations[lang]?.tagline_line1 ?? "",
        line2: p.translations[lang]?.tagline_line2 ?? "",
        sub: p.translations[lang]?.tagline_sub ?? "",
        body: p.translations[lang]?.body_markdown ?? "",
      }])
    );

    faq[lang] = faqItems.map((item) => ({
      q: item.translations[lang]?.q ?? "",
      a: item.translations[lang]?.a ?? "",
    }));
  }
  return { copy, nav, sections, faq, pages };
}

export function buildFallbackSite() {
  const supportedLanguages = Object.keys(COPY);
  return {
    source: "fallback",
    supportedLanguages,
    defaultLanguage: "en",
    branding: { siteName: "Perennia", logoUrl: "/static/logo.svg" },
    ...buildFromLocalFallback(supportedLanguages),
  };
}

/**
 * Loads everything needed to render the site, preferring the live
 * backend and falling back to bundled content per-piece if the
 * backend (or a specific call) is unreachable — so a partial outage
 * degrades gracefully instead of blanking the whole site.
 */
export async function loadSiteContent() {
  const [publicConfig, contentPages, faqItems] = await Promise.all([
    fetchPublicConfig(),
    fetchContentPages(),
    fetchFaqItems(),
  ]);

  const supportedLanguages = publicConfig?.["locale.supported_languages"] ?? Object.keys(COPY);
  const defaultLanguage = publicConfig?.["locale.default_language"] ?? "en";

  const haveFullApiData = publicConfig && contentPages && faqItems;
  const site = haveFullApiData
    ? buildFromApi(publicConfig, contentPages, faqItems, supportedLanguages)
    : buildFromLocalFallback(supportedLanguages);

  return {
    source: haveFullApiData ? "api" : "fallback",
    supportedLanguages,
    defaultLanguage,
    branding: {
      siteName: publicConfig?.["branding.site_name"] ?? "Perennia",
      logoUrl: publicConfig?.["branding.logo_url"] ?? "/static/logo.svg",
    },
    ...site,
  };
}

export { dirFor };
