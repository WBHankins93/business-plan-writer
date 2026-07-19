"""
agents/plan_writer.py
Agent 4 — Plan Writer

Writes the complete professional business plan document.
Uses all outputs from Agents 1, 2, and 3 as source material.
SaaS-aware: loads enriched persona if industry matches SaaS keywords.

Persona: Business Plan Architect (+ SaaS Founder for tech/software clients)
Model:   LLM_MODEL_WRITER (highest quality — defaults to llama-3.3-70b-versatile)
"""

from __future__ import annotations

import json
from typing import Any

from agents.prompt_utils import compact_json, truncate_text
from llm_client import RetryObserver, call_llm_detailed
from pipeline.contracts import ServiceResult, WriterInput, WriterOutput
from prompts.loader import build_agent_identity_for, resolve_agent_4_key

_TASK_INSTRUCTIONS = """
You are writing a professional business plan for a real client.

This plan will be submitted to a lender, grant committee, or investor.
It must read as if a senior business consultant wrote it — not as if an AI generated it.

You are the synthesis layer across Agent 1 (validation), Agent 2 (market), and Agent 3 (financial).
Do not override their analytical conclusions. Preserve key caveats, disagreements, and risk language.
If evidence is thin, mark it explicitly instead of inventing certainty.

Generic output is a failure condition.
Vague statements are a failure condition.
Padding with filler is a failure condition.

The plan must be:
- Specific to this business, this owner, this market
- Credible: claims are supported by data from the intake
- Reader-focused: organized around what the reader (lender/investor/committee) needs to know
- Professional in tone: confident, grounded, clear
- Appropriately honest: acknowledge real risks; address them directly rather than hiding them

---

DOCUMENT STRUCTURE:
Write the plan using the following sections in order. Use ## for main sections, ### for subsections.
Each section has a minimum word expectation — do not cut short.

## Executive Summary
3–4 paragraphs: business description, problem being solved, owner qualifications,
market opportunity with supporting data, the specific ask and how it will be used.
This is the most-read section — lead with the strongest information.
Target: 400–500 words.

## Company Overview
Business name, ownership structure, legal entity, location, founding date and stage.
Describe what the business does in concrete, plain terms — no jargon.
Include the mission and what success looks like at 3 years.
Target: 250–350 words.

## Owner & Management Team
Full professional background — credentials, licenses, years of experience, specific past roles.
Explain WHY this owner is uniquely positioned to build this specific business.
Address management depth: current team, advisory relationships, key hires planned.
Target: 350–450 words.

## Products & Services
Describe every service offering in detail: what it is, who it serves, how it is delivered,
how long a typical engagement lasts, and what the client experience looks like.
Pricing structure with specific dollar amounts.
What differentiates this offering from what already exists.
Future service lines planned (with timeline if known).
Target: 400–500 words.

## Market Analysis
[USE THE MARKET ANALYSIS PROVIDED BY AGENT 2 — incorporate it here, refine for flow,
do not paste verbatim. Add narrative context. Cite specific numbers where available.]

Cover: industry size and growth, local/regional demand, target customer profile,
market trends driving demand, and why now is the right time.
Target: 500–700 words.

## Marketing & Sales Strategy
How the business will be discovered, how leads become clients, how clients are retained.
Be specific: which channels, which referral sources, which platforms.
Include the sales process step by step.
Marketing budget in dollar terms. Expected cost per acquisition.
Client retention mechanisms and lifetime value expectations.
Target: 400–500 words.

## Competitive Analysis
Name specific competitors or competitor categories. Be direct.
Analyze their strengths and weaknesses relative to this business.
Articulate specific competitive advantages — not generic claims like "excellent service."
Explain the market positioning and why it is defensible.
Target: 300–400 words.

## Operations Plan
Day-to-day workflow: how clients are scheduled, served, and billed.
Technology stack: EHR, telehealth platform, scheduling, billing, communications.
Staffing model (owner + team structure).
Regulatory and compliance requirements and how they are met.
Facilities: current situation and planned expansion.
Target: 400–500 words.

## Implementation Plan
Phase-by-phase rollout with specific milestone dates.
What must happen in months 1–3 for the business to open.
Key milestones at 6 months, 12 months, and 24 months with measurable targets.
Risks associated with the timeline and how they are mitigated.
Target: 350–450 words.

## Financial Plan
[USE THE FINANCIAL VALIDATION SUMMARY PROVIDED BY AGENT 3 — frame the numbers credibly,
address any concerns raised. Do not hide weaknesses — acknowledge and respond to them.]

### Startup Costs
Table or itemized list of all startup expenses with dollar amounts.

### Revenue Projections
Monthly revenue table for Year 1 (12 rows, showing clients and revenue).
Annual summary for Years 1–3 with growth rationale.

### Operating Expenses
Table showing major expense categories by month or year.

### Break-Even Analysis
When does the business cover its costs? At what client volume?
State clearly and show the math.

### Cash Flow Narrative
Describe the cash position month by month through the first year.
Identify the months of highest risk and how they are managed.

Target: 600–800 words for the entire Financial Plan section.

## Funding Request
The specific dollar amount requested.
Detailed use of funds — line by line, not just categories.
How the funding enables the business to reach the milestones described above.
Repayment plan (if loan) or return expectations (if investor).
What happens if only partial funding is received.
Target: 300–400 words.

---

WRITING GUIDELINES:
- Write in third person for the business, first person for the owner's voice (where natural)
- Lead every section with the strongest, most credible information — not background
- Every claim should be grounded in a specific number, credential, or fact from the intake
- Use ### subsection headers within Financial Plan as shown above
- Use markdown tables for all financial projections (monthly revenue, expense breakdown)
- Do not include a table of contents — this is source material for a document formatter
- Preserve unresolved assumptions and disagreements explicitly in-line (do not smooth them away)
- Use [WRITER_NOTE: ...] to flag any areas where data was thin or missing, so the human can review
- Target total length: 4,000–6,000 words. This is a complete, submission-ready plan draft.
  A plan under 3,500 words is incomplete. Do not summarize — write the full content.
"""


