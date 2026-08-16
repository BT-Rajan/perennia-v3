import { FitOneLine, HeroButtons, HeroChatComposer } from "../HeroShared.jsx";

/**
 * "split" — two-column: headline, tagline, and the quick-chat box
 * left-aligned on one side, page-navigation cards stacked as a list
 * on the other. Stacks to a single column (main content first, then
 * nav) below the tablet breakpoint — see .hero-split-* in Hero.css.
 */
export default function SplitLayout({ copy, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, homeTopics, onTopicClick }) {
  return (
    <div className="hero-split-wrap">
      <div className="hero-split-main">
        <h1 className="hero-welcome hero-welcome-left">
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

      <div className="hero-split-nav">
        {homeTopics.map(({ id, label, body }) => (
          <button key={id} className="hero-section hero-section-row" onClick={() => onTopicClick(id)}>
            <h2>{label}</h2>
            <p>{body}</p>
            <span className="hero-section-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}
