"""
agents/market_builder.py
Agent 2 — Market Builder

Synthesizes market analysis context from intake data.
Produces structured market intelligence for Agent 4 (Plan Writer).

Persona: Pattern Seer — reads signals, connects dots, produces actionable intelligence.
Model:   llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from llm_client import call_llm
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are building the market intelligence foundation for a professional business plan.
You have received a validated business plan intake. Your job is to synthesize a
compelling, credible, and specific market analysis section that Agent 4 (Plan Writer)
will use directly when writing the business plan.

Write the market analysis as if you were a senior consultant who has done the research.
Do not add information you don't have. Do not invent statistics. Use only what is
in the intake data — but present it with clarity, structure, and professional framing.

Your output should cover:

1. **Industry Overview** — State of the industry, growth trajectory, key forces shaping demand. Ground in specifics from the intake.

2. **Target Market** — Detailed profile of the primary and secondary customer segments. Who they are, what they need, why they buy, what frustrates them about current alternatives.

3. **Geographic Market** — Specific market size, regional dynamics, and local context relevant to where this business operates.

4. **Market Opportunity** — The specific gap this business fills. What is unmet, underserved, or underpriced in this market?

5. **Market Timing** — Why now is the right time for this business. Tailwinds, trends, or shifts that make this the moment.

Write in professional prose, not bullet points. Use section headers (## format).
Length: 600–900 words. Be specific. Vague analysis fails. Generic analysis fails.
"""


def run(agent_1_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 2 market analysis on the validated intake.

    Args:
        agent_1_output: Full output dict from agents/validator.py

    Returns:
        dict with keys:
          - market_analysis: Markdown-formatted market analysis text
    """
    intake = agent_1_output["validated_intake"]
    agent_1_report = agent_1_output.get("agent_1_report", {})

    # Extract the most relevant intake sections for market analysis
    market_data = {
        "business_information": intake.get("business_information", {}),
        "product_service_summary": intake.get("product_service_summary", {}),
        "market_analysis": intake.get("market_analysis", {}),
        "advertising_strategy": intake.get("advertising_strategy", {}),
        "competition": intake.get("competition", {}),
    }

    user_prompt = f"""
BUSINESS INTAKE (market-relevant sections):
{json.dumps(market_data, indent=2, default=str)}

---

AGENT 1 NOTES (quality issues to be aware of):
Quality assessment: {agent_1_report.get("quality_assessment", "No issues flagged.")}
Thin fields: {json.dumps(agent_1_report.get("thin_fields", []), indent=2)}

---

Write the Market Analysis section for this business plan.
Focus on what is real, specific, and defensible. Avoid generic filler.
""".strip()

    system_prompt = build_agent_identity_for("agent_2") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
    market_analysis = call_llm(system_prompt, user_prompt, temperature=0.6)

    return {
        "market_analysis": market_analysis.strip(),
    }
