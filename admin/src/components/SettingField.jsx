import { useState } from "react";
import "./SettingField.css";

const LANG_LABELS = { en: "English", ar: "Arabic" };

function langLabel(code) {
  return LANG_LABELS[code] || code;
}

// A handful of types need their raw string edited as JSON (LIST, JSON) —
// this wraps that in one place: keep a local text buffer so the admin
// can type freely, only attempt to parse (and only report an error) on
// blur, rather than fighting them mid-keystroke.
function JsonTextArea({ value, onChange, onError, rows = 4 }) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));

  function handleBlur() {
    try {
      const parsed = JSON.parse(text);
      onError(null);
      onChange(parsed);
    } catch {
      onError("Not valid JSON.");
    }
  }

  return (
    <textarea
      className="setting-input setting-input-mono"
      rows={rows}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={handleBlur}
      spellCheck={false}
    />
  );
}

function SingleControl({ def, value, onChange, onError }) {
  switch (def.type) {
    case "bool":
      return (
        <label className="setting-toggle">
          <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
          <span>{value ? "On" : "Off"}</span>
        </label>
      );

    case "text":
      return (
        <textarea
          className="setting-input"
          rows={4}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case "int":
      return (
        <input
          type="number"
          step="1"
          className="setting-input"
          value={value ?? 0}
          onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        />
      );

    case "float":
      return (
        <input
          type="number"
          step="0.01"
          className="setting-input"
          value={value ?? 0}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        />
      );

    case "color":
      return (
        <div className="setting-color-row">
          <input type="color" value={value || "#000000"} onChange={(e) => onChange(e.target.value)} />
          <input
            type="text"
            className="setting-input setting-input-mono"
            value={value ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      );

    case "enum":
      return (
        <select className="setting-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          {(def.choices || []).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      );

    case "list":
      return (
        <input
          type="text"
          className="setting-input"
          value={Array.isArray(value) ? value.join(", ") : ""}
          onChange={(e) => {
            const items = e.target.value.split(",").map((s) => s.trim()).filter((s) => s !== "");
            // Preserve numeric lists (e.g. booking.workdays) rather than
            // turning them into strings of digits.
            const allOriginallyNumeric = Array.isArray(value) && value.every((v) => typeof v === "number");
            onChange(allOriginallyNumeric ? items.map(Number) : items);
          }}
          placeholder="Comma-separated"
        />
      );

    case "json":
      return <JsonTextArea value={value} onChange={onChange} onError={onError} rows={6} />;

    case "url":
      return (
        <input type="text" className="setting-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      );

    case "email":
      return (
        <input type="email" className="setting-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      );

    case "image":
      return (
        <input
          type="text"
          className="setting-input"
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder="/path/to/image.png or https://…"
        />
      );

    case "string":
    default:
      return (
        <input type="text" className="setting-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      );
  }
}

export default function SettingField({ field, value, error, onChange, onError }) {
  const errorId = `err-${field.key}`;

  // JSON types (including i18n JSON, e.g. templates.*) are edited as a
  // single raw JSON blob per language rather than exploded into
  // sub-fields — keeps this fully generic instead of hardcoding the
  // shape of every template.
  const isSecretText = field.secret;

  let control;
  if (isSecretText) {
    control = (
      <input
        type="password"
        className="setting-input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Leave blank to keep the current value"
        autoComplete="new-password"
      />
    );
  } else if (field.i18n) {
    const langs = Object.keys(field.default && typeof field.default === "object" ? field.default : { en: "" });
    control = (
      <div className="setting-i18n-group">
        {langs.map((lang) => (
          <div key={lang} className="setting-i18n-row">
            <span className="setting-i18n-lang">{langLabel(lang)}</span>
            <SingleControl
              def={field}
              value={value?.[lang]}
              onChange={(v) => onChange({ ...(value || {}), [lang]: v })}
              onError={(msg) => onError(msg)}
            />
          </div>
        ))}
      </div>
    );
  } else {
    control = <SingleControl def={field} value={value} onChange={onChange} onError={onError} />;
  }

  return (
    <div className="setting-field">
      <label className="setting-label" htmlFor={field.key}>
        {field.label}
        {isSecretText && <span className="setting-secret-badge">secret</span>}
      </label>
      {field.help_text && <p className="setting-help">{field.help_text}</p>}
      {control}
      {error && <p className="setting-error">{error}</p>}
    </div>
  );
}
