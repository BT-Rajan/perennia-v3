import { useEffect, useRef, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { api } from "../../api/client.js";
import TopBar from "../layout/TopBar.jsx";
import GlassPanel from "../ui/GlassPanel.jsx";
import Chip from "../ui/Chip.jsx";
import ChatMessage from "./ChatMessage.jsx";
import TypingIndicator from "./TypingIndicator.jsx";
import ChatInput from "./ChatInput.jsx";
import FaqTray from "./FaqTray.jsx";
import BookingPanel from "../booking/BookingPanel.jsx";
import "./ChatPage.css";

export default function ChatPage({ onBack, onNavigate, initialMessage, onConsumeInitialMessage }) {
  const { copy, lang, features, branding } = useLang();
  const t = copy.chat;

  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const scrollRef = useRef(null);
  const initialMessageSentRef = useRef(false);
  // Tracks whether the assistant has already gathered this visitor's
  // name/phone/email this session, so chat_service skips re-running
  // the lead-capture instructions once it's done. Reset alongside the
  // transcript on a language switch, same as a fresh session.
  const leadCapturedRef = useRef(false);

  // Reset the transcript with a fresh welcome message whenever language
  // changes, mirroring the original app's bilingual restart behavior. If the
  // person arrived here by typing into the hero's quick-start box and hitting
  // Enter, that message rides along as `initialMessage` — send it right after
  // the welcome message so the conversation continues rather than restarting.
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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  // `historyOverride` lets callers (like the initial-message effect above)
  // supply the conversation history explicitly, since it may not yet be
  // reflected in `messages` state at the point they fire.
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

  function handleFaqPick(item) {
    sendMessage(item.label);
  }

  function handleBookingResult(text) {
    setBookingOpen(false);
    setMessages((m) => [...m, { from: "ai", text }]);
  }

  return (
    <div className="chat-page">
      <TopBar
        onNavigate={onNavigate}
        onLogoClick={onBack}
      >
        {features.bookingEnabled && (
          <Chip icon="💬" onClick={() => setBookingOpen(true)}>{t.bookBtn}</Chip>
        )}
      </TopBar>

      <main className="chat-main">
        <div className="chat-tagline">
          <div className="chat-tagline-main">
            <span>{t.taglineLine1}</span>
            <span className="gold">{t.taglineLine2}</span>
          </div>
          <div className="chat-tagline-divider" />
          <div className="chat-tagline-sub">{t.sub}</div>
        </div>

        <div className="chat-content">
          <GlassPanel className="chat-shell" as="section">
            <div className="chat-header">
              <span className="status-dot" />
              <p className="chat-header-text">{t.header}</p>
            </div>

            <div className="chat-conversation-wrap">
              <div className="chat-conversation" ref={scrollRef}>
                <div className="chat-messages">
                  {messages.map((m, i) => (
                    <ChatMessage key={i} from={m.from} text={m.text} />
                  ))}
                  {typing && <TypingIndicator label={copy.common.assistantTyping} />}
                </div>
              </div>

              <ChatInput
                value={draft}
                onChange={setDraft}
                onSend={() => sendMessage(draft)}
                placeholder={t.inputPlaceholder}
                sendLabel={copy.common.send}
                disabled={typing}
              />

              {bookingOpen && features.bookingEnabled && (
                <BookingPanel onClose={() => setBookingOpen(false)} onResult={handleBookingResult} />
              )}
            </div>
          </GlassPanel>

          <FaqTray onPick={handleFaqPick} />
        </div>
      </main>
      
      <footer className="chat-footer">© {new Date().getFullYear()} {branding.siteName}. All rights reserved.</footer>
    </div>
  );
}
