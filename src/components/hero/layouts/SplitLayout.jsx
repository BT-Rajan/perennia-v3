import { HeroButtons, HeroChatComposer, HeroExamplePrompts, HeroHeadline, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "split" — two-column: headline, tagline, and the quick-chat box
 * left-aligned on one side, page-navigation cards stacked as a list
 * on the other. Stacks to a single column (main content first, then
 * nav) below the tablet breakpoint — see .hero-split-* in Hero.css.
 */
export default function SplitLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, copy, homeTopics, onTopicClick }) {
  return (
    <div className="hero-split-wrap">
      <div className="hero-split-main">
        <HeroHeadline
          statement={home.heroStatement}
          taglineLine1={home.taglineLine1}
          taglineLine2={home.taglineLine2}
          className="hero-welcome-left"
        />
        <HeroSupportingText text={home.supportingText} className="hero-supporting-left" />
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />
        <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} className="hero-example-prompts-left" />
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
