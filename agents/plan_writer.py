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

from llm_client import call_llm
from prompts.loader import build_agent_identity_for, resolve_agent_4_key

_TASK_INSTRUCTIONS = """
You are writing a professional business plan for a real client.

This plan will be submitted to a lender, grant committee, or investor.
It must read as if a senior business consultant wrote it — not as if an AI generated it.

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
Write the plan using the following sections in order. Use ## headers for each section.

## Executive Summary
A compelling 2–3 paragraph overview of the business, the opportunity, and the ask.
This is read first and often read alone — make it strong.

## Company Overview
Business name, ownership, location, legal structure, founding date, stage.
What the business does in plain terms.

## Owner & Management Team
The owner's background, credentials, and relevant experience.
Why they are uniquely qualified to build this business.
Hiring plans and team growth trajectory.

## Products & Services
What the business offers, how it is delivered, pricing structure.
What sets it apart from what exists today.
Future service line roadmap.

## Market Analysis
[USE THE MARKET ANALYSIS PROVIDED BY AGENT 2 — incorporate it here, refine if needed,
do not simply paste it verbatim. Integrate it as part of the overall document flow.]

## Marketing & Sales Strategy
How the business reaches and converts clients.
Sales process, referral strategy, advertising channels.
Marketing budget and return on investment expectations.

## Competitive Analysis
Who the competitors are and why this business wins.
Specific competitive advantages — not generic claims.

## Operations Plan
How the business runs day to day.
Technology, tools, workflows, service delivery process.
Regulatory compliance, licensing, insurance.

## Implementation Plan
Phased plan: what gets built, in what order, on what timeline.
Key milestones at 6, 12, and 24 months.

## Financial Plan
[USE THE FINANCIAL VALIDATION SUMMARY PROVIDED BY AGENT 3 — frame the financials
credibly, address any concerns the financial checker raised, do not hide weaknesses.]

Startup costs and funding use.
Revenue projections (monthly Year 1, annual Year 2–3).
Expense projections with major categories.
Break-even analysis.
Cash flow narrative.

## Funding Request
If applicable: amount sought, use of funds, repayment plan or return expectations.

---

WRITING GUIDELINES:
- Write in third person for the business, first person for the owner's voice (where natural)
- Each section should earn its place — cut anything that doesn't reduce doubt or add credibility
- Lead sections with the strongest information, not background context
- Use tables for financial projections (monthly revenue, expense breakdown)
- Do not include a table of contents — this is source material for a document formatter
- Use [WRITER_NOTE: ...] to flag any areas where data was thin or missing, so the human can review
- Aim for 2,000–3,000 words total for a strong initial draft
"""


def run(
    agent_1_output: dict[str, Any],
    agent_2_output: dict[str, Any],
    agent_3_output: dict[str, Any],
) -> dict[str, Any]:
    """
    Run Agent 4 to write the complete business plan.

    Args:
        agent_1_output: From agents/validator.py
        agent_2_output: From agents/market_builder.py
        agent_3_output: From agents/financial_checker.py

    Returns:
        dict with keys:
          - business_plan: Full business plan in markdown format
          - agent_4_key: Which agent 4 variant was used
    """
    intake = agent_1_output["validated_intake"]
    agent_1_report = agent_1_output.get("agent_1_report", {})
    market_analysis = agent_2_output.get("market_analysis", "")
    financial_validation = agent_3_output.get("financial_validation", {})

    # Determine persona (SaaS or standard)
    industry = intake.get("business_information", {}).get("industry", "")
    agent_4_key = resolve_agent_4_key(industry)

    # Build financial summary for Agent 4
    fin_summary = financial_validation.get(
        "financial_summary_narrative",
        "Financial projections provided — see intake data."
    )
    fin_credibility = financial_validation.get("overall_financial_credibility", "not assessed")
    writer_notes = financial_validation.get("writer_notes_for_agent_4", [])
    fin_issues = (
        financial_validation.get("revenue_validation", {}).get("issues", [])
        + financial_validation.get("expense_validation", {}).get("issues", [])
        + financial_validation.get("cash_flow_risks", [])
    )

    user_prompt = f"""
FULL INTAKE DATA:
{json.dumps(intake, indent=2, default=str)}

---

MARKET ANALYSIS (from Agent 2 — incorporate and refine, do not paste verbatim):
{market_analysis}

---

FINANCIAL VALIDATION SUMMARY (from Agent 3):
Overall credibility: {fin_credibility}
Financial narrative: {fin_summary}

Financial issues to address in writing:
{json.dumps(fin_issues, indent=2)}

Agent 3 writing notes:
{json.dumps(writer_notes, indent=2)}

---

AGENT 1 QUALITY NOTES (thin or missing fields):
{json.dumps(agent_1_report.get("thin_fields", []), indent=2)}
{json.dumps(agent_1_report.get("missing_required", []), indent=2)}
Inferred fields (use with care, mark as such):
{json.dumps(agent_1_report.get("inferred_fields", []), indent=2)}

---

Write the complete professional business plan now.
Follow the document structure and writing guidelines exactly.
This is the document the client will present to their reader.
""".strip()

    system_prompt = (
        build_agent_identity_for(agent_4_key) + "\n\n---\n\n" + _TASK_INSTRUCTIONS
    )
    business_plan = call_llm(system_prompt, user_prompt, writer=True, temperature=0.7)

    return {
        "business_plan": business_plan.strip(),
        "agent_4_key": agent_4_key,
    }
