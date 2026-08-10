import { useState } from "react";
import { LangProvider } from "./context/LangContext.jsx";
import Hero from "./components/hero/Hero.jsx";
import ChatPage from "./components/chat/ChatPage.jsx";
import ContentPage from "./components/pages/ContentPage.jsx";
import ContactPage from "./components/pages/ContactPage.jsx";
import StickyChat from "./components/StickyChat.jsx";

// Pages with dedicated components — every other page id routes through
// the generic, Markdown-driven ContentPage, so an admin can add a new
// page (any slug) with zero code changes on this end.
const SPECIAL_PAGE_IDS = new Set(["home", "chat", "contact"]);

export default function App() {
  const [page, setPage] = useState("home"); // "home" | "chat" | "contact" | any configured page slug
  // Message typed into the hero's quick-start chat box, carried across
  // into ChatPage so hitting Enter there feels like continuing the same
  // conversation rather than starting over.
  const [pendingMessage, setPendingMessage] = useState("");

  const handleStickyChat = () => {
    setPage("chat");
    // Scroll to top smoothly if not already on chat page
    if (page !== "chat") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleHeroEnter = (initialMessage) => {
    if (initialMessage) setPendingMessage(initialMessage);
    setPage("chat");
  };

  return (
    <LangProvider>
      {page === "home" && <Hero onEnter={handleHeroEnter} onNavigate={setPage} />}
      {page === "chat" && (
        <ChatPage
          onBack={() => setPage("home")}
          onNavigate={setPage}
          initialMessage={pendingMessage}
          onConsumeInitialMessage={() => setPendingMessage("")}
        />
      )}
      {page === "contact" && <ContactPage onBack={() => setPage("home")} onNavigate={setPage} />}
      {!SPECIAL_PAGE_IDS.has(page) && (
        <ContentPage pageId={page} onBack={() => setPage("home")} onNavigate={setPage} />
      )}

      {/* Sticky chat button — visible on all pages */}
      <StickyChat onChatClick={handleStickyChat} />
    </LangProvider>
  );
}
