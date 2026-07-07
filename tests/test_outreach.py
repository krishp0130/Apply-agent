from __future__ import annotations

import pytest

from internship_agent.outreach import (
    MissingEvidenceError,
    create_draft_payload,
    generate_outreach_draft,
)


VALID_EVIDENCE = {
    "sender_name": "Krish Patel",
    "recipient_name": "Avery Recruiter",
    "recipient_email": "avery@example.com",
    "company_name": "Example Robotics",
    "role_title": "Software Engineering Intern",
    "fit_evidence": "My Python automation project matches the role's tooling needs",
}


def test_generate_outreach_draft_is_deterministic_and_draft_only() -> None:
    first_draft = generate_outreach_draft(VALID_EVIDENCE)
    second_draft = generate_outreach_draft(VALID_EVIDENCE)

    assert first_draft == second_draft
    assert first_draft.to == "avery@example.com"
    assert first_draft.subject == (
        "Interest in Software Engineering Intern at Example Robotics"
    )
    assert first_draft.draft_only is True
    assert first_draft.send_allowed is False
    assert (
        "My Python automation project matches the role's tooling needs."
        in first_draft.body
    )


def test_draft_payload_cannot_send_email() -> None:
    draft = generate_outreach_draft(VALID_EVIDENCE)

    assert create_draft_payload(draft) == {
        "to": "avery@example.com",
        "subject": "Interest in Software Engineering Intern at Example Robotics",
        "body": draft.body,
        "draft_only": True,
        "send_allowed": False,
    }


def test_missing_required_evidence_refuses_to_draft() -> None:
    evidence = dict(VALID_EVIDENCE)
    evidence.pop("fit_evidence")

    with pytest.raises(MissingEvidenceError):
        generate_outreach_draft(evidence)


def test_unknown_placeholder_refuses_to_draft() -> None:
    evidence = dict(VALID_EVIDENCE, recipient_email="unknown")

    with pytest.raises(MissingEvidenceError):
        generate_outreach_draft(evidence)


def test_generic_fit_claim_refuses_to_draft() -> None:
    evidence = dict(VALID_EVIDENCE, fit_evidence="strong fit")

    with pytest.raises(MissingEvidenceError):
        generate_outreach_draft(evidence)
