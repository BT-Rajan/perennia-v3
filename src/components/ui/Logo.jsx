import { useState } from "react";
import { useLang } from "../../context/LangContext.jsx";
import "./Logo.css";

/**
 * Logo image URL and wordmark text both come from live branding config
 * (branding.logo_url / branding.site_name — see useLang()), so swapping
 * either from the admin panel needs no rebuild. Falls back to the
 * dashed "LOGO" placeholder badge if the image fails to load.
 */
export default function Logo() {
  const { branding } = useLang();
  const [imgFailed, setImgFailed] = useState(false);

  return (
    <div className="logo">
      {branding.logoUrl && !imgFailed ? (
        <img
          className="logo-img"
          src={branding.logoUrl}
          alt={`${branding.siteName} logo`}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <span className="logo-mark" aria-hidden="true">LOGO</span>
      )}
      <span className="logo-word">{branding.siteName}</span>
    </div>
  );
}
