from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from internship_agent.resume_latex import (
    LatexCompileStatus,
    LatexCompilerRun,
    LatexOperationKind,
    LatexTailoringOperation,
    LatexTextMode,
    OverwriteApprovalRequiredError,
    ResumeTailoringRequest,
    apply_tailoring_plan,
    compile_latex_document,
    create_tailoring_plan,
    escape_latex_text,
    read_latex_source,
    select_compiler_command,
)


RESUME_SOURCE = r"""\documentclass{article}
\begin{document}
\section{Experience}
\resumeItem{Built Python automation for CSV tracking.}
\section{Skills}
Python, pandas
\end{document}
"""


def test_create_tailoring_plan_reads_source_and_refuses_missing_evidence(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "resume.tex"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")
    supported_operation = LatexTailoringOperation(
        kind=LatexOperationKind.REPLACE,
        anchor_text="Python, pandas",
        replacement_text="Python, pandas, Playwright",
        evidence="Python, pandas",
    )
    fabricated_operation = LatexTailoringOperation(
        kind=LatexOperationKind.REPLACE,
        anchor_text="Python, pandas",
        replacement_text="Python, pandas, Kubernetes",
        evidence="Kubernetes production ownership",
    )

    plan = create_tailoring_plan(
        ResumeTailoringRequest(
            source_path=source_path,
            job_description="Python intern role using Playwright.",
            operations=(supported_operation, fabricated_operation),
        ),
    )

    assert plan.source_text == RESUME_SOURCE
    assert plan.output_path == tmp_path / "resume_tailored.tex"
    assert plan.operations == (supported_operation,)
    assert len(plan.refused_operations) == 1
    assert (
        plan.refused_operations[0].missing_evidence
        == "Kubernetes production ownership"
    )


def test_apply_tailoring_plan_writes_new_file_and_preserves_source(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "resume.tex"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")
    operation = LatexTailoringOperation(
        kind=LatexOperationKind.INSERT_AFTER,
        anchor_text="Python, pandas",
        insert_text=", C++ & ML_ops",
        evidence="C++ & ML_ops",
        text_mode=LatexTextMode.PLAIN_TEXT,
    )

    plan = create_tailoring_plan(
        ResumeTailoringRequest(
            source_path=source_path,
            job_description="Role asks for C++.",
            operations=(operation,),
            known_facts=("C++ & ML_ops",),
        ),
    )
    result = apply_tailoring_plan(plan)

    assert result.output_path == tmp_path / "resume_tailored.tex"
    assert source_path.read_text(encoding="utf-8") == RESUME_SOURCE
    assert "Python, pandas, C++ \\& ML\\_ops" in result.output_path.read_text(
        encoding="utf-8",
    )
    assert result.overwritten_source is False


def test_overwriting_source_requires_explicit_approval(tmp_path: Path) -> None:
    source_path = tmp_path / "resume.tex"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")
    operation = LatexTailoringOperation(
        kind=LatexOperationKind.REPLACE,
        anchor_text="Python, pandas",
        replacement_text="Python, pandas, BeautifulSoup",
        evidence="Python, pandas",
    )
    plan = create_tailoring_plan(
        ResumeTailoringRequest(
            source_path=source_path,
            output_path=source_path,
            job_description="Role mentions parsing.",
            operations=(operation,),
        ),
    )

    assert plan.requires_overwrite_approval is True
    with pytest.raises(OverwriteApprovalRequiredError):
        apply_tailoring_plan(plan)


def test_overwrite_source_after_explicit_approval(tmp_path: Path) -> None:
    source_path = tmp_path / "resume.tex"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")
    operation = LatexTailoringOperation(
        kind=LatexOperationKind.REPLACE,
        anchor_text="Python, pandas",
        replacement_text="Python, pandas, BeautifulSoup",
        evidence="Python, pandas",
    )

    plan = create_tailoring_plan(
        ResumeTailoringRequest(
            source_path=source_path,
            output_path=source_path,
            job_description="Role mentions parsing.",
            operations=(operation,),
            overwrite_source=True,
            overwrite_approved=True,
        ),
    )
    result = apply_tailoring_plan(plan)

    assert plan.requires_overwrite_approval is False
    assert result.overwritten_source is True
    assert "BeautifulSoup" in source_path.read_text(encoding="utf-8")


def test_read_latex_source_requires_tex_extension(tmp_path: Path) -> None:
    source_path = tmp_path / "resume.txt"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")

    with pytest.raises(ValueError):
        read_latex_source(source_path)


def test_escape_latex_text_escapes_plain_text_characters() -> None:
    assert escape_latex_text(r"C++ & 50%_done #1") == r"C++ \& 50\%\_done \#1"


def test_select_compiler_command_prefers_latexmk(tmp_path: Path) -> None:
    def fake_lookup(name: str) -> str | None:
        return {
            "latexmk": "/usr/bin/latexmk",
            "pdflatex": "/usr/bin/pdflatex",
        }.get(name)

    command = select_compiler_command(
        tmp_path / "resume.tex",
        tmp_path / "build",
        compiler_lookup=fake_lookup,
    )

    assert command is not None
    assert command.executable == "/usr/bin/latexmk"
    assert command.args[0] == "-pdf"


def test_select_compiler_command_falls_back_to_pdflatex(tmp_path: Path) -> None:
    def fake_lookup(name: str) -> str | None:
        return "/usr/bin/pdflatex" if name == "pdflatex" else None

    command = select_compiler_command(
        tmp_path / "resume.tex",
        tmp_path / "build",
        compiler_lookup=fake_lookup,
    )

    assert command is not None
    assert command.executable == "/usr/bin/pdflatex"
    assert "-output-directory" in command.args


def test_compile_latex_document_blocks_when_compiler_missing(tmp_path: Path) -> None:
    tex_path = tmp_path / "resume.tex"
    tex_path.write_text(RESUME_SOURCE, encoding="utf-8")

    result = compile_latex_document(
        tex_path,
        compiler_lookup=lambda _name: None,
    )

    assert result.status == LatexCompileStatus.BLOCKED
    assert result.log_path == tmp_path / "latex_build" / "resume.log"
    assert result.command is None


def test_compile_latex_document_uses_injected_runner(tmp_path: Path) -> None:
    tex_path = tmp_path / "resume.tex"
    tex_path.write_text(RESUME_SOURCE, encoding="utf-8")
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_lookup(name: str) -> str | None:
        return "/usr/bin/latexmk" if name == "latexmk" else None

    def fake_runner(command: Sequence[str], *, cwd: Path) -> LatexCompilerRun:
        calls.append((tuple(command), cwd))
        return LatexCompilerRun(returncode=0, stdout="ok")

    result = compile_latex_document(
        tex_path,
        compiler_lookup=fake_lookup,
        runner=fake_runner,
    )

    assert result.status == LatexCompileStatus.SUCCESS
    assert result.pdf_path == tmp_path / "latex_build" / "resume.pdf"
    assert result.stdout == "ok"
    assert calls == [(result.command, tmp_path)]


def test_apply_tailoring_plan_can_return_compile_status_without_tex(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "resume.tex"
    source_path.write_text(RESUME_SOURCE, encoding="utf-8")
    plan = create_tailoring_plan(
        ResumeTailoringRequest(
            source_path=source_path,
            job_description="Python role.",
        ),
    )

    result = apply_tailoring_plan(
        plan,
        compile_pdf=True,
        compiler_lookup=lambda _name: None,
    )

    assert result.compile_result is not None
    assert result.compile_result.status == LatexCompileStatus.BLOCKED
