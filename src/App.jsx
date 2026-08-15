import { useState } from "react";
import { LangProvider, useLang } from "./context/LangContext.jsx";
import Hero from "./components/hero/Hero.jsx";
import ChatWidget from "./components/chat/ChatWidget.jsx";
import ContentPage from "./components/pages/ContentPage.jsx";
import ContactPage from "./components/pages/ContactPage.jsx";
import StickyChat from "./components/StickyChat.jsx";
import BookingPanel from "./components/booking/BookingPanel.jsx";
import Toast from "./components/ui/Toast.jsx";

// Pages with dedicated components — every other page id routes through
// the generic, Markdown-driven ContentPage, so an admin can add a new
// page (any slug) with zero code changes on this end.
const SPECIAL_PAGE_IDS = new Set(["home", "contact"]);

// Needs useLang() (for features.bookingEnabled), which only works
// inside LangProvider — see the default export below.
function AppShell() {
  const { features } = useLang();
  const [page, setPage] = useState("home"); // "home" | "contact" | any configured page slug
  // Chat floats as a popover (see ChatWidget) instead of a routed
  // page, mirroring k-g-i.com's "Talk to Sulaiman" widget — it stays
  // mounted over whatever page is behind it rather than replacing it.
  // The homepage has no chat entry point of its own anymore — this
  // sticky-triggered popover (voice + text, see ChatWidget) is the
  // one chat surface on the whole site.
  const [chatOpen, setChatOpen] = useState(false);
  // The Appointments sticky button opens booking from any page, not
  // just from inside a chat conversation — this is that panel's state.
  const [bookingOpen, setBookingOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const handleStickyChat = () => setChatOpen((o) => !o);

  function handleBookingResult(text) {
    setBookingOpen(false);
    setToastMessage(text);
  }

  return (
    <>
      {page === "home" && <Hero onNavigate={setPage} />}
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
