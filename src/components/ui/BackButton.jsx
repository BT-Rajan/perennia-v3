import IconButton from "./IconButton.jsx";

/**
 * The back-arrow icon button shown at the leading edge of every page
 * that isn't Home (chat, about, products, services, contact). Pulled
 * out once so the icon/markup only lives in one place.
 */
export default function BackButton({ onClick, title = "Back" }) {
  return (
    <IconButton title={title} onClick={onClick} size="md" className="back-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
      </svg>
    </IconButton>
  );
}
