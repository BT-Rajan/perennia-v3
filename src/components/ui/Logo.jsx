import { useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import { BRAND } from "../../data/content.js";
import "./Logo.css";

// Path (or absolute URL) the logo image is served from, set via the
// VITE_LOGO_URL env var (see .env / .env.example) so the actual file
// can be swapped, or repointed at a backend/CDN URL, without touching
// this component. Falls back to the dashed "LOGO" placeholder badge
// if the var is unset or the image fails to load.
const LOGO_URL = import.meta.env.VITE_LOGO_URL;

export default function Logo() {
  const { lang } = useLang();
  const label = lang === "ar" ? BRAND.wordmarkAr : BRAND.name;
  const [imgFailed, setImgFailed] = useState(false);

  return (
    <div className="logo">
      {LOGO_URL && !imgFailed ? (
        <img
          className="logo-img"
          src={LOGO_URL}
          alt={`${BRAND.name} logo`}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <span className="logo-mark" aria-hidden="true">LOGO</span>
      )}
      <span className="logo-word">{label}</span>
    </div>
  );
}
