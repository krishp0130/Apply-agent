"""Safe recruiter outreach orchestration workflows."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from internship_agent.apollo import (
    DEFAULT_CONTACT_LIMIT,
    ApolloCompanyContactQuery,
    ApolloContactSearchPlan,
    OutreachTargetPlan,
)
from internship_agent.approval import (
    ApprovalRequest,
    ProtectedAction,
    ensure_approved,
)
from internship_agent.contacts import CONTACT_PRIORITY
from internship_agent.gmail import (
    GmailDraftMessage,
    GmailDraftResult,
)
from internship_agent.models import FitScore, InternshipRole, UserProfile
from internship_agent.outreach import (
    MissingEvidenceError,
    OutreachDraft,
    generate_outreach_draft,
)
from internship_agent.tracking import (
    ApplicationEventRow,
    ApprovalRow,
    ContactRow,
    OutreachDraftRow,
)


UNKNOWN_TEXT = {
    "",
    "n/a",
    "na",
    "none",
    "not provided",
    "tbd",
    "todo",
    "unknown",
    "unspecified",
}


class ApolloContactSearcher(Protocol):
    """ApolloContactAdapter-compatible contact search boundary."""

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery,
    ) -> ApolloContactSearchPlan:
        """Search Apollo for company contacts."""


class GmailDraftCreator(Protocol):
    """Draft-only Gmail creation boundary."""

    def create_draft(
        self,
        message: GmailDraftMessage,
        *,
        approval: ApprovalRequest | None,
    ) -> GmailDraftResult:
        """Create a Gmail draft without sending it."""


class ContactRepository(Protocol):
    """Repository that appends contact tracking rows."""

    def append(self, row: ContactRow) -> None:
        """Append a contact row."""


class OutreachDraftRepository(Protocol):
    """Repository that appends outreach draft tracking rows."""

    def append(self, row: OutreachDraftRow) -> None:
        """Append an outreach draft row."""


class ApprovalRepository(Protocol):
    """Repository that appends approval tracking rows."""

    def append(self, row: ApprovalRow) -> None:
        """Append an approval row."""


class ApplicationEventRepository(Protocol):
    """Repository that appends application event tracking rows."""

    def append(self, row: ApplicationEventRow) -> None:
        """Append an application event row."""


@dataclass(frozen=True)
class OutreachWorkflowRepositories:
    """Optional tracking repositories for outreach workflow side effects."""

    contacts: ContactRepository | None = None
    outreach_drafts: OutreachDraftRepository | None = None
    approvals: ApprovalRepository | None = None
    application_events: ApplicationEventRepository | None = None


class SenderInfo(BaseModel):
    """Known sender facts allowed in outreach drafts."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    email: str | None = None
    reply_to: str | None = None

    @field_validator("name", "email", "reply_to")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return None if stripped.lower() in UNKNOWN_TEXT else stripped


class SkippedOutreachTarget(BaseModel):
    """Selected target skipped before draft creation with the safe reason."""

    model_config = ConfigDict(frozen=True)

    target: OutreachTargetPlan
    reason: str


class PlannedOutreachDraft(BaseModel):
    """Draft content prepared for review and optional Gmail draft creation."""

    model_config = ConfigDict(frozen=True)

    target: OutreachTargetPlan
    draft: OutreachDraft
    draft_id: str


