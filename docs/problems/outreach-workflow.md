# Outreach Workflow

## Problem

Recruiter outreach needs to connect Apollo contact discovery, deterministic
email drafting, optional Gmail draft creation, and CSV tracking without ever
sending email or inventing missing information.

## Implemented Scope

- Builds a company-scoped Apollo query from an `InternshipRole`.
- Uses an injected `ApolloContactAdapter`-compatible searcher.
- Caps selected outreach targets at three contacts.
- Generates local draft-only emails only when the contact has an email and the
  workflow has concrete fit evidence.
- Requires approved `SEND_EMAIL` approval before creating Gmail drafts.
- Calls only injected Gmail draft creation; no send path is exposed.
- Optionally appends contact, outreach draft, approval, and workflow event rows
  through injected repositories.

## Safety Notes

- Missing contact emails are preserved and skipped for drafting.
- Missing or generic fit evidence prevents both local drafts and Gmail drafts.
- Gmail draft creation requires a sender email because Gmail needs a `From`
  address.
- The workflow is async because Apollo contact search is async.
