# Apollo Contact Scope

## Implemented Contract

- `ApolloClientProtocol` defines an injected async `search_company_contacts` method so the code does not assume any Apollo MCP tool is currently callable.
- `ApolloCompanyContactQuery` scopes searches to one company and carries optional role, domain, location, startup, target-role, and contact-limit inputs.
- `ApolloContactResult` accepts only returned contact facts and preserves missing emails or profile URLs as missing.
- `ApolloContactAdapter` classifies, ranks, and caps contacts using existing project priority rules, with a default maximum of three contacts per company.
- `OutreachTargetPlan` produces draft-only outreach/referral planning data and never grants email sending capability.

## Required Apollo MCP Capabilities

- Company-scoped people search by company name and, when available, company domain.
- Optional filters for title keywords, location, seniority, department, and employment status.
- Returned result metadata that identifies source provenance and Apollo record IDs when available.
- No side-effecting outreach action from the discovery endpoint.
- Clear pagination or result-limit controls so the caller can avoid over-collection.

## Required Data Fields

- Person name.
- Current company name.
- Current title.
- Work email, only when Apollo has an explicit verified or returned value.
- Public profile URL, only when Apollo returns one.
- Location, when available.
- Apollo/source record ID, when available.
- Source/provenance notes, including verification status when Apollo exposes it.

## Outreach Target Categories

The adapter maps titles into the project’s contact priority categories:

1. University recruiter.
2. Early talent recruiter.
3. Technical recruiter.
4. Engineering manager.
5. Software engineer.
6. Founder, only selected for small startups.

## Privacy and Compliance Risks

- Apollo data may include personal data; store only fields required for recruiting workflow tracking.
- Respect Apollo terms, user consent requirements, opt-out signals, and applicable privacy laws.
- Avoid bulk collection; company searches should use narrow queries and capped selections.
- Do not enrich, guess, or fabricate emails or profile URLs from names/domains.
- Do not send emails automatically; generated objects are draft/referral plans only.
- Preserve source and verification notes so the user can audit where contact data came from.

## Next Problems

- Build a concrete Apollo MCP client once the callable tool schema is known.
- Add tracking integration for selected contacts and outreach plans.
- Add user-visible review UI/CLI before creating Gmail drafts.
- Add source verification fields if Apollo exposes confidence or email status.
- Decide how to handle stale contacts and contact deletion requests in CSV tracking.
