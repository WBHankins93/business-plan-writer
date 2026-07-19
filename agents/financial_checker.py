"""
agents/financial_checker.py
Agent 3 — Financial Checker

Validates financial projections for internal consistency and credibility.
Flags unrealistic figures, gaps, and contradictions for Agent 4 to address.

Personas: Financial Analyst + Startup Operator — assumption rigor + early-stage execution realism.
Model:   llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.json_response import call_json_agent_strict, validate_agent_contract
from agents.prompt_utils import compact_json
from llm_client import RetryObserver, call_llm_detailed
from pipeline.contracts import FinancialInput, FinancialOutput, ServiceResult
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are performing a financial due diligence review of a business plan intake.
Your job is to validate the financial projections for internal consistency,
realism, and credibility — from the perspective of a lender or experienced
financial reviewer.

Persona lenses to apply:
- Financial Analyst: test math, assumptions, margins, and runway sensitivity.
- Startup Operator: judge feasibility of the financial plan given stage and operating constraints.

When these lenses disagree, do not average into weak conclusions. Surface the disagreement
and default to the more conservative interpretation.

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
  "assumption_quality": {
    "directional_only": ["<assumption that is directional but weakly supported>"],
    "credible_estimates": ["<assumption with credible support>"]
  },
  "runway_sensitivity": {
    "base_case": "<brief base-case runway view>",
    "downside_case": "<brief downside runway view>",
    "commentary": "<what changes management should make if downside occurs>"
  },
  "strengths": ["<financial strength 1>", "<financial strength 2>"],
  "writer_notes_for_agent_4": [
    "<note on how Agent 4 should address or frame a financial weakness>"
  ],
  "financial_summary_narrative": "<2-3 sentence narrative summary for Agent 4 to use when writing the financial section>"
}

Be specific and direct. If numbers don't add up, say so plainly.
"""


_REQUIRED_KEYS = (
    "overall_financial_credibility",
    "revenue_validation",
    "expense_validation",
    "break_even_validation",
    "funding_validation",
    "cash_flow_risks",
    "assumption_quality",
    "runway_sensitivity",
    "strengths",
    "writer_notes_for_agent_4",
    "financial_summary_narrative",
)


class FinancialService:
    """Test financial inputs and retain unsupported assumptions as structured data."""

    def __init__(self, llm_call=call_llm_detailed) -> None:
        self._llm_call = llm_call

    def execute(
        self,
        request: FinancialInput,
        *,
        on_retry: RetryObserver | None = None,
    ) -> ServiceResult[FinancialOutput]:
        validation = request.validation
        intake = validation.normalized_intake.data
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
{validation.quality_assessment}
Thin fields: {json.dumps(validation.thin_fields, indent=2)}
Missing fields: {json.dumps(validation.missing_required, indent=2)}

---

Perform the financial due diligence review. Do not accept vague projections at face value.
""".strip()
        system_prompt = build_agent_identity_for("agent_3") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
        result = call_json_agent_strict(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            required_keys=_REQUIRED_KEYS,
            required_types={
                "overall_financial_credibility": str,
                "revenue_validation": dict,
                "expense_validation": dict,
                "break_even_validation": dict,
                "funding_validation": dict,
                "cash_flow_risks": list,
                "assumption_quality": dict,
                "runway_sensitivity": dict,
                "strengths": list,
                "writer_notes_for_agent_4": list,
                "financial_summary_narrative": str,
            },
            temperature=0.3,
            llm_call=self._llm_call,
            on_retry=on_retry,
        )
        data = result.data
        with validate_agent_contract(result.telemetry):
            output = FinancialOutput(
                overall_credibility=str(data["overall_financial_credibility"]),
                revenue_validation=dict(data["revenue_validation"]),
                expense_validation=dict(data["expense_validation"]),
                break_even_validation=dict(data["break_even_validation"]),
                funding_validation=dict(data["funding_validation"]),
                cash_flow_risks=tuple(str(item) for item in data["cash_flow_risks"]),
                assumption_quality=dict(data["assumption_quality"]),
                runway_sensitivity=dict(data["runway_sensitivity"]),
                strengths=tuple(str(item) for item in data["strengths"]),
                writer_notes=tuple(str(item) for item in data["writer_notes_for_agent_4"]),
                summary_narrative=str(data["financial_summary_narrative"]),
                raw_agent_output=data,
            )
        return ServiceResult(output, result.telemetry)


def run(agent_1_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 3 financial validation on the validated intake.

    Args:
        agent_1_output: Full output dict from agents/validator.py

    Returns:
        dict with keys:
          - financial_validation: Structured financial review (dict)
    """
    from pipeline.legacy import validator_output_from_legacy

    result = FinancialService().execute(
        FinancialInput(validator_output_from_legacy(agent_1_output))
    ).value
    return {"financial_validation": dict(result.raw_agent_output)}
