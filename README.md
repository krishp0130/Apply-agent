# Internship Application Agent

A local, human-in-the-loop recruiting assistant for internship search workflows.

The agent is designed to help discover roles, score fit, find relevant contacts,
draft outreach, track progress, and assist with application forms while keeping
the user in control of final actions. It must never fabricate data, send emails,
or submit applications automatically.

## Current Capabilities

- CSV-backed tracking for roles, contacts, outreach drafts, approvals, and application events.
- Pydantic domain models for profiles, roles, contacts, fit scores, approvals, drafts, and application events.
- Explainable role scoring using only known profile and role evidence.
- Contact ranking based on recruiter/referral priority rules.
- Approval gates for protected actions.
- Deterministic draft-only outreach generation.
- Draft-only Gmail adapter with injected service client.
- GitHub Markdown source ingestion for:
  - `sndsh404/summer-2027-internships`
  - `vanshb03/Summer2027-Internships`
  - `speedyapply/2027-SWE-College-Jobs`
- Safe LinkedIn ingestion boundary for user-provided snippets or browser-extracted job card dictionaries.
- Apollo MCP-ready contact discovery contract with injected client protocol.
- Read-only CLI status reporting from local tracking CSVs.

## Guardrails

The project rules are intentionally strict:

- Do not fabricate user information.
- Do not fabricate recruiter information.
- Do not fabricate application answers.
- Do not send emails automatically.
- Do not submit applications automatically.
- Do not bypass CAPTCHAs, MFA, login prompts, or security controls.
- Stop for user approval before irreversible or externally visible actions.
- Persist meaningful actions to CSV tracking files.

See `SPEC.md` for product behavior and `AGENTS.md` for repository working rules.

## Project Layout

```text
src/internship_agent/
  apollo.py          Apollo MCP-ready contact discovery contract
  approval.py        Human approval gates for protected actions
  cli.py             Read-only command-line interface
  contacts.py        Contact priority ranking
  github_sources.py  GitHub Markdown internship-list ingestion
  gmail.py           Draft-only Gmail adapter
  linkedin.py        Safe LinkedIn ingestion boundary
  models.py          Shared Pydantic domain models
  outreach.py        Deterministic draft-only outreach generation
  parsing.py         HTML role parsing helpers
  scoring.py         Explainable role scoring
  sources.py         Source ingestion configuration and fetch interfaces
  status.py          CSV-backed status summaries
  tracking.py        Generic CSV repository and row models
```

Problem logs and follow-up notes live in `docs/problems/`.

## Installation

Use Python 3.12 or newer.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Tests

Run all unit tests:

```bash
python -m pytest
```

Current expected result after the latest integration:

```text
53 passed
```

## CLI

The CLI is read-only at this stage.

```bash
internship-agent status
internship-agent status --tracking-dir data/tracking
internship-agent status --format json
internship-agent status --fit-threshold 75
```

The default tracking directory is `data/tracking`. Missing CSV files are reported
as missing rather than created automatically.

## Tracking Files

The status command expects these CSV files when tracking data exists:

- `roles.csv`
- `contacts.csv`
- `approvals.csv`
- `outreach_drafts.csv`
- `application_events.csv`

CSV row models are defined in `src/internship_agent/tracking.py`.

## Source Ingestion

### GitHub Internship Lists

`src/internship_agent/github_sources.py` supports injected async fetching of raw
Markdown content from known internship-list repositories. The module does not
make network calls by default.

Supported repositories:

- `sndsh404/summer-2027-internships`
- `vanshb03/Summer2027-Internships`
- `speedyapply/2027-SWE-College-Jobs`

SpeedyApply is treated as an index that points to `INTERN_USA.md`.

### LinkedIn

`src/internship_agent/linkedin.py` intentionally does not implement background
scraping or login automation. It accepts user-provided snippets or already
extracted job-card dictionaries and converts them into `InternshipRole` objects.

Browser automation, when added later, must pause on login prompts, CAPTCHAs, MFA,
and review pages.

## Contacts And Outreach

`src/internship_agent/apollo.py` defines the adapter contract needed for Apollo
MCP integration. It ranks returned contacts using project priority rules and
caps selected contacts at three per company by default.

Priority order:

1. University Recruiter
2. Early Talent Recruiter
3. Technical Recruiter
4. Engineering Manager
5. Software Engineer
6. Founder for small startups

Outreach remains draft-only. `src/internship_agent/gmail.py` can create Gmail
drafts through an injected Gmail service client after approval, but it exposes no
send capability.

## Development Workflow

1. Read `SPEC.md`.
2. Pick the smallest useful increment.
3. Add or update focused unit tests for new behavior.
4. Run the full test suite.
5. Update relevant problem logs under `docs/problems/`.
6. Keep protected actions behind approval gates.

## Next Work

- Wire GitHub source ingestion into the CLI or a workflow command.
- Add tracking writes for discovered roles and created Gmail drafts.
- Add parser diagnostics for skipped or malformed source rows.
- Add a concrete Apollo MCP client once the callable tool schema is available.
- Add a browser-assisted LinkedIn extraction helper that operates only on the current visible page.
- Add a user profile configuration format and import command.
