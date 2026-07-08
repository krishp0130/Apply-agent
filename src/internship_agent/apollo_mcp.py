"""Concrete Apollo MCP client seam.

This module adapts an injected async MCP tool caller to ``ApolloClientProtocol``
without assuming the final Apollo MCP schema. The deployer must fill in:

- MCP server name.
- MCP tool name.
- Required environment variables.
- Search input schema.
- Result output schema.
- Rate limits or usage constraints.
- Email verification fields, if available.
- Any required review step before storing returned personal data.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from internship_agent.apollo import (
    ApolloCompanyContactQuery,
    ApolloContactResult,
    UNKNOWN_MARKERS,
)


DEFAULT_APOLLO_MCP_SERVER_NAME = "apollo"
DEFAULT_APOLLO_MCP_TOOL_NAME = "search_company_contacts"

DEFAULT_QUERY_FIELD_MAPPING: dict[str, str] = {
    "company_name": "company_name",
    "company_domain": "company_domain",
    "role_title": "role_title",
    "location": "location",
    "small_startup": "small_startup",
    "max_contacts": "max_contacts",
    "target_roles": "target_roles",
}

DEFAULT_CONTACT_FIELD_MAPPING: dict[str, str | tuple[str, ...]] = {
    "name": ("name", "full_name", "person.name", "person.full_name"),
    "company": (
        "company",
        "company_name",
        "organization.name",
        "person.organization.name",
    ),
    "title": ("title", "job_title", "person.title", "person.job_title"),
    "email": ("email", "email_address", "person.email", "person.email_address"),
    "profile_url": (
        "profile_url",
        "linkedin_url",
        "linkedin_profile_url",
        "person.profile_url",
        "person.linkedin_url",
        "person.linkedin_profile_url",
    ),
    "location": ("location", "person.location"),
    "apollo_id": ("apollo_id", "id", "person.apollo_id", "person.id"),
    "notes": ("notes", "person.notes"),
}

_MISSING = object()


class ApolloMCPResponseError(ValueError):
    """Raised when an MCP tool response cannot be normalized safely."""


@runtime_checkable
class MCPToolCallerProtocol(Protocol):
    """Minimal async seam for whichever MCP client runtime is installed later."""

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> Any:
        """Call an MCP tool and return its decoded response payload."""


class ApolloMCPClientConfig(BaseModel):
    """Configurable MCP tool and schema mapping details."""

    model_config = ConfigDict(frozen=True)

    server_name: str = DEFAULT_APOLLO_MCP_SERVER_NAME
    tool_name: str = DEFAULT_APOLLO_MCP_TOOL_NAME
    result_list_path: str | None = None
    query_field_mapping: Mapping[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_QUERY_FIELD_MAPPING)
    )
    contact_field_mapping: Mapping[str, str | Sequence[str]] = Field(
        default_factory=lambda: dict(DEFAULT_CONTACT_FIELD_MAPPING)
    )

    @field_validator("server_name", "tool_name", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("result_list_path", mode="before")
    @classmethod
    def _strip_optional_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("contact_field_mapping")
    @classmethod
    def _require_name_mapping(
        cls,
        value: Mapping[str, str | Sequence[str]],
    ) -> Mapping[str, str | Sequence[str]]:
        if "name" not in value:
            raise ValueError("contact_field_mapping must include required field 'name'")
        return value


class ApolloMCPClient:
    """ApolloClientProtocol adapter backed by an injected async MCP tool caller."""

    def __init__(
        self,
        tool_caller: MCPToolCallerProtocol,
        config: ApolloMCPClientConfig | None = None,
    ) -> None:
        self._tool_caller = tool_caller
        self._config = config or ApolloMCPClientConfig()

    async def search_company_contacts(
        self,
        query: ApolloCompanyContactQuery,
    ) -> Sequence[ApolloContactResult]:
        """Call the configured MCP tool and normalize returned contact dicts."""

        arguments = self._build_arguments(query)
        response = await self._tool_caller.call_tool(
            self._config.server_name,
            self._config.tool_name,
            arguments,
        )
        records = self._extract_contact_records(response)

        return tuple(
            self._normalize_contact_record(record, index=index)
            for index, record in enumerate(records)
        )

    def _build_arguments(self, query: ApolloCompanyContactQuery) -> dict[str, Any]:
        arguments: dict[str, Any] = {}
        for query_field, tool_field in self._config.query_field_mapping.items():
            value = getattr(query, query_field, None)
            if value is None:
                continue
            _assign_path(arguments, _parse_path(tool_field), _serialize_value(value))
        return arguments

    def _extract_contact_records(self, response: Any) -> tuple[Mapping[str, Any], ...]:
        if self._config.result_list_path is not None:
            value = _lookup_path(response, _parse_path(self._config.result_list_path))
            if value is _MISSING:
                raise ApolloMCPResponseError(
                    "Apollo MCP response is missing configured result_list_path "
                    f"'{self._config.result_list_path}'."
                )
            return _coerce_record_sequence(value)

        discovered = _discover_record_sequence(response)
        if discovered is _MISSING:
            raise ApolloMCPResponseError(
                "Apollo MCP response did not contain a contact list. Configure "
                "ApolloMCPClientConfig.result_list_path for the actual tool schema."
            )
        return _coerce_record_sequence(discovered)

    def _normalize_contact_record(
        self,
        record: Mapping[str, Any],
        *,
        index: int,
    ) -> ApolloContactResult:
        normalized: dict[str, Any] = {}
        for result_field, source_paths in self._config.contact_field_mapping.items():
            value = _first_available_value(record, source_paths)
            if value is not _MISSING:
                normalized[result_field] = value

        if _is_missing_required_text(normalized.get("name")):
            raise ApolloMCPResponseError(
                "Apollo MCP result at index "
                f"{index} is missing required field 'name'. Configure "
                "contact_field_mapping['name'] or ensure the MCP tool returns it."
            )

        try:
            return ApolloContactResult.model_validate(normalized)
        except ValidationError as exc:
            raise ApolloMCPResponseError(
                f"Apollo MCP result at index {index} could not be normalized: {exc}"
            ) from exc


def _discover_record_sequence(value: Any) -> Any:
    if _is_sequence(value):
        return value

    if not isinstance(value, Mapping):
        return _MISSING

    for key in ("contacts", "people", "results", "items", "data"):
        if key in value:
            candidate = value[key]
            if _is_sequence(candidate):
                return candidate
            nested = _discover_record_sequence(candidate)
            if nested is not _MISSING:
                return nested

    for key in ("structuredContent", "structured_content"):
        if key in value:
            nested = _discover_record_sequence(value[key])
            if nested is not _MISSING:
                return nested

    if "content" in value:
        nested = _discover_content_records(value["content"])
        if nested is not _MISSING:
            return nested

    if _looks_like_contact_record(value):
        return (value,)

    return _MISSING


def _discover_content_records(value: Any) -> Any:
    if not _is_sequence(value):
        return _discover_record_sequence(value)

    for item in value:
        if not isinstance(item, Mapping):
            continue
        for key in ("json", "data"):
            if key in item:
                nested = _discover_record_sequence(item[key])
                if nested is not _MISSING:
                    return nested
        text = item.get("text")
        if isinstance(text, str):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                continue
            nested = _discover_record_sequence(decoded)
            if nested is not _MISSING:
                return nested
    return _MISSING


def _coerce_record_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        value = (value,)

    if not _is_sequence(value):
        raise ApolloMCPResponseError(
            "Apollo MCP contact result path must resolve to a list of objects."
        )

    records: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ApolloMCPResponseError(
                "Apollo MCP contact result at index "
                f"{index} must be an object, not {type(item).__name__}."
            )
        records.append(item)
    return tuple(records)


def _first_available_value(
    record: Mapping[str, Any],
    source_paths: str | Sequence[str],
) -> Any:
    for path in _candidate_paths(source_paths):
        value = _lookup_path(record, path)
        if value is not _MISSING:
            return value
    return _MISSING


def _lookup_path(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _assign_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        nested = current.setdefault(segment, {})
        if not isinstance(nested, dict):
            raise ValueError(f"query field path '{'.'.join(path)}' conflicts")
        current = nested
    current[path[-1]] = value


def _candidate_paths(value: str | Sequence[str]) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, str):
        return (_parse_path(value),)
    return tuple(_parse_path(candidate) for candidate in value)


def _parse_path(value: str) -> tuple[str, ...]:
    path = tuple(segment.strip() for segment in value.split(".") if segment.strip())
    if not path:
        raise ValueError("field paths must not be empty")
    return path


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_value(mapped_value)
            for key, mapped_value in value.items()
        }
    return value


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    )


def _looks_like_contact_record(value: Mapping[str, Any]) -> bool:
    return any(
        key in value
        for key in (
            "name",
            "full_name",
            "title",
            "job_title",
            "email",
            "linkedin_url",
            "profile_url",
        )
    )


def _is_missing_required_text(value: Any) -> bool:
    if value is None:
        return True
    stripped = str(value).strip()
    return stripped.lower() in UNKNOWN_MARKERS
