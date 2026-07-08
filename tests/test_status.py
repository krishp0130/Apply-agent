from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from internship_agent.status import summarize_tracking_directory
from internship_agent.tracking import (
    ApplicationEventRow,
    ApprovalRow,
    ContactRow,
    CsvRepository,
    OutreachDraftRow,
    RoleRow,
)


def test_summarize_tracking_directory_counts_repository_rows(
    tmp_path: Path,
) -> None:
    tracking_dir = tmp_path / "tracking"
    CsvRepository(tracking_dir / "roles.csv", RoleRow).extend(
        [
            RoleRow(
                role_id="role-1",
                company_name="Example Co",
                role_title="Backend Intern",
                source="company site",
                date_discovered=date(2026, 7, 7),
                fit_score=82,
            ),
            RoleRow(
                role_id="role-2",
                company_name="Low Fit Co",
                role_title="Frontend Intern",
                source="company site",
                date_discovered=date(2026, 7, 7),
                fit_score=64,
            ),
            RoleRow(
                role_id="role-3",
                company_name="Unscored Co",
                role_title="Data Intern",
                source="job board",
                date_discovered=date(2026, 7, 7),
            ),
        ],
    )
    CsvRepository(tracking_dir / "contacts.csv", ContactRow).append(
        ContactRow(
            contact_id="contact-1",
            company_name="Example Co",
            full_name="Riley Recruiter",
            title="University Recruiter",
            source="apollo",
            date_found=date(2026, 7, 7),
        ),
    )
    CsvRepository(tracking_dir / "approvals.csv", ApprovalRow).extend(
        [
            ApprovalRow(
                approval_id="approval-1",
                action_type="send_email",
                target_id="draft-1",
                requested_at=datetime(2026, 7, 7, 10, 0),
                approved=None,
            ),
            ApprovalRow(
                approval_id="approval-2",
                action_type="submit_application",
                target_id="role-2",
                requested_at=datetime(2026, 7, 7, 11, 0),
                approved=False,
            ),
        ],
    )
    CsvRepository(tracking_dir / "outreach_drafts.csv", OutreachDraftRow).append(
        OutreachDraftRow(
            draft_id="draft-1",
            company_name="Example Co",
            subject="Internship interest",
            body="Hello",
            created_at=datetime(2026, 7, 7, 12, 0),
            status="draft_created",
        ),
    )
    CsvRepository(
        tracking_dir / "application_events.csv",
        ApplicationEventRow,
    ).extend(
        [
            ApplicationEventRow(
                event_id="event-1",
                role_id="role-1",
                event_type="application_started",
                occurred_at=datetime(2026, 7, 7, 13, 0),
                status="started_application",
            ),
            ApplicationEventRow(
                event_id="event-2",
                role_id="role-1",
                event_type="user_completed",
                occurred_at=datetime(2026, 7, 7, 14, 0),
                status="user_completed_application",
            ),
        ],
    )

    summary = summarize_tracking_directory(tracking_dir, fit_threshold=70)

    assert summary.roles_total == 3
    assert summary.roles_scored == 2
    assert summary.roles_unscored == 1
    assert summary.roles_below_threshold == 1
    assert summary.contacts_total == 1
    assert summary.approvals_requested == 1
    assert summary.approvals_rejected == 1
    assert summary.outreach_draft_status_counts == {"draft_created": 1}
    assert summary.application_status_counts == {
        "started_application": 1,
        "user_completed_application": 1,
    }
    assert summary.application_event_type_counts == {
        "application_started": 1,
        "user_completed": 1,
    }
    assert summary.missing_files == []


def test_summarize_tracking_directory_reports_missing_files(
    tmp_path: Path,
) -> None:
    summary = summarize_tracking_directory(tmp_path / "tracking")

    assert summary.roles_total == 0
    assert summary.missing_files == [
        "roles.csv",
        "contacts.csv",
        "approvals.csv",
        "outreach_drafts.csv",
        "application_events.csv",
    ]
