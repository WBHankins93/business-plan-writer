"""Compatibility conversions for the pre-contract agent ``run`` functions."""

from __future__ import annotations

from typing import Any

from pipeline.contracts import (
    CriticInput,
    CriticOutput,
    FinancialOutput,
    MarketOutput,
    NormalizedIntake,
    ValidationReport,
    ValidatorOutput,
    WriterOutput,
)


def validator_output_from_legacy(payload: dict[str, Any]) -> ValidatorOutput:
    report = payload.get("validation_report", {})
    agent = payload.get("agent_1_report", {})
    return ValidatorOutput(
        normalized_intake=NormalizedIntake(payload.get("validated_intake", {})),
        validation_report=ValidationReport(
            completeness_score=int(report.get("completeness_score", 0)),
            summary=str(report.get("summary", "")),
            typed_issues=tuple(report.get("typed_issues", [])),
            cross_field_issues=tuple(report.get("cross_field_issues", [])),
        ),
        completeness_score=int(agent.get("completeness_score", 0)),
        ready_for_pipeline=bool(agent.get("ready_for_pipeline", False)),
        quality_assessment=str(agent.get("quality_assessment", "")),
        actionability_assessment=str(agent.get("actionability_assessment", "")),
        missing_required=tuple(agent.get("missing_required", [])),
        thin_fields=tuple(agent.get("thin_fields", [])),
        inferred_fields=tuple(agent.get("inferred_fields", [])),
        writer_notes=tuple(agent.get("writer_notes", [])),
        contradictions=tuple(agent.get("contradictions", [])),
        raw_agent_output=agent,
    )


def market_output_from_legacy(payload: dict[str, Any]) -> MarketOutput:
    data = payload.get("market_intelligence", {})
    return MarketOutput(
        narrative=str(payload.get("market_analysis", data.get("narrative", ""))),
        industry_overview=str(data.get("industry_overview", "Not separately structured.")),
        target_segments=tuple(data.get("target_segments", [])),
        geographic_market=str(data.get("geographic_market", "Not separately structured.")),
        market_opportunity=str(data.get("market_opportunity", "Not separately structured.")),
        market_timing=str(data.get("market_timing", "Not separately structured.")),
        gtm_and_traction=str(data.get("gtm_and_traction", "Not separately structured.")),
        assumptions_and_risks=tuple(data.get("assumptions_and_risks", [])),
        unsupported_claims=tuple(data.get("unsupported_claims", [])),
        raw_agent_output=data,
    )


def financial_output_from_legacy(payload: dict[str, Any]) -> FinancialOutput:
    data = payload.get("financial_validation", {})
    return FinancialOutput(
        overall_credibility=str(data.get("overall_financial_credibility", "unknown")),
        revenue_validation=dict(data.get("revenue_validation", {})),
        expense_validation=dict(data.get("expense_validation", {})),
        break_even_validation=dict(data.get("break_even_validation", {})),
        funding_validation=dict(data.get("funding_validation", {})),
        cash_flow_risks=tuple(data.get("cash_flow_risks", [])),
        assumption_quality=dict(data.get("assumption_quality", {})),
        runway_sensitivity=dict(data.get("runway_sensitivity", {})),
        strengths=tuple(data.get("strengths", [])),
        writer_notes=tuple(data.get("writer_notes_for_agent_4", [])),
        summary_narrative=str(data.get("financial_summary_narrative", "")),
        raw_agent_output=data,
    )


def critic_input_from_legacy(
    validator: dict[str, Any],
    writer: dict[str, Any],
    market: dict[str, Any],
    financial: dict[str, Any],
) -> CriticInput:
    return CriticInput(
        validation=validator_output_from_legacy(validator),
        market=market_output_from_legacy(market),
        financial=financial_output_from_legacy(financial),
        draft=WriterOutput(
            markdown=str(writer.get("business_plan", "")),
            agent_key=str(writer.get("agent_4_key", "agent_4")),
            revision_number=0,
        ),
    )


def critic_output_to_legacy(output: CriticOutput) -> dict[str, Any]:
    return {
        "critique": dict(output.raw_agent_output),
        "approved": output.approval_status == "GO",
    }
