# Internship Application Agent Specification

## Goal

Build a reliable local AI recruiting assistant that helps with internship recruiting while keeping the user fully in control of all final actions.

The system should assist with:

- Finding internships.
- Scoring internships.
- Finding recruiter or hiring contacts.
- Drafting personalized outreach.
- Tracking applications and outreach.
- Assisting with application forms.

## Non-Goals

The system must not:

- Fabricate user information.
- Fabricate recruiter information.
- Fabricate application answers.
- Submit applications automatically.
- Send emails automatically.
- Bypass CAPTCHAs, MFA, login prompts, or other security controls.

## Human Control Requirements

The user must approve every irreversible or externally visible action before it happens.

The system must request confirmation before:

- Sending any email.
- Submitting any application.
- Deleting tracked data.
- Overwriting profile information.
- Applying to a role with a fit score below the configured threshold.

## Core Workflows

### Internship Discovery

The system should find internship roles from configured sources and store meaningful results in tracking CSV files.

Each discovered role should include, when available:

- Company name.
- Role title.
- Location or remote status.
- Application URL.
- Source.
- Date discovered.
- Internship term.
- Required skills.
- Notes or extracted job summary.

### Role Scoring

The system should score roles against the user's profile without exaggerating fit.

Scores should be explainable and based on available evidence, such as:

- Skills match.
- Experience match.
- Location fit.
- Internship term fit.
- Sponsorship or eligibility constraints, when known.
- User preferences.

The system must preserve the reasoning behind each score in tracked data.

### Contact Discovery

The system should identify relevant contacts for companies with tracked roles.

When multiple contacts are available, prioritize:

1. University Recruiter
2. Early Talent Recruiter
3. Technical Recruiter
4. Engineering Manager
5. Software Engineer
6. Founder, for small startups

The system must not contact more than three people per company unless instructed.

### Outreach Drafting

The system should draft concise, personalized outreach emails.

Emails should:

- Mention one concrete reason for fit.
- Avoid buzzwords.
- Avoid sounding mass-generated.
- Avoid exaggerating qualifications.
- Use only known user and role information.

The system may create Gmail drafts, but it must never send emails automatically.

### Application Assistance

The system should help complete application forms using known user profile data.

Browser automation should:

- Fill known fields.
- Upload the resume when requested.
- Pause for CAPTCHAs, login prompts, or MFA.
- Stop on the review page before submission.

The system must never submit an application automatically.

### CSV Tracking

Every meaningful action should be persisted to tracking CSV files.

Tracked state should include, where relevant:

- Discovered roles.
- Fit scores and reasoning.
- Contacts found.
- Outreach drafts created.
- Applications started.
- Applications completed by the user.
- User approvals.
- Follow-up reminders or next actions.

Nothing important should exist only in memory.

## Data Integrity Rules

- Do not invent missing data.
- Mark unknown fields explicitly instead of guessing.
- Keep source URLs or source notes when available.
- Do not overwrite profile information without approval.
- Log meaningful actions for auditability.

## Implementation Guidelines

- Use Python 3.12+.
- Keep business logic separated into modules.
- Use Pydantic models for structured data.
- Use pandas for CSV-backed tracking where appropriate.
- Use Playwright for browser automation.
- Use Gmail API only to create drafts unless the user explicitly approves sending.
- Use environment variables for secrets.
- Use logging instead of `print()`.
- Prefer async implementations where appropriate.
- Add unit tests for scoring, tracking, parsing, and approval-gate behavior where practical.
