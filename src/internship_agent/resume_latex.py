"""Safe utilities for tailoring and compiling LaTeX resumes.

The functions in this module are intentionally deterministic. They do not
generate resume content; callers must provide explicit, reviewable operations
and evidence for every change.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections.abc import Callable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from internship_agent.models import UnknownAwareModel


DEFAULT_BUILD_DIR_NAME = "latex_build"
TAILORED_SUFFIX = "_tailored"

UNKNOWN_MARKERS = {
    "",
    "n/a",
    "na",
    "none",
    "not provided",
    "tbd",
    "unknown",
    "unspecified",
}


class ResumeLatexError(ValueError):
    """Base error for safe LaTeX resume workflow failures."""


class OverwriteApprovalRequiredError(ResumeLatexError):
    """Raised when an operation would overwrite the source without approval."""


class LatexOperationKind(StrEnum):
    """Supported explicit edit operations."""

    REPLACE = "replace"
    INSERT_BEFORE = "insert_before"
    INSERT_AFTER = "insert_after"


class LatexTextMode(StrEnum):
    """Whether operation text is already LaTeX or plain text to escape."""

    LATEX = "latex"
    PLAIN_TEXT = "plain_text"


class LatexCompileStatus(StrEnum):
    """Compile outcome without requiring TeX to be installed."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class LatexTailoringOperation(UnknownAwareModel):
    """A single reviewable and evidence-backed resume edit."""

    kind: LatexOperationKind
    anchor_text: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    replacement_text: str | None = None
    insert_text: str | None = None
    text_mode: LatexTextMode = LatexTextMode.LATEX

    @field_validator("anchor_text", "evidence")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if stripped.lower() in UNKNOWN_MARKERS:
            msg = "operation anchor and evidence must be known."
            raise ValueError(msg)
        return stripped

    @field_validator("replacement_text", "insert_text")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return None if stripped.lower() in UNKNOWN_MARKERS else stripped

    @model_validator(mode="after")
    def _validate_operation_text(self) -> LatexTailoringOperation:
        if self.kind == LatexOperationKind.REPLACE:
            if self.replacement_text is None:
                msg = "replace operations require replacement_text."
                raise ValueError(msg)
            if self.insert_text is not None:
                msg = "replace operations cannot include insert_text."
                raise ValueError(msg)
            return self

        if self.insert_text is None:
            msg = "insert operations require insert_text."
            raise ValueError(msg)
        if self.replacement_text is not None:
            msg = "insert operations cannot include replacement_text."
            raise ValueError(msg)
        return self


class RefusedLatexOperation(UnknownAwareModel):
    """A requested edit that was not safe to apply."""

    operation: LatexTailoringOperation
    reason: str
    missing_evidence: str | None = None


