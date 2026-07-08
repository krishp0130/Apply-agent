# LinkedIn Source Scope Problem Log

## Legal and ToS Risk

- LinkedIn content and account access are governed by LinkedIn's terms and applicable law; this module does not grant permission to scrape or automate LinkedIn.
- Automated collection can create contractual, privacy, rate-limit, or anti-circumvention risk, especially when login walls, CAPTCHAs, MFA, or other controls appear.
- This implementation intentionally avoids credentials, login bypass, CAPTCHA/MFA bypass, background crawling, and automatic application submission.
- Callers are responsible for using only content they are allowed to access and for respecting LinkedIn's current policies.

## Assumptions

- Inputs are user-provided snippets or already browser-extracted job card dictionaries.
- No function in `src/internship_agent/linkedin.py` fetches LinkedIn pages, logs in, stores credentials, or navigates search results.
- `source` is always recorded as `linkedin` for parsed roles.
- Missing string fields are marked as `unknown` instead of guessed.
- Recency filtering applies when a posting age such as `today`, `2 days ago`, or `1 week ago` is present; absent recency is preserved rather than fabricated.

## Safe Workflow

1. The user chooses search terms, recency days, and location filters in `LinkedInSearchConfig`.
2. The user provides copied LinkedIn text/HTML snippets, or a browser helper supplies explicit job card dictionaries from the current page.
3. Browser automation, if added by a future caller, must pause on login/auth prompts, CAPTCHAs, and MFA.
4. Parsed cards become `InternshipRole` records with `source='linkedin'`.
5. Application assistance must stop before submission and wait for user approval.

## Guardrails

- No default scraping loop is included.
- No credentials are accepted or read from environment variables.
- No login, CAPTCHA, MFA, or security-control bypass is supported.
- No application submission capability is exposed.
- Scope filters are local-only and operate on already-provided content.

## Known Gaps

- LinkedIn's markup changes frequently, so HTML snippet selectors are best-effort.
- Plain-text parsing assumes one copied job card per blank-line-delimited block.
- Recency parsing handles common English relative labels only.
- Unknown recency is included because the parser must not invent dates.
- Job descriptions and required skills are only captured when explicitly provided.

## Next Problems

- Add parser diagnostics that explain why a provided card was filtered out.
- Add optional tracking notes for raw posted-age labels without changing `InternshipRole`.
- Decide whether shared role models should support nullable `company`, `title`, and `location` instead of the `unknown` sentinel.
- Build a separate browser extraction helper that operates only on the current visible page and enforces the guardrails before extraction.
- Add user-facing docs showing how to copy a safe snippet without automated browsing.
