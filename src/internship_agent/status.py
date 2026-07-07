"""Read-only status summaries for CSV-backed recruiting tracking files."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from internship_agent.tracking import (
    ApplicationEventRow,
    ApprovalRow,
    ContactRow,
    CsvRepository,
    OutreachDraftRow,
    RoleRow,
)

DEFAULT_TRACKING_DIR = Path("data/tracking")
DEFAULT_FIT_THRESHOLD = 70


@dataclass(frozen=True)
class TrackingPaths:
    """Paths for the known CSV tracking repositories."""

    roles: Path
    contacts: Path
    approvals: Path
    outreach_drafts: Path
    application_events: Path

    @classmethod
    def from_directory(cls, tracking_dir: Path) -> TrackingPaths:
        """Build conventional tracking file paths from a directory."""
        return cls(
            roles=tracking_dir / "roles.csv",
            contacts=tracking_dir / "contacts.csv",
            approvals=tracking_dir / "approvals.csv",
            outreach_drafts=tracking_dir / "outreach_drafts.csv",
            application_events=tracking_dir / "application_events.csv",
        )


class StatusSummary(BaseModel):
    """Aggregate counts from all known tracking repositories."""

    model_config = ConfigDict(extra="forbid")

    tracking_dir: str
    roles_total: int = 0
    roles_scored: int = 0
    roles_unscored: int = 0
    roles_below_threshold: int = 0
    contacts_total: int = 0
    outreach_drafts_total: int = 0
    outreach_draft_status_counts: dict[str, int] = Field(default_factory=dict)
    approvals_total: int = 0
    approvals_requested: int = 0
    approvals_approved: int = 0
    approvals_rejected: int = 0
    application_events_total: int = 0
    application_status_counts: dict[str, int] = Field(default_factory=dict)
    application_event_type_counts: dict[str, int] = Field(default_factory=dict)
    missing_files: list[str] = Field(default_factory=list)


def summarize_tracking_directory(
    tracking_dir: Path = DEFAULT_TRACKING_DIR,
    *,
    fit_threshold: int = DEFAULT_FIT_THRESHOLD,
) -> StatusSummary:
    """Load known CSV repositories and summarize their current local state."""
    paths = TrackingPaths.from_directory(tracking_dir)
    return summarize_tracking_paths(paths, fit_threshold=fit_threshold)


def summarize_tracking_paths(
    paths: TrackingPaths,
    *,
    fit_threshold: int = DEFAULT_FIT_THRESHOLD,
) -> StatusSummary:
    """Load known CSV repositories from explicit paths and summarize them."""
    roles = CsvRepository(paths.roles, RoleRow).list()
    contacts = CsvRepository(paths.contacts, ContactRow).list()
    approvals = CsvRepository(paths.approvals, ApprovalRow).list()
    outreach_drafts = CsvRepository(paths.outreach_drafts, OutreachDraftRow).list()
    application_events = CsvRepository(
        paths.application_events,
        ApplicationEventRow,
    ).list()

    approval_counts = _count_approval_states(approvals)

    return StatusSummary(
        tracking_dir=str(paths.roles.parent),
        roles_total=len(roles),
        roles_scored=sum(role.fit_score is not None for role in roles),
        roles_unscored=sum(role.fit_score is None for role in roles),
        roles_below_threshold=sum(
            role.fit_score is not None and role.fit_score < fit_threshold
            for role in roles
        ),
        contacts_total=len(contacts),
        outreach_drafts_total=len(outreach_drafts),
        outreach_draft_status_counts=_count_strings(
            draft.status for draft in outreach_drafts
        ),
        approvals_total=len(approvals),
        approvals_requested=approval_counts["requested"],
        approvals_approved=approval_counts["approved"],
        approvals_rejected=approval_counts["rejected"],
        application_events_total=len(application_events),
        application_status_counts=_count_strings(
            event.status for event in application_events
        ),
        application_event_type_counts=_count_strings(
            event.event_type for event in application_events
        ),
        missing_files=_missing_files(paths),
    )


def _count_approval_states(approvals: list[ApprovalRow]) -> dict[str, int]:
    counts = {"requested": 0, "approved": 0, "rejected": 0}
    for approval in approvals:
        if approval.approved is True:
            counts["approved"] += 1
        elif approval.approved is False:
            counts["rejected"] += 1
        else:
            counts["requested"] += 1
    return counts


def _count_strings(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(str(value) for value in values)
    return dict(sorted(counter.items()))


def _missing_files(paths: TrackingPaths) -> list[str]:
    known_paths = [
        paths.roles,
        paths.contacts,
        paths.approvals,
        paths.outreach_drafts,
        paths.application_events,
    ]
    return [path.name for path in known_paths if not path.exists()]
