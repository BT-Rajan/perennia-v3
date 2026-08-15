import { useState } from "react";
import { LangProvider, useLang } from "./context/LangContext.jsx";
import Hero from "./components/hero/Hero.jsx";
import ChatPage from "./components/chat/ChatPage.jsx";
import ChatWidget from "./components/chat/ChatWidget.jsx";
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
  // The sticky button still opens chat as a floating popover (see
  // ChatWidget), mirroring k-g-i.com's "Talk to Sulaiman" widget, from
  // any page. The hero's own central quick-start box is the site's
  // main/central chat entry point and routes to the full ChatPage
  // instead — that's the flow the k-g-i.com rework had dropped.
  const [chatOpen, setChatOpen] = useState(false);
  // Message typed into the hero's quick-start chat box, carried across
  // into ChatPage so hitting Enter there feels like continuing the
  // same conversation rather than starting over.
  const [pendingMessage, setPendingMessage] = useState("");
  // The Appointments sticky button opens booking from any page, not
  // just from inside a chat conversation — this is that panel's state.
  const [bookingOpen, setBookingOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const handleStickyChat = () => setChatOpen((o) => !o);

  const handleHeroEnter = (initialMessage) => {
    if (initialMessage) setPendingMessage(initialMessage);
    setPage("chat");
  };

  function handleBookingResult(text) {
    setBookingOpen(false);
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
        chatOpen={chatOpen}
      />

      <ChatWidget
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        onBookingClick={() => setBookingOpen(true)}
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
