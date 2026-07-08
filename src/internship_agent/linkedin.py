"""Safe LinkedIn ingestion boundaries for user-provided job snippets."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import Field, ValidationError

from internship_agent.models import InternshipRole, UnknownAwareModel
from internship_agent.parsing import UNKNOWN

logger = logging.getLogger(__name__)

LINKEDIN_SOURCE = "linkedin"
LINKEDIN_BASE_URL = "https://www.linkedin.com"


class LinkedInSearchConfig(UnknownAwareModel):
    """User-selected LinkedIn search scope for already-provided snippets."""

    search_terms: list[str] = Field(default_factory=list)
    recency_days: int = Field(default=7, ge=1, le=30)
    location_filters: list[str] = Field(default_factory=list)


class LinkedInBrowserGuardrails(UnknownAwareModel):
    """Hard constraints for any caller that uses browser automation."""

    pause_on_login_or_auth: Literal[True] = True
    pause_on_captcha: Literal[True] = True
    pause_on_mfa: Literal[True] = True
    must_not_submit_applications: Literal[True] = True
    credentials_supported: Literal[False] = False
    login_bypass_supported: Literal[False] = False
    default_scraping_loop_supported: Literal[False] = False


DEFAULT_GUARDRAILS = LinkedInBrowserGuardrails()


def parse_linkedin_job_cards(
    job_cards: Iterable[Mapping[str, Any]],
    *,
    config: LinkedInSearchConfig | None = None,
) -> list[InternshipRole]:
    """Parse browser-extracted LinkedIn job card dictionaries into roles."""
    config = config or LinkedInSearchConfig()
    roles: list[InternshipRole] = []

    for job_card in job_cards:
        role = _role_from_card_data(_normalize_card_data(job_card))
        if _matches_scope(role, _card_posted_text(job_card), config):
            roles.append(role)

    logger.info("Parsed %d LinkedIn roles from provided job cards", len(roles))
    return roles


def parse_linkedin_snippet(
    snippet: str,
    *,
    config: LinkedInSearchConfig | None = None,
) -> list[InternshipRole]:
    """Parse a user-provided LinkedIn HTML or plain-text snippet into roles."""
    if _looks_like_html(snippet):
        return parse_linkedin_html_snippet(snippet, config=config)
    return parse_linkedin_text_snippet(snippet, config=config)


def parse_linkedin_html_snippet(
    html: str,
    *,
    config: LinkedInSearchConfig | None = None,
) -> list[InternshipRole]:
    """Parse user-provided LinkedIn-like HTML without fetching remote pages."""
    config = config or LinkedInSearchConfig()
    soup = BeautifulSoup(html, "html.parser")
    cards = _select_html_cards(soup)

    roles: list[InternshipRole] = []
    for card in cards:
        data = _extract_html_card_data(card)
        role = _role_from_card_data(data)
        if _matches_scope(role, data.get("posted_at"), config):
            roles.append(role)

    logger.info("Parsed %d LinkedIn roles from provided HTML", len(roles))
    return roles


def parse_linkedin_text_snippet(
    text: str,
    *,
    config: LinkedInSearchConfig | None = None,
) -> list[InternshipRole]:
    """Parse user-provided LinkedIn-like plain text without network access."""
    config = config or LinkedInSearchConfig()
    blocks = [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]

    roles: list[InternshipRole] = []
    for block in blocks:
        data = _extract_text_card_data(block)
        role = _role_from_card_data(data)
        if _matches_scope(role, data.get("posted_at"), config):
            roles.append(role)

    logger.info("Parsed %d LinkedIn roles from provided text", len(roles))
    return roles


def linkedin_browser_guardrails() -> LinkedInBrowserGuardrails:
    """Return the non-negotiable LinkedIn browser automation guardrails."""
    return DEFAULT_GUARDRAILS


def _normalize_card_data(
    job_card: Mapping[str, Any],
) -> dict[str, str | list[str] | bool | None]:
    return {
        "company": _first_string(job_card, "company", "company_name", "employer"),
        "title": _first_string(job_card, "title", "job_title", "role"),
        "application_url": _first_string(
            job_card,
            "application_url",
            "url",
            "job_url",
            "link",
        ),
        "location": _first_string(job_card, "location", "job_location"),
        "remote": _first_bool(job_card, "remote", "is_remote"),
        "internship_term": _first_string(job_card, "internship_term", "term"),
        "required_skills": _skills_from_value(
            job_card.get("required_skills", job_card.get("skills")),
        ),
        "description": _first_string(
            job_card,
            "description",
            "summary",
            "insight",
            "metadata",
        ),
        "posted_at": _card_posted_text(job_card),
    }


def _role_from_card_data(data: Mapping[str, Any]) -> InternshipRole:
    role_data = {
        "company": _string_or_unknown(data.get("company")),
        "title": _string_or_unknown(data.get("title")),
        "application_url": _absolute_linkedin_url(data.get("application_url")),
        "source": LINKEDIN_SOURCE,
        "location": _string_or_unknown(data.get("location")),
        "remote": _remote_status(data),
        "internship_term": _string_or_unknown(data.get("internship_term")),
        "required_skills": _skills_from_value(data.get("required_skills")),
        "description": _string_or_unknown(data.get("description")),
    }

    try:
        return InternshipRole.model_validate(role_data)
    except ValidationError as error:
        logger.warning("Dropping invalid LinkedIn application URL: %s", error)
        role_data["application_url"] = None
        return InternshipRole.model_validate(role_data)


def _matches_scope(
    role: InternshipRole,
    posted_text: Any,
    config: LinkedInSearchConfig,
) -> bool:
    return (
        _matches_search_terms(role, config.search_terms)
        and _matches_locations(role, config.location_filters)
        and _matches_recency(posted_text, config.recency_days)
    )


def _matches_search_terms(role: InternshipRole, search_terms: Sequence[str]) -> bool:
    terms = [_normalize_filter_value(term) for term in search_terms if term.strip()]
    if not terms:
        return True

    haystack = " ".join(
        value
        for value in [role.title, role.description]
        if value and value != UNKNOWN
    ).casefold()
    return any(term in haystack for term in terms)


def _matches_locations(role: InternshipRole, location_filters: Sequence[str]) -> bool:
    filters = [_normalize_filter_value(item) for item in location_filters if item.strip()]
    if not filters:
        return True
    if role.location is None or role.location == UNKNOWN:
        return False

    location = role.location.casefold()
    return any(item in location for item in filters)


def _matches_recency(posted_text: Any, recency_days: int) -> bool:
    posting_age_days = _posting_age_days(posted_text)
    if posting_age_days is None:
        return True
    return posting_age_days <= recency_days


def _posting_age_days(posted_text: Any) -> int | None:
    if not isinstance(posted_text, str):
        return None

    text = posted_text.strip().casefold()
    if not text:
        return None
    if any(marker in text for marker in ["just posted", "now", "today", "moments ago"]):
        return 0

    match = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", text)
    if match is None:
        return None

    amount = int(match.group(1))
    unit = match.group(2)
    if unit in {"minute", "hour"}:
        return 0
    if unit == "day":
        return amount
    if unit == "week":
        return amount * 7
    return amount * 30


def _select_html_cards(soup: BeautifulSoup) -> list[Tag]:
    selectors = [
        "[data-linkedin-job-card]",
        "[data-job-id]",
        ".job-card-container",
        ".jobs-search-results__list-item",
        "li",
        "article",
    ]
    for selector in selectors:
        cards = [card for card in soup.select(selector) if isinstance(card, Tag)]
        if cards:
            return cards
    return []


def _extract_html_card_data(card: Tag) -> dict[str, str | list[str] | bool | None]:
    return {
        "company": _html_text(
            card,
            [
                "[data-company]",
                ".job-card-container__primary-description",
                ".base-search-card__subtitle",
                ".company",
            ],
        ),
        "title": _html_text(
            card,
            [
                "[data-title]",
                ".job-card-list__title",
                ".job-card-container__link",
                ".base-search-card__title",
                "h3",
                "h2",
            ],
        ),
        "application_url": _html_href(
            card,
            [
                "[data-application-url]",
                "a.job-card-container__link[href]",
                "a.base-card__full-link[href]",
                "a[href]",
            ],
        ),
        "location": _html_text(
            card,
            [
                "[data-location]",
                ".job-card-container__metadata-item",
                ".job-search-card__location",
                ".location",
            ],
        ),
        "remote": None,
        "internship_term": _html_text(card, ["[data-term]", ".term"]),
        "required_skills": _skills_from_value(_html_text(card, ["[data-skills]", ".skills"])),
        "description": _html_text(
            card,
            [
                "[data-description]",
                ".job-card-container__footer-item",
                ".description",
            ],
        ),
        "posted_at": _html_text(
            card,
            [
                "[data-posted-at]",
                "time",
                ".job-card-container__listed-time",
                ".posted",
            ],
        ),
    }


def _extract_text_card_data(text: str) -> dict[str, str | list[str] | bool | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    url = next((line for line in lines if line.startswith(("http://", "https://"))), None)
    posted_at = next((line for line in lines if _posting_age_days(line) is not None), None)
    non_metadata_lines = [
        line for line in lines if line != url and line != posted_at and not line.startswith("Easy Apply")
    ]

    return {
        "title": non_metadata_lines[0] if len(non_metadata_lines) >= 1 else None,
        "company": non_metadata_lines[1] if len(non_metadata_lines) >= 2 else None,
        "location": non_metadata_lines[2] if len(non_metadata_lines) >= 3 else None,
        "application_url": url,
        "remote": None,
        "internship_term": None,
        "required_skills": [],
        "description": " ".join(non_metadata_lines[3:]) or None,
        "posted_at": posted_at,
    }


def _html_text(card: Tag, selectors: Sequence[str]) -> str | None:
    for selector in selectors:
        selected = card.select_one(selector)
        if selected is None:
            continue
        text = selected.get_text(" ", strip=True)
        if text:
            return _clean_text(text)
    return None


def _html_href(card: Tag, selectors: Sequence[str]) -> str | None:
    for selector in selectors:
        selected = card.select_one(selector)
        if not isinstance(selected, Tag):
            continue
        href = selected.get("href")
        if isinstance(href, str) and href.strip():
            return href.strip()
    return None


def _absolute_linkedin_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return urljoin(LINKEDIN_BASE_URL, value.strip())


def _first_string(job_card: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = job_card.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value)
    return None


def _first_bool(job_card: Mapping[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = job_card.get(key)
        if isinstance(value, bool):
            return value
    return None


def _card_posted_text(job_card: Mapping[str, Any]) -> str | None:
    return _first_string(job_card, "posted_at", "posted", "listed_at", "age")


def _string_or_unknown(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return _clean_text(value)
    return UNKNOWN


def _skills_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_skills = re.split(r"[,;•\n]+", value)
    elif isinstance(value, Iterable):
        raw_skills = [str(item) for item in value]
    else:
        return []

    skills: list[str] = []
    seen: set[str] = set()
    for raw_skill in raw_skills:
        skill = raw_skill.strip()
        normalized = skill.casefold()
        if not skill or normalized in seen:
            continue
        seen.add(normalized)
        skills.append(skill)
    return skills


def _remote_status(data: Mapping[str, Any]) -> bool | None:
    remote = data.get("remote")
    if isinstance(remote, bool):
        return remote

    location = data.get("location")
    if isinstance(location, str) and "remote" in location.casefold():
        return True
    return None


def _normalize_filter_value(value: str) -> str:
    return value.strip().casefold()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_html(value: str) -> bool:
    return bool(re.search(r"<[a-zA-Z][^>]*>", value))
