from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import pytest

from internship_agent.apollo import (
    ApolloCompanyContactQuery,
    ApolloContactAdapter,
    ApolloContactResult,
)
from internship_agent.approval import (
    ApprovalRequiredError,
    ProtectedAction,
    create_approval_request,
)
from internship_agent.gmail import GmailDraftMessage, GmailDraftResult
from internship_agent.models import FitScore, InternshipRole, UserProfile
from internship_agent.tracking import (
    ApplicationEventRow,
    ApprovalRow,
    ContactRow,
    OutreachDraftRow,
)
from internship_agent.workflows import (
    OutreachWorkflowRepositories,
    run_recruiter_outreach_workflow,
)


class FakeApolloClient:
    def __init__(
        self,
        results: Sequence[ApolloContactResult | Mapping[str, Any]],
    ) -> None:
        self.results = results
        self.queries: list[ApolloCompanyContactQuery] = []

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery,
    ) -> Sequence[ApolloContactResult | Mapping[str, Any]]:
        self.queries.append(query)
        return self.results


class FakeGmailDraftCreator:
    def __init__(self) -> None:
        self.messages: list[GmailDraftMessage] = []

    def create_draft(
        self,
        message: GmailDraftMessage,
        *,
        approval: object,
    ) -> GmailDraftResult:
        self.messages.append(message)
        return GmailDraftResult(
            draft_id=f"gmail-draft-{len(self.messages)}",
            message_id=f"message-{len(self.messages)}",
            raw_message="raw-message",
            response={"id": f"gmail-draft-{len(self.messages)}"},
        )

    def send(self) -> None:
        raise AssertionError("Workflow must never send email.")


class FakeRepository:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def append(self, row: object) -> None:
        self.rows.append(row)


def test_outreach_workflow_searches_contacts_caps_targets_and_drafts_when_safe() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Sam Engineer",
                "title": "Software Engineer",
                "email": "sam@example.com",
            },
            {
                "name": "Tara Recruiter",
                "title": "Technical Recruiter",
                "email": "tara@example.com",
            },
            {
                "name": "Uma Campus",
                "title": "University Recruiter",
            },
            {
                "name": "Eli Early",
                "title": "Early Talent Recruiter",
                "email": "eli@example.com",
            },
        ]
    )
    adapter = ApolloContactAdapter(client)

    result = asyncio.run(
        run_recruiter_outreach_workflow(
            role=_role(),
            fit="My Python automation project matches the role's tooling needs",
            sender={"name": "Krish Patel", "email": "krish@example.com"},
            apollo=adapter,
        )
    )

    assert client.queries[0] == ApolloCompanyContactQuery(
        company_name="Example Robotics",
        role_title="Software Engineering Intern",
        location="Remote",
        max_contacts=3,
    )
    assert [target.recipient_name for target in result.selected_targets] == [
        "Uma Campus",
        "Eli Early",
        "Tara Recruiter",
    ]
    assert [draft.draft.to for draft in result.planned_drafts] == [
        "eli@example.com",
        "tara@example.com",
    ]
    assert [skip.reason for skip in result.skipped_targets] == ["missing_email"]
    assert all(draft.draft.draft_only for draft in result.planned_drafts)
    assert all(not draft.draft.send_allowed for draft in result.planned_drafts)
    assert result.gmail_drafts == ()


def test_fit_score_reason_can_supply_concrete_evidence() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Avery Recruiter",
                "title": "Technical Recruiter",
                "email": "avery@example.com",
            }
        ]
    )
    fit = FitScore(
        company="Example Robotics",
        role_title="Software Engineering Intern",
        score=84,
        reasons=["Matches required skills: python, playwright."],
    )

    result = asyncio.run(
        run_recruiter_outreach_workflow(
            role=_role(),
            fit=fit,
            sender=UserProfile(name="Krish Patel", email="krish@example.com"),
            apollo=ApolloContactAdapter(client),
        )
    )

    assert len(result.planned_drafts) == 1
    assert "Matches required skills" in result.planned_drafts[0].draft.body


