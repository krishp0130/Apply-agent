# Agent Assignments

This file tracks active branch-level workstreams for the internship application agent.

## Completed Branches

### `feature/data-source-ingestion`

- Owner scope: source configuration, source fetching interfaces, HTML parsing.
- Expected files: `src/internship_agent/sources.py`, `src/internship_agent/parsing.py`, `tests/test_sources.py`, `tests/test_parsing.py`.
- Problem log: `docs/problems/data-source-ingestion.md`.
- Constraints: no network calls by default, preserve unknown fields, parse into `InternshipRole`.
- Status: merged into `develop`.

### `feature/cli-status`

- Owner scope: local CLI and CSV-backed status summaries.
- Expected files: `src/internship_agent/cli.py`, `src/internship_agent/status.py`, `tests/test_cli.py`, `tests/test_status.py`.
- Problem log: `docs/problems/cli-status.md`.
- Constraints: no destructive commands, no credentials, no network calls.
- Status: merged into `develop`.

### `feature/gmail-draft-adapter`

- Owner scope: Gmail draft creation adapter.
- Expected files: `src/internship_agent/gmail.py`, `tests/test_gmail.py`.
- Problem log: `docs/problems/gmail-draft-adapter.md`.
- Constraints: drafts only, no send capability, injected service client, no direct credential reads.
- Status: merged into `develop`.

### `feature/github-list-sources`

- Owner scope: GitHub Markdown internship-list ingestion for known 2027 repositories.
- Expected files: `src/internship_agent/github_sources.py`, `tests/test_github_sources.py`.
- Problem log: `docs/problems/github-list-sources.md`.
- Constraints: use raw Markdown content through injected fetchers, parse Markdown tables into `InternshipRole`, support the known repo shapes from `sndsh404/summer-2027-internships`, `vanshb03/Summer2027-Internships`, and `speedyapply/2027-SWE-College-Jobs`.
- Status: merged into `develop`.

### `feature/linkedin-source-scope`

- Owner scope: recent LinkedIn posting ingestion design and safe browser-assisted extraction boundaries.
- Expected files: `src/internship_agent/linkedin.py`, `tests/test_linkedin.py`.
- Problem log: `docs/problems/linkedin-source-scope.md`.
- Constraints: no login bypass, no CAPTCHA/MFA bypass, no default scraping loop, require user-provided/exported page content or explicit browser session control.
- Status: merged into `develop`.

### `feature/apollo-contact-scope`

- Owner scope: Apollo MCP contact discovery adapter contract and recruiter/referral outreach workflow.
- Expected files: `src/internship_agent/apollo.py`, `tests/test_apollo.py`.
- Problem log: `docs/problems/apollo-contact-scope.md`.
- Constraints: no fabricated contacts, no automatic email sending, cap contact targets at three per company unless instructed, prioritize recruiter roles before employees.
- Status: merged into `develop`.

## Coordination Rules

- Each branch must read `SPEC.md` before implementation.
- Each branch must keep changes focused to its assigned files.
- Each branch must include tests for new behavior where practical.
- Each branch must document assumptions, gaps, risks, and follow-up problems in its problem log.
- Feature branches should not merge themselves into `develop`.
