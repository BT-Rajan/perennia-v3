# Knowledge base for the chat assistant

## What this adds

An admin can upload documents (.txt, .md, .html, .docx, .pdf) or add a
website address, and the chat assistant grounds its replies in that
content — a pricing sheet, an FAQ page, a policy document, a page
pulled straight from the live site, etc., without needing to hand-copy
any of it into the system prompt setting.

```
backend/app/
├── knowledge_extract.py    byte-sniffing extraction (pdf/docx/html/txt/md)
│                            + URL fetching with SSRF guards
├── knowledge_service.py     CRUD + the prompt-injection text builder
├── models.py                 + KnowledgeSource
├── settings_registry.py      + knowledge.* (enabled, size/count limits)
├── chat_service.py            appends the knowledge block to every
│                              reply's system prompt
└── routers/admin_knowledge.py  upload / add-URL / refresh / list / toggle / delete

admin/src/pages/KnowledgePage.jsx   upload form, URL form, source list,
                                     inline text preview, refresh/delete
```

## Built by studying the reference implementation first, as asked

`BT-Rajan/perennia-production`'s approach (`app/extract.py`,
`app/prompt.py`) is deliberately simple: no vector search or
embeddings — extract each document's text once, cap it, and
concatenate every active document into the system prompt with
`--- DOCUMENT START/END ---` delimiters, plus a per-document line cap
as defense against prompt injection via an adversarial or oversized
upload. This project follows that same approach for the same reason:
it's the right amount of complexity for a single-digit-to-low-hundreds
document knowledge base, and adding real RAG (embeddings, a vector
store, chunked retrieval) would be premature complexity for that scale.

**What the reference didn't have, and this adds:** HTML file support,
and — the main ask — ingesting a *website address* directly, not just
uploaded files. Fetching an admin-supplied URL from the server needed
its own security treatment (see below), since the reference never did
this at all.

## Security: SSRF guards on URL fetching

Fetching an admin-supplied URL from the backend is a classic SSRF
vector — even for an admin-only endpoint, "trusted admin" isn't a
reason to skip it (a compromised admin session, or a well-meaning
admin pasting a URL they don't realize points somewhere internal, are
both realistic). `knowledge_extract._validate_public_url`:

- Only allows `http`/`https`.
- Resolves the hostname and rejects private, loopback, link-local
  (including the `169.254.169.254` cloud-metadata address — a classic
  SSRF target for credential theft), reserved, and multicast ranges.
- Re-validates the *final* URL after following redirects, so a
  redirect can't be used to reach a blocked address after an initial
  check passes.
- Caps the response size while streaming (5MB), so a malicious or
  enormous page can't exhaust memory.

Documented directly in the code as reasonable defense-in-depth, not a
complete guarantee — this doesn't defend against DNS rebinding
(resolving safely at check time, differently at request time), which
would need a proxy or a strict allowlist to fully close.

## Same "extension is never trusted" principle as image uploads

Every file type is determined by sniffing actual bytes — a `.pdf`
extension isn't enough to be treated as a PDF, and a `.txt` extension
isn't enough to be treated as plain text (a `_looks_binary` check
rejects a renamed binary file). Content wins over the claimed
extension in every direction: a PDF renamed to `.docx` is correctly
extracted as a PDF; a real `.docx` renamed to `.txt` is correctly
extracted as a docx. Verified with tests for both directions.

## Verified end to end, live, with a real file and a real (failing) network call

- 137 backend tests pass (29 new): extraction correctness across all
  five formats, sniff-wins-over-extension in both directions, SSRF
  rejection (localhost, loopback, private ranges, the metadata IP),
  capacity limits, settings validation, and — importantly — that the
  chat system prompt genuinely contains an uploaded document's content
  when the knowledge base is active, and genuinely excludes it when
  the source is inactive or the feature is disabled (mocked LLM call,
  asserting on the actual `system_prompt` argument).
- **Live browser test**: logged into the real admin UI, uploaded an
  actual markdown file through the file picker, watched it appear with
  the correct type/size/status, opened the inline preview and
  confirmed the extracted text matches exactly what was uploaded.
- **Verified the production code path directly against the live
  database** — not just the test suite — by calling
  `knowledge_service.build_prompt_block()` in a shell against the
  server actually running with that uploaded file, and confirmed the
  real, uploaded pricing content (including a unique marker string)
  appears in exactly the block `chat_service.py` appends to every reply.
- Sent a real chat request through the running server with a
  genuinely invalid Anthropic key — a real network round trip to
  `api.anthropic.com`, same technique as Pass 5 — and confirmed no
  crash, correct graceful fallback, with the knowledge base fully wired
  in the whole time.
- Tested the URL-add path against `https://example.com/`: this
  sandbox's network egress only allows a fixed domain list, so the
  fetch was blocked (HTTP 403) — exactly the graceful-degradation path
  (source created, marked not-ok, clear error message, "Refresh"
  button available), verified both via the API and rendered correctly
  in the actual UI screenshot. Real-world domains aren't restricted
  this way; this is a sandbox limitation, not a product one, consistent
  with the same caveat noted for WhatsApp/Twilio in Pass 6.

## A real bug caught while writing tests, not shipped

The upload endpoint's rate limit was hardcoded (`"10/hour"` directly in
the decorator) rather than reading from a configurable infra setting —
the established pattern everywhere else in this codebase (`RATE_LIMIT_LOGIN`,
`RATE_LIMIT_APPOINTMENT`) specifically so tests can relax it. Caught
because the test suite's own uploads (this file does a lot of them)
started hitting a real 429 partway through. Fixed by adding
`RATE_LIMIT_KNOWLEDGE_UPLOAD` to `config.py` and reading it in the router,
same as the other two.

## Deliberately deferred

- No chunking/retrieval — every active source's full (capped) text
  goes into every reply's prompt. Fine at the scale this is designed
  for; would need revisiting (real RAG) if someone tries to load in
  hundreds of large documents.
- No scheduled re-fetching of URL sources — refresh is manual, via the
  button in the admin UI.
- No per-source language/audience targeting (a document is either
  included for every reply or not at all, no way to say "only use this
  for Arabic-language conversations").
