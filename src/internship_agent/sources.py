"""Configured source ingestion for internship discovery."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from enum import StrEnum
from typing import Protocol

from pydantic import Field, HttpUrl

from internship_agent.models import InternshipRole, UnknownAwareModel
from internship_agent.parsing import HtmlRoleParserConfig, parse_internship_roles_from_html

logger = logging.getLogger(__name__)

FetchCallable = Callable[["InternshipSourceConfig"], str | Awaitable[str]]


class SourceKind(StrEnum):
    """Supported internship source kinds."""

    HTML = "html"


class InternshipSourceConfig(UnknownAwareModel):
    """Configuration for one internship source."""

    name: str = Field(min_length=1)
    kind: SourceKind = SourceKind.HTML
    url: HttpUrl | None = None
    enabled: bool = True
    inline_html: str | None = None
    parser: HtmlRoleParserConfig = Field(default_factory=HtmlRoleParserConfig)


class FetchedSource(UnknownAwareModel):
    """Fetched source content plus provenance."""

    source_name: str
    url: HttpUrl | None = None
    html: str


class SourceFetchError(RuntimeError):
    """Raised when a source cannot be fetched safely."""


class SourceFetcher(Protocol):
    """Async source fetcher protocol for dependency injection."""

    async def fetch(self, source: InternshipSourceConfig) -> str:
        """Fetch HTML for a configured source."""


async def fetch_source(
    source: InternshipSourceConfig,
    fetcher: SourceFetcher | FetchCallable | None = None,
) -> FetchedSource:
    """Fetch one source without making network calls unless a fetcher is injected."""
    if source.inline_html is not None:
        logger.info("Using inline HTML for source %s", source.name)
        return FetchedSource(
            source_name=source.name,
            url=source.url,
            html=source.inline_html,
        )

    if fetcher is None:
        msg = (
            f"No content or fetcher configured for source {source.name!r}; "
            "network fetching is not performed by default."
        )
        raise SourceFetchError(msg)

    html = await _call_fetcher(fetcher, source)
    return FetchedSource(source_name=source.name, url=source.url, html=html)


async def ingest_sources(
    sources: Iterable[InternshipSourceConfig],
    fetcher: SourceFetcher | FetchCallable | None = None,
) -> list[InternshipRole]:
    """Fetch enabled configured sources and parse them into internship roles."""
    roles: list[InternshipRole] = []

    for source in sources:
        if not source.enabled:
            logger.info("Skipping disabled source %s", source.name)
            continue
        if source.kind != SourceKind.HTML:
            msg = f"Unsupported source kind for {source.name!r}: {source.kind}"
            raise SourceFetchError(msg)

        fetched = await fetch_source(source, fetcher)
        roles.extend(
            parse_internship_roles_from_html(
                fetched.html,
                source_name=fetched.source_name,
                source_url=fetched.url,
                parser_config=source.parser,
            ),
        )

    logger.info("Ingested %d internship roles", len(roles))
    return roles


async def _call_fetcher(
    fetcher: SourceFetcher | FetchCallable,
    source: InternshipSourceConfig,
) -> str:
    if hasattr(fetcher, "fetch"):
        result = fetcher.fetch(source)  # type: ignore[union-attr]
    else:
        result = fetcher(source)

    if inspect.isawaitable(result):
        result = await result

    if not isinstance(result, str):
        msg = f"Fetcher for source {source.name!r} returned {type(result).__name__}."
        raise SourceFetchError(msg)

    return result
