import { useLayoutEffect, useRef } from "react";
import { isSafeHref } from "../../data/siteContent.js";
import ChatInput from "../chat/ChatInput.jsx";

/**
 * Resolves admin-provisioned hero buttons (copy.home_hero_buttons) into
 * a flat, render-ready list — i18n label lookup + href safety check
 * done once, shared by every place that renders this same config
 * (HeroButtons above, CenteredCardLayout's pill row).
 */
export function resolveHeroButtons(buttons, lang) {
  return (buttons || [])
    .map((btn, i) => {
      const label = btn.label?.[lang] ?? Object.values(btn.label || {})[0] ?? "";
      if (!label || !isSafeHref(btn.url)) return null;
      return { key: i, label, url: btn.url, external: /^https?:\/\//.test(btn.url) };
    })
    .filter(Boolean);
}

/**
 * Admin-provisioned row of slim buttons, shown instead of the plain
 * tagline once at least one is configured. Every button shares the
 * same background (pill outline), so the row reads as one control
 * regardless of count or label length.
 */
export function HeroButtons({ buttons, lang }) {
  return (
    <div className="hero-buttons" role="navigation">
      {resolveHeroButtons(buttons, lang).map(({ key, label, url, external }) => (
        <a
          key={key}
          className="hero-button"
          href={url}
          {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        >
          {label}
        </a>
      ))}
    </div>
  );
}

/**
 * Small circular avatar — an uploaded image (chat.avatar_url, admin-
 * configurable, Settings > Chat / AI assistant) if set, otherwise a
 * plain initial letter. Used by both HeroChatComposer here and
 * ChatWidget's header, so the homepage entry point and the sticky
 * popover always show the same face rather than looking like two
 * different assistants.
 */
export function ChatAvatar({ avatarUrl, initial, className }) {
  return (
    <span className={`chat-avatar ${className || ""}`.trim()} aria-hidden="true">
      {avatarUrl ? <img src={avatarUrl} alt="" /> : (initial || "A")}
    </span>
  );
}

/**
 * The homepage's quick-start entry into the AI Assistant — a plain
 * single-line text composer (no avatar here; ChatWidget's own header
 * still shows one once the conversation opens). Deliberately kept
 * text-only (no mic here, unlike the sticky ChatWidget popover, which
 * also supports voice) and this compact: it's meant to read as a fast
 * way in to the *same* assistant, not as a second, competing chat
 * surface with its own message history and status states.
 */
export function HeroChatComposer({ value, onChange, onSend, placeholder, sendLabel, className }) {
  return (
    <div className={`hero-quick-chat ${className || ""}`.trim()}>
      <ChatInput value={value} onChange={onChange} onSend={onSend} placeholder={placeholder} sendLabel={sendLabel} />
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
export function FitOneLine({ text, className, styleId }) {
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
    <div ref={outerRef} className={`fit-one-line ${className || ""}`.trim()} data-headline-style={styleId || "ripple-gradient"}>
      <span ref={innerRef} className="fit-one-line-inner">
        {text}
      </span>
    </div>
  );
}
