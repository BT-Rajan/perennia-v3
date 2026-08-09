import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { adminApi } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import SettingField from "../components/SettingField.jsx";
import ThemePresetPicker from "../components/ThemePresetPicker.jsx";
import "./SettingsPage.css";

// Nicer labels for the sidebar than a raw category key. Anything not
// listed here just gets capitalized — adding a brand-new category in
// the backend registry still shows up automatically, just title-cased.
const CATEGORY_LABELS = {
  branding: "Branding",
  theme: "Theme",
  locale: "Language",
  contact: "Contact",
  features: "Features",
  booking: "Booking",
  chat: "Chat / AI assistant",
  notifications: "Notifications",
  templates: "Message templates",
  copy: "On-screen text",
};

function labelFor(category) {
  return CATEGORY_LABELS[category] || category[0].toUpperCase() + category.slice(1);
}

export default function SettingsPage() {
  const { handleSessionExpired } = useAuth();
  const { category: categoryParam } = useParams();
  const navigate = useNavigate();

  const [categories, setCategories] = useState(null);
  const [schema, setSchema] = useState(null);
  const [values, setValues] = useState({});
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState(null);

  // Load the category list once, then land on the first one if the
  // URL didn't specify one.
  useEffect(() => {
    adminApi
      .listSettingCategories()
      .then((cats) => {
        setCategories(cats);
        if (!categoryParam && cats.length > 0) {
          navigate(`/settings/${cats[0]}`, { replace: true });
        }
      })
      .catch((e) => (e.status === 401 ? handleSessionExpired() : setError(e.message)));
  }, [categoryParam, navigate, handleSessionExpired]);

  const loadCategory = useCallback(
    (category) => {
      setLoading(true);
      setError("");
      setSavedAt(null);
      adminApi
        .getSettingCategory(category)
        .then((data) => {
          setSchema(data.schema_);
          // Secret fields never arrive with a real value (see backend) —
          // start them blank; a blank secret field on save just means
          // "leave the stored value alone".
          const initial = { ...data.values };
          for (const f of data.schema_) {
            if (f.secret) initial[f.key] = "";
          }
          setValues(initial);
          setFieldErrors({});
        })
        .catch((e) => (e.status === 401 ? handleSessionExpired() : setError(e.message)))
        .finally(() => setLoading(false));
    },
    [handleSessionExpired]
  );

  useEffect(() => {
    if (categoryParam) loadCategory(categoryParam);
  }, [categoryParam, loadCategory]);

  function handleFieldChange(key, value) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function handleFieldError(key, message) {
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (message) next[key] = message;
      else delete next[key];
      return next;
    });
  }

  async function handleSave(e) {
    e.preventDefault();
    if (Object.keys(fieldErrors).length > 0) return;

    setSaving(true);
    setError("");
    setSavedAt(null);
    try {
      // Secret fields: only send one the admin actually typed into —
      // an untouched (blank) secret field means "keep what's stored".
      const payload = {};
      for (const f of schema) {
        const v = values[f.key];
        if (f.secret && v === "") continue;
        payload[f.key] = v;
      }
      await adminApi.updateSettingCategory(categoryParam, payload);
      setSavedAt(Date.now());
      loadCategory(categoryParam); // re-fetch so secret placeholders reflect the new state
    } catch (e) {
      if (e.status === 401) handleSessionExpired();
      else setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div className="page-error">{error}</div>;
  if (!categories) return <div className="page-loading">Loading…</div>;

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Everything customer-facing on the site is configured here — no deploy needed."
      />

      <div className="settings-layout">
        <nav className="settings-nav card">
          {categories.map((c) => (
            <button
              key={c}
              className={c === categoryParam ? "settings-nav-item active" : "settings-nav-item"}
              onClick={() => navigate(`/settings/${c}`)}
            >
              {labelFor(c)}
            </button>
          ))}
        </nav>

        <div className="card settings-form-wrap">
          {loading || !schema ? (
            <div className="page-loading">Loading…</div>
          ) : (
            <form onSubmit={handleSave}>
              <h2 className="settings-form-title">{labelFor(categoryParam)}</h2>

              {categoryParam === "theme" && (
                <ThemePresetPicker
                  values={values}
                  onApply={(presetValues) => setValues((prev) => ({ ...prev, ...presetValues }))}
                />
              )}

              {schema.map((field) => (
                <SettingField
                  key={field.key}
                  field={field}
                  value={values[field.key]}
                  error={fieldErrors[field.key]}
                  onChange={(v) => handleFieldChange(field.key, v)}
                  onError={(msg) => handleFieldError(field.key, msg)}
                />
              ))}

              <div className="settings-form-footer">
                <button type="submit" className="btn-primary" disabled={saving || Object.keys(fieldErrors).length > 0}>
                  {saving ? "Saving…" : "Save changes"}
                </button>
                {savedAt && <span className="settings-saved-msg">Saved.</span>}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
