"""
demo.py
Business Plan Writer — Deterministic Demo Run

Replays a previously recorded pipeline run through the EXACT same console
walkthrough that `main.py` produces — agent by agent, score by score — but
from canned artifacts instead of live LLM calls. That makes it:

  • identical every time (great for screen-shares / demos)
  • free — no API keys, no token spend
  • reliable — it cannot fail mid-demo on a flaky network

The recorded run lives in `output/documents/demo-workflow/` and was produced by
a real end-to-end run on the Second Line Psychiatry reference intake (Client #1).

Usage:
    python demo.py              # full walkthrough with realistic pacing
    python demo.py --fast       # no delays (instant)
    python demo.py --rebuild    # also rebuild the .docx from the recorded plan
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Reuse main.py's console helpers so formatting is byte-for-byte identical.
from main import (
    console,
    Panel,
    _step,
    _ok,
    _warn,
    _fail,
    _info,
    _build_summary,
)

ROOT = Path(__file__).resolve().parent
RECORDING_DIR = ROOT / "output" / "documents" / "demo-workflow"
INTAKE_PATH = ROOT / "sample_intake" / "sample_client.json"

# Pacing (seconds). Overridden to 0 with --fast.
_PAUSE_LINE = 0.35   # between individual result lines
_PAUSE_STEP = 0.9    # between agent stages
_PAUSE_THINK = 1.2   # simulated "agent working" beat


def _sleep(seconds: float) -> None:
    if not _FAST:
        time.sleep(seconds)


def _working(label: str) -> None:
    """Mimic an agent doing work before it reports."""
    if _FAST:
        return
    console.print(f"  [dim]… {label}[/dim]")
    _sleep(_PAUSE_THINK)


def _load_json(name: str) -> dict:
    return json.loads((RECORDING_DIR / name).read_text(encoding="utf-8"))


def _load_text(name: str) -> str:
    return (RECORDING_DIR / name).read_text(encoding="utf-8")


def run_demo(rebuild_docx: bool) -> int:
    # ── Preflight ────────────────────────────────────────────────────────────
    if not RECORDING_DIR.exists():
        _fail(f"Recorded run not found: {RECORDING_DIR}")
        _info("The demo replays output/documents/demo-workflow/ — that folder is missing.")
        return 1

    intake = json.loads(INTAKE_PATH.read_text(encoding="utf-8"))
    business_name = intake.get("business_information", {}).get("business_name", "Unknown Business")
    intake_date = intake.get("_meta", {}).get("intake_date")

    # ── Header ───────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold white]Business Plan Writer[/bold white]  [dim]Phase 1 Pipeline · DEMO REPLAY[/dim]",
            border_style="blue",
        )
    )
    console.print()
    _info("Deterministic replay of a recorded run — no live LLM calls.")
    console.print()

    _step("Preflight")
    _working("validating prompt library")
    _ok("Prompt library validated")
    _ok(f"Intake loaded: {business_name}")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Agent 1 — Validator ──────────────────────────────────────────────────
    _step("Agent 1 — Intake Validator")
    _working("scoring completeness, inferring fields, checking contradictions")
    a1 = _load_json("raw_agent_1.json")
    report = a1.get("agent_1_report", {})
    score = report.get("completeness_score", "?")
    ready = report.get("ready_for_pipeline", True)

    _ok(f"Completeness score: {score}/100")
    _sleep(_PAUSE_LINE)
    _info(report.get("quality_assessment", ""))
    _sleep(_PAUSE_LINE)

    if not ready:
        _warn("Intake flagged as not ready.")
        _warn("Proceeding due to --allow-unready override.")

    missing = report.get("missing_required", [])
    if missing:
        _warn(f"{len(missing)} missing required field(s):")
        for item in missing[:5]:
            field = item.get("field", item) if isinstance(item, dict) else item
            _info(f"  · {field}")
        if len(missing) > 5:
            _info(f"  · … and {len(missing) - 5} more")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Agent 2 — Market Builder ─────────────────────────────────────────────
    _step("Agent 2 — Market Builder")
    _working("researching market size, demand drivers, competitive landscape")
    market = _load_text("raw_agent_2.md")
    _ok(f"Market analysis generated ({len(market):,} characters)")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Agent 3 — Financial Checker ──────────────────────────────────────────
    _step("Agent 3 — Financial Checker")
    _working("stress-testing projections, break-even, and cash-flow assumptions")
    a3 = _load_json("raw_agent_3.json")
    fv = a3.get("financial_validation", {})
    credibility = fv.get("overall_financial_credibility", "?")
    _ok(f"Financial credibility rating: {credibility}")
    risks = fv.get("cash_flow_risks", [])
    if risks:
        _sleep(_PAUSE_LINE)
        _info(f"Cash flow risks identified: {len(risks)}")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Agent 4 — Plan Writer ────────────────────────────────────────────────
    _step("Agent 4 — Plan Writer")
    _working("composing the full business plan from upstream agent outputs")
    plan = _load_text("raw_agent_4.md")
    try:
        from prompts.loader import resolve_agent_4_key

        persona = resolve_agent_4_key(intake.get("business_information", {}).get("industry", ""))
    except Exception:
        persona = "agent_4"
    _ok(f"Business plan written ({len(plan):,} characters, persona: {persona})")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Agent 5 — Critic ─────────────────────────────────────────────────────
    _step("Agent 5 — Critic")
    _working("scoring the draft across five dimensions and flagging issues")
    a5 = _load_json("raw_agent_5.json")
    critique = a5.get("critique", {})
    approved = a5.get("approved", False)
    recommendation = critique.get("recommendation", "unknown")
    scores = critique.get("scores", {})
    overall = scores.get("overall", "?")

    _ok(f"Overall score: {overall}/10  |  Recommendation: {recommendation.upper()}")
    for dim in ("clarity", "completeness", "credibility", "professionalism", "persuasiveness"):
        _sleep(_PAUSE_LINE)
        _info(f"  {dim.capitalize()}: {scores.get(dim, '?')}/10")

    issues = critique.get("critical_issues", [])
    if issues:
        _sleep(_PAUSE_LINE)
        _warn(f"{len(issues)} critical issue(s) flagged:")
        for issue in issues[:3]:
            if isinstance(issue, dict):
                sev = str(issue.get("severity", "?")).upper()
                text = issue.get("issue", str(issue))
                _info(f"  [{sev}] {text}")
    if not approved:
        _warn("Plan not approved — review critic output. Continuing to output anyway.")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Output ───────────────────────────────────────────────────────────────
    _step("Output — .docx")
    recorded_docx = next(RECORDING_DIR.glob("*_business_plan.docx"), None)

    if rebuild_docx:
        _working("rendering Markdown → Word document")
        from output.docx_builder import build_docx

        out_path = RECORDING_DIR / "demo_rebuilt_business_plan.docx"
        build_docx(
            business_plan_markdown=plan,
            business_name=business_name,
            output_path=out_path,
            intake_date=intake_date,
        )
        docx_path = out_path
        _ok(f"Word document rebuilt: {docx_path}")
    elif recorded_docx is not None:
        docx_path = recorded_docx
        _ok(f"Word document (recorded): {docx_path}")
    else:
        docx_path = RECORDING_DIR / "second_line_psychiatry_business_plan.docx"
        _warn("No recorded .docx found — run with --rebuild to generate one.")
    console.print()
    _sleep(_PAUSE_STEP)

    # ── Summary ──────────────────────────────────────────────────────────────
    console.print(
        Panel.fit(
            _build_summary(
                business_name=business_name,
                score=score,
                overall=overall,
                recommendation=recommendation,
                docx_path=docx_path,
                pdf_path=None,
                approved=approved,
            ),
            title="[bold green]Demo Replay Complete[/bold green]",
            border_style="green",
        )
    )
    console.print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay a recorded Business Plan Writer pipeline run (no LLM calls)."
    )
    parser.add_argument("--fast", action="store_true", help="Disable pacing delays.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the .docx from the recorded plan instead of pointing at the recorded file.",
    )
    args = parser.parse_args()

    global _FAST
    _FAST = args.fast

    return run_demo(rebuild_docx=args.rebuild)


_FAST = False

if __name__ == "__main__":
    sys.exit(main())
