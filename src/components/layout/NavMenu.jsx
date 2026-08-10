import { useLang } from "../../context/LangContext.jsx";
import "./NavMenu.css";

/**
 * Persistent header nav, styled after the reference site's layout:
 * logo — nav menu — actions. `onNavigate(id)` is called with the
 * section id ("home" | "about" | "products" | "services" | "contact")
 * when a link is clicked; the caller decides what that means on its
 * page. A Home icon always leads the menu, ahead of the
 * admin-configured page links, so there's a way back to Home from the
 * nav itself (independent of the logo, which also does this).
 */
export default function NavMenu({ onNavigate }) {
  const { nav, copy } = useLang();

  return (
    <nav className="nav-menu" aria-label={copy.common.primaryNav}>
      <button
        key="home"
        className="nav-menu-link nav-menu-home"
        onClick={() => onNavigate?.("home")}
        title={copy.common.goHome}
        aria-label={copy.common.goHome}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 11.5 12 4l9 7.5" />
          <path d="M5.5 10v9a1 1 0 0 0 1 1H9a1 1 0 0 0 1-1v-4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v4a1 1 0 0 0 1 1h2.5a1 1 0 0 0 1-1v-9" />
        </svg>
      </button>
      {nav.map((item) => (
        <button key={item.id} className="nav-menu-link" onClick={() => onNavigate?.(item.id)}>
          {item.label}
        </button>
      ))}
    </nav>
  );
}
