from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class UnknownAwareModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    SCORED = "scored"
    DRAFTED_OUTREACH = "drafted_outreach"
    STARTED_APPLICATION = "started_application"
    USER_COMPLETED_APPLICATION = "user_completed_application"


class ContactRole(StrEnum):
    UNIVERSITY_RECRUITER = "university_recruiter"
    EARLY_TALENT_RECRUITER = "early_talent_recruiter"
    TECHNICAL_RECRUITER = "technical_recruiter"
    ENGINEERING_MANAGER = "engineering_manager"
    SOFTWARE_ENGINEER = "software_engineer"
    FOUNDER = "founder"
    OTHER = "other"


class ApprovalAction(StrEnum):
    SEND_EMAIL = "send_email"
    SUBMIT_APPLICATION = "submit_application"
    DELETE_TRACKED_DATA = "delete_tracked_data"
    OVERWRITE_PROFILE = "overwrite_profile"
    APPLY_BELOW_THRESHOLD = "apply_below_threshold"


class ApprovalStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserProfile(UnknownAwareModel):
    name: str
    email: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_keywords: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
    desired_terms: list[str] = Field(default_factory=list)
    requires_sponsorship: bool | None = None
    preferences: list[str] = Field(default_factory=list)


class InternshipRole(UnknownAwareModel):
    company: str
    title: str
    application_url: HttpUrl | None = None
    source: str
    date_discovered: date = Field(default_factory=date.today)
    location: str | None = None
    remote: bool | None = None
    internship_term: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    description: str | None = None
    sponsorship_notes: str | None = None
    status: ApplicationStatus = ApplicationStatus.DISCOVERED


class FitScore(UnknownAwareModel):
    company: str
    role_title: str
    score: int = Field(ge=0, le=100)
    threshold: int = Field(default=70, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def below_threshold(self) -> bool:
        return self.score < self.threshold


class Contact(UnknownAwareModel):
    company: str
    name: str
    role: ContactRole = ContactRole.OTHER
    title: str | None = None
    email: str | None = None
    profile_url: HttpUrl | None = None
    source: str | None = None
    notes: str | None = None


class OutreachDraft(UnknownAwareModel):
    company: str
    recipient_name: str
    recipient_email: str | None = None
    subject: str
    body: str
    concrete_fit_reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRecord(UnknownAwareModel):
    action: ApprovalAction
    status: ApprovalStatus = ApprovalStatus.REQUESTED
    reason: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class ApplicationEvent(UnknownAwareModel):
    company: str
    role_title: str
    status: ApplicationStatus
    note: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
