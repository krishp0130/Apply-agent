# Project Roadmap

## Increment 1: Local Core

- Define Pydantic models for roles, profile data, contacts, fit scores, outreach drafts, approvals, and application events.
- Add CSV repositories so meaningful actions are persisted.
- Add deterministic fit scoring with explainable reasons.
- Add contact ranking based on recruiter priority rules.
- Add approval-gate utilities for protected actions.
- Add tests for scoring, contact ranking, approval gates, and CSV persistence.

## Increment 2: Data Sources

- Add configured internship source ingestion.
- Add HTML parsing utilities for job postings.
- Preserve source URLs and unknown fields without guessing.

## Increment 3: Outreach Drafts

- Add Gmail draft creation behind explicit approval gates.
- Add OpenAI-assisted drafting with evidence checks.
- Persist every draft and approval decision.

## Increment 4: Browser Assistance

- Add Playwright form assistance.
- Fill known fields only.
- Stop at CAPTCHAs, login prompts, MFA, and review pages.

## Increment 5: Automation UX

- Add CLI commands for common workflows.
- Add status reports from tracked CSV files.
- Add follow-up reminder tracking.
