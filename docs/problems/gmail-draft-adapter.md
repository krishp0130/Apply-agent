# Gmail Draft Adapter Problem Log

## Assumptions

- Creating a Gmail draft is treated as externally visible because it writes to a connected Gmail account, so it requires an approved `SEND_EMAIL` approval.
- The caller owns OAuth setup and injects an already authorized Gmail service client.
- The adapter only needs plain-text MIME drafts for the first integration.

## Known Gaps

- No credential loading or OAuth refresh flow is included by design.
- No HTML body, attachments, CC, or BCC support is implemented yet.
- Draft creation is not yet wired into CSV tracking for outreach events.
- Gmail API errors are allowed to propagate to callers without retry handling.

## Risks

- A caller could inject a misconfigured or unauthorized Gmail client; this adapter does not validate account identity.
- Gmail draft creation may still reveal content to synced clients, browser sessions, or Gmail-side extensions.
- Approval records are checked in memory here; persistence must be handled by the caller.

## Next Problems

- Add tracking integration for successful draft creation.
- Add an OAuth bootstrap module that stores no credentials in code and can be tested separately.
- Add richer MIME support for attachments and HTML once resume-upload and template requirements are defined.
- Add caller-level retry and user-facing error classification for Gmail API failures.
