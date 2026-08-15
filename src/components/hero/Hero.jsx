import { useLayoutEffect, useRef } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { isSafeHref } from "../../data/siteContent.js";
import TopBar from "../layout/TopBar.jsx";
import "./Hero.css";

/**
 * Admin-provisioned row of slim buttons, shown instead of the plain
 * tagline once at least one is configured. Every button shares the
 * same background (pill outline), so the row reads as one control
 * regardless of count or label length.
 */
function HeroButtons({ buttons, lang }) {
  return (
    <div className="hero-buttons" role="navigation">
      {buttons.map((btn, i) => {
        const label = btn.label?.[lang] ?? Object.values(btn.label || {})[0] ?? "";
        if (!label || !isSafeHref(btn.url)) return null;
        const external = /^https?:\/\//.test(btn.url);
        return (
          <a
            key={i}
            className="hero-button"
            href={btn.url}
            {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            {label}
          </a>
        );
      })}
    </div>
  );
}

/**
 * Renders `text` as a single unbroken line that always fits its
 * container, at any viewport width and at any string length (the
 * headline is admin-configurable copy, so we can't assume how long
 * it will be). Rather than guessing a font-size breakpoint by
 * breakpoint, it measures the natural width of the text after
 * render and uniformly scales it down just enough to fit — same
 * idea as `text-overflow: clamp`-by-hand. Re-measures on resize and
 * whenever the text itself changes (e.g. a language switch).
 *
 * Deliberately kept as ONE text node (no per-word/per-letter
 * splitting) — splitting the string into separate inline elements
 * broke text shaping and caused the words to overlap instead of
 * flowing normally. The ripple is done separately as a shimmer
 * sweep across the gradient fill (see .fit-one-line-inner in
 * Hero.css), which animates safely without touching layout at all.
 */
function FitOneLine({ text, className }) {
  const outerRef = useRef(null);
  const innerRef = useRef(null);

  useLayoutEffect(() => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;

    function fit() {
      inner.style.transform = "scale(1)";
      const outerWidth = outer.clientWidth;
      const innerWidth = inner.scrollWidth;
      // outerWidth can legitimately be 0 for a frame or two before the
      // parent has been laid out (first paint, font swap, tab restore).
      // Scaling to 0 in that window used to hide the headline for good —
      // ResizeObserver only fires on width *changes*, so if the width
      // never moves off 0→real in one observed step it never re-fires.
      if (outerWidth === 0 || innerWidth === 0) return;
      const nextScale = innerWidth > outerWidth ? outerWidth / innerWidth : 1;
      // Applied straight to the DOM instead of through React state.
      // fit() always resets the element to scale(1) before it
      // re-measures — if the final scale is set via setState and the
      // freshly computed value happens to match whatever was already
      // in state (very common: multiple ResizeObserver callbacks
      // firing for the same settled width), React bails out of the
      // re-render since the state didn't change, and the scale(1)
      // reset is left on screen — that's the desktop headline
      // clipping bug (text overflows both edges of the container's
      // overflow: hidden box). Writing the style directly guarantees
      // every fit() call ends with the correct scale applied, with no
      // dependency on whether the value changed since last time.
      inner.style.transform = `scale(${nextScale})`;
    }

    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(outer);
    // Re-fit once webfonts finish loading — the first measurement can
    // run before the display font swaps in, which would otherwise
    // lock in a scale sized for the fallback font's (different) width.
    document.fonts?.ready?.then(fit);
    return () => ro.disconnect();
  }, [text]);

  return (
    <div ref={outerRef} className={`fit-one-line ${className || ""}`.trim()}>
      <span ref={innerRef} className="fit-one-line-inner">
        {text}
      </span>
    </div>
  );
}

/**
 * Landing page. Entry into the chat assistant is via the always-visible
 * sticky AI Assistant button (see StickyChat/ChatWidget) — the rippling,
 * always-single-line headline (see FitOneLine above) is the page's
 * signature visual, sitting where the old pulsing "voice orb" used to be.
 *
 * The cards below double as the mobile entry point into the
 * standalone content pages (whichever pages are currently configured
 * to show in the nav — see the `nav` list from useLang()), since the
 * header nav menu only shows at desktop widths.
 */
export default function Hero({ onNavigate }) {
  const { copy, sections, nav, branding, heroButtons, lang } = useLang();

  return (
    <div className="hero-page">
      <TopBar onNavigate={onNavigate} />

      <div className="hero-center">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.welcome} />
        </h1>
        {heroButtons?.length > 0 ? (
          <HeroButtons buttons={heroButtons} lang={lang} />
        ) : (
          <div className="hero-tagline">{copy.home.tagline}</div>
        )}
      </div>

      <div className="hero-sections">
        {nav.map(({ id }) => (
          <button key={id} className="hero-section" onClick={() => onNavigate(id)}>
            <h2>{sections[id]?.title}</h2>
            <p>{sections[id]?.body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>

      <footer className="hero-footer">© {new Date().getFullYear()} {branding.siteName}</footer>
    </div>
  );
}
