"""Deterministic, draft-only outreach generation."""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


UNKNOWN_MARKERS = {
    "n/a",
    "na",
    "none",
    "not provided",
    "tbd",
    "todo",
    "unknown",
    "unspecified",
}

GENERIC_FIT_CLAIMS = {
    "great fit",
    "i am a great fit",
    "i am a strong fit",
    "passionate",
    "strong fit",
}


class MissingEvidenceError(ValueError):
    """Raised when outreach cannot be drafted from known evidence."""


class OutreachEvidence(BaseModel):
    """Known facts allowed to appear in an outreach draft."""

    model_config = ConfigDict(frozen=True)

    sender_name: str = Field(min_length=1)
    recipient_name: str = Field(min_length=1)
    recipient_email: str = Field(min_length=3)
    company_name: str = Field(min_length=1)
    role_title: str = Field(min_length=1)
    fit_evidence: str = Field(min_length=1)

    @field_validator(
        "sender_name",
        "recipient_name",
        "recipient_email",
        "company_name",
        "role_title",
        "fit_evidence",
    )
    @classmethod
    def _require_known_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or stripped.lower() in UNKNOWN_MARKERS:
            raise ValueError("Outreach evidence cannot be missing or unknown.")
        return stripped

    @field_validator("recipient_email")
    @classmethod
    def _validate_email_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("recipient_email must be a known email address.")
        return value

    @field_validator("fit_evidence")
    @classmethod
    def _require_specific_fit_evidence(cls, value: str) -> str:
        if value.lower() in GENERIC_FIT_CLAIMS:
            raise ValueError("fit_evidence must be concrete, not generic praise.")
        return value


class OutreachDraft(BaseModel):
    """Draft-only email content that is never authorized for sending."""

    model_config = ConfigDict(frozen=True)

    to: str
    subject: str
    body: str
    draft_only: Literal[True] = True
    send_allowed: Literal[False] = False
    evidence: OutreachEvidence


def generate_outreach_draft(
    evidence: OutreachEvidence | Mapping[str, Any],
) -> OutreachDraft:
    """Build a concise outreach draft using only supplied evidence."""

    known_evidence = _coerce_evidence(evidence)
    greeting_name = known_evidence.recipient_name.split()[0]
    fit_sentence = _as_sentence(known_evidence.fit_evidence)

    subject = (
        f"Interest in {known_evidence.role_title} at "
        f"{known_evidence.company_name}"
    )
    body = "\n\n".join(
        [
            f"Hi {greeting_name},",
            (
            f"I'm {known_evidence.sender_name}, and I'm interested in the "
                f"{known_evidence.role_title} role at "
                f"{known_evidence.company_name}. {fit_sentence}"
            ),
            (
                "Would you be open to pointing me toward the right internship "
                "recruiting process or sharing whether this team is considering "
                "interns?"
            ),
            f"Best,\n{known_evidence.sender_name}",
        ]
    )

    return OutreachDraft(
        to=known_evidence.recipient_email,
        subject=subject,
        body=body,
        evidence=known_evidence,
    )


def create_draft_payload(draft: OutreachDraft) -> dict[str, str | bool]:
    """Return a draft payload without any send capability."""

    return {
        "to": draft.to,
        "subject": draft.subject,
        "body": draft.body,
        "draft_only": draft.draft_only,
        "send_allowed": draft.send_allowed,
    }


def _coerce_evidence(
    evidence: OutreachEvidence | Mapping[str, Any],
) -> OutreachEvidence:
    if isinstance(evidence, OutreachEvidence):
        return evidence
    try:
        return OutreachEvidence.model_validate(evidence)
    except ValidationError as exc:
        raise MissingEvidenceError(
            "Cannot draft outreach without complete known evidence."
        ) from exc


def _as_sentence(value: str) -> str:
    if value.endswith((".", "!", "?")):
        return value
    return f"{value}."