class WriterService:
    """Synthesize validated evidence without erasing its uncertainty markers."""

    def __init__(self, llm_call=call_llm_detailed) -> None:
        self._llm_call = llm_call

    def execute(
        self,
        request: WriterInput,
        *,
        on_retry: RetryObserver | None = None,
    ) -> ServiceResult[WriterOutput]:
        validation = request.validation
        market = request.market
        financial = request.financial
        intake = validation.normalized_intake.data
        market_analysis = market.narrative

        industry = intake.get("business_information", {}).get("industry", "")
        agent_4_key = resolve_agent_4_key(industry)

        fin_issues = (
            list(financial.revenue_validation.get("issues", []))
            + list(financial.expense_validation.get("issues", []))
            + list(financial.cash_flow_risks)
        )
        uncertainty_notes = (
            tuple(market.assumptions_and_risks)
            + tuple(market.unsupported_claims)
            + tuple(financial.assumption_quality.get("directional_only", []))
        )

        user_prompt = f"""
FULL INTAKE DATA:
{compact_json(intake, max_chars=14000)}

---

MARKET ANALYSIS (from Agent 2 — incorporate and refine, do not paste verbatim):
{truncate_text(market_analysis, max_chars=7000)}

---

FINANCIAL VALIDATION SUMMARY (from Agent 3):
Overall credibility: {financial.overall_credibility}
Financial narrative: {financial.summary_narrative}

Financial issues to address in writing:
{json.dumps(fin_issues, indent=2)}

Agent 3 writing notes:
{json.dumps(financial.writer_notes, indent=2)}

UNSUPPORTED OR UNVALIDATED ASSUMPTIONS (must remain explicit):
{json.dumps(uncertainty_notes, indent=2)}

---

AGENT 1 QUALITY NOTES (thin or missing fields):
{json.dumps(validation.thin_fields, indent=2)}
{json.dumps(validation.missing_required, indent=2)}
Inferred fields (use with care, mark as such):
{json.dumps(validation.inferred_fields, indent=2)}

---

Write the complete professional business plan now.
Follow the document structure and writing guidelines exactly.
This is the document the client will present to their reader.
""".strip()
        if request.revision_notes:
            user_prompt += (
                "\n\n---\n\n"
                "REVISION CONTEXT (from Agent 5 Critic):\n"
                f"{request.revision_notes}\n\n"
                "If prior draft content is included below, revise it in-place while preserving strengths.\n"
                "Address critical issues directly and keep the document complete.\n"
            )
        if request.prior_draft:
            user_prompt += (
                "\n\nPRIOR DRAFT TO REVISE:\n"
                f"{truncate_text(request.prior_draft, max_chars=20000)}"
            )

        system_prompt = (
            build_agent_identity_for(agent_4_key) + "\n\n---\n\n" + _TASK_INSTRUCTIONS
        )
        response = self._llm_call(
            system_prompt,
            user_prompt,
            writer=True,
            temperature=0.7,
            on_retry=on_retry,
        )
        output = WriterOutput(
            markdown=response.text.strip(),
            agent_key=agent_4_key,
            revision_number=request.revision_number,
            uncertainty_notes=tuple(str(item) for item in uncertainty_notes),
        )
        return ServiceResult(output, (response.telemetry,))


def run(
    agent_1_output: dict[str, Any],
    agent_2_output: dict[str, Any],
    agent_3_output: dict[str, Any],
    *,
    revision_notes: str = "",
    prior_draft: str = "",
) -> dict[str, Any]:
    """Compatibility wrapper for the original dictionary-based API."""
    from pipeline.legacy import (
        financial_output_from_legacy,
        market_output_from_legacy,
        validator_output_from_legacy,
    )

    validation = validator_output_from_legacy(agent_1_output)
    result = WriterService().execute(
        WriterInput(
            validation=validation,
            market=market_output_from_legacy(agent_2_output),
            financial=financial_output_from_legacy(agent_3_output),
            revision_notes=revision_notes or None,
            prior_draft=prior_draft or None,
            revision_number=1 if revision_notes else 0,
        )
    ).value
    return {
        "business_plan": result.markdown,
        "agent_4_key": result.agent_key,
    }
