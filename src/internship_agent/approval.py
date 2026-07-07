"""Approval gates for protected recruiting actions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProtectedAction(str, Enum):
    """Actions that must not happen without explicit human approval."""

    SEND_EMAIL = "send_email"
    SUBMIT_APPLICATION = "submit_application"
    DELETE_TRACKED_DATA = "delete_tracked_data"
    OVERWRITE_PROFILE = "overwrite_profile"
    APPLY_BELOW_THRESHOLD = "apply_below_threshold"


class ApprovalStatus(str, Enum):
    """Decision state for an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequiredError(RuntimeError):
    """Raised when a protected action is attempted without approval."""


PROTECTED_ACTION_REASONS: Final[dict[ProtectedAction, str]] = {
    ProtectedAction.SEND_EMAIL: "Sending email is externally visible.",
    ProtectedAction.SUBMIT_APPLICATION: "Submitting an application is irreversible.",
    ProtectedAction.DELETE_TRACKED_DATA: "Deleting tracked data can lose audit history.",
    ProtectedAction.OVERWRITE_PROFILE: "Overwriting profile information changes user data.",
    ProtectedAction.APPLY_BELOW_THRESHOLD: "Applying below the fit threshold needs user confirmation.",
}


class ApprovalRequest(BaseModel):
    """Human approval record for one protected action."""

    model_config = ConfigDict(frozen=True)

    action: ProtectedAction
    subject: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    decided_at: datetime | None = None
    decided_by: str | None = None
    notes: str | None = None

    @field_validator("subject", "reason")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Approval text fields cannot be blank.")
        return stripped

    @field_validator("decided_by", "notes")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _validate_decision_fields(self) -> ApprovalRequest:
        if self.status == ApprovalStatus.PENDING:
            if self.decided_at is not None or self.decided_by is not None:
                raise ValueError("Pending approvals cannot include decision metadata.")
            return self

        if self.decided_at is None:
            raise ValueError("Decided approvals must include decided_at.")
        if not self.decided_by:
            raise ValueError("Decided approvals must include decided_by.")
        return self

    @property
    def is_approved(self) -> bool:
        """Whether this request explicitly approves the action."""

        return self.status is ApprovalStatus.APPROVED

    def approve(
        self,
        *,
        decided_by: str,
        decided_at: datetime | None = None,
        notes: str | None = None,
    ) -> ApprovalRequest:
        """Return an approved copy of this request."""

        return ApprovalRequest.model_validate(
            {
                **self.model_dump(),
                "status": ApprovalStatus.APPROVED,
                "decided_at": decided_at or datetime.now(timezone.utc),
                "decided_by": decided_by,
                "notes": notes,
            }
        )

    def reject(
        self,
        *,
        decided_by: str,
        decided_at: datetime | None = None,
        notes: str | None = None,
    ) -> ApprovalRequest:
        """Return a rejected copy of this request."""

        return ApprovalRequest.model_validate(
            {
                **self.model_dump(),
                "status": ApprovalStatus.REJECTED,
                "decided_at": decided_at or datetime.now(timezone.utc),
                "decided_by": decided_by,
                "notes": notes,
            }
        )


def create_approval_request(
    action: ProtectedAction,
    *,
    subject: str,
    reason: str | None = None,
) -> ApprovalRequest:
    """Create a pending approval request for a protected action."""

    return ApprovalRequest(
        action=action,
        subject=subject,
        reason=reason or PROTECTED_ACTION_REASONS[action],
    )


def ensure_approved(
    action: ProtectedAction,
    approval: ApprovalRequest | None,
) -> ApprovalRequest:
    """Return approval when it permits action, otherwise raise."""

    if approval is None:
        raise ApprovalRequiredError(
            f"Approval is required before {action.value}."
        )
    if approval.action != action:
        raise ApprovalRequiredError(
            f"Approval for {approval.action.value} cannot authorize {action.value}."
        )
    if not approval.is_approved:
        raise ApprovalRequiredError(
            f"Approval for {action.value} is {approval.status.value}."
        )
    return approval


def required_application_actions(
    *,
    fit_score: int,
    minimum_fit_score: int,
) -> tuple[ProtectedAction, ...]:
    """Return approval gates needed before applying to a role."""

    if not 0 <= fit_score <= 100:
        raise ValueError("fit_score must be between 0 and 100.")
    if not 0 <= minimum_fit_score <= 100:
        raise ValueError("minimum_fit_score must be between 0 and 100.")

    actions = [ProtectedAction.SUBMIT_APPLICATION]
    if fit_score < minimum_fit_score:
        actions.append(ProtectedAction.APPLY_BELOW_THRESHOLD)
    return tuple(actions)
