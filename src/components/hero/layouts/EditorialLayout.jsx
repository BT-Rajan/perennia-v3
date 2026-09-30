import { HeroButtons, HeroChatComposer, HeroCtas, HeroEyebrow, HeroExamplePrompts, HeroHeadline, HeroPrinciples, HeroSituations, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "editorial" — a bigger, left-aligned headline and a narrower
 * quick-chat box beneath it, with page-navigation rendered as a
 * horizontal-scrolling strip of compact cards instead of a grid —
 * a more magazine/editorial feel than the centered classic layout.
 */
export default function EditorialLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, onCtaPrimary, onCtaSecondary, copy, homeTopics, onTopicClick, headlineTypingSpeedCps }) {
  return (
    <>
      <div className="hero-editorial-main">
        <HeroEyebrow text={home.eyebrow} className="hero-eyebrow-left" />
        <HeroHeadline
          statement={home.heroStatement}
          taglineLine1={home.taglineLine1}
          taglineLine2={home.taglineLine2}
          className="hero-welcome-left hero-welcome-editorial"
          typingSpeedCps={headlineTypingSpeedCps}
        />
        <HeroSupportingText text={home.supportingText} className="hero-supporting-left" />
        <HeroCtas primaryLabel={home.ctaPrimary} secondaryLabel={home.ctaSecondary} onPrimary={onCtaPrimary} onSecondary={onCtaSecondary} className="hero-ctas-left" />
        <HeroPrinciples items={home.principles} className="hero-principles-left" />
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
          label={home.assistantLabel}
          className="hero-quick-chat-narrow"
        />
        <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} className="hero-example-prompts-left" />
      </div>

      <HeroSituations
        heading={home.situationsHeading}
        intro={home.situationsIntro}
        topics={homeTopics}
        onTopicClick={onTopicClick}
        ctaNote={home.situationsCtaNote}
        ctaLabel={home.ctaPrimary}
        onCta={onCtaPrimary}
        className="hero-situations-start"
        listClassName="hero-editorial-strip"
        cardClassName="hero-section-compact"
      />
    </>
  );
}
