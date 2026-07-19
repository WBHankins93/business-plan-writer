"""
Five independently testable agent services for the business plan pipeline.

Agent 1 (validator)          — Validates and enriches intake data
Agent 2 (market_builder)     — Builds market analysis context
Agent 3 (financial_checker)  — Validates financial projections
Agent 4 (plan_writer)        — Writes the complete business plan
Agent 5 (critic)             — Quality review and scoring

Agent 2 and Agent 3 run concurrently after Agent 1. Orchestration lives in
``pipeline.orchestration``; this package owns agent-specific prompting and typed
input/output conversion.
"""
