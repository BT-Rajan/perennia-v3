import { useState } from "react";
import { useLang } from "../context/LangContext.jsx";
import styles from "./StickyChat.module.css";

/**
 * Sticky chat button that floats at bottom-right.
 * Positioned absolutely at viewport corner, stays visible across all pages.
 * @param {function} onChatClick - Callback when button is clicked
 */
export default function StickyChat({ onChatClick }) {
  const { copy } = useLang();
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = () => {
    onChatClick?.();
  };

  return (
    <div className={styles.stickyContainer}>
      <button
        className={`${styles.chatButton} ${isHovered ? styles.hovered : ""}`}
        onClick={handleClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        aria-label={copy?.common?.chat_button_label || "Open chat"}
        title={copy?.common?.chat_button_label || "Chat with us"}
      >
        {/* Chat icon SVG */}
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
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>

        {/* Label on hover */}
        <span className={styles.label}>
          {copy?.common?.chat_button_text || "Chat"}
        </span>
      </button>

      {/* Pulse animation (visible when not interacting) */}
      <div className={styles.pulse} />
    </div>
  );
}
