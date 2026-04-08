"""
agents/critic.py
Agent 5 — Critic

Quality review of the completed business plan.
Scores the plan across multiple dimensions and flags issues for human review.

Personas: Red Team (finds problems) + Builder-Refiner (filters to what matters)
Model:    llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.prompt_utils import truncate_text
from llm_client import call_llm
from prompts.loader import build_agent_identity_for

_TASK_INSTRUCTIONS = """
You are performing a final quality review of a completed business plan draft.

Your role is two-part:
1. RED TEAM: Aggressively stress-test the plan. Find problems, gaps, weak reasoning,
   and anything a lender or investor would question. Assume a skeptical reader.
2. BUILDER-REFINER: Filter your critique down to the issues that actually matter.
   Not every imperfection needs to be flagged. Focus on what would cause a reader
   to reject or doubt the plan.

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
- An overall recommendation

Return your response as valid JSON with this exact structure:
{
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
  "sections_to_revise": ["<section name>"],
  "overall_assessment": "<2-3 sentence honest assessment>",
  "recommendation": "approve" | "revise" | "reject",
  "revision_notes": "<if revise: specific instructions for Agent 4 revision>"
}

Be a genuine critic. A plan that passes without earning it fails everyone.
"""


def run(
    agent_1_output: dict[str, Any],
    agent_4_output: dict[str, Any],
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
    intake = agent_1_output["validated_intake"]
    business_plan = agent_4_output.get("business_plan", "")
    agent_1_report = agent_1_output.get("agent_1_report", {})

    # Minimal context from intake for validation
    business_name = intake.get("business_information", {}).get("business_name", "Unknown Business")
    industry = intake.get("business_information", {}).get("industry", "Unknown Industry")

    user_prompt = f"""
BUSINESS: {business_name} ({industry})

---

KNOWN INTAKE QUALITY ISSUES (from Agent 1):
Completeness score: {agent_1_report.get("completeness_score", "unknown")}/100
Quality assessment: {agent_1_report.get("quality_assessment", "not available")}
Missing required fields: {json.dumps(agent_1_report.get("missing_required", []), indent=2)}
Thin fields: {json.dumps(agent_1_report.get("thin_fields", []), indent=2)}

---

BUSINESS PLAN TO REVIEW:
{truncate_text(business_plan, max_chars=20000)}

---

Perform your full quality review. Return the JSON critique as instructed.
Judge this plan as a skeptical lender or grant committee reviewer would.
""".strip()

    system_prompt = build_agent_identity_for("agent_5") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
    raw_response = call_llm(system_prompt, user_prompt, temperature=0.4)

    critique = _parse_json_response(raw_response)
    approved = critique.get("recommendation") == "approve"

    return {
        "critique": critique,
        "approved": approved,
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
            "scores": {},
            "recommendation": "revise",
            "overall_assessment": "Parse error — raw response below.",
            "raw_response": raw,
        }
