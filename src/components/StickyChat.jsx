import { useState } from "react";
import styles from "./StickyChat.module.css";

function StickyButton({ label, icon, onClick, variant }) {
  const [isHovered, setIsHovered] = useState(false);
  return (
    <button
      className={`${styles.chatButton} ${variant ? styles[variant] : ""} ${isHovered ? styles.hovered : ""}`}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      aria-label={label}
      title={label}
    >
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={styles.icon}
      >
        {icon}
      </svg>
      <span className={styles.label}>{label}</span>
    </button>
  );
}

/**
 * Sticky action buttons that float at bottom-right, stacked vertically
 * and stay visible across all pages: Appointments above AI Assistant.
 * @param {function} onChatClick - Callback when the AI Assistant button is clicked
 * @param {function} onBookingClick - Callback when the Appointments button is clicked
 * @param {boolean} showBooking - Whether the Appointments button renders at all
 */
export default function StickyChat({ onChatClick, onBookingClick, showBooking = true }) {
  return (
    <div className={styles.stickyContainer}>
      {showBooking && (
        <StickyButton
          label="Appointments"
          variant="booking"
          onClick={() => onBookingClick?.()}
          icon={
            <>
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </>
          }
        />
      )}
      <div className={styles.chatButtonWrap}>
        <StickyButton
          label="AI Assistant"
          onClick={() => onChatClick?.()}
          icon={<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />}
        />
        {/* Pulse animation (visible when not interacting) — kept on the
            primary AI Assistant button only, same as before this had a
            second button added alongside it. */}
        <div className={styles.pulse} />
      </div>
    </div>
  );
}
