import { FitOneLine, HeroChatComposer, resolveHeroButtons } from "../HeroShared.jsx";

/**
 * "centered-card" — headline, tagline, quick-chat, and topic pills all
 * live inside one bordered glass card instead of being spread across
 * the page.
 *
 * The pill row below the quick-chat box comes from the admin's Hero
 * buttons config (Settings > On-screen text > Home hero buttons) —
 * deliberately NOT the top nav/page menu — falling back to the 4
 * homepage topic buttons only if no hero buttons are configured, so
 * the card never ends up with an empty pill row on a fresh install.
 */
export default function CenteredCardLayout({ copy, heroButtons, lang, quickDraft, setQuickDraft, onQuickSend, homeTopics, onTopicClick }) {
  const resolvedHeroButtons = resolveHeroButtons(heroButtons, lang);
  const usingHeroButtons = resolvedHeroButtons.length > 0;

  return (
    <div className="hero-card-wrap">
      <div className="hero-card">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.tagline} styleId="solid-white" />
        </h1>

        <HeroChatComposer
          value={quickDraft}
          onChange={setQuickDraft}
          onSend={onQuickSend}
          placeholder={copy.chat.inputPlaceholder}
          sendLabel={copy.common.send}
        />

        {usingHeroButtons ? (
          <div className="hero-card-pills">
            {resolvedHeroButtons.map(({ key, label, url, external }) => (
              <a
                key={key}
                className="hero-card-pill"
                href={url}
                {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              >
                {label}
              </a>
            ))}
          </div>
        ) : homeTopics.length > 0 && (
          <div className="hero-card-pills">
            {homeTopics.map(({ id, label }) => (
              <button key={id} className="hero-card-pill" onClick={() => onTopicClick(id)}>
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
