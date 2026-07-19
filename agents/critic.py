"""
agents/critic.py
Agent 5 — Critic

Quality review of the completed business plan.
Scores the plan across multiple dimensions and flags issues for human review.

Personas: Red Team (primary) + VC Partner + GTM Strategist
Model:    llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.json_response import call_json_agent_strict, validate_agent_contract
from agents.prompt_utils import compact_json, truncate_text
from llm_client import RetryObserver, call_llm_detailed
from pipeline.contracts import CriticInput, CriticOutput, ServiceResult
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are performing a final quality review of a completed business plan draft.

Your role is three-part:
1. RED TEAM: Aggressively stress-test the plan. Find problems, gaps, weak reasoning,
   and anything a lender or investor would question. Assume a skeptical reader.
2. VC PARTNER: Evaluate investor-grade quality of market logic, defensibility, and
   assumptions that would fail under diligence.
3. GTM STRATEGIST: Pressure-test distribution realism, ICP clarity, channel strategy,
   and early traction assumptions.

When lenses disagree, surface disagreement explicitly and default to a conservative
evaluation stance.

Score the plan on five dimensions (1–10 each, where 10 = excellent):
- Clarity: Is the plan easy to understand and follow?
- Completeness: Does it cover all the sections a reader would expect?
- Credibility: Are claims supported? Do the numbers add up?
- Professionalism: Does it read like a senior consultant wrote it?
- Persuasiveness: Would this plan build confidence in the reader?

Then identify:
- Top 3 strengths of the plan (specific, not generic)
- Top 3 issues that must be addressed before submission (ranked by severity)
- Any sections that should be revised or expanded
- An overall recommendation and approval status
- Fatal flaws (if any)
- Assumptions requiring validation before execution

Return your response as valid JSON with this exact structure:
{
  "confidence_score": <0-100>,
  "approval_status": "GO" | "CONDITIONAL" | "NO-GO",
  "scores": {
    "clarity": <1-10>,
    "completeness": <1-10>,
    "credibility": <1-10>,
    "professionalism": <1-10>,
    "persuasiveness": <1-10>,
    "overall": <calculated average, 1 decimal>
  },
  "strengths": [
    "<specific strength 1>",
    "<specific strength 2>",
    "<specific strength 3>"
  ],
  "critical_issues": [
    {
      "severity": "high" | "medium" | "low",
      "section": "<which section>",
      "issue": "<what is wrong>",
      "recommendation": "<what to do about it>"
    }
  ],
  "primary_risks": [
    "<most important risk 1>",
    "<most important risk 2>"
  ],
  "fatal_flaws": [
    "<fatal flaw if present>"
  ],
  "assumptions_requiring_validation": [
    "<assumption that must be validated>"
  ],
  "sections_to_revise": ["<section name>"],
  "overall_assessment": "<2-3 sentence honest assessment>",
  "recommendation": "go" | "conditional" | "no-go",
  "revision_notes": "<if revise: specific instructions for Agent 4 revision>"
}

Be a genuine critic. A plan that passes without earning it fails everyone.
"""


_REQUIRED_KEYS = (
    "confidence_score",
    "approval_status",
    "scores",
    "strengths",
    "critical_issues",
    "primary_risks",
    "fatal_flaws",
    "assumptions_requiring_validation",
    "sections_to_revise",
    "overall_assessment",
    "recommendation",
    "revision_notes",
)


