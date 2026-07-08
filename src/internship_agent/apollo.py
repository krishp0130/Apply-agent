"""Apollo MCP contact discovery adapter contract.

This module intentionally does not import or call a concrete Apollo MCP tool.
A future MCP client can satisfy ``ApolloClientProtocol`` and be injected into
``ApolloContactAdapter``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from internship_agent.contacts import rank_contacts
from internship_agent.models import Contact, ContactRole, UnknownAwareModel


APOLLO_SOURCE = "apollo_mcp"
DEFAULT_CONTACT_LIMIT = 3

OUTREACH_TARGET_ROLES: tuple[ContactRole, ...] = (
    ContactRole.UNIVERSITY_RECRUITER,
    ContactRole.EARLY_TALENT_RECRUITER,
    ContactRole.TECHNICAL_RECRUITER,
    ContactRole.ENGINEERING_MANAGER,
    ContactRole.SOFTWARE_ENGINEER,
    ContactRole.FOUNDER,
)

RECRUITER_ROLES: frozenset[ContactRole] = frozenset(
    {
        ContactRole.UNIVERSITY_RECRUITER,
        ContactRole.EARLY_TALENT_RECRUITER,
        ContactRole.TECHNICAL_RECRUITER,
    }
)

REFERRAL_ROLES: frozenset[ContactRole] = frozenset(
    {
        ContactRole.ENGINEERING_MANAGER,
        ContactRole.SOFTWARE_ENGINEER,
        ContactRole.FOUNDER,
    }
)

UNKNOWN_MARKERS = {
    "",
    "n/a",
    "na",
    "none",
    "not provided",
    "tbd",
    "unknown",
    "unspecified",
}


class ApolloCompanyContactQuery(UnknownAwareModel):
    """A company-scoped Apollo contact search request."""

    company_name: str = Field(min_length=1)
    role_title: str | None = None
    company_domain: str | None = None
    location: str | None = None
    small_startup: bool = False
    max_contacts: int = Field(default=DEFAULT_CONTACT_LIMIT, ge=1)
    target_roles: tuple[ContactRole, ...] = OUTREACH_TARGET_ROLES

    @field_validator(
        "company_name",
        "role_title",
        "company_domain",
        "location",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return None if stripped.lower() in UNKNOWN_MARKERS else stripped


class ApolloContactResult(UnknownAwareModel):
    """Contact data returned by an injected Apollo-compatible client."""

    name: str = Field(min_length=1)
    company: str | None = None
    title: str | None = None
    email: str | None = None
    profile_url: HttpUrl | None = None
    location: str | None = None
    apollo_id: str | None = None
    source: str = APOLLO_SOURCE
    notes: str | None = None

    @field_validator(
        "name",
        "company",
        "title",
        "email",
        "profile_url",
        "location",
        "apollo_id",
        "source",
        "notes",
        mode="before",
    )
    @classmethod
    def _strip_unknown_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return None if stripped.lower() in UNKNOWN_MARKERS else stripped

    @field_validator("email")
    @classmethod
    def _validate_email_if_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("email must be a valid known email address.")
        return value


class OutreachTargetPlan(BaseModel):
    """Draft-only outreach/referral target plan for downstream drafting."""

    model_config = ConfigDict(frozen=True)

    company: str
    recipient_name: str
    contact_role: ContactRole
    recommended_action: Literal["draft_outreach", "request_referral"]
    title: str | None = None
    recipient_email: str | None = None
    profile_url: HttpUrl | None = None
    source: str | None = None
    notes: str | None = None
    draft_only: Literal[True] = True
    send_allowed: Literal[False] = False

    def to_outreach_evidence(
        self,
        *,
        sender_name: str,
        role_title: str,
        fit_evidence: str,
    ) -> dict[str, str] | None:
        """Return evidence for draft generation only when email is known."""

        if self.recipient_email is None:
            return None

        return {
            "sender_name": sender_name,
            "recipient_name": self.recipient_name,
            "recipient_email": self.recipient_email,
            "company_name": self.company,
            "role_title": role_title,
            "fit_evidence": fit_evidence,
        }


class ApolloContactSearchPlan(BaseModel):
    """Ranked contact discovery result for one company."""

    model_config = ConfigDict(frozen=True)

    query: ApolloCompanyContactQuery
    discovered_contacts: tuple[Contact, ...]
    selected_contacts: tuple[Contact, ...]
    outreach_targets: tuple[OutreachTargetPlan, ...]


@runtime_checkable
class ApolloClientProtocol(Protocol):
    """Protocol a future Apollo MCP client adapter must satisfy."""

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery,
    ) -> Sequence[ApolloContactResult | Mapping[str, Any]]:
        """Return Apollo contacts for a company-scoped query."""


class ApolloContactAdapter:
    """Ranks Apollo contact results into safe draft-only outreach plans."""

    def __init__(self, client: ApolloClientProtocol) -> None:
        self._client = client

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery | Mapping[str, Any],
    ) -> ApolloContactSearchPlan:
        """Search, classify, rank, and cap Apollo contacts for one company."""

        contact_query = _coerce_query(query)
        raw_results = await self._client.search_company_contacts(contact_query)
        apollo_results = tuple(
            _coerce_apollo_result(raw_result) for raw_result in raw_results
        )
        discovered_contacts = tuple(
            _to_contact(result, contact_query) for result in apollo_results
        )
        selected_contacts = tuple(
            rank_contacts(
                [
                    contact
                    for contact in discovered_contacts
                    if _is_eligible_target(contact.role, contact_query)
                ],
                limit=contact_query.max_contacts,
            )
        )
        outreach_targets = tuple(
            _to_outreach_target(contact) for contact in selected_contacts
        )

        return ApolloContactSearchPlan(
            query=contact_query,
            discovered_contacts=discovered_contacts,
            selected_contacts=selected_contacts,
            outreach_targets=outreach_targets,
        )


def categorize_contact_title(title: str | None) -> ContactRole:
    """Map a known title into the project's contact priority categories."""

    normalized = _normalize_text(title)
    if not normalized:
        return ContactRole.OTHER

    if _contains_any(
        normalized,
        (
            "university recruiter",
            "campus recruiter",
            "college recruiter",
            "university relations",
            "campus talent",
            "student programs",
        ),
    ):
        return ContactRole.UNIVERSITY_RECRUITER

    if _contains_any(
        normalized,
        (
            "early talent",
            "emerging talent",
            "new grad",
            "intern recruiter",
            "internship recruiter",
        ),
    ):
        return ContactRole.EARLY_TALENT_RECRUITER

    if _contains_any(
        normalized,
        (
            "technical recruiter",
            "tech recruiter",
            "engineering recruiter",
            "recruiter",
            "talent acquisition",
        ),
    ):
        return ContactRole.TECHNICAL_RECRUITER

    if _contains_any(
        normalized,
        (
            "founder",
            "co-founder",
            "cofounder",
            "chief executive",
            "ceo",
        ),
    ):
        return ContactRole.FOUNDER

    if _contains_any(
        normalized,
        (
            "engineering manager",
            "software engineering manager",
            "director of engineering",
            "head of engineering",
            "vp engineering",
            "engineering lead",
            "technical lead",
        ),
    ):
        return ContactRole.ENGINEERING_MANAGER

    if _contains_any(
        normalized,
        (
            "software engineer",
            "backend engineer",
            "front end engineer",
            "frontend engineer",
            "full stack engineer",
            "full-stack engineer",
            "developer",
            "swe",
        ),
    ):
        return ContactRole.SOFTWARE_ENGINEER

    return ContactRole.OTHER


