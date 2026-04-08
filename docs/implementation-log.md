# Implementation Log — Codebase Improvements

This file records each improvement task completed, in commit order, so changes are easy to retrace later.

## 1) LLM Reliability Controls
- Added standardized LLM exception classes in `llm_client.py`.
- Added configurable timeout and retry/backoff controls:
  - `LLM_TIMEOUT_SECONDS`
  - `LLM_MAX_RETRIES`
  - `LLM_RETRY_BACKOFF_SECONDS`
- Wrapped provider calls with retry orchestration and jittered exponential backoff.
- Added timeout forwarding to provider SDK calls where supported.
- Updated README configuration snippet with the new reliability env vars.

## 2) Intake Readiness Gating
- Added `--allow-unready` CLI flag in `main.py`.
- Changed default behavior to stop the pipeline when Agent 1 reports `ready_for_pipeline = false`.
- Added clear console messaging for stop/override behavior.
- Updated README CLI docs for the new flag.

## 3) Founding Date Field Normalization
- Fixed `main.py` to read intake date from canonical `business_information.year_founded`.
- Added backward-compatible fallback to `business_information.founding_date`.
- This resolves schema/runtime mismatch without breaking older intakes.

## 4) Stronger Schema Validation (Typed + Cross-Field)
- Added typed validation issue collection to `ValidationReport`.
- Added parseable-numeric checks for key financial fields (funding, revenue, expenses, marketing budget).
- Added cross-field consistency check between monthly and annual revenue projections (with tolerance).
- Included typed and cross-field validation issues in Agent 1 prompt context and returned report payload.

## 5) Prompt Size Compaction
- Added `agents/prompt_utils.py` with shared helpers:
  - `compact_json(...)`
  - `truncate_text(...)`
- Updated Agents 1–5 prompt assembly to cap oversized JSON/text blocks before model calls.
- Preserved both head and tail context when truncating large payloads.

## 6) Prompt Identity Loader Caching
- Added `functools.lru_cache` to prompt file reads in `prompts/loader.py`.
- This avoids repeated disk reads for the same identity components during a run.

## 7) Automated Tests + Smoke Coverage
- Added `tests/test_schema_validation.py` for typed and cross-field validation behavior.
- Added `tests/test_prompt_utils.py` for prompt compaction helper behavior.
- Added `tests/test_cli.py` to smoke-test CLI help and new readiness override flag visibility.
- Added README test command documentation (`python -m unittest discover ...`).

## 8) Code Quality Cleanup
- Removed unused `Text` import from `main.py`.
- Removed unused `TYPE_CHECKING` block, markdown regex constants, and unused `qn` import from `output/pdf_exporter.py`.
