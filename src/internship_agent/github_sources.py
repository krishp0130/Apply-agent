"""GitHub Markdown list ingestion for internship discovery."""

from __future__ import annotations

import inspect
import logging
import re
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from enum import StrEnum
from html import unescape
from typing import Protocol
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import Field, HttpUrl, ValidationError

from internship_agent.models import InternshipRole, UnknownAwareModel
from internship_agent.parsing import UNKNOWN

logger = logging.getLogger(__name__)

MarkdownFetchCallable = Callable[[str], str | Awaitable[str]]

RAW_GITHUB_BASE_URL = "https://raw.githubusercontent.com"


class GitHubMarkdownSourceKind(StrEnum):
    """Supported GitHub Markdown ingestion strategies."""

    README_TABLE = "readme_table"
    SPEEDYAPPLY_INDEX = "speedyapply_index"


class GitHubMarkdownSource(UnknownAwareModel):
    """Configuration for one known GitHub internship list."""

    name: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    readme_raw_url: HttpUrl
    kind: GitHubMarkdownSourceKind = GitHubMarkdownSourceKind.README_TABLE


class GitHubMarkdownFetchError(RuntimeError):
    """Raised when GitHub Markdown content cannot be fetched safely."""


class GitHubMarkdownFetcher(Protocol):
    """Async Markdown fetcher protocol for dependency injection."""

    async def fetch(self, url: str) -> str:
        """Fetch raw Markdown for a URL."""

KNOWN_GITHUB_MARKDOWN_SOURCES: tuple[GitHubMarkdownSource, ...] = (
    GitHubMarkdownSource(
        name="sndsh404 summer 2027 internships",
        repository="sndsh404/summer-2027-internships",
        readme_raw_url=(
            "https://raw.githubusercontent.com/"
            "sndsh404/summer-2027-internships/main/README.md"
        ),
    ),
    GitHubMarkdownSource(
        name="Vansh Summer 2027 Internships",
        repository="vanshb03/Summer2027-Internships",
        readme_raw_url=(
            "https://raw.githubusercontent.com/"
            "vanshb03/Summer2027-Internships/main/README.md"
        ),
    ),
    GitHubMarkdownSource(
        name="SpeedyApply 2027 SWE College Jobs",
        repository="speedyapply/2027-SWE-College-Jobs",
        readme_raw_url=(
            "https://raw.githubusercontent.com/"
            "speedyapply/2027-SWE-College-Jobs/main/README.md"
        ),
        kind=GitHubMarkdownSourceKind.SPEEDYAPPLY_INDEX,
    ),
)

COMPANY_COLUMNS = ("company", "employer", "organization")
TITLE_COLUMNS = ("role", "title", "position", "job title", "job")
LOCATION_COLUMNS = ("location", "locations")
APPLY_COLUMNS = ("apply", "application", "application link", "link", "url")
TERM_COLUMNS = ("term", "season", "internship term")
SPONSORSHIP_COLUMNS = ("sponsorship", "sponsor", "visa", "eligibility")
NOTE_COLUMNS = ("added", "date added", "date posted", "posted", "notes", "note", "status")


async def ingest_known_github_markdown_sources(
    fetcher: GitHubMarkdownFetcher | MarkdownFetchCallable | None = None,
) -> list[InternshipRole]:
    """Fetch and parse all known GitHub Markdown sources with an injected fetcher."""
    if fetcher is None:
        msg = "GitHub Markdown ingestion requires an injected fetcher; no network calls are made by default."
        raise GitHubMarkdownFetchError(msg)

    roles: list[InternshipRole] = []
    for source in KNOWN_GITHUB_MARKDOWN_SOURCES:
        roles.extend(await ingest_github_markdown_source(source, fetcher))

    deduped = dedupe_internship_roles(roles)
    logger.info("Ingested %d GitHub Markdown roles", len(deduped))
    return deduped


