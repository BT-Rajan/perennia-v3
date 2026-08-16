import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "split" — two-column: headline, tagline, and the quick-chat box
 * left-aligned on one side, page-navigation cards stacked as a list
 * on the other. Stacks to a single column (main content first, then
 * nav) below the tablet breakpoint — see .hero-split-* in Hero.css.
 */
export default function SplitLayout({ copy, sections, nav, heroButtons, lang, onNavigate, quickDraft, setQuickDraft, onQuickSend, headlineStyle, branding }) {
  return (
    <div className="hero-split-wrap">
      <div className="hero-split-main">
        <h1 className="hero-welcome hero-welcome-left">
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

      <div className="hero-split-nav">
        {nav.map(({ id }) => (
          <button key={id} className="hero-section hero-section-row" onClick={() => onNavigate(id)}>
            <h2>{sections[id]?.title}</h2>
            <p>{sections[id]?.body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}
