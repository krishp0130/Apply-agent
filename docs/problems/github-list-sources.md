# GitHub List Sources Problem Log

## Assumptions

- The three supported repositories are `sndsh404/summer-2027-internships`, `vanshb03/Summer2027-Internships`, and `speedyapply/2027-SWE-College-Jobs`.
- Fetching is dependency-injected and receives raw Markdown URLs; this module does not perform network calls by default.
- `sndsh404/summer-2027-internships` exposes a README Markdown table with `Company`, `Role`, `Location`, `Apply`, and `Added` columns.
- `vanshb03/Summer2027-Internships` is parsed when its README contains a comparable Markdown table with company, title/role/position, location, and application columns.
- `speedyapply/2027-SWE-College-Jobs` is treated as an index README that links to `INTERN_USA.md`; roles are parsed from that target Markdown table.

## Repo-Specific Formats

- **sndsh404**: `Company` maps to `InternshipRole.company`, `Role` maps to `title`, `Location` maps to `location`, `Apply` provides the application URL when linked, and `Added` is preserved in `description`.
- **Vansh-style README**: `Company`, `Role`/`Title`/`Position`, `Location`, `Apply`/`Application`, optional date/status/notes columns, and optional sponsorship columns are supported.
- **SpeedyApply**: the README must contain a Markdown, GitHub blob, raw GitHub, or relative link to `INTERN_USA.md`; that file is fetched through the same injected fetcher and parsed as a table.

## Risks

- These public README table schemas may change without notice, reducing parsed roles or dropping fields.
- `InternshipRole` has no dedicated source URL or notes fields, so source URLs and row notes are preserved in `source` and `description`.
- Closed or non-link application cells are preserved as notes, not as application URLs.
- Markdown table parsing is intentionally conservative and does not infer missing company, title, term, sponsorship, or application data.
- Deduplication by company, title, and application URL may merge rows that differ only by note text.

## Next Problems

- Add parser diagnostics so tracking can record skipped tables, missing columns, and invalid links.
- Add source snapshots or fixtures from known repo versions to catch schema drift.
- Decide whether `InternshipRole` should gain explicit `source_url` and `source_notes` fields.
- Add an optional rate-limited HTTP fetcher that can be reused by HTML and Markdown sources.
- Add integration wiring if GitHub lists should be selectable through the generic source configuration layer.
