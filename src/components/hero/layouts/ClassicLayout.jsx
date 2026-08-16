import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "classic" — the site's original, and default, homepage body:
 * centered headline/tagline/quick-chat stacked above a grid of nav
 * cards. This is exactly the markup that existed before the layout
 * template setting did, so picking "classic" (or leaving the setting
 * unset) can never look different from what's already live.
 */
export default function ClassicLayout({ copy, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, homeTopics, onTopicClick }) {
  return (
    <>
      <div className="hero-center">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.tagline} styleId="solid-white" />
        </h1>
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />
      </div>

      <div className="hero-sections">
        {homeTopics.map(({ id, label, body }) => (
          <button key={id} className="hero-section" onClick={() => onTopicClick(id)}>
            <h2>{label}</h2>
            <p>{body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </>
  );
}