async def ingest_github_markdown_source(
    source: GitHubMarkdownSource,
    fetcher: GitHubMarkdownFetcher | MarkdownFetchCallable | None = None,
) -> list[InternshipRole]:
    """Fetch and parse one known GitHub Markdown source."""
    if fetcher is None:
        msg = f"GitHub Markdown source {source.repository!r} requires an injected fetcher."
        raise GitHubMarkdownFetchError(msg)

    readme_url = str(source.readme_raw_url)
    readme_markdown = await _call_markdown_fetcher(fetcher, readme_url)

    if source.kind == GitHubMarkdownSourceKind.SPEEDYAPPLY_INDEX:
        target_url = _find_speedyapply_intern_usa_url(readme_markdown, readme_url)
        target_markdown = await _call_markdown_fetcher(fetcher, target_url)
        return parse_github_markdown_table_roles(
            target_markdown,
            source_name=source.name,
            source_url=target_url,
        )

    return parse_github_markdown_table_roles(
        readme_markdown,
        source_name=source.name,
        source_url=readme_url,
    )


def parse_github_markdown_table_roles(
    markdown: str,
    *,
    source_name: str,
    source_url: HttpUrl | str,
) -> list[InternshipRole]:
    """Parse Markdown tables into internship roles without inferring missing fields."""
    roles: list[InternshipRole] = []
    for table in _iter_markdown_tables(markdown):
        table_roles = _parse_markdown_table(table, source_name=source_name, source_url=str(source_url))
        roles.extend(table_roles)

    deduped = dedupe_internship_roles(roles)
    logger.info("Parsed %d GitHub Markdown roles from %s", len(deduped), source_name)
    return deduped


