# Apollo MCP Client Seam

## Status

Implemented a concrete Apollo MCP client seam in
`src/internship_agent/apollo_mcp.py`. The seam satisfies the existing
`ApolloClientProtocol` by wrapping an injected async MCP tool caller.

## What Is Configurable

- MCP server name.
- MCP tool name.
- Query field mapping from `ApolloCompanyContactQuery` to tool arguments.
- Result list path for the tool response.
- Contact field mapping from returned dicts to `ApolloContactResult`.

## Details To Fill In Later

When real Apollo MCP credentials and schema are available, document:

- Exact MCP server name.
- Exact MCP tool name for company/person search.
- Required environment variables.
- Search input schema and supported filters.
- Result output schema and nested paths for people/contact objects.
- Rate limits, quota behavior, and retry constraints.
- Email confidence, verification, or deliverability fields.
- Required approval/review step before storing returned personal data.

## Safety Notes

- Tests use fake MCP callers only and make no network calls.
- Missing emails and profile URLs remain missing.
- Missing required contact names raise a clear normalization error.
- The seam does not submit applications, send emails, or store personal data.
