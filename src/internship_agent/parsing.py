"""HTML parsing helpers for internship source ingestion."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import Field, HttpUrl, ValidationError

from internship_agent.models import InternshipRole, UnknownAwareModel

logger = logging.getLogger(__name__)

UNKNOWN = "unknown"


class HtmlRoleParserConfig(UnknownAwareModel):
    """CSS selectors that map an HTML source into internship role fields."""

    role_selector: str = Field(default="[data-internship-role]", min_length=1)
    company_selector: str | None = "[data-company]"
    title_selector: str | None = "[data-title]"
    application_url_selector: str | None = "a[href]"
    location_selector: str | None = "[data-location]"
    internship_term_selector: str | None = "[data-term]"
    required_skills_selector: str | None = "[data-skills]"
    description_selector: str | None = "[data-description]"


def parse_internship_roles_from_html(
    html: str,
    *,
    source_name: str,
    source_url: HttpUrl | str | None = None,
    parser_config: HtmlRoleParserConfig | None = None,
) -> list[InternshipRole]:
    """Parse configured role cards from HTML into validated internship roles."""
    parser_config = parser_config or HtmlRoleParserConfig()
    soup = BeautifulSoup(html, "html.parser")
    role_cards = soup.select(parser_config.role_selector)

    roles: list[InternshipRole] = []
    for card in role_cards:
        if not isinstance(card, Tag):
            continue

        role = _parse_role_card(
            card,
            source_name=source_name,
            source_url=source_url,
            parser_config=parser_config,
        )
        roles.append(role)

    logger.info("Parsed %d internship roles from %s", len(roles), source_name)
    return roles


def _parse_role_card(
    card: Tag,
    *,
    source_name: str,
    source_url: HttpUrl | str | None,
    parser_config: HtmlRoleParserConfig,
) -> InternshipRole:
    location = _selected_text(card, parser_config.location_selector)
    description = _selected_text(card, parser_config.description_selector)

    role_data = {
        "company": _selected_text(card, parser_config.company_selector) or UNKNOWN,
        "title": _selected_text(card, parser_config.title_selector) or UNKNOWN,
        "application_url": _selected_url(
            card,
            parser_config.application_url_selector,
            source_url,
        ),
        "source": source_name,
        "location": location,
        "remote": _remote_status(location),
        "internship_term": _selected_text(
            card,
            parser_config.internship_term_selector,
        ),
        "required_skills": _selected_skills(
            card,
            parser_config.required_skills_selector,
        ),
        "description": description,
    }

    try:
        return InternshipRole.model_validate(role_data)
    except ValidationError as error:
        logger.warning(
            "Dropping invalid application URL while parsing role from %s: %s",
            source_name,
            error,
        )
        role_data["application_url"] = None
        return InternshipRole.model_validate(role_data)


def _selected_text(card: Tag, selector: str | None) -> str | None:
    if selector is None:
        return None

    selected = card.select_one(selector)
    if selected is None:
        return None

    text = selected.get_text(" ", strip=True)
    return text or None


def _selected_url(
    card: Tag,
    selector: str | None,
    source_url: HttpUrl | str | None,
) -> str | None:
    if selector is None:
        return None

    selected = card.select_one(selector)
    if not isinstance(selected, Tag):
        return None

    href = selected.get("href")
    if not isinstance(href, str) or not href.strip():
        return None

    if source_url is None:
        return href.strip()

    return urljoin(str(source_url), href.strip())


def _selected_skills(card: Tag, selector: str | None) -> list[str]:
    if selector is None:
        return []

    selected = card.select(selector)
    skills: list[str] = []
    for element in selected:
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        skills.extend(_split_skills(text))

    return _dedupe_preserving_order(skills)


def _split_skills(text: str) -> list[str]:
    return [
        skill.strip()
        for skill in re.split(r"[,;•\n]+", text)
        if skill.strip()
    ]


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def _remote_status(location: str | None) -> bool | None:
    if location is None:
        return None
    if "remote" in location.casefold():
        return True
    return None
