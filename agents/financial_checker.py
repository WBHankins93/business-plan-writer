"""
agents/financial_checker.py
Agent 3 — Financial Checker

Validates financial projections for internal consistency and credibility.
Flags unrealistic figures, gaps, and contradictions for Agent 4 to address.

Persona: Finance Dragon — skeptical, grounded, calls out weak projections.
Model:   llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.prompt_utils import compact_json
from llm_client import call_llm
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are performing a financial due diligence review of a business plan intake.
Your job is to validate the financial projections for internal consistency,
realism, and credibility — from the perspective of a lender or experienced
financial reviewer.

Review the following:

1. **Revenue projections** — Are they internally consistent? Does the client volume
   math support the revenue figures at the stated pricing? Are growth rates realistic
   for this industry and business stage?

2. **Expense projections** — Do total expenses make sense for the business type and
   revenue scale? Are major cost categories present (payroll, rent, insurance, software)?
   Are any costs obviously missing?

3. **Break-even analysis** — Does the stated break-even make sense given the projected
   expenses and revenue ramp?

4. **Funding use** — If funding is sought, is the stated use plausible and well-allocated?
   Does it match the scale of what is being built?

5. **Cash flow realism** — Will the business have sufficient cash to survive the
   early months? Are there cash flow gaps that need to be addressed?

6. **Assumption strength** — What underlying assumptions are the projections built on?
   Are those assumptions stated, defensible, and consistent?

Return your response as valid JSON with this exact structure:
{
  "overall_financial_credibility": "strong" | "moderate" | "weak",
  "revenue_validation": {
    "assessment": "<1-2 sentences>",
    "math_check": "<does client volume × price ≈ revenue projections?>",
    "issues": ["<issue 1>", "<issue 2>"]
  },
  "expense_validation": {
    "assessment": "<1-2 sentences>",
    "missing_costs": ["<any cost categories not accounted for>"],
    "issues": ["<issue 1>"]
  },
  "break_even_validation": {
    "assessment": "<1-2 sentences>",
    "projected_break_even": "<what the intake says>",
    "credibility": "credible" | "optimistic" | "unrealistic"
  },
  "funding_validation": {
    "assessment": "<1-2 sentences>",
    "amount_sought": "<from intake>",
    "use_credibility": "credible" | "optimistic" | "unclear"
  },
  "cash_flow_risks": ["<risk 1>", "<risk 2>"],
  "strengths": ["<financial strength 1>", "<financial strength 2>"],
  "writer_notes_for_agent_4": [
    "<note on how Agent 4 should address or frame a financial weakness>"
  ],
  "financial_summary_narrative": "<2-3 sentence narrative summary for Agent 4 to use when writing the financial section>"
}

Be specific and direct. If numbers don't add up, say so plainly.
"""


def run(agent_1_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 3 financial validation on the validated intake.

    Args:
        agent_1_output: Full output dict from agents/validator.py

    Returns:
        dict with keys:
          - financial_validation: Structured financial review (dict)
    """
    intake = agent_1_output["validated_intake"]
    agent_1_report = agent_1_output.get("agent_1_report", {})

    # Extract financial sections
    financial_data = {
        "business_information": intake.get("business_information", {}),
        "product_service_summary": {
            "pricing_structure": intake.get("product_service_summary", {}).get("pricing_structure"),
        },
        "financial_information": intake.get("financial_information", {}),
        "income": intake.get("income", {}),
        "expenses": intake.get("expenses", {}),
        "milestones": intake.get("milestones", {}),
    }

    user_prompt = f"""
FINANCIAL INTAKE DATA:
{compact_json(financial_data, max_chars=10000)}

---

AGENT 1 QUALITY NOTES:
{agent_1_report.get("quality_assessment", "No additional notes.")}
Thin fields: {json.dumps(agent_1_report.get("thin_fields", []), indent=2)}

---

Perform your financial due diligence review. Return the JSON report as instructed.
Do not accept vague projections at face value — if the math doesn't work, say so.
""".strip()

    system_prompt = build_agent_identity_for("agent_3") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
    raw_response = call_llm(system_prompt, user_prompt, temperature=0.3)

    financial_validation = _parse_json_response(raw_response)

    return {
        "financial_validation": financial_validation,
    }


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from the LLM response, handling markdown code blocks."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "overall_financial_credibility": "unknown",
            "financial_summary_narrative": "Parse error — raw response below.",
            "raw_response": raw,
        }
