from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from internship_agent.apollo import (
    ApolloClientProtocol,
    ApolloCompanyContactQuery,
    ApolloContactAdapter,
)
from internship_agent.apollo_mcp import (
    ApolloMCPClient,
    ApolloMCPClientConfig,
    ApolloMCPResponseError,
    MCPToolCallerProtocol,
)


class FakeMCPToolCaller:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> Any:
        self.calls.append((server_name, tool_name, arguments))
        return self.response


def run_mcp_search(
    response: Any,
    *,
    config: ApolloMCPClientConfig | None = None,
    query: ApolloCompanyContactQuery | None = None,
) -> tuple[list[Any], FakeMCPToolCaller]:
    caller = FakeMCPToolCaller(response)
    client = ApolloMCPClient(caller, config=config)
    results = asyncio.run(
        client.search_company_contacts(
            query or ApolloCompanyContactQuery(company_name="Example Robotics")
        )
    )
    return list(results), caller


def test_fake_mcp_caller_matches_protocol() -> None:
    caller = FakeMCPToolCaller({"contacts": []})

    assert isinstance(caller, MCPToolCallerProtocol)


def test_apollo_mcp_client_satisfies_apollo_client_protocol() -> None:
    client = ApolloMCPClient(FakeMCPToolCaller({"contacts": []}))

    assert isinstance(client, ApolloClientProtocol)


def test_default_response_normalization_preserves_missing_email_and_profile_url() -> None:
    results, caller = run_mcp_search(
        {
            "contacts": [
                {
                    "name": "Uma Campus",
                    "title": "University Relations Recruiter",
                    "email": "unknown",
                }
            ]
        }
    )

    assert caller.calls == [
        (
            "apollo",
            "search_company_contacts",
            {
                "company_name": "Example Robotics",
                "small_startup": False,
                "max_contacts": 3,
                "target_roles": [
                    "university_recruiter",
                    "early_talent_recruiter",
                    "technical_recruiter",
                    "engineering_manager",
                    "software_engineer",
                    "founder",
                ],
            },
        )
    ]
    assert results[0].name == "Uma Campus"
    assert results[0].email is None
    assert results[0].profile_url is None


def test_custom_tool_names_input_mapping_and_output_mapping() -> None:
    config = ApolloMCPClientConfig(
        server_name="apollo-prod",
        tool_name="people.search",
        result_list_path="payload.people",
        query_field_mapping={
            "company_name": "organization.name",
            "company_domain": "organization.domain",
            "max_contacts": "limit",
            "target_roles": "roles",
        },
        contact_field_mapping={
            "name": "person.fullName",
            "company": "company.displayName",
            "title": "person.jobTitle",
            "email": "person.workEmail",
            "profile_url": "person.linkedinUrl",
            "apollo_id": "person.id",
        },
    )
    query = ApolloCompanyContactQuery(
        company_name="Example Robotics",
        company_domain="example.com",
        max_contacts=2,
    )

    results, caller = run_mcp_search(
        {
            "payload": {
                "people": [
                    {
                        "person": {
                            "fullName": "Tara Recruiter",
                            "jobTitle": "Technical Recruiter",
                            "workEmail": "tara@example.com",
                            "linkedinUrl": "https://linkedin.example/tara",
                            "id": "apollo-person-123",
                        },
                        "company": {"displayName": "Example Robotics"},
                    }
                ]
            }
        },
        config=config,
        query=query,
    )

    assert caller.calls[0] == (
        "apollo-prod",
        "people.search",
        {
            "organization": {
                "name": "Example Robotics",
                "domain": "example.com",
            },
            "limit": 2,
            "roles": [
                "university_recruiter",
                "early_talent_recruiter",
                "technical_recruiter",
                "engineering_manager",
                "software_engineer",
                "founder",
            ],
        },
    )
    assert results[0].name == "Tara Recruiter"
    assert results[0].company == "Example Robotics"
    assert results[0].email == "tara@example.com"
    assert str(results[0].profile_url) == "https://linkedin.example/tara"
    assert results[0].apollo_id == "apollo-person-123"


def test_missing_required_name_raises_clear_error() -> None:
    with pytest.raises(ApolloMCPResponseError, match="missing required field 'name'"):
        run_mcp_search({"contacts": [{"email": "unknown"}]})


def test_missing_configured_result_path_raises_clear_error() -> None:
    config = ApolloMCPClientConfig(result_list_path="payload.people")

    with pytest.raises(ApolloMCPResponseError, match="result_list_path"):
        run_mcp_search({"contacts": []}, config=config)


def test_mcp_client_works_with_existing_apollo_contact_adapter() -> None:
    caller = FakeMCPToolCaller(
        {
            "contacts": [
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
            ]
        }
    )
    client = ApolloMCPClient(caller)
    adapter = ApolloContactAdapter(client)

    plan = asyncio.run(
        adapter.search_company_contacts({"company_name": "Example Robotics"})
    )

    assert [contact.name for contact in plan.selected_contacts] == [
        "Tara Recruiter",
        "Sam Engineer",
    ]
    assert plan.outreach_targets[0].recommended_action == "draft_outreach"
    assert plan.outreach_targets[1].recommended_action == "request_referral"
