import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "editorial" — a bigger, left-aligned headline and a narrower
 * quick-chat box beneath it, with page-navigation rendered as a
 * horizontal-scrolling strip of compact cards instead of a grid —
 * a more magazine/editorial feel than the centered classic layout.
 */
export default function EditorialLayout({ copy, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, homeTopics, onTopicClick }) {
  return (
    <>
      <div className="hero-editorial-main">
        <h1 className="hero-welcome hero-welcome-left hero-welcome-editorial">
          <FitOneLine text={copy.home.tagline} styleId="solid-white" />
        </h1>
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
          className="hero-quick-chat-narrow"
        />
      </div>

      <div className="hero-editorial-strip">
        {homeTopics.map(({ id, label, body }) => (
          <button key={id} className="hero-section hero-section-compact" onClick={() => onTopicClick(id)}>
            <h2>{label}</h2>
            <p>{body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </>
  );
}
