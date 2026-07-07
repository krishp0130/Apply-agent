from __future__ import annotations

import asyncio

import pytest

from internship_agent.github_sources import (
    GitHubMarkdownFetchError,
    GitHubMarkdownSource,
    GitHubMarkdownSourceKind,
    ingest_github_markdown_source,
    ingest_known_github_markdown_sources,
    parse_github_markdown_table_roles,
)


def test_ingest_known_github_sources_requires_injected_fetcher() -> None:
    with pytest.raises(GitHubMarkdownFetchError, match="injected fetcher"):
        asyncio.run(ingest_known_github_markdown_sources())


def test_parse_sndsh404_table_columns_and_preserves_added_note() -> None:
    markdown = """
    | Company | Role | Location | Apply | Added |
    | --- | --- | --- | --- | --- |
    | Example Co | Software Engineering Intern | Remote - US | [Apply](https://example.com/apply) | Jul 1 |
    | No Link Co | Data Intern | New York, NY | Closed | Jul 2 |
    """

    roles = parse_github_markdown_table_roles(
        markdown,
        source_name="sndsh404 summer 2027 internships",
        source_url="https://raw.githubusercontent.com/sndsh404/summer-2027-internships/main/README.md",
    )

    assert len(roles) == 2
    assert roles[0].company == "Example Co"
    assert roles[0].title == "Software Engineering Intern"
    assert str(roles[0].application_url) == "https://example.com/apply"
    assert roles[0].location == "Remote - US"
    assert roles[0].remote is True
    assert "Source URL: https://raw.githubusercontent.com/sndsh404/summer-2027-internships/main/README.md" in (
        roles[0].description or ""
    )
    assert "Added: Jul 1" in (roles[0].description or "")
    assert roles[1].application_url is None
    assert "Apply: Closed" in (roles[1].description or "")


def test_parse_vansh_style_readme_table_if_present() -> None:
    markdown = """
    # Summer 2027 Internships

    | Company | Position | Location | Application | Date Posted | Sponsorship |
    | :--- | :--- | :--- | :--- | :--- | :--- |
    | [Widgets Inc](https://widgets.example) | SWE Intern | Austin, TX | <a href="https://widgets.example/jobs/1">Apply</a> | 2026-07-01 | Unknown |
    """

    roles = parse_github_markdown_table_roles(
        markdown,
        source_name="Vansh Summer 2027 Internships",
        source_url="https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/main/README.md",
    )

    assert len(roles) == 1
    role = roles[0]
    assert role.company == "Widgets Inc"
    assert role.title == "SWE Intern"
    assert str(role.application_url) == "https://widgets.example/jobs/1"
    assert role.location == "Austin, TX"
    assert role.sponsorship_notes == "Unknown"
    assert "Date Posted: 2026-07-01" in (role.description or "")


def test_speedyapply_ingestion_follows_intern_usa_link_and_parses_target_table() -> None:
    source = GitHubMarkdownSource(
        name="SpeedyApply 2027 SWE College Jobs",
        repository="speedyapply/2027-SWE-College-Jobs",
        readme_raw_url="https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        kind=GitHubMarkdownSourceKind.SPEEDYAPPLY_INDEX,
    )
    readme = "Find US internships in [INTERN_USA.md](./INTERN_USA.md)."
    target = """
    | Company | Title | Location | Apply | Notes |
    | --- | --- | --- | --- | --- |
    | Speedy Co | Backend Intern | Seattle, WA | [Apply](https://speedy.example/apply) | Opens soon |
    """
    fetched_urls: list[str] = []

    async def fetcher(url: str) -> str:
        fetched_urls.append(url)
        if url.endswith("/README.md"):
            return readme
        if url.endswith("/INTERN_USA.md"):
            return target
        raise AssertionError(f"Unexpected URL: {url}")

    roles = asyncio.run(ingest_github_markdown_source(source, fetcher))

    assert fetched_urls == [
        "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/INTERN_USA.md",
    ]
    assert len(roles) == 1
    assert roles[0].company == "Speedy Co"
    assert roles[0].title == "Backend Intern"
    assert str(roles[0].application_url) == "https://speedy.example/apply"
    assert "Notes: Opens soon" in (roles[0].description or "")


def test_known_source_ingestion_dedupes_by_company_title_and_application_url() -> None:
    duplicate_table = """
    | Company | Role | Location | Apply | Added |
    | --- | --- | --- | --- | --- |
    | Same Co | SWE Intern | Remote | [Apply](https://same.example/apply) | Jul 1 |
    | Same Co | SWE Intern | Remote | [Apply](https://same.example/apply) | Jul 2 |
    """
    speedy_readme = "[US Internships](https://github.com/speedyapply/2027-SWE-College-Jobs/blob/main/INTERN_USA.md)"
    fetched: dict[str, str] = {
        "https://raw.githubusercontent.com/sndsh404/summer-2027-internships/main/README.md": duplicate_table,
        "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/main/README.md": duplicate_table,
        "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md": speedy_readme,
        "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/INTERN_USA.md": duplicate_table,
    }

    roles = asyncio.run(ingest_known_github_markdown_sources(lambda url: fetched[url]))

    assert len(roles) == 1
    assert roles[0].company == "Same Co"
    assert roles[0].title == "SWE Intern"
    assert str(roles[0].application_url) == "https://same.example/apply"
