import { useEffect, useRef, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { api } from "../../api/client.js";
import GlassPanel from "../ui/GlassPanel.jsx";
import ChatMessage from "./ChatMessage.jsx";
import TypingIndicator from "./TypingIndicator.jsx";
import ChatInput from "./ChatInput.jsx";
import "./ChatWidget.css";

/**
 * Floating chat popover, docked bottom-right and layered above
 * StickyChat's toggle pill. Mirrors k-g-i.com's "Talk to Sulaiman"
 * widget: named persona + online status in the header, a starter
 * screen of tappable quick questions plus a standalone "Book a call"
 * row before the first message, and a small "Powered by" credit line
 * in the footer — instead of the old full-page chat route.
 */
export default function ChatWidget({ open, onClose, initialMessage, onConsumeInitialMessage, onBookingClick }) {
  const { copy, lang, nav, branding, features } = useLang();
  const t = copy.chat;

  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef(null);
  const initialMessageSentRef = useRef(false);
  const leadCapturedRef = useRef(false);

  useEffect(() => {
    const welcome = { from: "ai", text: t.welcomeMsg };
    setMessages([welcome]);
    leadCapturedRef.current = false;

    if (initialMessage && !initialMessageSentRef.current) {
      initialMessageSentRef.current = true;
      sendMessage(initialMessage, [welcome]);
      onConsumeInitialMessage?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  useEffect(() => {
    if (open) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing, open]);

  async function sendMessage(text, historyOverride) {
    const outgoing = text.trim();
    if (!outgoing) return;
    setMessages((m) => [...m, { from: "user", text: outgoing }]);
    setDraft("");
    setTyping(true);
    const history = historyOverride ?? messages.map(({ from, text }) => ({ from, text }));
    const { reply, leadCaptured } = await api.chat(outgoing, lang, history, leadCapturedRef.current);
    leadCapturedRef.current = leadCaptured;
    setTyping(false);
    setMessages((m) => [...m, { from: "ai", text: reply }]);
  }

  // Starter screen (quick questions + book-a-call) only shows before
  // the visitor has sent anything — same moment KGI shows theirs.
  const showStarter = messages.length <= 1 && !typing;
  const starterQuestions = nav.slice(0, 3);

  if (!open) return null;

  return (
    <GlassPanel className="chat-widget" as="section" role="dialog" aria-modal="true" aria-label={t.header}>
      <div className="chat-widget-header">
        <div className="chat-widget-persona">
          <span className="chat-widget-avatar" aria-hidden="true">{branding.siteName?.[0] ?? "A"}</span>
          <div className="chat-widget-persona-text">
            <p className="chat-widget-name">{t.header}</p>
            <p className="chat-widget-status"><span className="status-dot" />{t.onlineStatus}</p>
          </div>
        </div>
        <button className="chat-widget-close" onClick={onClose} aria-label={copy.common.close}>✕</button>
      </div>

      <div className="chat-widget-conversation" ref={scrollRef}>
        <div className="chat-messages">
          {messages.map((m, i) => (
            <ChatMessage key={i} from={m.from} text={m.text} />
          ))}
          {typing && <TypingIndicator label={copy.common.assistantTyping} />}
        </div>

        {showStarter && (
          <div className="chat-widget-starter">
            {starterQuestions.map((item) => (
              <button key={item.id} className="chat-widget-chip" onClick={() => sendMessage(item.label)}>
                {item.label}
              </button>
            ))}
            {features.bookingEnabled && (
              <button className="chat-widget-book-row" onClick={onBookingClick}>
                {t.bookBtn} <span aria-hidden="true">➤</span>
              </button>
            )}
          </div>
        )}
      </div>

      <ChatInput
        value={draft}
        onChange={setDraft}
        onSend={() => sendMessage(draft)}
        placeholder={t.inputPlaceholder}
        sendLabel={copy.common.send}
        disabled={typing}
      />

      <footer className="chat-widget-footer">{t.poweredBy} {branding.siteName}</footer>
    </GlassPanel>
  );
}
