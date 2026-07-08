# Next Session Handoff

## Repository State

- Main branch: `main`.
- Latest integrated branch state has Apollo MCP, recruiter outreach, and LaTeX resume workflows merged into `main`.
- Full test suite passed with `/private/tmp/apply-agent-test-venv/bin/python -m pytest`.
- Expected test count: `77 passed`.

## Integrated Feature Areas

- Source ingestion foundation: `src/internship_agent/sources.py`, `src/internship_agent/parsing.py`.
- GitHub internship-list ingestion: `src/internship_agent/github_sources.py`.
- Safe LinkedIn source boundary: `src/internship_agent/linkedin.py`.
- Local status CLI: `src/internship_agent/cli.py`, `src/internship_agent/status.py`.
- Draft-only Gmail adapter: `src/internship_agent/gmail.py`.
- Apollo MCP-ready contact contract: `src/internship_agent/apollo.py`.
- Apollo MCP client seam: `src/internship_agent/apollo_mcp.py`.
- Recruiter outreach workflow: `src/internship_agent/workflows.py`.
- LaTeX resume tailoring workflow: `src/internship_agent/resume_latex.py`.

## Important Guardrails

- No automatic email sending.
- No automatic application submission.
- No fabricated user, recruiter, contact, or application data.
- No LinkedIn login, CAPTCHA, MFA, or security-control bypass.
- Apollo contacts must come from returned data only; do not infer emails or profile URLs.
- Resume edits must use existing resume facts or explicit user-provided facts only.
- Source LaTeX resumes must not be overwritten without approval.
- Meaningful actions should be persisted to CSV tracking files.

## Recommended Next Tasks

1. Fill in the real Apollo MCP server/tool names and field mappings once details are provided.
2. Add CLI commands for GitHub ingestion, recruiter outreach, and LaTeX resume tailoring.
3. Persist discovered roles, selected Apollo contacts, Gmail draft creation, and resume tailoring events.
4. Add a user profile configuration model and role-scoring workflow.
5. Add browser-assisted LinkedIn extraction only for the current visible page with explicit pause gates.
6. Connect future AI-assisted resume suggestions to the deterministic evidence checks.

## Problem Logs

Detailed assumptions, gaps, and risks are documented in:

- `docs/problems/data-source-ingestion.md`
- `docs/problems/github-list-sources.md`
- `docs/problems/linkedin-source-scope.md`
- `docs/problems/cli-status.md`
- `docs/problems/gmail-draft-adapter.md`
- `docs/problems/apollo-contact-scope.md`
- `docs/problems/apollo-mcp-client.md`
- `docs/problems/outreach-workflow.md`
- `docs/problems/latex-resume-workflow.md`
