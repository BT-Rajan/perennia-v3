import { HeroButtons, HeroCapabilities, HeroChatComposer, HeroCtas, HeroEyebrow, HeroExamplePrompts, HeroHeadline, HeroPrinciples, HeroSituations, HeroSupportingText } from "../HeroShared.jsx";

/**
 * "split" — two-column: headline, tagline, and the quick-chat box
 * left-aligned on one side, page-navigation cards stacked as a list
 * on the other. Stacks to a single column (main content first, then
 * nav) below the tablet breakpoint — see .hero-split-* in Hero.css.
 */
export default function SplitLayout({ home, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, onExamplePick, onCtaPrimary, onCtaSecondary, copy, homeTopics, homeCapabilities, onTopicClick, headlineTypingSpeedCps }) {
  return (
    <>
      <div className="hero-split-wrap">
        <div className="hero-split-main">
          <HeroEyebrow text={home.eyebrow} className="hero-eyebrow-left" />
          <HeroHeadline
            statement={home.heroStatement}
            taglineLine1={home.taglineLine1}
            taglineLine2={home.taglineLine2}
            className="hero-welcome-left"
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
          />
          <HeroExamplePrompts prompts={home.examplePrompts} onPick={onExamplePick} className="hero-example-prompts-left" />
        </div>

        {/* No section CTA here — this column sits right beside the hero's
            own CTAs, so a second booking button would just repeat them. */}
        <HeroSituations
          heading={home.situationsHeading}
          intro={home.situationsIntro}
          topics={homeTopics}
          onTopicClick={onTopicClick}
          className="hero-situations-aside hero-block-start"
          listClassName="hero-split-nav"
          cardClassName="hero-section-row"
        />
      </div>

      <HeroCapabilities
        heading={home.capabilitiesHeading}
        intro={home.capabilitiesIntro}
        items={homeCapabilities}
        roles={home.capabilitiesRoles}
        scopeNote={home.capabilitiesScopeNote}
        ctas={<HeroCtas primaryLabel={home.ctaPrimary} secondaryLabel={home.ctaSecondary} onPrimary={onCtaPrimary} onSecondary={onCtaSecondary} className="hero-ctas-left" />}
        className="hero-block-start"
      />
    </>
  );
}
