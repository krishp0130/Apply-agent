from __future__ import annotations

import base64
from email.parser import BytesParser
from email.policy import default
from typing import Any, Mapping

import pytest

from internship_agent.approval import (
    ApprovalRequiredError,
    ProtectedAction,
    create_approval_request,
)
from internship_agent.gmail import (
    GmailDraftAdapter,
    GmailDraftMessage,
    build_raw_mime_message,
)


class FakeExecuteRequest:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = response

    def execute(self) -> Mapping[str, Any]:
        return self._response


class FakeDraftsResource:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []

    def create(
        self,
        *,
        userId: str,
        body: Mapping[str, Any],
    ) -> FakeExecuteRequest:
        self.create_calls.append({"userId": userId, "body": body})
        return FakeExecuteRequest({"id": "draft-123", "message": {"id": "msg-456"}})

    def send(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("GmailDraftAdapter must never send mail.")


class FakeUsersResource:
    def __init__(self, drafts_resource: FakeDraftsResource) -> None:
        self._drafts_resource = drafts_resource

    def drafts(self) -> FakeDraftsResource:
        return self._drafts_resource

    def messages(self) -> object:
        raise AssertionError("GmailDraftAdapter must never use messages.send.")


class FakeGmailService:
    def __init__(self) -> None:
        self.drafts_resource = FakeDraftsResource()

    def users(self) -> FakeUsersResource:
        return FakeUsersResource(self.drafts_resource)


def test_build_raw_mime_message_contains_expected_headers() -> None:
    message = GmailDraftMessage(
        sender="krish@example.com",
        to=("avery@example.com",),
        subject="Interest in internship",
        body_text="Thanks for taking a look.",
        reply_to="krish.personal@example.com",
    )

    parsed_message = _decode_raw_message(build_raw_mime_message(message))

    assert parsed_message["From"] == "krish@example.com"
    assert parsed_message["To"] == "avery@example.com"
    assert parsed_message["Subject"] == "Interest in internship"
    assert parsed_message["Reply-To"] == "krish.personal@example.com"
    assert parsed_message.get_content().strip() == "Thanks for taking a look."


def test_create_draft_requires_approved_send_email_gate() -> None:
    service = FakeGmailService()
    adapter = GmailDraftAdapter(service)
    message = GmailDraftMessage(
        sender="krish@example.com",
        to=("avery@example.com",),
        subject="Interest in internship",
        body_text="Thanks for taking a look.",
    )

    with pytest.raises(ApprovalRequiredError):
        adapter.create_draft(message, approval=None)

    pending_approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Create Gmail draft for avery@example.com",
    )
    with pytest.raises(ApprovalRequiredError):
        adapter.create_draft(message, approval=pending_approval)

    assert service.drafts_resource.create_calls == []


def test_create_draft_uses_injected_service_and_drafts_create_only() -> None:
    service = FakeGmailService()
    adapter = GmailDraftAdapter(service, user_id="me")
    message = GmailDraftMessage(
        sender="krish@example.com",
        to=("avery@example.com",),
        subject="Interest in internship",
        body_text="Thanks for taking a look.",
    )
    approval = create_approval_request(
        ProtectedAction.SEND_EMAIL,
        subject="Create Gmail draft for avery@example.com",
    ).approve(decided_by="Krish")

    result = adapter.create_draft(message, approval=approval)

    assert result.draft_id == "draft-123"
    assert result.message_id == "msg-456"
    assert len(service.drafts_resource.create_calls) == 1
    create_call = service.drafts_resource.create_calls[0]
    assert create_call["userId"] == "me"
    assert create_call["body"] == {"message": {"raw": result.raw_message}}
    parsed_message = _decode_raw_message(result.raw_message)
    assert parsed_message["From"] == "krish@example.com"
    assert parsed_message["To"] == "avery@example.com"


def test_gmail_draft_message_rejects_header_injection() -> None:
    with pytest.raises(ValueError):
        GmailDraftMessage(
            sender="krish@example.com",
            to=("avery@example.com",),
            subject="Hello\nBcc: hidden@example.com",
            body_text="Thanks for taking a look.",
        )


def _decode_raw_message(raw_message: str) -> Any:
    return BytesParser(policy=default).parsebytes(
        base64.urlsafe_b64decode(raw_message.encode("ascii"))
    )