class GmailDraftCreation(BaseModel):
    """Gmail draft creation result tied to the planned local draft."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    result: GmailDraftResult


class RecruiterOutreachWorkflowResult(BaseModel):
    """Complete outcome of the safe recruiter outreach workflow."""

    model_config = ConfigDict(frozen=True)

    search_plan: ApolloContactSearchPlan
    selected_targets: tuple[OutreachTargetPlan, ...]
    planned_drafts: tuple[PlannedOutreachDraft, ...]
    skipped_targets: tuple[SkippedOutreachTarget, ...]
    gmail_drafts: tuple[GmailDraftCreation, ...] = ()


async def run_recruiter_outreach_workflow(
    *,
    role: InternshipRole,
    fit: FitScore | str,
    sender: SenderInfo | UserProfile | Mapping[str, Any],
    apollo: ApolloContactSearcher,
    gmail: GmailDraftCreator | None = None,
    gmail_approval: ApprovalRequest | None = None,
    repositories: OutreachWorkflowRepositories | None = None,
    company_domain: str | None = None,
    small_startup: bool = False,
    max_contacts: int = DEFAULT_CONTACT_LIMIT,
    now: datetime | None = None,
) -> RecruiterOutreachWorkflowResult:
    """Find contacts, prepare safe draft-only outreach, and optionally draft in Gmail.

    Gmail draft creation is treated as protected by the SEND_EMAIL approval gate,
    but this workflow never sends email.
    """

    sender_info = _coerce_sender(sender)
    current_time = now or datetime.now(timezone.utc)
    effective_limit = min(max_contacts, DEFAULT_CONTACT_LIMIT)
    fit_evidence = _resolve_fit_evidence(fit)

    query = ApolloCompanyContactQuery(
        company_name=role.company,
        role_title=role.title,
        company_domain=company_domain,
        location=role.location,
        small_startup=small_startup,
        max_contacts=effective_limit,
    )
    search_plan = await apollo.search_company_contacts(query)
    selected_targets = search_plan.outreach_targets[:effective_limit]

    _track_selected_contacts(
        repositories,
        role,
        search_plan,
        selected_targets,
        current_time,
    )

    planned_drafts, skipped_targets = _build_planned_drafts(
        role=role,
        sender=sender_info,
        fit_evidence=fit_evidence,
        targets=selected_targets,
    )
    _track_planned_drafts(repositories, role, planned_drafts, current_time)

    gmail_drafts: tuple[GmailDraftCreation, ...] = ()
    if gmail is not None and planned_drafts:
        approved_request = ensure_approved(
            ProtectedAction.SEND_EMAIL,
            gmail_approval,
        )
        _track_approval(
            repositories,
            approval=approved_request,
            target_id=_role_id(role),
            current_time=current_time,
        )
        gmail_drafts = tuple(
            _create_gmail_draft(
                gmail,
                sender_info,
                planned_draft,
                approved_request,
            )
            for planned_draft in planned_drafts
        )
        _track_gmail_draft_events(
            repositories,
            role,
            gmail_drafts,
            current_time,
        )
    elif gmail_approval is not None:
        _track_approval(
            repositories,
            approval=gmail_approval,
            target_id=_role_id(role),
            current_time=current_time,
        )

    return RecruiterOutreachWorkflowResult(
        search_plan=search_plan,
        selected_targets=selected_targets,
        planned_drafts=planned_drafts,
        skipped_targets=skipped_targets,
        gmail_drafts=gmail_drafts,
    )


def _coerce_sender(
    sender: SenderInfo | UserProfile | Mapping[str, Any],
) -> SenderInfo:
    if isinstance(sender, SenderInfo):
        return sender
    if isinstance(sender, UserProfile):
        return SenderInfo(name=sender.name, email=sender.email)
    return SenderInfo.model_validate(sender)


def _resolve_fit_evidence(fit: FitScore | str) -> str | None:
    if isinstance(fit, str):
        return _known_text_or_none(fit)

    for reason in fit.reasons:
        known_reason = _known_text_or_none(reason)
        if known_reason is not None:
            return known_reason
    return None


def _build_planned_drafts(
    *,
    role: InternshipRole,
    sender: SenderInfo,
    fit_evidence: str | None,
    targets: tuple[OutreachTargetPlan, ...],
) -> tuple[tuple[PlannedOutreachDraft, ...], tuple[SkippedOutreachTarget, ...]]:
    planned_drafts: list[PlannedOutreachDraft] = []
    skipped_targets: list[SkippedOutreachTarget] = []

    for target in targets:
        if fit_evidence is None:
            skipped_targets.append(
                SkippedOutreachTarget(
                    target=target,
                    reason="missing_concrete_fit_evidence",
                )
            )
            continue

        evidence = target.to_outreach_evidence(
            sender_name=sender.name,
            role_title=role.title,
            fit_evidence=fit_evidence,
        )
        if evidence is None:
            skipped_targets.append(
                SkippedOutreachTarget(target=target, reason="missing_email")
            )
            continue

        try:
            draft = generate_outreach_draft(evidence)
        except MissingEvidenceError:
            skipped_targets.append(
                SkippedOutreachTarget(
                    target=target,
                    reason="invalid_or_generic_fit_evidence",
                )
            )
            continue

        planned_drafts.append(
            PlannedOutreachDraft(
                target=target,
                draft=draft,
                draft_id=_draft_id(role, target),
            )
        )

    return tuple(planned_drafts), tuple(skipped_targets)


def _create_gmail_draft(
    gmail: GmailDraftCreator,
    sender: SenderInfo,
    planned_draft: PlannedOutreachDraft,
    approval: ApprovalRequest,
) -> GmailDraftCreation:
    if sender.email is None:
        raise ValueError("sender.email is required to create Gmail drafts.")

    result = gmail.create_draft(
        GmailDraftMessage(
            sender=sender.email,
            to=(planned_draft.draft.to,),
            subject=planned_draft.draft.subject,
            body_text=planned_draft.draft.body,
            reply_to=sender.reply_to,
        ),
        approval=approval,
    )
    return GmailDraftCreation(draft_id=planned_draft.draft_id, result=result)


def _track_selected_contacts(
    repositories: OutreachWorkflowRepositories | None,
    role: InternshipRole,
    search_plan: ApolloContactSearchPlan,
    selected_targets: tuple[OutreachTargetPlan, ...],
    current_time: datetime,
) -> None:
    if repositories is None:
        return

    if repositories.contacts is not None:
        for contact in search_plan.selected_contacts[: len(selected_targets)]:
            repositories.contacts.append(
                ContactRow(
                    contact_id=_contact_id(contact.company, contact.name, contact.email),
                    company_name=contact.company,
                    full_name=contact.name,
                    title=contact.title or "unknown",
                    source=contact.source or "unknown",
                    date_found=current_time.date(),
                    profile_url=(
                        str(contact.profile_url) if contact.profile_url else "unknown"
                    ),
                    email=contact.email or "unknown",
                    priority=CONTACT_PRIORITY[contact.role],
                    notes=contact.notes or "",
                )
            )

    if repositories.application_events is not None and selected_targets:
        repositories.application_events.append(
            ApplicationEventRow(
                event_id=_event_id(
                    search_plan.query.company_name,
                    "outreach_contacts_selected",
                    current_time,
                ),
                role_id=_role_id(role),
                event_type="outreach_contacts_selected",
                occurred_at=current_time,
                status="completed",
                notes=f"Selected {len(selected_targets)} Apollo contact(s).",
            )
        )


def _track_planned_drafts(
    repositories: OutreachWorkflowRepositories | None,
    role: InternshipRole,
    planned_drafts: tuple[PlannedOutreachDraft, ...],
    current_time: datetime,
) -> None:
    if repositories is None:
        return

    if repositories.outreach_drafts is not None:
        for planned_draft in planned_drafts:
            repositories.outreach_drafts.append(
                OutreachDraftRow(
                    draft_id=planned_draft.draft_id,
                    company_name=role.company,
                    subject=planned_draft.draft.subject,
                    body=planned_draft.draft.body,
                    created_at=current_time,
                    contact_id=_target_contact_id(planned_draft.target),
                    role_id=_role_id(role),
                    status="draft_created",
                    notes="Draft content generated locally; not sent.",
                )
            )

    if repositories.application_events is not None and planned_drafts:
        repositories.application_events.append(
            ApplicationEventRow(
                event_id=_event_id(role.company, "outreach_drafts_created", current_time),
                role_id=_role_id(role),
                event_type="outreach_drafts_created",
                occurred_at=current_time,
                status="completed",
                notes=f"Generated {len(planned_drafts)} draft-only outreach email(s).",
            )
        )


def _track_approval(
    repositories: OutreachWorkflowRepositories | None,
    *,
    approval: ApprovalRequest,
    target_id: str,
    current_time: datetime,
) -> None:
    if repositories is None or repositories.approvals is None:
        return

    repositories.approvals.append(
        ApprovalRow(
            approval_id=_approval_id(approval, target_id),
            action_type=approval.action.value,
            target_id=target_id,
            requested_at=approval.requested_at,
            approved=approval.is_approved,
            approved_at=approval.decided_at,
            notes=approval.notes or f"Approval tracked at {current_time.isoformat()}.",
        )
    )


def _track_gmail_draft_events(
    repositories: OutreachWorkflowRepositories | None,
    role: InternshipRole,
    gmail_drafts: tuple[GmailDraftCreation, ...],
    current_time: datetime,
) -> None:
    if (
        repositories is None
        or repositories.application_events is None
        or not gmail_drafts
    ):
        return

    repositories.application_events.append(
        ApplicationEventRow(
            event_id=_event_id(role.company, "gmail_drafts_created", current_time),
            role_id=_role_id(role),
            event_type="gmail_drafts_created",
            occurred_at=current_time,
            status="completed",
            notes=f"Created {len(gmail_drafts)} Gmail draft(s); none sent.",
        )
    )


def _known_text_or_none(value: str) -> str | None:
    stripped = value.strip()
    if stripped.lower() in UNKNOWN_TEXT:
        return None
    return stripped


def _role_id(role: InternshipRole) -> str:
    return _stable_id(
        "role",
        role.company,
        role.title,
        str(role.application_url or ""),
        role.source,
    )


def _contact_id(company: str, name: str, email: str | None) -> str:
    return _stable_id("contact", company, name, email or "")


def _target_contact_id(target: OutreachTargetPlan) -> str:
    return _contact_id(
        target.company,
        target.recipient_name,
        target.recipient_email,
    )


def _draft_id(role: InternshipRole, target: OutreachTargetPlan) -> str:
    return _stable_id(
        "draft",
        role.company,
        role.title,
        target.recipient_name,
        target.recipient_email or "",
    )


def _approval_id(approval: ApprovalRequest, target_id: str) -> str:
    return _stable_id(
        "approval",
        approval.action.value,
        target_id,
        approval.requested_at.isoformat(),
    )


def _event_id(company: str, event_type: str, current_time: datetime) -> str:
    return _stable_id("event", company, event_type, current_time.isoformat())


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(
        "\x1f".join(parts).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"
