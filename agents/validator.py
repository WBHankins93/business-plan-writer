"""
agents/validator.py
Agent 1 — Intake Validator

Validates completeness of the intake JSON, identifies thin/missing fields,
infers context where possible, and produces a quality report for downstream agents.

Persona: Startup Operator — scope realism, actionability, and execution readiness.
Model:   llama-3.3-70b-versatile
"""

from __future__ import annotations

import json
from typing import Any

from agents.json_response import AgentJSONError, parse_strict_json
from agents.prompt_utils import compact_json
from llm_client import LLMClientError, call_llm
from prompts.loader import build_agent_identity_for
from intake.schema import validate_intake

# Model for this agent — llama-3.1-8b-instant has a 6K TPM free-tier limit
# which the full intake prompt exceeds. Using the standard model.
_MODEL = "llama-3.3-70b-versatile"

_TASK_INSTRUCTIONS = """
You are reviewing a business plan intake submission for completeness, clarity, and quality.
You have received:
1. The raw intake JSON (all 12 sections)
2. A schema validation report identifying missing or thin fields

Your job:

Startup Operator lens requirements:
- Evaluate whether the proposed scope is realistically executable for an early-stage business.
- Flag over-scoped or non-actionable requests.
- Separate clear facts from assumptions; do not present assumptions as facts.
- Be conservative when evidence is weak.

1. REVIEW each flagged issue from the validation report.
2. For Tier 1 (critical) missing fields: attempt to INFER the value from other available intake data. If you can reasonably infer it, provide the inferred value and note it as "[INFERRED]". If you cannot infer it, mark it as "[MISSING — REQUIRED]".
3. For Tier 2 (structural) thin fields: flag them as "[THIN — needs follow-up]" and note what specific information would strengthen the section.
4. For Tier 3 (enhancement) missing fields: mark as "[WRITER_NOTE: not provided]".
5. Identify any CONTRADICTIONS in the intake data (e.g., funding amount inconsistency, dates that don't align).
6. Add a concise ACTIONABILITY CHECK explaining whether this intake is actionable now.
7. Produce an overall QUALITY ASSESSMENT.

Return your response as valid JSON with this exact structure:
{
  "completeness_score": <integer 0-100>,
  "inferred_fields": [
    {"field": "<section.field_name>", "inferred_value": "<value>", "basis": "<why you inferred this>"}
  ],
  "thin_fields": [
    {"field": "<section.field_name>", "current_value": "<value>", "missing": "<what's needed>"}
  ],
  "missing_required": [
    {"field": "<section.field_name>", "impact": "<why this matters>"}
  ],
  "writer_notes": [
    {"field": "<section.field_name>", "note": "not provided"}
  ],
  "contradictions": [
    {"description": "<what contradicts what>", "recommendation": "<how to resolve>"}
  ],
  "quality_assessment": "<1-3 sentence overall quality assessment>",
  "actionability_assessment": "<1-2 sentence operator assessment of execution readiness>",
  "ready_for_pipeline": <true or false>
}

Be direct and specific. Do not pad the response with filler.
"""


def run(intake: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 1 validation on the intake data.

    Args:
        intake: Raw intake JSON loaded from file.

    Returns:
        dict with keys:
          - validated_intake: The original intake (Agent 4 will use this directly)
          - validation_report: Schema-level validation report summary
          - agent_1_report: LLM quality analysis (dict)
    """
    # Step 1: Run schema validation
    _, schema_report = validate_intake(intake)

    validation_summary = schema_report.summary()
    missing_t1 = [
        {"section": r.field.section, "field": r.field.name, "label": r.field.label}
        for r in schema_report.missing_tier1
    ]
    thin_t2 = [
        {
            "section": r.field.section,
            "field": r.field.name,
            "label": r.field.label,
            "current_value": str(r.value or "")[:200],
        }
        for r in schema_report.thin_tier2
    ]
    missing_t3 = [
        {"section": r.field.section, "field": r.field.name, "label": r.field.label}
        for r in schema_report.missing_tier3
    ]

    # Step 2: Build user prompt for LLM
    user_prompt = f"""
INTAKE DATA:
{compact_json(intake, max_chars=14000)}

---

SCHEMA VALIDATION REPORT:
Completeness score: {schema_report.completeness_score}/100

Missing Tier 1 (critical):
{json.dumps(missing_t1, indent=2)}

Thin Tier 2 (structural — needs more detail):
{json.dumps(thin_t2, indent=2)}

Missing Tier 3 (enhancement):
{json.dumps(missing_t3, indent=2)}

Typed validation issues:
{json.dumps(schema_report.typed_issues, indent=2)}

Cross-field issues:
{json.dumps(schema_report.cross_field_issues, indent=2)}

---

Please review the intake and return your JSON quality report as instructed.
""".strip()

    # Step 3: Call LLM
    system_prompt = build_agent_identity_for("agent_1") + "\n\n---\n\n" + _TASK_INSTRUCTIONS
    agent_report = _call_with_strict_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    return {
        "validated_intake": intake,
        "validation_report": {
            "completeness_score": schema_report.completeness_score,
            "summary": validation_summary,
            "typed_issues": schema_report.typed_issues,
            "cross_field_issues": schema_report.cross_field_issues,
        },
        "agent_1_report": agent_report,
    }
def _call_with_strict_json(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call LLM and require valid JSON output with one retry."""
    try:
        first = call_llm(system_prompt, user_prompt, model=_MODEL, temperature=0.3)
    except LLMClientError as exc:
        return {
            "completeness_score": 0,
            "quality_assessment": "LLM provider error prevented validator output.",
            "actionability_assessment": "Unable to assess due to provider failure.",
            "ready_for_pipeline": False,
            "error": {"type": "llm_provider_error", "message": str(exc)},
        }

    try:
        return parse_strict_json(first)
    except AgentJSONError:
        retry_prompt = (
            f"{user_prompt}\n\n"
            "IMPORTANT: Your previous reply was not valid JSON. "
            "Return valid JSON only, with no markdown or extra text."
        )
        try:
            second = call_llm(system_prompt, retry_prompt, model=_MODEL, temperature=0.0)
            return parse_strict_json(second)
        except (LLMClientError, AgentJSONError) as exc:
            return {
                "completeness_score": 0,
                "quality_assessment": "Validator returned invalid JSON after one retry.",
                "actionability_assessment": "Unable to assess due to malformed model output.",
                "ready_for_pipeline": False,
                "error": {"type": "invalid_json_response", "message": str(exc)},
                "raw_response": first,
            }