def _coerce_query(
    query: ApolloCompanyContactQuery | Mapping[str, Any],
) -> ApolloCompanyContactQuery:
    if isinstance(query, ApolloCompanyContactQuery):
        return query
    return ApolloCompanyContactQuery.model_validate(query)


def _coerce_apollo_result(
    result: ApolloContactResult | Mapping[str, Any],
) -> ApolloContactResult:
    if isinstance(result, ApolloContactResult):
        return result
    return ApolloContactResult.model_validate(result)


def _to_contact(
    result: ApolloContactResult,
    query: ApolloCompanyContactQuery,
) -> Contact:
    return Contact(
        company=result.company or query.company_name,
        name=result.name,
        role=categorize_contact_title(result.title),
        title=result.title,
        email=result.email,
        profile_url=result.profile_url,
        source=result.source,
        notes=result.notes,
    )


def _is_eligible_target(
    role: ContactRole,
    query: ApolloCompanyContactQuery,
) -> bool:
    if role not in query.target_roles:
        return False
    if role == ContactRole.FOUNDER and not query.small_startup:
        return False
    return role in OUTREACH_TARGET_ROLES


def _to_outreach_target(contact: Contact) -> OutreachTargetPlan:
    recommended_action: Literal["draft_outreach", "request_referral"]
    if contact.role in RECRUITER_ROLES:
        recommended_action = "draft_outreach"
    elif contact.role in REFERRAL_ROLES:
        recommended_action = "request_referral"
    else:
        recommended_action = "draft_outreach"

    return OutreachTargetPlan(
        company=contact.company,
        recipient_name=contact.name,
        recipient_email=contact.email,
        contact_role=contact.role,
        recommended_action=recommended_action,
        title=contact.title,
        profile_url=contact.profile_url,
        source=contact.source,
        notes=contact.notes,
    )


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return f" {re.sub(r'[^a-z0-9+#]+', ' ', value.lower()).strip()} "


def _contains_any(value: str, needles: Sequence[str]) -> bool:
    return any(f" {needle} " in value for needle in needles)
