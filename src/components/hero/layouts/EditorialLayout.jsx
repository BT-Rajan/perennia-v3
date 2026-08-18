import { HeroButtons, HeroChatComposer, HeroExamplePrompts, HeroHeadline, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "editorial" — a bigger, left-aligned headline and a narrower
 * quick-chat box beneath it, with page-navigation rendered as a
 * horizontal-scrolling strip of compact cards instead of a grid —
 * a more magazine/editorial feel than the centered classic layout.
 */
export default function EditorialLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, copy, homeTopics, onTopicClick, headlineTypingSpeedCps }) {
  return (
    <>
      <div className="hero-editorial-main">
        <HeroHeadline
          statement={home.heroStatement}
          taglineLine1={home.taglineLine1}
          taglineLine2={home.taglineLine2}
          className="hero-welcome-left hero-welcome-editorial"
          typingSpeedCps={headlineTypingSpeedCps}
        />
        <HeroSupportingText text={home.supportingText} className="hero-supporting-left" />
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
          className="hero-quick-chat-narrow"
        />
        <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} className="hero-example-prompts-left" />
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
