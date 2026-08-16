import { useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { HOME_TOPICS } from "../../data/content.js";
import TopBar from "../layout/TopBar.jsx";
import ClassicLayout from "./layouts/ClassicLayout.jsx";
import SplitLayout from "./layouts/SplitLayout.jsx";
import CenteredCardLayout from "./layouts/CenteredCardLayout.jsx";
import EditorialLayout from "./layouts/EditorialLayout.jsx";
import "./Hero.css";

// Keyed by theme.layout_template (see backend/app/settings_registry.py).
// "classic" is both the map's fallback and the default admin value, so
// an unset or unrecognized template can never fail to render — it
// just renders the site's original layout. Every layout receives the
// exact same props/data and calls the exact same onNavigate/onEnter
// handlers — only the arrangement of headline, tagline, quick-chat
// box, and nav cards differs between them. None of them touch chat,
// booking, or voice functionality, which all live in ChatWidget.
const LAYOUTS = {
  classic: ClassicLayout,
  split: SplitLayout,
  "centered-card": CenteredCardLayout,
  editorial: EditorialLayout,
};

/**
 * Landing page. Entry into the chat assistant is either straight from
 * the quick-start chat box (which hands the typed message off to the
 * sticky AI Assistant widget — see onEnter/App.jsx) or via the
 * always-visible sticky button itself. Which arrangement the headline/
 * tagline/quick-chat/nav-cards render in is chosen by the admin (see
 * Settings > Theme > Homepage layout) — see LAYOUTS above.
 */
export default function Hero({ onEnter, onNavigate }) {
  const { copy, sections, nav, branding, heroButtons, lang, theme } = useLang();
  const [quickDraft, setQuickDraft] = useState("");

  function handleQuickSend() {
    const text = quickDraft.trim();
    if (!text) return;
    setQuickDraft("");
    onEnter(text);
  }

  // The 4 homepage topic buttons (Software Development / Artificial
  // Intelligence / Digital Transformation / Consulting) aren't page
  // links — clicking one hands its preset question straight to the
  // AI Assistant, the same handoff the quick-chat box uses above.
  const homeTopics = HOME_TOPICS[lang] || HOME_TOPICS.en;
  function handleTopicClick(topicId) {
    const topic = homeTopics.find((t) => t.id === topicId);
    if (topic) onEnter(topic.question);
  }

  const Layout = LAYOUTS[theme?.layoutTemplate] || ClassicLayout;

  return (
    <div className="hero-page">
      <TopBar onNavigate={onNavigate} />

      <Layout
        copy={copy}
        sections={sections}
        nav={nav}
        heroButtons={heroButtons}
        lang={lang}
        onNavigate={onNavigate}
        quickDraft={quickDraft}
        setQuickDraft={setQuickDraft}
        onQuickSend={handleQuickSend}
        headlineStyle={theme?.headlineStyle}
        branding={branding}
        homeTopics={homeTopics}
        onTopicClick={handleTopicClick}
      />

      <footer className="hero-footer">© {new Date().getFullYear()} {branding.siteName}</footer>
    </div>
  );
}
