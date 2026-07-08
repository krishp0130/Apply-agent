# Apollo Outreach and LaTeX Resume Workflow Spec

## Goal

Extend the recruiting assistant so it can:

- Search Apollo for company contacts when role data is available.
- Prioritize recruiters and referral targets.
- Draft concise outreach emails to selected contacts.
- Create Gmail drafts only after explicit approval.
- Tailor a LaTeX resume to a job description without fabricating experience.
- Compile the tailored LaTeX resume and report whether it is valid.

The user remains in control of every final action.

## Non-Goals

The system must not:

- Send emails automatically.
- Submit applications automatically.
- Invent recruiter names, email addresses, profile URLs, or job facts.
- Invent user experience, projects, skills, metrics, or resume bullets.
- Overwrite the user's source resume without approval.
- Bypass Apollo, Gmail, LinkedIn, website, CAPTCHA, login, or MFA controls.

## Apollo MCP Integration

### Current State

`src/internship_agent/apollo.py` already defines an injected client protocol:

- `ApolloCompanyContactQuery`
- `ApolloContactResult`
- `ApolloClientProtocol`
- `ApolloContactAdapter`
- `ApolloContactSearchPlan`
- `OutreachTargetPlan`

This contract should remain the boundary between the rest of the agent and any
concrete Apollo MCP implementation.

### Required Future MCP Details

When the user provides Apollo MCP details, the concrete adapter should document:

- MCP server name.
- MCP tool name for company/person search.
- Required environment variables.
- Search input schema.
- Result output schema.
- Rate limits or usage constraints.
- Email verification fields, if available.
- Any required approval or review step before storing returned personal data.

### Required Behavior

The Apollo integration must:

- Search by company name and optional domain.
- Prefer narrow company-scoped searches over broad people searches.
- Return only facts Apollo provides.
- Preserve missing emails and profile URLs as missing.
- Rank contacts using the project priority order.
- Select at most three contacts per company by default.
- Separate recruiter outreach from referral requests.
- Persist meaningful contact discovery and draft creation events to CSV tracking.

### Contact Priority

1. University Recruiter
2. Early Talent Recruiter
3. Technical Recruiter
4. Engineering Manager
5. Software Engineer
6. Founder, for small startups

## Outreach Workflow

### Inputs

- `InternshipRole`
- `FitScore`
- Known user profile facts.
- Apollo contact search results.
- One concrete fit reason grounded in the role and user profile.
- Optional approved Gmail draft creation request.

### Steps

1. Build an Apollo company query from the role.
2. Search Apollo through the injected MCP client.
3. Rank and cap contacts.
4. Build draft-only outreach plans.
5. Generate concise outreach draft content.
6. Request approval before creating a Gmail draft.
7. Create Gmail drafts only through the injected Gmail service client.
8. Track contacts, drafts, and approvals in CSV files.

### Approval Gates

The workflow must request approval before:

- Creating a Gmail draft in the user's account.
- Sending email, if a future send function ever exists.
- Overwriting any tracked contact or draft data.

The current implementation should not expose email sending.

## LaTeX Resume Workflow

### Inputs

- Path to the user's LaTeX resume file.
- Job description text.
- Known user profile facts or approved resume facts.
- Optional tailoring instructions from the user.

### Required Behavior

The resume workflow must:

- Read the LaTeX source from the user's selected file.
- Generate a reviewable tailoring plan before edits are applied.
- Use only existing resume facts or explicit user-provided facts.
- Mark missing evidence instead of inventing content.
- Write tailored output to a new file by default.
- Require approval before overwriting the source resume.
- Compile the tailored `.tex` file when a LaTeX compiler is available.
- Report compile success or failure with log path.

### Safe Editing Rules

- Do not invent companies, projects, metrics, skills, coursework, dates, or awards.
- Prefer reordering, selecting, or lightly rephrasing existing bullets.
- Add new bullets only when the exact fact was provided by the user.
- Keep edits reviewable as explicit operations.
- Preserve LaTeX commands and escaping.
- Never delete the only copy of the source resume.

### Compile Rules

- Prefer `latexmk -pdf` when available.
- Fall back to `pdflatex` when available.
- If neither is available, return a blocked compile result rather than failing silently.
- Write build outputs to a separate build directory.
- Do not require network access.

## Tracking Requirements

The workflow should eventually update:

- `contacts.csv` when Apollo returns selected contacts.
- `outreach_drafts.csv` when draft content is created.
- `approvals.csv` when the user approves or rejects Gmail draft creation.
- `application_events.csv` when resume tailoring or outreach milestones happen.

## Unit Test Expectations

New code must include focused unit tests for:

- Apollo MCP result normalization.
- Apollo search workflow behavior with fake clients.
- Contact capping and recruiter/referral prioritization.
- Draft-only outreach behavior.
- Gmail draft approval enforcement.
- LaTeX resume parse/edit planning.
- Safe refusal when resume facts are missing.
- Compile command selection and blocked compiler states.

Tests must not call Apollo, Gmail, OpenAI, LinkedIn, or external networks.

## Branch Workstreams

### Apollo MCP Client Seam

- Implement a concrete adapter wrapper around an injected MCP tool caller.
- Keep it compatible with `ApolloClientProtocol`.
- Add tests with fake MCP tool responses.

### Outreach Workflow

- Orchestrate role, fit score, Apollo contacts, outreach draft creation, Gmail draft creation, and tracking.
- Keep email draft creation approval-gated.
- Add tests with fake Apollo and Gmail clients.

### LaTeX Resume Workflow

- Implement safe LaTeX resume tailoring models and compile checks.
- Write tailored files to a new path by default.
- Add tests using temporary `.tex` files and fake compiler runners.

## Open Questions

- Exact Apollo MCP tool name and schema.
- Whether Apollo returns email confidence or verification status.
- Where the user's canonical resume file will live.
- Whether resume tailoring should use OpenAI later or remain deterministic first.
- Which CSV schema changes are needed for resume-tailoring events.
