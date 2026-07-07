from __future__ import annotations

from datetime import datetime, timezone

import pytest

from internship_agent.approval import (
    ApprovalRequiredError,
    ApprovalStatus,
    ProtectedAction,
    create_approval_request,
    ensure_approved,
    required_application_actions,
)


def test_pending_protected_action_requires_approval() -> None:
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Email recruiter@example.com",
    )

    assert approval.status is ApprovalStatus.PENDING
    with pytest.raises(ApprovalRequiredError):
        ensure_approved(ProtectedAction.SEND_EMAIL, approval)


def test_approved_matching_action_is_allowed() -> None:
    requested_at = datetime(2026, 7, 7, tzinfo=timezone.utc)
    approval = create_approval_request(
        ProtectedAction.DELETE_TRACKED_DATA,
        subject="Delete duplicate outreach row",
    ).approve(decided_by="Krish", decided_at=requested_at)

    assert ensure_approved(ProtectedAction.DELETE_TRACKED_DATA, approval) == approval


def test_mismatched_approval_does_not_authorize_other_action() -> None:
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Email recruiter@example.com",
    ).approve(
        decided_by="Krish",
        decided_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
    )

    with pytest.raises(ApprovalRequiredError):
        ensure_approved(ProtectedAction.SUBMIT_APPLICATION, approval)


def test_required_application_actions_include_low_fit_gate() -> None:
    assert required_application_actions(
        fit_score=82,
        minimum_fit_score=70,
    ) == (ProtectedAction.SUBMIT_APPLICATION,)

    assert required_application_actions(
        fit_score=40,
        minimum_fit_score=70,
    ) == (
        ProtectedAction.SUBMIT_APPLICATION,
        ProtectedAction.APPLY_BELOW_THRESHOLD,
    )
