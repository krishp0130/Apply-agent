"""Draft-only Gmail adapter.

This module intentionally does not build or read credentials. Callers must
inject an already configured Gmail service client.
"""

from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from email.policy import SMTP
from typing import Any, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from internship_agent.approval import (
    ApprovalRequest,
    ProtectedAction,
    ensure_approved,
)


EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class GmailExecuteRequest(Protocol):
    """Executable Gmail API request."""

    def execute(self) -> Mapping[str, Any]:
        """Execute the request and return the Gmail API response."""


class GmailDraftsResource(Protocol):
    """Subset of Gmail drafts resource needed by this adapter."""

    def create(
        self,
        *,
        userId: str,
        body: Mapping[str, Any],
    ) -> GmailExecuteRequest:
        """Create a Gmail draft request."""


class GmailUsersResource(Protocol):
    """Subset of Gmail users resource needed by this adapter."""

    def drafts(self) -> GmailDraftsResource:
        """Return the drafts resource."""


class GmailServiceClient(Protocol):
    """Injected Gmail service client interface."""

    def users(self) -> GmailUsersResource:
        """Return the users resource."""


class GmailDraftMessage(BaseModel):
    """Validated outbound draft content."""

    model_config = ConfigDict(frozen=True)

    sender: str = Field(min_length=3)
    to: tuple[str, ...] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body_text: str = Field(min_length=1)
    reply_to: str | None = None

    @field_validator("sender", "reply_to")
    @classmethod
    def _validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not EMAIL_PATTERN.fullmatch(stripped):
            raise ValueError("Email fields must be valid email addresses.")
        return stripped

    @field_validator("to")
    @classmethod
    def _validate_recipients(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        stripped_values = tuple(value.strip() for value in values)
        if not stripped_values:
            raise ValueError("At least one recipient is required.")
        invalid_values = [
            value
            for value in stripped_values
            if not EMAIL_PATTERN.fullmatch(value)
        ]
        if invalid_values:
            raise ValueError("Recipients must be valid email addresses.")
        return stripped_values

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Subject cannot be blank.")
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("Subject cannot contain line breaks.")
        return stripped

    @field_validator("body_text")
    @classmethod
    def _validate_body_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Email body cannot be blank.")
        return stripped


class GmailDraftResult(BaseModel):
    """Result returned after creating a Gmail draft."""

    model_config = ConfigDict(frozen=True)

    draft_id: str | None = None
    message_id: str | None = None
    raw_message: str
    response: Mapping[str, Any]


class GmailDraftAdapter:
    """Create Gmail drafts through an injected service client only."""

    def __init__(
        self,
        service: GmailServiceClient,
        *,
        user_id: str = "me",
    ) -> None:
        self._service = service
        self._user_id = user_id

    def create_draft(
        self,
        message: GmailDraftMessage,
        *,
        approval: ApprovalRequest | None,
    ) -> GmailDraftResult:
        """Create a Gmail draft after SEND_EMAIL approval is confirmed."""

        ensure_approved(ProtectedAction.SEND_EMAIL, approval)
        raw_message = build_raw_mime_message(message)
        response = (
            self._service.users()
            .drafts()
            .create(
                userId=self._user_id,
                body={"message": {"raw": raw_message}},
            )
            .execute()
        )
        message_response = response.get("message")
        message_id = None
        if isinstance(message_response, Mapping):
            message_id_value = message_response.get("id")
            if isinstance(message_id_value, str):
                message_id = message_id_value

        draft_id_value = response.get("id")
        return GmailDraftResult(
            draft_id=draft_id_value if isinstance(draft_id_value, str) else None,
            message_id=message_id,
            raw_message=raw_message,
            response=response,
        )


def build_mime_message(message: GmailDraftMessage) -> EmailMessage:
    """Build an RFC 5322 text MIME message for a Gmail draft."""

    mime_message = EmailMessage(policy=SMTP)
    mime_message["From"] = message.sender
    mime_message["To"] = ", ".join(message.to)
    mime_message["Subject"] = message.subject
    if message.reply_to is not None:
        mime_message["Reply-To"] = message.reply_to
    mime_message.set_content(message.body_text)
    return mime_message


def build_raw_mime_message(message: GmailDraftMessage) -> str:
    """Return a base64url encoded MIME message for Gmail drafts.create."""

    return base64.urlsafe_b64encode(
        build_mime_message(message).as_bytes()
    ).decode("ascii")
