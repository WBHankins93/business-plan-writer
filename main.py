"""
main.py
Business Plan Writer — Phase 1 Pipeline Entry Point

Usage:
    python main.py --intake path/to/intake.json [--no-pdf] [--output-dir path]

Pipeline:
    Agent 1 (Validator) → [Agent 2 (Market) || Agent 3 (Financial)]
    → Agent 4 (Writer) → Agent 5 (Critic) → optional revision + re-review
    → .docx + .pdf output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

from pipeline.artifacts import ArtifactService
from pipeline.contracts import EventType, PipelineRequest, PipelineStatus, ProgressEvent, RawIntake
from pipeline.orchestration import OrchestrationService

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
except ModuleNotFoundError:
    class Console:  # type: ignore[no-redef]
        def print(self, *args, **kwargs) -> None:
            print(*args)

        def log(self, *args, **kwargs) -> None:
            print(*args)

    class Panel:  # type: ignore[no-redef]
        @staticmethod
        def fit(content: str, **kwargs) -> str:
            return content

    class Rule:  # type: ignore[no-redef]
        def __init__(self, title: str = "", **kwargs) -> None:
            self.title = title

        def __str__(self) -> str:
            return self.title

console = Console()
progress_file: Path | None = None


def _step(label: str) -> None:
    console.print(Rule(f"[bold cyan]{label}[/bold cyan]", style="cyan"))


def _ok(msg: str) -> None:
    console.print(f"  [bold green]✓[/bold green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"  [bold yellow]⚠[/bold yellow]  {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [bold red]✗[/bold red] {msg}")


def _info(msg: str) -> None:
    console.print(f"  [dim]{msg}[/dim]")


def _progress(event: ProgressEvent) -> None:
    if progress_file is not None:
        with progress_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    if event.event_type is EventType.STARTED:
        _step(event.step.value.replace("_", " ").title())
    elif event.event_type is EventType.RETRYING:
        _warn(f"{event.step.value} retry {event.attempt}: {event.message}")
    elif event.event_type is EventType.COMPLETED:
        _ok(event.message)
    elif event.event_type is EventType.FAILED:
        _fail(f"{event.step.value}: {event.message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a professional business plan from a structured intake JSON."
    )
    parser.add_argument(
        "--run-id",
        help="Explicit run identifier used in progress and audit artifacts.",
    )
    parser.add_argument(
        "--progress-file",
        metavar="PATH",
        help="Optional JSON Lines destination for machine-readable progress events.",
    )
    parser.add_argument(
        "--intake",
        required=True,
        metavar="PATH",
        help="Path to the intake JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/documents",
        metavar="PATH",
        help="Directory for generated output files (default: output/documents).",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF export (produce .docx only).",
    )
    parser.add_argument(
        "--allow-unready",
        action="store_true",
        help=(
            "Allow pipeline to continue when Agent 1 marks intake as not ready. "
            "Default behavior is to stop early."
        ),
    )
    parser.add_argument(
        "--revise",
        action="store_true",
        help="Run an optional Agent 4 revision pass when Agent 5 does not return GO.",
    )
    args = parser.parse_args()

    global progress_file
    progress_file = Path(args.progress_file) if args.progress_file else None
    if progress_file is not None:
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        progress_file.write_text("", encoding="utf-8")
    run_id = args.run_id or str(uuid4())

    intake_path = Path(args.intake)
    output_dir = Path(args.output_dir)

    # ── Header ──────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold white]Business Plan Writer[/bold white]  [dim]Phase 1 Pipeline[/dim]",
            border_style="blue",
        )
    )
    console.print()

    # ── Preflight checks ────────────────────────────────────────────────────
    _step("Preflight")

    # Verify prompt library
    from prompts.loader import validate_library

    if not validate_library():
        _fail("Prompt library incomplete. Run: python scripts/sync_prompts.py")
        return 1
    _ok("Prompt library validated")

    # Load intake
    if not intake_path.exists():
        _fail(f"Intake file not found: {intake_path}")
        return 1

    try:
        with open(intake_path, encoding="utf-8") as f:
            intake = json.load(f)
    except json.JSONDecodeError as e:
        _fail(f"Invalid JSON in intake file: {e}")
        return 1

    business_name = (
        intake.get("business_information", {}).get("business_name", "Unknown Business")
    )
    artifact_dir = output_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    business_info = intake.get("business_information", {})
    intake_date = intake.get("_meta", {}).get("intake_date")
    if not intake_date:
        intake_date = business_info.get("year_founded") or business_info.get("founding_date")

    _ok(f"Intake loaded: {business_name}")
    console.print()

    raw_intake = RawIntake(intake)
    result = OrchestrationService(event_sink=_progress).execute(
        PipelineRequest(
            raw_intake=raw_intake,
            allow_unready=args.allow_unready,
            revise_on_critic=args.revise,
            run_id=run_id,
        )
    )
    ArtifactService().write_run(artifact_dir, raw_intake, result)

    if result.status is PipelineStatus.INCOMPLETE_INTAKE:
        _fail("Intake is not ready. Re-run with --allow-unready to continue anyway.")
        return 1
    if result.status is PipelineStatus.FAILED:
        reason = result.failures[-1].reason if result.failures else "unknown pipeline failure"
        _fail(f"Pipeline failed: {reason}")
        return 1

    assert result.validation and result.financial and result.draft and result.critique
    score = result.validation.completeness_score
    credibility = result.financial.overall_credibility
    recommendation = result.critique.recommendation
    approved = result.critique.approval_status == "GO"
    overall = result.critique.scores.get("overall", "?")
    _info(f"Financial credibility: {credibility}")
    _info(f"Final critic recommendation: {recommendation.upper()}")
    if result.revisions:
        _ok("Critic-triggered revision and second review completed")
    console.print()

    # ── Output: .docx ───────────────────────────────────────────────────────
    _step("Output — .docx")
    from output.docx_builder import build_docx

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = business_name.lower().replace(" ", "_").replace("/", "-")[:50]
    today = date.today().strftime("%Y%m%d")
    docx_filename = f"{safe_name}_{today}_business_plan.docx"
    docx_path = output_dir / docx_filename

    build_docx(
        business_plan_markdown=result.draft.markdown,
        business_name=business_name,
        output_path=docx_path,
        intake_date=intake_date,
    )
    _ok(f"Word document saved: {docx_path}")
    console.print()

    # ── Output: PDF ─────────────────────────────────────────────────────────
    pdf_path = None
    if not args.no_pdf:
        _step("Output — PDF")
        from output.pdf_exporter import export_pdf

        pdf_path = docx_path.with_suffix(".pdf")
        try:
            export_pdf(docx_path, pdf_path)
            _ok(f"PDF saved: {pdf_path}")
        except Exception as e:
            _warn(f"PDF export failed: {e}")
            _info("The .docx file is still available.")
        console.print()

    # ── Summary ─────────────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            _build_summary(
                business_name=business_name,
                score=score,
                overall=overall,
                recommendation=recommendation,
                docx_path=docx_path,
                pdf_path=pdf_path,
                approved=approved,
            ),
            title="[bold green]Pipeline Complete[/bold green]",
            border_style="green",
        )
    )
    console.print()

    return 0


def _build_summary(
    *,
    business_name: str,
    score,
    overall,
    recommendation: str,
    docx_path: Path,
    pdf_path: Path | None,
    approved: bool,
) -> str:
    lines = [
        f"[bold]{business_name}[/bold]",
        "",
        f"Intake completeness:  {score}/100",
        f"Plan quality score:   {overall}/10",
        f"Critic recommendation: [{'green' if approved else 'yellow'}]{recommendation.upper()}[/{'green' if approved else 'yellow'}]",
        "",
        f"[dim]Word doc:  {docx_path}[/dim]",
    ]
    if pdf_path and pdf_path.exists():
        lines.append(f"[dim]PDF:       {pdf_path}[/dim]")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
