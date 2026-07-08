from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from internship_agent.apollo import (
    ApolloClientProtocol,
    ApolloCompanyContactQuery,
    ApolloContactAdapter,
    ApolloContactResult,
    ApolloContactSearchPlan,
    categorize_contact_title,
)
from internship_agent.models import ContactRole


class FakeApolloClient:
    def __init__(
        self,
        results: Sequence[ApolloContactResult | Mapping[str, Any]],
    ) -> None:
        self.results = results
        self.queries: list[ApolloCompanyContactQuery] = []

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery,
    ) -> Sequence[ApolloContactResult | Mapping[str, Any]]:
        self.queries.append(query)
        return self.results


def run_search(
    results: Sequence[ApolloContactResult | Mapping[str, Any]],
    query: ApolloCompanyContactQuery | Mapping[str, Any] | None = None,
) -> tuple[ApolloContactSearchPlan, FakeApolloClient]:
    client = FakeApolloClient(results)
    adapter = ApolloContactAdapter(client)
    search_query = query or {"company_name": "Example Robotics"}

    return asyncio.run(adapter.search_company_contacts(search_query)), client


def test_fake_client_matches_apollo_protocol() -> None:
    client = FakeApolloClient([])

    assert isinstance(client, ApolloClientProtocol)


def test_search_ranks_existing_contact_priority_and_caps_to_three() -> None:
    plan, client = run_search(
        [
            {
                "name": "Sam Engineer",
                "title": "Software Engineer",
                "email": "sam@example.com",
            },
            {
                "name": "Tara Recruiter",
                "title": "Technical Recruiter",
                "email": "tara@example.com",
            },
            {
                "name": "Uma Campus",
                "title": "University Recruiter",
            },
            {
                "name": "Eli Early",
                "title": "Early Talent Recruiter",
                "email": "eli@example.com",
            },
            {
                "name": "Maya Manager",
                "title": "Engineering Manager",
                "email": "maya@example.com",
            },
        ],
    )

    assert client.queries[0].company_name == "Example Robotics"
    assert [contact.name for contact in plan.selected_contacts] == [
        "Uma Campus",
        "Eli Early",
        "Tara Recruiter",
    ]
    assert len(plan.outreach_targets) == 3
    assert plan.outreach_targets[0].recipient_email is None
    assert plan.outreach_targets[0].send_allowed is False


def test_founders_are_only_selected_for_small_startups() -> None:
    results = [
        {
            "name": "Frank Founder",
            "title": "Co-Founder and CEO",
            "email": "frank@example.com",
        },
        {
            "name": "Sia Engineer",
            "title": "Software Engineer",
            "email": "sia@example.com",
        },
    ]

    mature_company_plan, _ = run_search(results)
    small_startup_plan, _ = run_search(
        results,
        {"company_name": "Tiny Robotics", "small_startup": True},
    )

    assert [contact.role for contact in mature_company_plan.selected_contacts] == [
        ContactRole.SOFTWARE_ENGINEER
    ]
    assert [contact.role for contact in small_startup_plan.selected_contacts] == [
        ContactRole.SOFTWARE_ENGINEER,
        ContactRole.FOUNDER,
    ]


def test_outreach_target_can_feed_draft_generation_when_email_is_known() -> None:
    plan, _ = run_search(
        [
            {
                "name": "Tara Recruiter",
                "title": "Technical Recruiter",
                "email": "tara@example.com",
                "profile_url": "https://example.com/tara",
            }
        ]
    )

    evidence = plan.outreach_targets[0].to_outreach_evidence(
        sender_name="Krish Patel",
        role_title="Software Engineering Intern",
        fit_evidence="My Python automation project matches the internship tooling",
    )

    assert evidence == {
        "sender_name": "Krish Patel",
        "recipient_name": "Tara Recruiter",
        "recipient_email": "tara@example.com",
        "company_name": "Example Robotics",
        "role_title": "Software Engineering Intern",
        "fit_evidence": "My Python automation project matches the internship tooling",
    }
    assert plan.outreach_targets[0].draft_only is True
    assert plan.outreach_targets[0].send_allowed is False


def test_missing_email_or_profile_url_stays_missing() -> None:
    plan, _ = run_search(
        [
            {
                "name": "Uma Campus",
                "title": "University Relations Recruiter",
                "email": "unknown",
            }
        ]
    )

    target = plan.outreach_targets[0]

    assert target.recipient_email is None
    assert target.profile_url is None
    assert target.to_outreach_evidence(
        sender_name="Krish Patel",
        role_title="Software Engineering Intern",
        fit_evidence="Known project evidence",
    ) is None


def test_title_categorization_identifies_target_categories() -> None:
    assert (
        categorize_contact_title("Campus Talent Partner")
        == ContactRole.UNIVERSITY_RECRUITER
    )
    assert (
        categorize_contact_title("Emerging Talent Recruiter")
        == ContactRole.EARLY_TALENT_RECRUITER
    )
    assert (
        categorize_contact_title("Engineering Recruiter")
        == ContactRole.TECHNICAL_RECRUITER
    )
    assert (
        categorize_contact_title("Director of Engineering")
        == ContactRole.ENGINEERING_MANAGER
    )
    assert categorize_contact_title("Backend Engineer") == ContactRole.SOFTWARE_ENGINEER
    assert categorize_contact_title("Founder") == ContactRole.FOUNDER
