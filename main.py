"""
main.py
Business Plan Writer — Phase 1 Pipeline Entry Point

Usage:
    python main.py --intake path/to/intake.json [--no-pdf] [--output-dir path]

Pipeline:
    Agent 1 (Validator) → Agent 2 (Market Builder) → Agent 3 (Financial Checker)
    → Agent 4 (Plan Writer) → Agent 5 (Critic) → .docx + .pdf output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

console = Console()


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a professional business plan from a structured intake JSON."
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
    args = parser.parse_args()

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
    intake_date = intake.get("business_information", {}).get("founding_date", None)

    _ok(f"Intake loaded: {business_name}")
    console.print()

    # ── Agent 1 — Validator ─────────────────────────────────────────────────
    _step("Agent 1 — Intake Validator")
    import agents.validator as validator

    agent_1_output = validator.run(intake)
    a1_report = agent_1_output.get("agent_1_report", {})
    score = a1_report.get("completeness_score", "?")
    ready = a1_report.get("ready_for_pipeline", True)

    _ok(f"Completeness score: {score}/100")
    _info(a1_report.get("quality_assessment", ""))

    if not ready:
        _warn("Intake flagged as not ready — proceeding anyway (Phase 2 will gate this).")

    missing = a1_report.get("missing_required", [])
    if missing:
        _warn(f"{len(missing)} missing required field(s):")
        for item in missing[:5]:
            field = item.get("field", item) if isinstance(item, dict) else item
            _info(f"  · {field}")
        if len(missing) > 5:
            _info(f"  · … and {len(missing) - 5} more")

    console.print()

    # ── Agent 2 — Market Builder ────────────────────────────────────────────
    _step("Agent 2 — Market Builder")
    import agents.market_builder as market_builder

    agent_2_output = market_builder.run(agent_1_output)
    market_len = len(agent_2_output.get("market_analysis", ""))
    _ok(f"Market analysis generated ({market_len:,} characters)")
    console.print()

    # ── Agent 3 — Financial Checker ─────────────────────────────────────────
    _step("Agent 3 — Financial Checker")
    import agents.financial_checker as financial_checker

    agent_3_output = financial_checker.run(agent_1_output)
    fv = agent_3_output.get("financial_validation", {})
    credibility = fv.get("overall_financial_credibility", "?")
    _ok(f"Financial credibility rating: {credibility}")

    risks = fv.get("cash_flow_risks", [])
    if risks:
        _info(f"Cash flow risks identified: {len(risks)}")

    console.print()

    # ── Agent 4 — Plan Writer ───────────────────────────────────────────────
    _step("Agent 4 — Plan Writer")
    import agents.plan_writer as plan_writer

    agent_4_output = plan_writer.run(agent_1_output, agent_2_output, agent_3_output)
    plan_len = len(agent_4_output.get("business_plan", ""))
    agent_key_used = agent_4_output.get("agent_4_key", "agent_4")
    _ok(f"Business plan written ({plan_len:,} characters, persona: {agent_key_used})")
    console.print()

    # ── Agent 5 — Critic ────────────────────────────────────────────────────
    _step("Agent 5 — Critic")
    import agents.critic as critic

    agent_5_output = critic.run(agent_1_output, agent_4_output)
    critique = agent_5_output.get("critique", {})
    approved = agent_5_output.get("approved", False)
    recommendation = critique.get("recommendation", "unknown")

    scores = critique.get("scores", {})
    overall = scores.get("overall", "?")
    _ok(f"Overall score: {overall}/10  |  Recommendation: {recommendation.upper()}")

    for dim in ("clarity", "completeness", "credibility", "professionalism", "persuasiveness"):
        val = scores.get(dim, "?")
        _info(f"  {dim.capitalize()}: {val}/10")

    issues = critique.get("critical_issues", [])
    if issues:
        _warn(f"{len(issues)} critical issue(s) flagged:")
        for issue in issues[:3]:
            if isinstance(issue, dict):
                sev = issue.get("severity", "?").upper()
                text = issue.get("issue", str(issue))
                _info(f"  [{sev}] {text}")

    if not approved:
        _warn("Plan not approved — review critic output. Continuing to output anyway.")

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
        business_plan_markdown=agent_4_output["business_plan"],
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
