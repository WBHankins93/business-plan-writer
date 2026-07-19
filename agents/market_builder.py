"""
agents/market_builder.py
Agent 2 — Market Builder

Synthesizes market analysis context from intake data.
Produces structured market intelligence for Agent 4 (Plan Writer).

Personas: GTM Strategist + VC Partner — go-to-market precision + investor-grade market logic.
Model:   llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.json_response import call_json_agent_strict, validate_agent_contract
from agents.prompt_utils import compact_json
from llm_client import RetryObserver, call_llm_detailed
from pipeline.contracts import MarketInput, MarketOutput, ServiceResult
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are building the market intelligence foundation for a professional business plan.
You have received a validated business plan intake. Your job is to synthesize a
compelling, credible, and specific market analysis section that Agent 4 (Plan Writer)
will use directly when writing the business plan.

Write the market analysis as if you were a senior consultant who has done the research.
Do not add information you don't have. Do not invent statistics. Use only what is
in the intake data — but present it with clarity, structure, and professional framing.

Persona lenses to apply:
- GTM Strategist: sharpen ICP, positioning, differentiation, and channel strategy.
- VC Partner: test market size logic, early traction realism, and assumption quality.

If the two lenses disagree, explicitly surface the disagreement and default to the more
conservative interpretation.

Your output should cover:

1. **Industry Overview** — State of the industry, growth trajectory, key forces shaping demand. Ground in specifics from the intake.

2. **Target Market** — Detailed profile of the primary and secondary customer segments. Who they are, what they need, why they buy, what frustrates them about current alternatives.

3. **Geographic Market** — Specific market size, regional dynamics, and local context relevant to where this business operates.

4. **Market Opportunity** — The specific gap this business fills. What is unmet, underserved, or underpriced in this market?

5. **Market Timing** — Why now is the right time for this business. Tailwinds, trends, or shifts that make this the moment.
6. **GTM & Traction Realism** — Specific distribution channels, channel risk, and what near-term traction is actually plausible.
7. **Assumptions & Risks** — Critical assumptions that still need validation before scaling.

Return valid JSON with exactly these keys:
{
  "narrative": "<700-1000 word markdown market analysis with ## headings>",
  "industry_overview": "<evidence-grounded summary>",
  "target_segments": ["<segment>"],
  "geographic_market": "<specific geographic assessment>",
  "market_opportunity": "<specific opportunity>",
  "market_timing": "<why now, or state that evidence is insufficient>",
  "gtm_and_traction": "<channels, risks, and plausible early traction>",
  "assumptions_and_risks": ["<unvalidated assumption or risk>"],
  "unsupported_claims": ["<claim in the intake that lacks support>"]
}
Do not omit uncertainty to make the analysis sound more confident.
"""


_REQUIRED_KEYS = (
    "narrative",
    "industry_overview",
    "target_segments",
    "geographic_market",
    "market_opportunity",
    "market_timing",
    "gtm_and_traction",
    "assumptions_and_risks",
    "unsupported_claims",
)


class MarketService:
    """Build structured market evidence from a validated intake."""

    def __init__(self, llm_call=call_llm_detailed) -> None:
        self._llm_call = llm_call

    def execute(
        self,
        request: MarketInput,
        *,
        on_retry: RetryObserver | None = None,
    ) -> ServiceResult[MarketOutput]:
        validation = request.validation
        intake = validation.normalized_intake.data
        market_data = {
            "business_information": intake.get("business_information", {}),
            "product_service_summary": intake.get("product_service_summary", {}),
            "market_analysis": intake.get("market_analysis", {}),
            "advertising_strategy": intake.get("advertising_strategy", {}),
            "competition": intake.get("competition", {}),
        }
        user_prompt = f"""
BUSINESS INTAKE (market-relevant sections):
{compact_json(market_data, max_chars=9000)}

---

AGENT 1 NOTES (quality issues to be aware of):
Quality assessment: {validation.quality_assessment}
Thin fields: {json.dumps(validation.thin_fields, indent=2)}
Missing fields: {json.dumps(validation.missing_required, indent=2)}

---

Build the structured market analysis. Use only supplied evidence and preserve uncertainty.
""".strip()
        system_prompt = build_agent_identity_for("agent_2") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
        result = call_json_agent_strict(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            required_keys=_REQUIRED_KEYS,
            required_types={
                "narrative": str,
                "industry_overview": str,
                "target_segments": list,
                "geographic_market": str,
                "market_opportunity": str,
                "market_timing": str,
                "gtm_and_traction": str,
                "assumptions_and_risks": list,
                "unsupported_claims": list,
            },
            temperature=0.6,
            llm_call=self._llm_call,
            on_retry=on_retry,
        )
        data = result.data
        with validate_agent_contract(result.telemetry):
            output = MarketOutput(
                narrative=str(data["narrative"]).strip(),
                industry_overview=str(data["industry_overview"]),
                target_segments=tuple(str(item) for item in data["target_segments"]),
                geographic_market=str(data["geographic_market"]),
                market_opportunity=str(data["market_opportunity"]),
                market_timing=str(data["market_timing"]),
                gtm_and_traction=str(data["gtm_and_traction"]),
                assumptions_and_risks=tuple(str(item) for item in data["assumptions_and_risks"]),
                unsupported_claims=tuple(str(item) for item in data["unsupported_claims"]),
                raw_agent_output=data,
            )
        return ServiceResult(output, result.telemetry)


def run(agent_1_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 2 market analysis on the validated intake.

    Args:
        agent_1_output: Full output dict from agents/validator.py

    Returns:
        dict with keys:
          - market_analysis: Markdown-formatted market analysis text
    """
    from pipeline.legacy import validator_output_from_legacy

    result = MarketService().execute(
        MarketInput(validator_output_from_legacy(agent_1_output))
    ).value
    return {"market_analysis": result.narrative, "market_intelligence": dict(result.raw_agent_output)}
