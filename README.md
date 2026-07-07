# Internship Application Agent

A local recruiting assistant for internship search workflows. The project is designed to keep the human in control: it can discover roles, score fit, draft outreach, track progress, and assist with forms, but it must not send emails or submit applications without approval.

## Current Scope

- CSV-backed tracking for roles, contacts, outreach drafts, approvals, and application events.
- Explainable fit scoring from known profile and role data.
- Contact prioritization for recruiter discovery results.
- Approval gates before irreversible or externally visible actions.
- Draft-only outreach generation.

## Development

```bash
python -m pytest
```

Project behavior and guardrails are defined in `SPEC.md`. Repository-level engineering rules are defined in `AGENTS.md`.
