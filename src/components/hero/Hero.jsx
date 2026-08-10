import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import TopBar from "../layout/TopBar.jsx";
import ChatInput from "../chat/ChatInput.jsx";
import "./Hero.css";

/**
 * Renders `text` as a single unbroken line that always fits its
 * container, at any viewport width and at any string length (the
 * headline is admin-configurable copy, so we can't assume how long
 * it will be). Rather than guessing a font-size breakpoint by
 * breakpoint, it measures the natural width of the text after
 * render and uniformly scales it down just enough to fit — same
 * idea as `text-overflow: clamp`-by-hand. Re-measures on resize and
 * whenever the text itself changes (e.g. a language switch).
 */
function FitOneLine({ text, className }) {
  const outerRef = useRef(null);
  const innerRef = useRef(null);
  const [scale, setScale] = useState(1);

  useLayoutEffect(() => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;

    function fit() {
      inner.style.transform = "scale(1)";
      const outerWidth = outer.clientWidth;
      const innerWidth = inner.scrollWidth;
      setScale(innerWidth > outerWidth ? outerWidth / innerWidth : 1);
    }

    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(outer);
    return () => ro.disconnect();
  }, [text]);

  const words = text.split(" ");

  return (
    <div ref={outerRef} className={`fit-one-line ${className || ""}`.trim()}>
      <span ref={innerRef} className="fit-one-line-inner" style={{ transform: `scale(${scale})` }}>
        {words.map((word, i) => (
          <span key={i} className="ripple-word" style={{ animationDelay: `${i * 0.12}s` }}>
            {word}
            {i < words.length - 1 ? "\u00A0" : ""}
          </span>
        ))}
      </span>
    </div>
  );
}

/**
 * Landing page. Auto-advances into the chat assistant after a short
 * countdown (length set by theme.heroAutoAdvanceSeconds — see
 * useLang().theme), or the person can jump in early via the CTA or
 * by typing straight into the quick-start chat box. The rippling,
 * always-single-line headline (see FitOneLine above) sits where the
 * old pulsing "voice orb" used to be — it's the page's signature
 * visual now.
 *
 * The cards below double as the mobile entry point into the
 * standalone content pages (whichever pages are currently configured
 * to show in the nav — see the `nav` list from useLang()), since the
 * header nav menu only shows at desktop widths.
 */
export default function Hero({ onEnter, onNavigate }) {
  const { copy, sections, nav, branding, theme } = useLang();
  const [progress, setProgress] = useState(0);
  const [quickDraft, setQuickDraft] = useState("");
  const autoAdvanceMs = (theme.heroAutoAdvanceSeconds ?? 7) * 1000;

  function handleQuickSend() {
    const text = quickDraft.trim();
    if (!text) return;
    setQuickDraft("");
    onEnter(text);
  }

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
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.welcome} />
        </h1>
        <div className="hero-tagline">{copy.home.tagline}</div>

        <div className="hero-quick-chat">
          <ChatInput
            value={quickDraft}
            onChange={setQuickDraft}
            onSend={handleQuickSend}
            placeholder={copy.chat.inputPlaceholder}
            sendLabel={copy.common.send}
          />
        </div>

        <button className="hero-cta" onClick={() => onEnter()}>
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
