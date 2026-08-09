import { useEffect, useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import TopBar from "../layout/TopBar.jsx";
import GlassPanel from "../ui/GlassPanel.jsx";
import BackButton from "../ui/BackButton.jsx";
import Button from "../ui/Button.jsx";
import Markdown from "../ui/Markdown.jsx";
import BookingPanel from "../booking/BookingPanel.jsx";
import "./ContentPage.css";
import "./ContactPage.css";

/**
 * The Contact Us page: the same shell as ContentPage, plus a "Talk to
 * Us" call-to-action that opens the existing booking flow in place —
 * no separate route needed for scheduling a call.
 */
export default function ContactPage({ onBack, onNavigate }) {
  const { copy, pages, branding, features } = useLang();
  const meta = pages.contact;

  const [bookingOpen, setBookingOpen] = useState(false);
  const [confirmation, setConfirmation] = useState(null);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  function handleBookingResult(text) {
    setBookingOpen(false);
    setConfirmation(text);
  }

  if (!meta) return null;

  return (
    <div className="content-page">
      <TopBar onNavigate={onNavigate} onLogoClick={onBack} leading={<BackButton onClick={onBack} />} />

      <main className="content-main">
        <div className="content-tagline">
          <div className="content-tagline-main">
            <span>{meta.line1}</span>
            <span className="gold">{meta.line2}</span>
          </div>
          <div className="content-tagline-divider" />
          <div className="content-tagline-sub">{meta.sub}</div>
        </div>

        <GlassPanel className="content-shell contact-shell" as="section">
          <Markdown source={meta.body} />

          {confirmation && <p className="contact-confirmation">{confirmation}</p>}

          {features.bookingEnabled && (
            <>
              <div className="contact-cta-row">
                <Button variant="primary" onClick={() => setBookingOpen(true)}>
                  {copy.chat.bookBtn}
                </Button>
              </div>

              {bookingOpen && (
                <BookingPanel onClose={() => setBookingOpen(false)} onResult={handleBookingResult} />
              )}
            </>
          )}
        </GlassPanel>
      </main>

      <footer className="content-footer">© {new Date().getFullYear()} {branding.siteName}. All rights reserved.</footer>
    </div>
  );
}