class ResumeTailoringRequest(UnknownAwareModel):
    """Inputs for creating a safe, reviewable tailoring plan."""

    source_path: Path
    job_description: str = Field(min_length=1)
    operations: tuple[LatexTailoringOperation, ...] = ()
    known_facts: tuple[str, ...] = ()
    instructions: str | None = None
    output_path: Path | None = None
    overwrite_source: bool = False
    overwrite_approved: bool = False

    @field_validator("source_path", "output_path")
    @classmethod
    def _require_tex_path(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        if value.suffix.lower() != ".tex":
            msg = "LaTeX resume paths must use the .tex extension."
            raise ValueError(msg)
        return value

    @field_validator("job_description")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if stripped.lower() in UNKNOWN_MARKERS:
            msg = "job_description must be known."
            raise ValueError(msg)
        return stripped

    @field_validator("instructions")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return None if stripped.lower() in UNKNOWN_MARKERS else stripped

    @field_validator("known_facts", mode="before")
    @classmethod
    def _strip_known_facts(cls, value: Sequence[str] | str | None) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        return tuple(
            fact.strip()
            for fact in value
            if fact is not None and fact.strip().lower() not in UNKNOWN_MARKERS
        )


class ResumeTailoringPlan(UnknownAwareModel):
    """A safe plan containing only operations that can be reviewed and applied."""

    source_path: Path
    output_path: Path
    source_sha256: str
    source_text: str
    operations: tuple[LatexTailoringOperation, ...]
    refused_operations: tuple[RefusedLatexOperation, ...] = ()
    requires_overwrite_approval: bool = False
    overwrite_source: bool = False
    overwrite_approved: bool = False


class LatexCompilerCommand(BaseModel):
    """Concrete compiler invocation selected for a LaTeX file."""

    model_config = ConfigDict(frozen=True)

    executable: str
    args: tuple[str, ...]

    @property
    def command(self) -> tuple[str, ...]:
        """Return the full command line."""

        return (self.executable, *self.args)


class LatexCompilerRun(BaseModel):
    """Normalized result returned by an injected compiler runner."""

    model_config = ConfigDict(frozen=True)

    returncode: int
    stdout: str = ""
    stderr: str = ""


class LatexCompileResult(BaseModel):
    """Compile status and paths, even when no compiler is installed."""

    model_config = ConfigDict(frozen=True)

    status: LatexCompileStatus
    tex_path: Path
    build_dir: Path
    log_path: Path
    pdf_path: Path | None = None
    command: tuple[str, ...] | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str | None = None


class ResumeTailoringResult(UnknownAwareModel):
    """Outcome after applying a safe tailoring plan."""

    source_path: Path
    output_path: Path
    source_sha256: str
    applied_operations: tuple[LatexTailoringOperation, ...]
    refused_operations: tuple[RefusedLatexOperation, ...]
    overwritten_source: bool = False
    compile_result: LatexCompileResult | None = None


class LatexCompileRunner(Protocol):
    """Injected compiler runner used to keep tests independent of TeX."""

    def __call__(self, command: Sequence[str], *, cwd: Path) -> LatexCompilerRun:
        """Run a selected compiler command in a working directory."""


CompilerLookup = Callable[[str], str | None]


def read_latex_source(path: Path) -> str:
    """Read a selected LaTeX resume source file."""

    if path.suffix.lower() != ".tex":
        msg = "LaTeX resume source must be a .tex file."
        raise ResumeLatexError(msg)
    return path.read_text(encoding="utf-8")


def create_tailoring_plan(request: ResumeTailoringRequest) -> ResumeTailoringPlan:
    """Read the source resume and produce safe, reviewable operations."""

    source_text = read_latex_source(request.source_path)
    output_path = request.output_path or default_tailored_output_path(
        request.source_path,
    )
    output_is_source = output_path.resolve() == request.source_path.resolve()
    requires_overwrite_approval = output_is_source and not (
        request.overwrite_source and request.overwrite_approved
    )

    operations: list[LatexTailoringOperation] = []
    refused_operations: list[RefusedLatexOperation] = []
    for operation in request.operations:
        refusal = _refusal_for_operation(operation, source_text, request.known_facts)
        if refusal is None:
            operations.append(operation)
        else:
            refused_operations.append(refusal)

    return ResumeTailoringPlan(
        source_path=request.source_path,
        output_path=output_path,
        source_sha256=_sha256(source_text),
        source_text=source_text,
        operations=tuple(operations),
        refused_operations=tuple(refused_operations),
        requires_overwrite_approval=requires_overwrite_approval,
        overwrite_source=output_is_source,
        overwrite_approved=request.overwrite_approved,
    )


def apply_tailoring_plan(
    plan: ResumeTailoringPlan,
    *,
    compile_pdf: bool = False,
    compiler_lookup: CompilerLookup = shutil.which,
    compiler_runner: LatexCompileRunner | None = None,
    build_dir: Path | None = None,
) -> ResumeTailoringResult:
    """Apply safe operations to an output file, using a new file by default."""

    if plan.requires_overwrite_approval:
        msg = "Overwriting the source resume requires explicit approval."
        raise OverwriteApprovalRequiredError(msg)

    tailored_source = plan.source_text
    for operation in plan.operations:
        tailored_source = _apply_operation(tailored_source, operation)

    plan.output_path.parent.mkdir(parents=True, exist_ok=True)
    plan.output_path.write_text(tailored_source, encoding="utf-8")

    compile_result = None
    if compile_pdf:
        compile_result = compile_latex_document(
            plan.output_path,
            build_dir=build_dir,
            compiler_lookup=compiler_lookup,
            runner=compiler_runner,
        )

    return ResumeTailoringResult(
        source_path=plan.source_path,
        output_path=plan.output_path,
        source_sha256=plan.source_sha256,
        applied_operations=plan.operations,
        refused_operations=plan.refused_operations,
        overwritten_source=plan.overwrite_source,
        compile_result=compile_result,
    )


def escape_latex_text(text: str) -> str:
    """Escape plain text so it can be inserted safely into LaTeX content."""

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def default_tailored_output_path(source_path: Path) -> Path:
    """Return the default non-source output path for a tailored resume."""

    return source_path.with_name(f"{source_path.stem}{TAILORED_SUFFIX}.tex")


def select_compiler_command(
    tex_path: Path,
    build_dir: Path,
    *,
    compiler_lookup: CompilerLookup = shutil.which,
) -> LatexCompilerCommand | None:
    """Prefer latexmk and fall back to pdflatex when selecting a compiler."""

    latexmk = compiler_lookup("latexmk")
    if latexmk is not None:
        return LatexCompilerCommand(
            executable=latexmk,
            args=(
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-outdir",
                str(build_dir),
                str(tex_path),
            ),
        )

    pdflatex = compiler_lookup("pdflatex")
    if pdflatex is not None:
        return LatexCompilerCommand(
            executable=pdflatex,
            args=(
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory",
                str(build_dir),
                str(tex_path),
            ),
        )

    return None


def compile_latex_document(
    tex_path: Path,
    *,
    build_dir: Path | None = None,
    compiler_lookup: CompilerLookup = shutil.which,
    runner: LatexCompileRunner | None = None,
) -> LatexCompileResult:
    """Compile a LaTeX document if a compiler is available."""

    if tex_path.suffix.lower() != ".tex":
        msg = "LaTeX compile input must be a .tex file."
        raise ResumeLatexError(msg)

    effective_build_dir = build_dir or tex_path.parent / DEFAULT_BUILD_DIR_NAME
    effective_build_dir.mkdir(parents=True, exist_ok=True)
    log_path = effective_build_dir / f"{tex_path.stem}.log"
    pdf_path = effective_build_dir / f"{tex_path.stem}.pdf"

    compiler_command = select_compiler_command(
        tex_path,
        effective_build_dir,
        compiler_lookup=compiler_lookup,
    )
    if compiler_command is None:
        return LatexCompileResult(
            status=LatexCompileStatus.BLOCKED,
            tex_path=tex_path,
            build_dir=effective_build_dir,
            log_path=log_path,
            reason="No LaTeX compiler found; install latexmk or pdflatex.",
        )

    effective_runner = runner or _run_compiler_subprocess
    try:
        run_result = effective_runner(
            compiler_command.command,
            cwd=tex_path.parent,
        )
    except FileNotFoundError as error:
        return LatexCompileResult(
            status=LatexCompileStatus.BLOCKED,
            tex_path=tex_path,
            build_dir=effective_build_dir,
            log_path=log_path,
            command=compiler_command.command,
            reason=str(error),
        )

    status = (
        LatexCompileStatus.SUCCESS
        if run_result.returncode == 0
        else LatexCompileStatus.FAILED
    )
    return LatexCompileResult(
        status=status,
        tex_path=tex_path,
        build_dir=effective_build_dir,
        log_path=log_path,
        pdf_path=pdf_path if status == LatexCompileStatus.SUCCESS else None,
        command=compiler_command.command,
        returncode=run_result.returncode,
        stdout=run_result.stdout,
        stderr=run_result.stderr,
    )


def _run_compiler_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
) -> LatexCompilerRun:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return LatexCompilerRun(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _refusal_for_operation(
    operation: LatexTailoringOperation,
    source_text: str,
    known_facts: Sequence[str],
) -> RefusedLatexOperation | None:
    if operation.anchor_text not in source_text:
        return RefusedLatexOperation(
            operation=operation,
            reason="anchor_text was not found in the source resume.",
        )

    if not _has_evidence(operation.evidence, source_text, known_facts):
        return RefusedLatexOperation(
            operation=operation,
            reason="operation evidence was not found in resume or approved facts.",
            missing_evidence=operation.evidence,
        )

    return None


def _has_evidence(
    evidence: str,
    source_text: str,
    known_facts: Sequence[str],
) -> bool:
    normalized_evidence = _normalize(evidence)
    if not normalized_evidence:
        return False
    if normalized_evidence in _normalize(source_text):
        return True
    return any(normalized_evidence in _normalize(fact) for fact in known_facts)


def _apply_operation(source_text: str, operation: LatexTailoringOperation) -> str:
    if operation.kind == LatexOperationKind.REPLACE:
        replacement = _operation_text(operation.replacement_text or "", operation)
        return source_text.replace(operation.anchor_text, replacement, 1)

    insertion = _operation_text(operation.insert_text or "", operation)
    if operation.kind == LatexOperationKind.INSERT_BEFORE:
        replacement = f"{insertion}{operation.anchor_text}"
    else:
        replacement = f"{operation.anchor_text}{insertion}"
    return source_text.replace(operation.anchor_text, replacement, 1)


def _operation_text(text: str, operation: LatexTailoringOperation) -> str:
    if operation.text_mode == LatexTextMode.PLAIN_TEXT:
        return escape_latex_text(text)
    return text


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