def dedupe_internship_roles(roles: Iterable[InternshipRole]) -> list[InternshipRole]:
    """Deduplicate roles by company, title, and application URL while preserving order."""
    seen: set[tuple[str, str, str]] = set()
    deduped: list[InternshipRole] = []

    for role in roles:
        key = (
            role.company.strip().casefold(),
            role.title.strip().casefold(),
            str(role.application_url or "").strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(role)

    return deduped


async def _call_markdown_fetcher(
    fetcher: GitHubMarkdownFetcher | MarkdownFetchCallable,
    url: str,
) -> str:
    if hasattr(fetcher, "fetch"):
        result = fetcher.fetch(url)  # type: ignore[union-attr]
    else:
        result = fetcher(url)

    if inspect.isawaitable(result):
        result = await result

    if not isinstance(result, str):
        msg = f"Fetcher for {url!r} returned {type(result).__name__}."
        raise GitHubMarkdownFetchError(msg)

    return result


def _parse_markdown_table(
    table: list[dict[str, str]],
    *,
    source_name: str,
    source_url: str,
) -> list[InternshipRole]:
    roles: list[InternshipRole] = []
    for row in table:
        normalized_row = {_normalize_header(header): value for header, value in row.items()}
        if not _looks_like_internship_row(normalized_row):
            continue

        company_cell = _first_value(normalized_row, COMPANY_COLUMNS)
        title_cell = _first_value(normalized_row, TITLE_COLUMNS)
        location_cell = _first_value(normalized_row, LOCATION_COLUMNS)
        apply_cell = _first_value(normalized_row, APPLY_COLUMNS)
        term_cell = _first_value(normalized_row, TERM_COLUMNS)
        sponsorship_cell = _first_value(normalized_row, SPONSORSHIP_COLUMNS)

        application_url = _extract_application_url(apply_cell, source_url)
        role_data = {
            "company": _markdown_text(company_cell) or UNKNOWN,
            "title": _markdown_text(title_cell) or UNKNOWN,
            "application_url": application_url,
            "source": f"{source_name} ({source_url})",
            "location": _markdown_text(location_cell),
            "remote": _remote_status(_markdown_text(location_cell)),
            "internship_term": _markdown_text(term_cell),
            "description": _source_notes(normalized_row, source_url, apply_cell, application_url),
            "sponsorship_notes": _markdown_text(sponsorship_cell),
        }

        try:
            roles.append(InternshipRole.model_validate(role_data))
        except ValidationError as error:
            logger.warning(
                "Dropping invalid application URL while parsing GitHub source %s: %s",
                source_name,
                error,
            )
            role_data["application_url"] = None
            roles.append(InternshipRole.model_validate(role_data))

    return roles


def _iter_markdown_tables(markdown: str) -> Iterator[list[dict[str, str]]]:
    lines = markdown.splitlines()
    index = 0
    while index < len(lines) - 1:
        if "|" not in lines[index] or not _is_separator_row(lines[index + 1]):
            index += 1
            continue

        headers = [_markdown_text(cell) for cell in _split_markdown_table_row(lines[index])]
        rows: list[dict[str, str]] = []
        index += 2

        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            if _is_separator_row(lines[index]):
                index += 1
                continue

            cells = _split_markdown_table_row(lines[index])
            padded_cells = [*cells, *([""] * max(0, len(headers) - len(cells)))]
            row = dict(zip(headers, padded_cells[: len(headers)], strict=False))
            if any(value.strip() for value in row.values()):
                rows.append(row)
            index += 1

        if rows:
            yield rows


def _split_markdown_table_row(row: str) -> list[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if char == "\\" and not escaped:
            escaped = True
            current.append(char)
            continue
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
        escaped = False

    cells.append("".join(current).strip())
    return cells


def _is_separator_row(row: str) -> bool:
    if "|" not in row:
        return False

    cells = _split_markdown_table_row(row)
    if not cells:
        return False

    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in cells if cell.strip())


def _looks_like_internship_row(row: Mapping[str, str]) -> bool:
    headers = set(row)
    return bool(headers & set(COMPANY_COLUMNS)) and bool(headers & set(TITLE_COLUMNS))


def _first_value(row: Mapping[str, str], candidate_headers: Iterable[str]) -> str | None:
    for header in candidate_headers:
        value = row.get(header)
        if value is not None and value.strip():
            return value
    return None


def _source_notes(
    row: Mapping[str, str],
    source_url: str,
    apply_cell: str | None,
    application_url: str | None,
) -> str:
    notes: list[str] = [f"Source URL: {source_url}"]

    for header in NOTE_COLUMNS:
        value = _markdown_text(row.get(header))
        if value:
            notes.append(f"{header.title()}: {value}")

    apply_note = _markdown_text(apply_cell)
    if apply_note and application_url is None:
        notes.append(f"Apply: {apply_note}")

    return "; ".join(notes)


def _extract_application_url(cell: str | None, source_url: str) -> str | None:
    if cell is None:
        return None

    markdown_match = re.search(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", cell)
    if markdown_match is not None:
        return _resolve_markdown_url(markdown_match.group(1), source_url)

    soup = BeautifulSoup(cell, "html.parser")
    html_link = soup.find("a", href=True)
    if html_link is not None:
        href = html_link.get("href")
        if isinstance(href, str):
            return _resolve_markdown_url(href, source_url)

    bare_match = re.search(r"https?://[^\s)>]+", cell)
    if bare_match is not None:
        return _resolve_markdown_url(bare_match.group(0), source_url)

    return None


def _find_speedyapply_intern_usa_url(markdown: str, readme_url: str) -> str:
    markdown_link_pattern = re.compile(r"(?<!!)\[[^\]]*]\(([^)]*INTERN_USA\.md[^)]*)\)", re.IGNORECASE)
    markdown_link_match = markdown_link_pattern.search(markdown)
    if markdown_link_match is not None:
        return _resolve_markdown_url(markdown_link_match.group(1), readme_url)

    bare_link_pattern = re.compile(r"(?<![\w/-])([^\s)]+INTERN_USA\.md)(?:#[^\s)]*)?", re.IGNORECASE)
    bare_link_match = bare_link_pattern.search(markdown)
    if bare_link_match is not None:
        return _resolve_markdown_url(bare_link_match.group(1), readme_url)

    msg = "SpeedyApply README did not link to INTERN_USA.md."
    raise GitHubMarkdownFetchError(msg)


def _resolve_markdown_url(url: str, base_url: str) -> str:
    cleaned_url = url.strip().strip("<>")
    cleaned_url = cleaned_url.split("#", maxsplit=1)[0]
    parsed = urlparse(cleaned_url)

    if parsed.netloc == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 5 and parts[2] == "blob":
            owner, repo, _, branch, *path_parts = parts
            return f"{RAW_GITHUB_BASE_URL}/{owner}/{repo}/{branch}/{'/'.join(path_parts)}"

    if parsed.scheme in {"http", "https"}:
        return cleaned_url

    return urljoin(base_url, cleaned_url)


def _markdown_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", value)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"<br\s*/?>", "; ", text, flags=re.IGNORECASE)
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = unescape(text)
    text = text.replace(r"\|", "|")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _normalize_header(header: str) -> str:
    normalized = _markdown_text(header) or ""
    normalized = normalized.casefold().replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _remote_status(location: str | None) -> bool | None:
    if location is None:
        return None
    if "remote" in location.casefold():
        return True
    return None
