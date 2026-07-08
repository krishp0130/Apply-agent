from __future__ import annotations

import asyncio

import pytest

from internship_agent.sources import (
    InternshipSourceConfig,
    SourceFetchError,
    fetch_source,
    ingest_sources,
)


def test_fetch_source_uses_inline_html_without_fetcher() -> None:
    source = InternshipSourceConfig(
        name="inline source",
        inline_html="<article data-internship-role></article>",
    )

    fetched = asyncio.run(fetch_source(source))

    assert fetched.source_name == "inline source"
    assert fetched.html == "<article data-internship-role></article>"


def test_fetch_source_requires_injected_content_or_fetcher() -> None:
    source = InternshipSourceConfig(
        name="remote source",
        url="https://example.com/jobs",
    )

    with pytest.raises(SourceFetchError, match="network fetching is not performed"):
        asyncio.run(fetch_source(source))


def test_ingest_sources_uses_injected_async_fetcher_and_skips_disabled() -> None:
    enabled = InternshipSourceConfig(
        name="enabled source",
        url="https://example.com/jobs",
    )
    disabled = InternshipSourceConfig(
        name="disabled source",
        enabled=False,
        inline_html="""
        <article data-internship-role>
          <h2 data-title>Should Not Appear</h2>
          <p data-company>Disabled Co</p>
        </article>
        """,
    )
    fetched_sources: list[str] = []

    async def fetcher(source: InternshipSourceConfig) -> str:
        fetched_sources.append(source.name)
        return """
        <article data-internship-role>
          <h2 data-title>Data Intern</h2>
          <p data-company>Fetched Co</p>
          <a href="https://example.com/apply">Apply</a>
        </article>
        """

    roles = asyncio.run(ingest_sources([enabled, disabled], fetcher=fetcher))

    assert fetched_sources == ["enabled source"]
    assert len(roles) == 1
    assert roles[0].company == "Fetched Co"
    assert roles[0].title == "Data Intern"
    assert roles[0].source == "enabled source"
    assert str(roles[0].application_url) == "https://example.com/apply"


def test_ingest_sources_accepts_fetcher_objects() -> None:
    class ObjectFetcher:
        async def fetch(self, source: InternshipSourceConfig) -> str:
            return f"""
            <article data-internship-role>
              <h2 data-title>{source.name} Role</h2>
              <p data-company>Object Co</p>
            </article>
            """

    source = InternshipSourceConfig(name="object source")

    roles = asyncio.run(ingest_sources([source], fetcher=ObjectFetcher()))

    assert len(roles) == 1
    assert roles[0].company == "Object Co"
    assert roles[0].title == "object source Role"
