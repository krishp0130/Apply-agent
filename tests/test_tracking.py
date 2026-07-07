from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from internship_agent.tracking import (
    ApprovalRow,
    CsvRepository,
    RoleRow,
)


class ExampleRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: str
    tags: list[str]
    score: int | None = None


def test_append_and_list_round_trips_generic_pydantic_rows(tmp_path: Path) -> None:
    repository = CsvRepository(tmp_path / "examples.csv", ExampleRow)
    row = ExampleRow(row_id="row-1", tags=["python", "backend"], score=9)

    repository.append(row)

    assert repository.list() == [row]


def test_list_returns_empty_for_missing_file(tmp_path: Path) -> None:
    repository = CsvRepository(tmp_path / "missing.csv", ExampleRow)

    assert repository.list() == []


def test_role_row_round_trips_dates_lists_and_optional_values(tmp_path: Path) -> None:
    repository = CsvRepository(tmp_path / "roles.csv", RoleRow)
    row = RoleRow(
        role_id="role-1",
        company_name="Example Co",
        role_title="Software Engineering Intern",
        location="Remote",
        application_url="https://example.com/apply",
        source="company careers page",
        date_discovered=date(2026, 7, 7),
        internship_term="Summer 2027",
        required_skills=["Python", "SQL"],
        notes="Requires work authorization.",
        fit_score=None,
        fit_reasoning="Not scored yet.",
    )

    repository.append(row)

    assert repository.list() == [row]


def test_approval_row_round_trips_datetimes_booleans_and_none(
    tmp_path: Path,
) -> None:
    repository = CsvRepository(tmp_path / "approvals.csv", ApprovalRow)
    row = ApprovalRow(
        approval_id="approval-1",
        action_type="application_submit",
        target_id="role-1",
        requested_at=datetime(2026, 7, 7, 12, 30),
        approved=False,
        approved_at=None,
        notes="User declined for now.",
    )

    repository.append(row)

    assert repository.list() == [row]


def test_append_rejects_wrong_model_type(tmp_path: Path) -> None:
    repository = CsvRepository(tmp_path / "examples.csv", ExampleRow)
    wrong_row = RoleRow(
        role_id="role-1",
        company_name="Example Co",
        role_title="Software Engineering Intern",
        source="company careers page",
        date_discovered=date(2026, 7, 7),
    )

    with pytest.raises(TypeError, match="Expected ExampleRow"):
        repository.append(wrong_row)  # type: ignore[arg-type]


def test_append_rejects_existing_file_with_unexpected_header(
    tmp_path: Path,
) -> None:
    path = tmp_path / "examples.csv"
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["unexpected"])

    repository = CsvRepository(path, ExampleRow)

    with pytest.raises(ValueError, match="CSV header"):
        repository.append(ExampleRow(row_id="row-1", tags=[]))
