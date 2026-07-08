# LaTeX Resume Workflow

## Scope

Implement safe, deterministic utilities for tailoring a LaTeX resume while
keeping every change reviewable and evidence-backed.

## Current Behavior

- Reads a user-selected `.tex` source file.
- Builds a reviewable plan from explicit replace and insert operations.
- Refuses operations whose evidence is not present in the source resume or
  approved facts supplied by the user.
- Writes tailored output to a separate `*_tailored.tex` file by default.
- Requires explicit overwrite approval before writing back to the source file.
- Escapes plain-text operation content before inserting it into LaTeX.
- Selects `latexmk` before `pdflatex`, and reports a blocked compile result when
  no compiler is installed.
- Runs compilation through an injected runner so tests do not require TeX.

## Follow-Ups

- Connect the planner to future AI-assisted suggestions while preserving the
  evidence checks.
- Add tracking rows for resume tailoring milestones when CSV schemas are updated.
