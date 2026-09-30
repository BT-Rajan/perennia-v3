import { HeroButtons, HeroChatComposer, HeroCtas, HeroEyebrow, HeroExamplePrompts, HeroHeadline, HeroPrinciples, HeroSituations, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "classic" — the site's original, and default, homepage body:
 * centered headline/tagline/quick-chat stacked above a grid of nav
 * cards. This is exactly the markup that existed before the layout
 * template setting did, so picking "classic" (or leaving the setting
 * unset) can never look different from what's already live.
 */
export default function ClassicLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, onCtaPrimary, onCtaSecondary, copy, homeTopics, onTopicClick, headlineTypingSpeedCps }) {
  return (
    <>
      <div className="hero-center">
        <HeroEyebrow text={home.eyebrow} />
        <HeroHeadline statement={home.heroStatement} taglineLine1={home.taglineLine1} taglineLine2={home.taglineLine2} typingSpeedCps={headlineTypingSpeedCps} />
        <HeroSupportingText text={home.supportingText} />
        <HeroCtas primaryLabel={home.ctaPrimary} secondaryLabel={home.ctaSecondary} onPrimary={onCtaPrimary} onSecondary={onCtaSecondary} />
        <HeroPrinciples items={home.principles} />
        {heroButtons?.length > 0 && <HeroButtons buttons={heroButtons} lang={lang} />}

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
          label={home.assistantLabel}
        />
        <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} />
      </div>

      <HeroSituations
        heading={home.situationsHeading}
        intro={home.situationsIntro}
        topics={homeTopics}
        onTopicClick={onTopicClick}
        ctaNote={home.situationsCtaNote}
        ctaLabel={home.ctaPrimary}
        onCta={onCtaPrimary}
        listClassName="hero-sections"
      />
    </>
  );
}
