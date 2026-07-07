from __future__ import annotations

from internship_agent.models import Contact, ContactRole


CONTACT_PRIORITY: dict[ContactRole, int] = {
    ContactRole.UNIVERSITY_RECRUITER: 0,
    ContactRole.EARLY_TALENT_RECRUITER: 1,
    ContactRole.TECHNICAL_RECRUITER: 2,
    ContactRole.ENGINEERING_MANAGER: 3,
    ContactRole.SOFTWARE_ENGINEER: 4,
    ContactRole.FOUNDER: 5,
    ContactRole.OTHER: 6,
}


def rank_contacts(contacts: list[Contact], limit: int = 3) -> list[Contact]:
    """Rank contacts by project priority rules and cap outreach targets."""

    if limit < 1:
        return []

    return sorted(
        contacts,
        key=lambda contact: (
            CONTACT_PRIORITY[contact.role],
            contact.company.lower(),
            contact.name.lower(),
        ),
    )[:limit]
