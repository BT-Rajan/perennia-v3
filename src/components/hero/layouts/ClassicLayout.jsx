import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "classic" — the site's original, and default, homepage body:
 * centered headline/tagline/quick-chat stacked above a grid of nav
 * cards. This is exactly the markup that existed before the layout
 * template setting did, so picking "classic" (or leaving the setting
 * unset) can never look different from what's already live.
 */
export default function ClassicLayout({ copy, sections, nav, heroButtons, lang, onNavigate, quickDraft, setQuickDraft, onQuickSend, headlineStyle, branding }) {
  return (
    <>
      <div className="hero-center">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.welcome} styleId={headlineStyle} />
        </h1>
        {heroButtons?.length > 0 ? (
          <HeroButtons buttons={heroButtons} lang={lang} />
        ) : (
          <div className="hero-tagline">{copy.home.tagline}</div>
        )}

        <HeroChatComposer
          avatarUrl={branding?.chatAvatarUrl}
          avatarInitial={branding?.siteName?.[0]}
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />
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
    </>
  );
}
