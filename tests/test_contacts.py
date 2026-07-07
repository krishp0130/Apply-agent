from internship_agent.contacts import rank_contacts
from internship_agent.models import Contact, ContactRole


def test_rank_contacts_prioritizes_recruiting_roles_and_limits_to_three() -> None:
    contacts = [
        Contact(company="Example", name="Engineer", role=ContactRole.SOFTWARE_ENGINEER),
        Contact(company="Example", name="Technical", role=ContactRole.TECHNICAL_RECRUITER),
        Contact(company="Example", name="University", role=ContactRole.UNIVERSITY_RECRUITER),
        Contact(company="Example", name="Manager", role=ContactRole.ENGINEERING_MANAGER),
    ]

    ranked = rank_contacts(contacts)

    assert [contact.name for contact in ranked] == ["University", "Technical", "Manager"]


def test_rank_contacts_allows_lower_limit() -> None:
    contacts = [
        Contact(company="Example", name="Founder", role=ContactRole.FOUNDER),
        Contact(company="Example", name="Early", role=ContactRole.EARLY_TALENT_RECRUITER),
    ]

    ranked = rank_contacts(contacts, limit=1)

    assert [contact.name for contact in ranked] == ["Early"]
