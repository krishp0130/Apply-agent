"""CSV-backed tracking repositories for recruiting workflows."""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Generic, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

RowModel = TypeVar("RowModel", bound=BaseModel)


class CsvRepository(Generic[RowModel]):
    """Append-only CSV repository for Pydantic row models."""

    def __init__(self, path: Path, row_type: type[RowModel]) -> None:
        self.path = path
        self.row_type = row_type
        self._fieldnames = list(row_type.model_fields)

    def append(self, row: RowModel) -> None:
        """Persist one validated row to the CSV file."""
        if not isinstance(row, self.row_type):
            msg = f"Expected {self.row_type.__name__}, got {type(row).__name__}."
            raise TypeError(msg)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not self.path.exists() or self.path.stat().st_size == 0

        if not needs_header:
            self._validate_header()

        with self.path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self._fieldnames)
            if needs_header:
                writer.writeheader()
            writer.writerow(self._serialize(row))

        logger.info(
            "Appended %s row to %s",
            self.row_type.__name__,
            self.path,
        )

    def extend(self, rows: Iterable[RowModel]) -> None:
        """Persist multiple rows in order."""
        for row in rows:
            self.append(row)

    def list(self) -> list[RowModel]:
        """Read all CSV rows and validate them as Pydantic models."""
        if not self.path.exists():
            logger.info("Tracking file does not exist yet: %s", self.path)
            return []

        with self.path.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            self._validate_fieldnames(reader.fieldnames)
            rows = [
                self.row_type.model_validate(self._deserialize(raw_row))
                for raw_row in reader
            ]

        logger.info(
            "Loaded %d %s rows from %s",
            len(rows),
            self.row_type.__name__,
            self.path,
        )
        return rows

    def _serialize(self, row: RowModel) -> dict[str, str]:
        values = row.model_dump(mode="json")
        return {
            field: self._serialize_value(values.get(field))
            for field in self._fieldnames
        }

    def _deserialize(self, row: dict[str, str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field, value in row.items():
            if value == "" and self._field_allows_none(field):
                values[field] = None
            elif value.startswith(("[", "{")):
                values[field] = _deserialize_json_value(value)
            else:
                values[field] = value
        return values

    def _validate_header(self) -> None:
        with self.path.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader, None)
        self._validate_fieldnames(header)

    def _validate_fieldnames(self, fieldnames: list[str] | None) -> None:
        if fieldnames != self._fieldnames:
            msg = (
                f"CSV header for {self.path} does not match "
                f"{self.row_type.__name__}: expected {self._fieldnames}, "
                f"got {fieldnames}."
            )
            raise ValueError(msg)

    def _field_allows_none(self, field: str) -> bool:
        annotation = self.row_type.model_fields[field].annotation
        return _allows_none(annotation)

    @staticmethod
    def _serialize_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list | dict):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)


class RoleRow(BaseModel):
    """Tracked internship role row."""

    model_config = ConfigDict(extra="forbid")

    role_id: str
    company_name: str
    role_title: str
    location: str = "unknown"
    application_url: str = "unknown"
    source: str
    date_discovered: date
    internship_term: str = "unknown"
    required_skills: list[str] = Field(default_factory=list)
    notes: str = ""
    fit_score: int | None = None
    fit_reasoning: str = ""


class ContactRow(BaseModel):
    """Tracked recruiting contact row."""

    model_config = ConfigDict(extra="forbid")

    contact_id: str
    company_name: str
    full_name: str
    title: str
    source: str
    date_found: date
    profile_url: str = "unknown"
    email: str = "unknown"
    priority: int | None = None
    notes: str = ""


class ApprovalRow(BaseModel):
    """Tracked human approval request row."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    action_type: str
    target_id: str
    requested_at: datetime
    approved: bool | None = None
    approved_at: datetime | None = None
    notes: str = ""


class OutreachDraftRow(BaseModel):
    """Tracked outreach draft row."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    company_name: str
    subject: str
    body: str
    created_at: datetime
    contact_id: str = "unknown"
    role_id: str = "unknown"
    status: str = "draft_created"
    notes: str = ""


class ApplicationEventRow(BaseModel):
    """Tracked application workflow event row."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    role_id: str
    event_type: str
    occurred_at: datetime
    status: str
    notes: str = ""


def _allows_none(annotation: Any) -> bool:
    if annotation is None or annotation is NoneType:
        return True

    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        return any(_allows_none(argument) for argument in get_args(annotation))

    return False


def _deserialize_json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
