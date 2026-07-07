from __future__ import annotations

import json
from datetime import date
from io import StringIO
from pathlib import Path

from internship_agent.cli import run
from internship_agent.tracking import CsvRepository, RoleRow


def test_status_command_renders_text_summary(tmp_path: Path) -> None:
    tracking_dir = tmp_path / "tracking"
    CsvRepository(tracking_dir / "roles.csv", RoleRow).append(
        RoleRow(
            role_id="role-1",
            company_name="Example Co",
            role_title="Backend Intern",
            source="company site",
            date_discovered=date(2026, 7, 7),
            fit_score=80,
        ),
    )
    output = StringIO()
    errors = StringIO()

    exit_code = run(
        ["status", "--tracking-dir", str(tracking_dir)],
        output_stream=output,
        error_stream=errors,
    )

    assert exit_code == 0
    assert "Internship Agent Status" in output.getvalue()
    assert "- roles: 1 (scored: 1, unscored: 0, below threshold: 0)" in output.getvalue()
    assert "- contacts: 0" in output.getvalue()
    assert errors.getvalue() == ""


def test_status_command_renders_json_summary(tmp_path: Path) -> None:
    output = StringIO()
    errors = StringIO()

    exit_code = run(
        ["status", "--tracking-dir", str(tmp_path), "--format", "json"],
        output_stream=output,
        error_stream=errors,
    )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["tracking_dir"] == str(tmp_path)
    assert payload["roles_total"] == 0
    assert payload["missing_files"] == [
        "roles.csv",
        "contacts.csv",
        "approvals.csv",
        "outreach_drafts.csv",
        "application_events.csv",
    ]
    assert errors.getvalue() == ""


def test_cli_requires_a_subcommand() -> None:
    output = StringIO()
    errors = StringIO()

    exit_code = run([], output_stream=output, error_stream=errors)

    assert exit_code == 2
    assert output.getvalue() == ""
    assert "usage: internship-agent" in errors.getvalue()
