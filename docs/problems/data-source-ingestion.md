# Data Source Ingestion Problem Log

## Assumptions

- Sources are configured explicitly and are HTML-only for this first version.
- Network access is opt-in through an injected fetcher; no default code path performs network calls.
- Tests and local callers can provide inline HTML with `InternshipSourceConfig.inline_html`.
- Required `InternshipRole` strings use `unknown` when the source does not provide the value.

## Known Gaps

- No built-in HTTP fetcher is included yet.
- No JavaScript-rendered page support is included yet.
- Parsing requires CSS selectors and does not auto-discover arbitrary job boards.
- Invalid application links are dropped instead of stored separately as raw source notes.
- Remote status is only set to `True` when the parsed location explicitly contains `remote`.

## Risks

- Source HTML changes can silently reduce parsed fields or roles.
- Generic selectors may parse unrelated cards if configured too broadly.
- Required `company` and `title` fields must use `unknown` until the shared model supports nullable values.
- Relative links require a configured source URL to resolve safely.

## Next Problems

- Add a safe, rate-limited HTTP fetcher that remains dependency-injected and testable.
- Add parser diagnostics so tracking can record missing required source fields.
- Add source-specific selector examples for common internship pages.
- Decide whether `InternshipRole` should support nullable `company` and `title`.
- Store raw source snippets or parse warnings for auditability without overloading descriptions.
