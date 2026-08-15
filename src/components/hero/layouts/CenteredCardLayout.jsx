import { FitOneLine, HeroButtons } from "../HeroShared.jsx";
import ChatInput from "../../chat/ChatInput.jsx";

/**
 * "centered-card" — headline, tagline, quick-chat, and page nav all
 * live inside one bordered glass card instead of being spread across
 * the page. Nav renders as a row of small pill shortcuts (not full
 * description cards — there isn't room for both inside the card),
 * so this template favors a compact, boutique feel over the
 * classic/split layouts' larger nav cards.
 */
export default function CenteredCardLayout({ copy, sections, nav, heroButtons, lang, onNavigate, quickDraft, setQuickDraft, onQuickSend }) {
  return (
    <div className="hero-card-wrap">
      <div className="hero-card">
        <h1 className="hero-welcome">
          <FitOneLine text={copy.home.welcome} />
        </h1>
        {heroButtons?.length > 0 ? (
          <HeroButtons buttons={heroButtons} lang={lang} />
        ) : (
          <div className="hero-tagline">{copy.home.tagline}</div>
        )}

        <div className="hero-quick-chat">
          <ChatInput
            value={quickDraft}
            onChange={setQuickDraft}
            onSend={onQuickSend}
            placeholder={copy.chat.inputPlaceholder}
            sendLabel={copy.common.send}
          />
        </div>

        {nav.length > 0 && (
          <div className="hero-card-pills">
            {nav.map(({ id }) => (
              <button key={id} className="hero-card-pill" onClick={() => onNavigate(id)}>
                {sections[id]?.title}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
