import { useLang } from "../../context/LangContext.jsx";
import "./NavMenu.css";

/**
 * Persistent header nav, styled after the reference site's layout:
 * logo — nav menu — actions. `onNavigate(id)` is called with the
 * section id ("about" | "products" | "services" | "contact") when a
 * link is clicked; the caller decides what that means on its page.
 */
export default function NavMenu({ onNavigate }) {
  const { nav, copy } = useLang();

  return (
    <nav className="nav-menu" aria-label={copy.common.primaryNav}>
      {nav.map((item) => (
        <button key={item.id} className="nav-menu-link" onClick={() => onNavigate?.(item.id)}>
          {item.label}
        </button>
      ))}
    </nav>
  );
}
