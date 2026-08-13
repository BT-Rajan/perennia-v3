import { useState } from "react";
import { LangProvider, useLang } from "./context/LangContext.jsx";
import Hero from "./components/hero/Hero.jsx";
import ChatPage from "./components/chat/ChatPage.jsx";
import ContentPage from "./components/pages/ContentPage.jsx";
import ContactPage from "./components/pages/ContactPage.jsx";
import StickyChat from "./components/StickyChat.jsx";
import BookingPanel from "./components/booking/BookingPanel.jsx";
import Toast from "./components/ui/Toast.jsx";

// Pages with dedicated components — every other page id routes through
// the generic, Markdown-driven ContentPage, so an admin can add a new
// page (any slug) with zero code changes on this end.
const SPECIAL_PAGE_IDS = new Set(["home", "chat", "contact"]);

// Needs useLang() (for features.bookingEnabled), which only works
// inside LangProvider — see the default export below.
function AppShell() {
  const { features } = useLang();
  const [page, setPage] = useState("home"); // "home" | "chat" | "contact" | any configured page slug
  // Message typed into the hero's quick-start chat box, carried across
  // into ChatPage so hitting Enter there feels like continuing the same
  // conversation rather than starting over.
  const [pendingMessage, setPendingMessage] = useState("");
  // The Appointments sticky button opens booking from any page, not
  // just from inside a chat conversation — this is that panel's state.
  const [bookingOpen, setBookingOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

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

  function handleBookingResult(text) {
    setBookingOpen(false);
    // No chat conversation to drop this confirmation/cancellation text
    // into here (unlike the same BookingPanel opened from inside
    // ChatPage) — a toast is the equivalent surface for that outcome.
    setToastMessage(text);
  }

  return (
    <>
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

      {/* Sticky action buttons — visible on all pages */}
      <StickyChat
        onChatClick={handleStickyChat}
        onBookingClick={() => setBookingOpen(true)}
        showBooking={features.bookingEnabled}
      />

      {bookingOpen && features.bookingEnabled && (
        <BookingPanel onClose={() => setBookingOpen(false)} onResult={handleBookingResult} />
      )}

      {toastMessage && <Toast message={toastMessage} onDismiss={() => setToastMessage("")} />}
    </>
  );
}

export default function App() {
  return (
    <LangProvider>
      <AppShell />
    </LangProvider>
  );
}
