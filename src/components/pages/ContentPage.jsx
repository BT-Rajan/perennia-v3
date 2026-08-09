import { useEffect } from "react";
import { useLang } from "../../context/LangContext.jsx";
import TopBar from "../layout/TopBar.jsx";
import GlassPanel from "../ui/GlassPanel.jsx";
import BackButton from "../ui/BackButton.jsx";
import Markdown from "../ui/Markdown.jsx";
import "./ContentPage.css";

/**
 * Standalone page for any page an admin has configured (About /
 * Products / Services / anything added later) — same header, tagline,
 * glass-panel shell, and footer treatment as the chat page, so every
 * page in the app feels like one family. `pageId` selects which
 * content record (fetched from the backend, see src/data/siteContent.js)
 * renders inside the shell.
 */
export default function ContentPage({ pageId, onBack, onNavigate }) {
  const { copy, pages, branding } = useLang();
  const meta = pages[pageId];

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pageId]);

  if (!meta) return null; // an admin-removed or not-yet-loaded page id; nothing to render

  return (
    <div className="content-page">
      <TopBar onNavigate={onNavigate} onLogoClick={onBack} leading={<BackButton onClick={onBack} title={copy.common.back} />} />

      <main className="content-main">
        <div className="content-tagline">
          <div className="content-tagline-main">
            <span>{meta.line1}</span>
            <span className="gold">{meta.line2}</span>
          </div>
          <div className="content-tagline-divider" />
          <div className="content-tagline-sub">{meta.sub}</div>
        </div>

        <GlassPanel className="content-shell" as="section">
          <Markdown source={meta.body} />
        </GlassPanel>
      </main>

      <footer className="content-footer">© {new Date().getFullYear()} {branding.siteName}. All rights reserved.</footer>
    </div>
  );
}
