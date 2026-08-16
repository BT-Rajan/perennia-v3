import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "editorial" — a bigger, left-aligned headline and a narrower
 * quick-chat box beneath it, with page-navigation rendered as a
 * horizontal-scrolling strip of compact cards instead of a grid —
 * a more magazine/editorial feel than the centered classic layout.
 */
export default function EditorialLayout({ copy, sections, nav, heroButtons, lang, onNavigate, quickDraft, setQuickDraft, onQuickSend, headlineStyle, branding }) {
  return (
    <>
      <div className="hero-editorial-main">
        <h1 className="hero-welcome hero-welcome-left hero-welcome-editorial">
          <FitOneLine text={copy.home.welcome} styleId={headlineStyle} />
        </h1>
        {heroButtons?.length > 0 ? (
          <HeroButtons buttons={heroButtons} lang={lang} />
        ) : (
          <div className="hero-tagline hero-tagline-left">{copy.home.tagline}</div>
        )}

        <HeroChatComposer
          avatarUrl={branding?.chatAvatarUrl}
          avatarInitial={branding?.siteName?.[0]}
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
          className="hero-quick-chat-narrow"
        />
      </div>

      <div className="hero-editorial-strip">
        {nav.map(({ id }) => (
          <button key={id} className="hero-section hero-section-compact" onClick={() => onNavigate(id)}>
            <h2>{sections[id]?.title}</h2>
            <p>{sections[id]?.body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </>
  );
}
