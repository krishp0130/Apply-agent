# CLI Status Problem Log

## Assumptions

- The local tracking directory uses the repository CSV filenames `roles.csv`, `contacts.csv`, `approvals.csv`, `outreach_drafts.csv`, and `application_events.csv`.
- Missing tracking files mean no rows have been recorded yet; they are reported rather than created.
- Approval state is derived from `ApprovalRow.approved`: `None` is requested, `True` is approved, and `False` is rejected.
- The default below-threshold role count uses a fit score threshold of `70`, matching the default scoring threshold in the core models.

## Known Gaps

- The CLI only has a read-only `status` command.
- Status output is aggregate-only; it does not show per-company or per-role detail.
- The tracking directory default is `data/tracking`, but no global project configuration file exists yet.
- Invalid CSV headers or malformed rows stop the report instead of producing a partial summary.

## Risks

- Future tracking filename changes will need matching updates in the status path mapping.
- Application event statuses are free-form strings, so inconsistent status names will appear as separate counts.
- Aggregate summaries can hide stale or duplicate rows until a richer audit command exists.

## Next Problems

- Add a shared project configuration source for tracking paths.
- Add a non-destructive detail view for roles requiring follow-up.
- Add validation diagnostics that identify malformed files without mutating them.
- Add documentation to the main README once CLI commands stabilize.
