import { useLang } from "../../context/LangContext.jsx";
import "./FaqTray.css";

/**
 * Short floating menu tray docked inside the chat window, always
 * visible — desktop-only by design (see FaqTray.css; it renders
 * nothing below 1024px). Mirrors the site's About/Products/Services/
 * Contact Us menu as one-tap shortcuts right inside the conversation.
 */
export default function FaqTray({ onPick }) {
  const { nav, copy } = useLang();

  return (
    <div className="faq-tray" role="navigation" aria-label={copy.common.quickMenu}>
      <div className="faq-tray-list">
        {nav.map((item) => (
          <button key={item.id} className="faq-tray-item" onClick={() => onPick(item)}>
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
