import { useEffect, useLayoutEffect, useRef, useState } from "react";
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

// Admin-configurable — theme.headline_typing_speed_cps (characters per
// second; see backend/app/settings_registry.py and applyTheme.js). This
// is only the fallback for when no theme value has loaded yet.
const DEFAULT_TYPING_SPEED_CPS = 5;
const HOLD_AFTER_TYPE_MS = 1100; // beat before handing off to the permanent tagline

/**
 * The homepage's H1: types out the admin-configured `statement`
 * (copy.home.heroStatement — "what Perennia does"), then hands off to
 * the permanent two-line brand tagline (copy.home.taglineLine1/2),
 * which stays on screen for good (no looping/repeating — see the
 * brief). Both layers are mounted for the entire lifetime of this
 * component, stacked in the same grid cell (grid-area: 1/1), so the
 * container's height is reserved from first paint and never changes
 * as the visible layer swaps — only opacity animates, never layout.
 *
 * The typed-so-far substring runs through FitOneLine, reusing its
 * scale-to-fit measurement (transform: scale, not a layout property)
 * so an in-progress or very long statement never overflows.
 *
 * Accessibility: the essential content (both strings) is exposed via
 * a single static aria-label on the <h1>, independent of animation
 * phase — a screen reader never has to wait for the typing to finish,
 * and prefers-reduced-motion skips straight to the final tagline.
 */
export function HeroHeadline({ statement, taglineLine1, taglineLine2, className, typingSpeedCps }) {
  const reduceMotionRef = useRef(
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
  const skip = reduceMotionRef.current || !statement;

  const [phase, setPhase] = useState(skip ? "tagline" : "typing"); // "typing" -> "tagline"
  const [count, setCount] = useState(0);

  // Admin-configurable (theme.headline_typing_speed_cps) characters-
  // per-second, converted to a per-character delay. Falls back to
  // DEFAULT_TYPING_SPEED_CPS if the theme hasn't loaded / is unset.
  const typeSpeedMs = Math.max(1, Math.round(1000 / (typingSpeedCps || DEFAULT_TYPING_SPEED_CPS)));

  useEffect(() => {
    if (skip || phase !== "typing") return;
    if (count < statement.length) {
      const id = setTimeout(() => setCount((c) => c + 1), typeSpeedMs);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => setPhase("tagline"), HOLD_AFTER_TYPE_MS);
    return () => clearTimeout(id);
  }, [phase, count, statement, skip, typeSpeedMs]);

  const typingDone = phase !== "typing";
  // A literal newline in copy.home.hero_statement (admin-editable, see
  // settings_registry.py) types across two lines instead of one — the
  // typed-so-far substring is split on "\n" and each line renders as
  // its own FitOneLine, stacked (FitOneLine is block-level, so this
  // stacks with no extra markup). No newline present = today's
  // single-line behavior, unchanged.
  const flatStatement = statement ? statement.replace(/\n/g, " ") : "";
  const accessibleName = statement ? `${flatStatement} — ${taglineLine1} ${taglineLine2}` : `${taglineLine1} ${taglineLine2}`;
  const typedLines = statement ? statement.slice(0, count).split("\n") : [];

  return (
    <h1 className={`hero-headline-stage ${className || ""}`.trim()} aria-label={accessibleName}>
      {statement && (
        <span className={`hero-headline-layer ${typingDone ? "is-hidden" : ""}`} aria-hidden="true">
          {typedLines.map((line, i) => (
            <FitOneLine key={i} text={line} styleId="solid-white" />
          ))}
        </span>
      )}
      <span className={`hero-headline-layer hero-tagline-layer ${typingDone ? "is-visible" : ""}`} aria-hidden="true">
        <span className="hero-tagline-line1">{taglineLine1}</span>
        <span className="hero-tagline-line2">{taglineLine2}</span>
      </span>
    </h1>
  );
}

/**
 * One-line supporting proposition beneath the headline — the
 * "we design, build and operate…" sentence in the brief's hero
 * hierarchy. Plain paragraph, no admin styling hooks needed.
 */
export function HeroSupportingText({ text, className }) {
  if (!text) return null;
  return <p className={`hero-supporting ${className || ""}`.trim()}>{text}</p>;
}

/**
 * Subtle example-prompt chips under the quick-chat composer — tapping
 * one hands the preset question straight to onPick (same handoff the
 * composer's own Send button and the topic cards use). Kept as plain
 * text chips, deliberately quieter than the hero buttons/CTAs, so they
 * read as suggestions rather than another row of calls to action.
 */
export function HeroExamplePrompts({ prompts, onPick, className }) {
  if (!prompts?.length) return null;
  return (
    <div className={`hero-example-prompts ${className || ""}`.trim()}>
      {prompts.map((prompt, i) => (
        <button key={i} type="button" className="hero-example-prompt" onClick={() => onPick(prompt)}>
          {prompt}
        </button>
      ))}
    </div>
  );
}