def test_missing_or_generic_fit_evidence_prevents_local_and_gmail_drafts() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Avery Recruiter",
                "title": "Technical Recruiter",
                "email": "avery@example.com",
            }
        ]
    )
    gmail = FakeGmailDraftCreator()
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Create Gmail draft",
    ).approve(decided_by="Krish")

    result = asyncio.run(
        run_recruiter_outreach_workflow(
            role=_role(),
            fit="strong fit",
            sender={"name": "Krish Patel", "email": "krish@example.com"},
            apollo=ApolloContactAdapter(client),
            gmail=gmail,
            gmail_approval=approval,
        )
    )

    assert result.planned_drafts == ()
    assert result.gmail_drafts == ()
    assert gmail.messages == []
    assert [skip.reason for skip in result.skipped_targets] == [
        "invalid_or_generic_fit_evidence"
    ]


def test_gmail_draft_creation_requires_approved_send_email_approval() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Avery Recruiter",
                "title": "Technical Recruiter",
                "email": "avery@example.com",
            }
        ]
    )
    gmail = FakeGmailDraftCreator()

    with pytest.raises(ApprovalRequiredError):
        asyncio.run(
            run_recruiter_outreach_workflow(
                role=_role(),
                fit="My Python automation project matches the role's tooling needs",
                sender={"name": "Krish Patel", "email": "krish@example.com"},
                apollo=ApolloContactAdapter(client),
                gmail=gmail,
            )
        )

    assert gmail.messages == []


def test_approved_gmail_creation_uses_drafts_only_and_never_sends() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Avery Recruiter",
                "title": "Technical Recruiter",
                "email": "avery@example.com",
            }
        ]
    )
    gmail = FakeGmailDraftCreator()
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Create Gmail draft for avery@example.com",
    ).approve(decided_by="Krish")

    result = asyncio.run(
        run_recruiter_outreach_workflow(
            role=_role(),
            fit="My Python automation project matches the role's tooling needs",
            sender={
                "name": "Krish Patel",
                "email": "krish@example.com",
                "reply_to": "krish.personal@example.com",
            },
            apollo=ApolloContactAdapter(client),
            gmail=gmail,
            gmail_approval=approval,
        )
    )

    assert len(result.gmail_drafts) == 1
    assert gmail.messages[0].sender == "krish@example.com"
    assert gmail.messages[0].to == ("avery@example.com",)
    assert gmail.messages[0].reply_to == "krish.personal@example.com"


def test_tracking_repositories_receive_contacts_drafts_approvals_and_events() -> None:
    client = FakeApolloClient(
        [
            {
                "name": "Avery Recruiter",
                "title": "Technical Recruiter",
                "email": "avery@example.com",
                "profile_url": "https://example.com/avery",
            }
        ]
    )
    contacts = FakeRepository()
    drafts = FakeRepository()
    approvals = FakeRepository()
    events = FakeRepository()
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Create Gmail draft for avery@example.com",
    ).approve(decided_by="Krish")

    asyncio.run(
        run_recruiter_outreach_workflow(
            role=_role(),
            fit="My Python automation project matches the role's tooling needs",
            sender={"name": "Krish Patel", "email": "krish@example.com"},
            apollo=ApolloContactAdapter(client),
            gmail=FakeGmailDraftCreator(),
            gmail_approval=approval,
            repositories=OutreachWorkflowRepositories(
                contacts=contacts,
                outreach_drafts=drafts,
                approvals=approvals,
                application_events=events,
            ),
            now=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert len(contacts.rows) == 1
    assert isinstance(contacts.rows[0], ContactRow)
    assert contacts.rows[0].email == "avery@example.com"
    assert len(drafts.rows) == 1
    assert isinstance(drafts.rows[0], OutreachDraftRow)
    assert drafts.rows[0].status == "draft_created"
    assert len(approvals.rows) == 1
    assert isinstance(approvals.rows[0], ApprovalRow)
    assert approvals.rows[0].action_type == "send_email"
    assert approvals.rows[0].approved is True
    assert [event.event_type for event in events.rows if isinstance(event, ApplicationEventRow)] == [
        "outreach_contacts_selected",
        "outreach_drafts_created",
        "gmail_drafts_created",
    ]


def _role() -> InternshipRole:
    return InternshipRole(
        company="Example Robotics",
        title="Software Engineering Intern",
        source="company careers page",
        location="Remote",
        required_skills=["Python", "Playwright"],
    )
