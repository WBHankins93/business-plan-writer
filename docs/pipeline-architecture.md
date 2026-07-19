# ADR-001: Typed in-process five-agent pipeline

**Status:** Accepted
**Date:** 2026-07-19

## Context

The original CLI passed untyped dictionaries through five sequential agent functions.
The CLI also owned sequencing, artifact writes, status display, and revision branching.
Provider fallbacks could hide failures, and JSON correction could multiply provider retries.

The pipeline must remain a simple set of modules in one repository. Website, authentication,
database, paywall, and marketing behavior are outside this decision.

## Decision

The five modules in `agents/` are the validator, market, financial, writer, and critic
service boundaries. Each exposes an `execute(typed_input) -> ServiceResult[typed_output]`
method and retains its old `run(...)` dictionary wrapper for compatibility.

`pipeline/orchestration.py` is the sole sequencing boundary:

```text
validator → (market || financial) → writer → critic
                                      ▲         │
                                      └ revision┘  (zero or one pass)
```

`pipeline/artifacts.py` is the sole audit-artifact boundary. It writes raw intake,
normalized intake, agent records, draft versions, critique versions, telemetry, failures,
progress events, and a manifest as distinguishable files.

## Contracts and state

`pipeline/contracts.py` defines immutable records for every input, output, model call,
failure, event, request, and final result. Intake payloads remain mappings because the
questionnaire is intentionally extensible; their lifecycle containers are typed and raw
input is deep-copied before it becomes normalized input.

Progress transitions are `started`, `retrying`, `completed`, `failed`, and `skipped`.
Every event carries a run ID, step, UTC timestamp, attempt when applicable, and details.

## Retry budget

Only `llm_client.call_llm_detailed` retries provider calls. `LLM_MAX_RETRIES` is the total
attempt count, not retries-after-first. A malformed JSON response gets one correction call
with `max_attempts=1`. The orchestrator does not retry a whole agent, so provider attempts
cannot multiply across nested orchestration and parse loops.

## Telemetry

Each model call records provider, model, duration, attempts, token usage when the provider
returns it, and estimated cost when per-million-token environment rates are configured.
Failed provider calls record their failure reason. Pipeline failures are also retained as
typed failure records rather than converted to plausible-looking agent output.

## Behavior changes

- Agent 2 now returns structured market evidence plus its Markdown narrative.
- Agent 2 and Agent 3 start concurrently after a ready Agent 1 result.
- Agent 5 receives the full structured market and financial records directly.
- `--revise` performs at most one revision and then runs Agent 5 again.
- Audit files use descriptive versioned names instead of `raw_agent_N.*` names.
- Provider or invalid-JSON failures stop the pipeline; they are no longer smoothed into
  fallback reports that downstream agents might mistake for real analysis.

## Consequences

The services can be tested with injected model call functions and fake peer services.
Parallel execution reduces analysis latency but may increase provider concurrency. Cost
estimates remain `null` unless token usage and pricing rates are both available, because
hard-coded provider prices would become stale.
