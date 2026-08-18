import { HeroButtons, HeroChatComposer, HeroExamplePrompts, HeroHeadline, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "classic" — the site's original, and default, homepage body:
 * centered headline/tagline/quick-chat stacked above a grid of nav
 * cards. This is exactly the markup that existed before the layout
 * template setting did, so picking "classic" (or leaving the setting
 * unset) can never look different from what's already live.
 */
export default function ClassicLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, copy, homeTopics, onTopicClick, headlineTypingSpeedCps }) {
  return (
    <>
      <div className="hero-center">
        <HeroHeadline statement={home.heroStatement} taglineLine1={home.taglineLine1} taglineLine2={home.taglineLine2} typingSpeedCps={headlineTypingSpeedCps} />
        <HeroSupportingText text={home.supportingText} />
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />
        <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} />
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
