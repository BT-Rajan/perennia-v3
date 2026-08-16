import { FitOneLine, HeroChatComposer, resolveHeroButtons } from "../HeroShared.jsx";

/**
 * "centered-card" — headline, tagline, quick-chat, and page nav all
 * live inside one bordered glass card instead of being spread across
 * the page.
 *
 * Unlike the other three layouts, the tagline here is always plain
 * text (never swapped for the admin's hero-button row) — this layout
 * already has its own dedicated pill row below, so the two don't
 * compete for the same slot. Those pills come from the admin's Hero
 * buttons config (Settings > On-screen text > Home hero buttons) —
 * deliberately NOT the top nav/page menu — falling back to the page
 * nav only if no hero buttons are configured, so the card never ends
 * up with an empty pill row on a fresh install.
 */
export default function CenteredCardLayout({ copy, sections, nav, heroButtons, lang, onNavigate, quickDraft, setQuickDraft, onQuickSend, headlineStyle, branding }) {
  const resolvedHeroButtons = resolveHeroButtons(heroButtons, lang);
  const usingHeroButtons = resolvedHeroButtons.length > 0;

  return (
    <div className="hero-card-wrap">
      <div className="hero-card">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.welcome} styleId={headlineStyle} />
        </h1>
        <div className="hero-tagline">{copy.home.tagline}</div>

        <HeroChatComposer
          avatarUrl={branding?.chatAvatarUrl}
          avatarInitial={branding?.siteName?.[0]}
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />

        {usingHeroButtons ? (
          <div className="hero-card-pills">
            {resolvedHeroButtons.map(({ key, label, url, external }) => (
              <a
                key={key}
                className="hero-card-pill"
                href={url}
                {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              >
                {label}
              </a>
            ))}
          </div>
        ) : nav.length > 0 && (
          <div className="hero-card-pills">
            {nav.map(({ id }) => (
              <button key={id} className="hero-card-pill" onClick={() => onNavigate(id)}>
                {sections[id]?.title}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
