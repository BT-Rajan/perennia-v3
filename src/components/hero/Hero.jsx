import { useEffect, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import TopBar from "../layout/TopBar.jsx";
import "./Hero.css";

/**
 * Landing page. Auto-advances into the chat assistant after a short
 * countdown (length set by theme.heroAutoAdvanceSeconds — see
 * useLang().theme), or the person can jump in early via the CTA. The
 * cards below double as the mobile entry point into the standalone
 * content pages (whichever pages are currently configured to show in
 * the nav — see the `nav` list from useLang()), since the header nav
 * menu only shows at desktop widths.
 */
export default function Hero({ onEnter, onNavigate }) {
  const { copy, sections, nav, branding, theme } = useLang();
  const [progress, setProgress] = useState(0);
  const autoAdvanceMs = (theme.heroAutoAdvanceSeconds ?? 7) * 1000;

  useEffect(() => {
    let rafId;
    let cancelled = false;
    const start = performance.now();

    function tick(now) {
      if (cancelled) return;
      const pct = Math.min(100, ((now - start) / autoAdvanceMs) * 100);
      setProgress(pct);
      if (pct >= 100) {
        onEnter();
      } else {
        rafId = requestAnimationFrame(tick);
      }
    }
    rafId = requestAnimationFrame(tick);

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAdvanceMs]);

  return (
    <div className="hero-page">
      <TopBar onNavigate={onNavigate} />
      <div className="hero-center">
        <div className="hero-welcome">{copy.home.welcome}</div>
        <div className="hero-tagline">{copy.home.tagline}</div>
        <button className="hero-cta" onClick={onEnter}>
          {copy.home.hint}
        </button>
        <div className="hero-progress-track">
          <div className="hero-progress-fill" style={{ width: `${progress}%` }} />
        </div>
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
