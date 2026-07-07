# Agent Assignments

This file tracks active branch-level workstreams for the internship application agent.

## Active Branches

### `feature/data-source-ingestion`

- Owner scope: source configuration, source fetching interfaces, HTML parsing.
- Expected files: `src/internship_agent/sources.py`, `src/internship_agent/parsing.py`, `tests/test_sources.py`, `tests/test_parsing.py`.
- Problem log: `docs/problems/data-source-ingestion.md`.
- Constraints: no network calls by default, preserve unknown fields, parse into `InternshipRole`.

### `feature/cli-status`

- Owner scope: local CLI and CSV-backed status summaries.
- Expected files: `src/internship_agent/cli.py`, `src/internship_agent/status.py`, `tests/test_cli.py`, `tests/test_status.py`.
- Problem log: `docs/problems/cli-status.md`.
- Constraints: no destructive commands, no credentials, no network calls.

### `feature/gmail-draft-adapter`

- Owner scope: Gmail draft creation adapter.
- Expected files: `src/internship_agent/gmail.py`, `tests/test_gmail.py`.
- Problem log: `docs/problems/gmail-draft-adapter.md`.
- Constraints: drafts only, no send capability, injected service client, no direct credential reads.

## Coordination Rules

- Each branch must read `SPEC.md` before implementation.
- Each branch must keep changes focused to its assigned files.
- Each branch must include tests for new behavior where practical.
- Each branch must document assumptions, gaps, risks, and follow-up problems in its problem log.
- Feature branches should not merge themselves into `develop`.
