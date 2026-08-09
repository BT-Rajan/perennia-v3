# Pass 3 — Theming, branding, and asset uploads

## What this pass adds

Everything visual that was still a literal value in `tokens.css` or
`index.html` is now driven by the same settings registry from Pass 1,
plus a real image-upload endpoint for logo/favicon.

```
backend/app/
├── settings_registry.py    + theme.* (colors, fonts, layout metrics),
│                              branding.meta_description; branding.site_name
│                              fixed to be properly bilingual (was a single
│                              string — a wordmark isn't always a literal
│                              translation, e.g. "Perennia" / "بيرينيا")
├── config.py                + UPLOADS_DIR, MAX_UPLOAD_IMAGE_BYTES
└── routers/
    └── admin_uploads.py      POST /admin/api/uploads/image — magic-byte
                                sniffed, size-capped, SVG deliberately
                                rejected (stored-XSS risk), random filename

src/
├── styles/tokens.css        rewritten: ~15 hardcoded colors → 4 base
│                              tokens + color-mix()-derived scale
├── theme/applyTheme.js       pushes live theme/branding onto the DOM:
│                              CSS vars, favicon, title, meta description,
│                              Google Fonts link
├── context/LangContext.jsx   + theme, resolved per-language branding
└── components/ui/Logo.jsx    now reads live branding instead of a
                                build-time env var
```

## The core design decision: 4 base tokens, not 20

`tokens.css` used to hardcode ~15 independent colors (a 6-step navy
scale, 3 gold gradient stops, glass surface opacities, muted-text
levels...). Exposing all of those to an admin would mean a 15-field
color form where most fields are really "shade 3 of the background,
slightly lighter" — repetitive for the admin and easy to end up
visually inconsistent (e.g. background changes but the navy scale
doesn't follow).

Instead, four base tokens are configurable
(`theme.background_color`, `theme.primary_color`, `theme.accent_color`,
`theme.text_color`), and every derived shade in `tokens.css` computes
from them with `color-mix()`:

```css
--navy-2: color-mix(in srgb, var(--brand-bg) 92%, white);
--gold-shade-2: color-mix(in srgb, var(--brand-primary) 82%, black);
--on-gold-text: var(--brand-bg);   /* always legible on a gold button */
```

Changing one base color re-themes everything derived from it,
automatically, in the browser, with no rebuild. Verified live: setting
`theme.background_color` and `theme.primary_color` via the admin API
and reloading correctly repainted the navy scale, gold gradients, and
button text color together.

Two categories of color were deliberately left non-configurable and
documented as such directly in `tokens.css`: decorative secondary
accents (purple/cyan/emerald/rose used sparingly in background
gradients — variety, not brand identity) and semantic status colors
(success green, danger red — conventional, not a brand choice). Making
every color a knob would produce an admin form with no real
customization value at the cost of a much larger surface for a site to
end up looking broken.

## Uploads: real files, not just URL text boxes

`branding.logo_url` / `branding.favicon_url` were already plain URL
settings since Pass 1 (an admin could always point them at an
externally-hosted image). This pass adds `/admin/api/uploads/image` so
an admin can upload a file directly instead of needing separate image
hosting. Security-relevant choices:

- The file type is determined by **sniffing actual magic bytes**, never
  trusted from the client's `Content-Type` header or filename extension
  — both are attacker-controlled. Verified with a test that sends
  `<script>...` bytes labeled `image/png` and confirms it's rejected.
- **SVG is not accepted**, even though it's a legitimate logo format —
  an SVG can embed `<script>` and event-handler attributes, so serving
  one back verbatim from this endpoint would be a stored-XSS vector. An
  admin who specifically wants an SVG can still set the URL field to
  one hosted elsewhere; this endpoint just won't accept an *upload* of one.
- Stored filenames are random (`secrets.token_hex`), never derived from
  the client-supplied name — no path traversal, no overwrite collisions.

## Runtime application: `applyTheme.js`

`index.html`'s favicon link, theme-color meta tag, meta description,
and Google Fonts stylesheet link all got stable `id`s so
`applyTheme.js` can update them once real config loads — same
fallback-first, silent-upgrade pattern as content in Pass 2. The
static values in `index.html`/`tokens.css` are what render before any
network round trip; live config overrides them a moment later if the
backend is reachable.

## What changed for the frontend dev setup

- `vite.config.js` now also proxies `/uploads` to the backend (logo/
  favicon images are served from there) — without this, Vite's SPA
  fallback would silently serve `index.html` for any `/uploads/*`
  request instead of 404ing or proxying, which is a sharp edge worth
  flagging: it looked like a working 200 response until the content-type
  was actually checked.
- Removed the now-obsolete root `.env`/`.env.example` and
  `VITE_LOGO_URL` — the logo is fully backend-driven now, no
  build-time env var needed.

## Verified end to end

- 46 backend tests pass (11 new: theme validation bounds, font string
  fields, Google Fonts URL validation, and 6 upload tests including the
  magic-byte-sniffing and SVG-rejection cases).
- `npm run build` succeeds, lint clean.
- Headless-browser test: loaded the default theme, read back the
  computed CSS variables and confirmed they matched the registry
  defaults exactly; then changed `theme.primary_color`,
  `theme.background_color`, and `theme.header_height_px` via the admin
  API, reloaded, and confirmed the *derived* values (gradient shades,
  navy scale, on-gold text color) updated correctly too — not just the
  base variables.
- Uploaded a real PNG via the admin API, set it as `branding.logo_url`,
  reloaded, and confirmed the header actually renders that image.

## Deliberately deferred to later passes

- No admin UI yet (color pickers, upload dropzone) — still API-only,
  fully covered by tests in the meantime, same as Pass 1/2.
- Production static-file serving topology (backend serving the built
  `dist/` + `/uploads` from one origin, or a reverse proxy in front of
  both) isn't settled yet — flagged for Pass 10 alongside Docker/deploy.
- Spacing scale, breakpoints, and motion timing remain static — a
  legitimate future extension, but a much lower-value one than color/
  font/logo, and left out to keep this pass's admin surface focused.
