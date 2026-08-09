import { useEffect, useRef, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { api } from "../../api/client.js";
import TopBar from "../layout/TopBar.jsx";
import GlassPanel from "../ui/GlassPanel.jsx";
import BackButton from "../ui/BackButton.jsx";
import Chip from "../ui/Chip.jsx";
import ChatMessage from "./ChatMessage.jsx";
import TypingIndicator from "./TypingIndicator.jsx";
import ChatInput from "./ChatInput.jsx";
import FaqTray from "./FaqTray.jsx";
import BookingPanel from "../booking/BookingPanel.jsx";
import "./ChatPage.css";

export default function ChatPage({ onBack, onNavigate }) {
  const { copy, lang } = useLang();
  const t = copy.chat;

  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const scrollRef = useRef(null);

  // Reset the transcript with a fresh welcome message whenever language changes,
  // mirroring the original app's bilingual restart behavior.
  useEffect(() => {
    setMessages([{ from: "ai", text: t.welcomeMsg }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  async function sendMessage(text) {
    const outgoing = text.trim();
    if (!outgoing) return;
    setMessages((m) => [...m, { from: "user", text: outgoing }]);
    setDraft("");
    setTyping(true);
    const history = messages.map(({ from, text }) => ({ from, text }));
    const reply = await api.chat(outgoing, lang, history);
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
        leading={<BackButton onClick={onBack} />}
      >
        <Chip icon="💬" onClick={() => setBookingOpen(true)}>{t.bookBtn}</Chip>
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
                  {typing && <TypingIndicator />}
                </div>
              </div>

              <ChatInput
                value={draft}
                onChange={setDraft}
                onSend={() => sendMessage(draft)}
                placeholder={t.inputPlaceholder}
                disabled={typing}
              />

              {bookingOpen && (
                <BookingPanel onClose={() => setBookingOpen(false)} onResult={handleBookingResult} />
              )}
            </div>
          </GlassPanel>

          <FaqTray onPick={handleFaqPick} />
        </div>
      </main>
      
      <footer className="chat-footer">© 2026 Perennia. All rights reserved.</footer>
    </div>
  );
}