class CriticService:
    """Audit a draft against intake, market evidence, and financial evidence."""

    def __init__(self, llm_call=call_llm_detailed) -> None:
        self._llm_call = llm_call

    def execute(
        self,
        request: CriticInput,
        *,
        on_retry: RetryObserver | None = None,
    ) -> ServiceResult[CriticOutput]:
        validation = request.validation
        intake = validation.normalized_intake.data
        business_name = intake.get("business_information", {}).get("business_name", "Unknown Business")
        industry = intake.get("business_information", {}).get("industry", "Unknown Industry")

        market_evidence = {
            "industry_overview": request.market.industry_overview,
            "target_segments": request.market.target_segments,
            "geographic_market": request.market.geographic_market,
            "market_opportunity": request.market.market_opportunity,
            "market_timing": request.market.market_timing,
            "gtm_and_traction": request.market.gtm_and_traction,
            "assumptions_and_risks": request.market.assumptions_and_risks,
            "unsupported_claims": request.market.unsupported_claims,
        }
        financial_evidence = dict(request.financial.raw_agent_output)
        user_prompt = f"""
BUSINESS: {business_name} ({industry})

---

KNOWN INTAKE QUALITY ISSUES (from Agent 1):
Completeness score: {validation.completeness_score}/100
Quality assessment: {validation.quality_assessment}
Missing required fields: {json.dumps(validation.missing_required, indent=2)}
Thin fields: {json.dumps(validation.thin_fields, indent=2)}

---

STRUCTURED MARKET EVIDENCE (from Agent 2):
{compact_json(market_evidence, max_chars=9000)}

---

STRUCTURED FINANCIAL EVIDENCE (from Agent 3):
{compact_json(financial_evidence, max_chars=9000)}

---

BUSINESS PLAN TO REVIEW (revision {request.draft.revision_number}):
{truncate_text(request.draft.markdown, max_chars=20000)}

---

Perform the full quality review. Check the draft against the structured evidence and
explicitly flag any place where uncertainty or an unsupported assumption was smoothed away.
""".strip()
        system_prompt = build_agent_identity_for("agent_5") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
        result = call_json_agent_strict(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            required_keys=_REQUIRED_KEYS,
            required_types={
                "confidence_score": int,
                "approval_status": str,
                "scores": dict,
                "strengths": list,
                "critical_issues": list,
                "primary_risks": list,
                "fatal_flaws": list,
                "assumptions_requiring_validation": list,
                "sections_to_revise": list,
                "overall_assessment": str,
                "recommendation": str,
                "revision_notes": str,
            },
            temperature=0.4,
            llm_call=self._llm_call,
            on_retry=on_retry,
        )
        data = result.data
        approval_status = str(data["approval_status"]).upper()
        with validate_agent_contract(result.telemetry):
            output = CriticOutput(
                confidence_score=int(data["confidence_score"]),
                approval_status=approval_status,
                scores={key: float(value) for key, value in dict(data["scores"]).items()},
                strengths=tuple(str(item) for item in data["strengths"]),
                critical_issues=tuple(dict(item) for item in data["critical_issues"]),
                primary_risks=tuple(str(item) for item in data["primary_risks"]),
                fatal_flaws=tuple(str(item) for item in data["fatal_flaws"]),
                assumptions_requiring_validation=tuple(
                    str(item) for item in data["assumptions_requiring_validation"]
                ),
                sections_to_revise=tuple(str(item) for item in data["sections_to_revise"]),
                overall_assessment=str(data["overall_assessment"]),
                recommendation=str(data["recommendation"]).lower(),
                revision_notes=str(data["revision_notes"]),
                requires_revision=approval_status != "GO",
                raw_agent_output=data,
            )
        return ServiceResult(output, result.telemetry)


def run(
    agent_1_output: dict[str, Any],
    agent_4_output: dict[str, Any],
    agent_2_output: dict[str, Any] | None = None,
    agent_3_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run Agent 5 quality review on the completed business plan.

    Args:
        agent_1_output: From agents/validator.py (for context on known issues)
        agent_4_output: From agents/plan_writer.py (the business plan text)

    Returns:
        dict with keys:
          - critique: Structured critique (dict)
          - approved: Boolean — True if recommendation is "approve"
    """
    from pipeline.legacy import (
        critic_input_from_legacy,
        critic_output_to_legacy,
    )

    result = CriticService().execute(
        critic_input_from_legacy(
            agent_1_output,
            agent_4_output,
            agent_2_output or {},
            agent_3_output or {},
        )
    ).value
    return critic_output_to_legacy(result)
