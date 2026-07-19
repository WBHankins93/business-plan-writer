import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import llm_client
from agents.json_response import AgentJSONError
from agents.validator import ValidatorService
from llm_client import LLMConfigurationError, LLMRequestError, LLMResponse, LLMTimeoutError
from pipeline.contracts import (
    CriticOutput,
    EventType,
    FinancialOutput,
    MarketOutput,
    ModelCallTelemetry,
    ModelUsage,
    NormalizedIntake,
    PipelineRequest,
    PipelineStatus,
    RawIntake,
    ServiceResult,
    ValidationReport,
    ValidatorInput,
    ValidatorOutput,
    WriterOutput,
)
from pipeline.artifacts import ArtifactService
from pipeline.orchestration import OrchestrationService


def _telemetry(failure_reason=None) -> ModelCallTelemetry:
    return ModelCallTelemetry(
        provider="test-provider",
        model="test-model",
        duration_ms=12,
        attempts=1,
        usage=ModelUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost_usd=0.0001,
        failure_reason=failure_reason,
    )


def _validation(*, ready=True) -> ValidatorOutput:
    intake = {
        "business_information": {"business_name": "Acme", "industry": "Services"}
    }
    return ValidatorOutput(
        normalized_intake=NormalizedIntake(intake),
        validation_report=ValidationReport(90, "ready"),
        completeness_score=90,
        ready_for_pipeline=ready,
        quality_assessment="Evidence is usable but incomplete.",
        actionability_assessment="Proceed with caveats." if ready else "Needs follow-up.",
        raw_agent_output={"ready_for_pipeline": ready},
    )


def _market() -> MarketOutput:
    return MarketOutput(
        narrative="## Market\nEvidence-based narrative.",
        industry_overview="Growing, based only on intake evidence.",
        target_segments=("Primary buyer",),
        geographic_market="Local",
        market_opportunity="Documented gap",
        market_timing="Timing is not yet validated.",
        gtm_and_traction="Referral channel; conversion unvalidated.",
        assumptions_and_risks=("Conversion rate is unvalidated.",),
        unsupported_claims=("Market growth claim lacks a source.",),
        raw_agent_output={"narrative": "structured"},
    )


def _financial() -> FinancialOutput:
    return FinancialOutput(
        overall_credibility="moderate",
        revenue_validation={"issues": ["Volume is unvalidated."]},
        expense_validation={"issues": []},
        break_even_validation={},
        funding_validation={},
        cash_flow_risks=("Month three cash gap",),
        assumption_quality={"directional_only": ["Client ramp"]},
        runway_sensitivity={},
        strengths=(),
        writer_notes=("Keep the client-ramp caveat.",),
        summary_narrative="Directional forecast only.",
        raw_agent_output={"overall_financial_credibility": "moderate"},
    )


def _critique(status="GO") -> CriticOutput:
    return CriticOutput(
        confidence_score=80,
        approval_status=status,
        scores={"overall": 8.0},
        strengths=("Clear",),
        critical_issues=() if status == "GO" else ({"issue": "Revise assumptions"},),
        primary_risks=(),
        fatal_flaws=(),
        assumptions_requiring_validation=("Client ramp",),
        sections_to_revise=() if status == "GO" else ("Financial Plan",),
        overall_assessment="Acceptable" if status == "GO" else "Needs revision",
        recommendation="go" if status == "GO" else "conditional",
        revision_notes="Retain and quantify the client-ramp caveat.",
        requires_revision=status != "GO",
        raw_agent_output={"approval_status": status},
    )


class StaticService:
    def __init__(self, value, barrier=None):
        self.value = value
        self.barrier = barrier
        self.calls = []

    def execute(self, request, *, on_retry=None):
        self.calls.append(request)
        if self.barrier:
            self.barrier.wait(timeout=2)
        return ServiceResult(self.value, (_telemetry(),))


class WriterServiceFake:
    def __init__(self):
        self.calls = []

    def execute(self, request, *, on_retry=None):
        self.calls.append(request)
        return ServiceResult(
            WriterOutput(
                markdown=f"draft-v{request.revision_number}",
                agent_key="agent_4",
                revision_number=request.revision_number,
                uncertainty_notes=("Client ramp",),
            ),
            (_telemetry(),),
        )


class CriticServiceFake:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def execute(self, request, *, on_retry=None):
        self.calls.append(request)
        return ServiceResult(self.outputs.pop(0), (_telemetry(),))


class RaisingService:
    def __init__(self, error):
        self.error = error

    def execute(self, request, *, on_retry=None):
        raise self.error


class RetryingService(StaticService):
    def execute(self, request, *, on_retry=None):
        if on_retry:
            on_retry(2, 3, "transient provider error")
        return super().execute(request, on_retry=on_retry)


class PipelineTests(unittest.TestCase):
    def _orchestrator(self, *, ready=True, critic_outputs=None):
        barrier = threading.Barrier(2)
        market = StaticService(_market(), barrier)
        financial = StaticService(_financial(), barrier)
        writer = WriterServiceFake()
        critic = CriticServiceFake(critic_outputs or [_critique()])
        service = OrchestrationService(
            validator=StaticService(_validation(ready=ready)),
            market=market,
            financial=financial,
            writer=writer,
            critic=critic,
        )
        return service, market, financial, writer, critic

    def test_happy_path_runs_market_and_financial_in_parallel(self):
        service, market, financial, writer, critic = self._orchestrator()

        result = service.execute(PipelineRequest(RawIntake({"raw": True})))

        self.assertEqual(result.status, PipelineStatus.COMPLETED)
        self.assertEqual(len(market.calls), 1)
        self.assertEqual(len(financial.calls), 1)
        self.assertIs(critic.calls[0].market, result.market)
        self.assertIs(critic.calls[0].financial, result.financial)
        self.assertTrue(any(e.event_type is EventType.STARTED for e in result.events))
        self.assertEqual(len(result.telemetry), 5)
        self.assertEqual(writer.calls[0].revision_number, 0)

    def test_incomplete_intake_stops_before_parallel_services(self):
        service, market, financial, writer, critic = self._orchestrator(ready=False)

        result = service.execute(PipelineRequest(RawIntake({"raw": True})))

        self.assertEqual(result.status, PipelineStatus.INCOMPLETE_INTAKE)
        self.assertEqual(market.calls, [])
        self.assertEqual(financial.calls, [])
        self.assertEqual(writer.calls, [])
        self.assertEqual(critic.calls, [])

    def test_provider_failure_is_preserved_with_telemetry(self):
        error = LLMRequestError("provider unavailable", telemetry=_telemetry("503"))
        service = OrchestrationService(validator=RaisingService(error))

        result = service.execute(PipelineRequest(RawIntake({})))

        self.assertEqual(result.status, PipelineStatus.FAILED)
        self.assertEqual(result.failures[0].error_type, "LLMRequestError")
        self.assertEqual(result.telemetry[0].failure_reason, "503")

    def test_provider_retry_is_emitted_as_progress_event(self):
        service, market, financial, writer, critic = self._orchestrator()
        service.validator = RetryingService(_validation())

        result = service.execute(PipelineRequest(RawIntake({})))

        retry = next(event for event in result.events if event.event_type is EventType.RETRYING)
        self.assertEqual(retry.attempt, 2)
        self.assertEqual(retry.details["max_attempts"], 3)

    def test_timeout_is_classified_as_retryable_failure(self):
        error = LLMTimeoutError("timed out", telemetry=_telemetry("timeout"))
        service = OrchestrationService(validator=RaisingService(error))

        result = service.execute(PipelineRequest(RawIntake({})))

        self.assertEqual(result.status, PipelineStatus.FAILED)
        self.assertTrue(result.failures[0].retryable)
        self.assertEqual(result.failures[0].error_type, "LLMTimeoutError")

    def test_critic_can_trigger_one_revision_and_second_review(self):
        service, _, _, writer, critic = self._orchestrator(
            critic_outputs=[_critique("CONDITIONAL"), _critique("GO")]
        )

        result = service.execute(
            PipelineRequest(RawIntake({}), revise_on_critic=True, max_revision_passes=1)
        )

        self.assertEqual(result.status, PipelineStatus.COMPLETED)
        self.assertEqual([call.revision_number for call in writer.calls], [0, 1])
        self.assertEqual(len(critic.calls), 2)
        self.assertEqual(result.draft.markdown, "draft-v1")
        self.assertEqual([item.revision_number for item in result.draft_history], [0, 1])
        self.assertEqual(len(result.revisions), 1)
        self.assertEqual([item.approval_status for item in result.critique_history], ["CONDITIONAL", "GO"])

    def test_artifact_service_separates_inputs_outputs_and_audit_records(self):
        service, _, _, _, _ = self._orchestrator()
        raw = RawIntake({"source": "raw"})
        result = service.execute(PipelineRequest(raw))

        with tempfile.TemporaryDirectory() as directory:
            manifest = ArtifactService().write_run(Path(directory), raw, result)
            names = {path.name for path in manifest.files}

        self.assertIn("intake.raw.json", names)
        self.assertIn("intake.normalized.json", names)
        self.assertIn("agent-2.market.json", names)
        self.assertIn("agent-3.financial.json", names)
        self.assertIn("agent-4.draft.v0.md", names)
        self.assertIn("progress-events.json", names)
        self.assertIn("telemetry.json", names)
        self.assertIn("failures.json", names)
        self.assertIn("run-manifest.json", names)


class JSONAndRetryTests(unittest.TestCase):
    def test_invalid_json_gets_one_non_retrying_repair_then_fails(self):
        calls = []

        def invalid_llm(*args, **kwargs):
            calls.append(kwargs.get("max_attempts"))
            return LLMResponse("not json", _telemetry())

        service = ValidatorService(llm_call=invalid_llm)

        with self.assertRaises(AgentJSONError):
            service.execute(ValidatorInput(RawIntake({})))

        self.assertEqual(calls, [None, 1])

    def test_provider_timeout_retries_are_bounded(self):
        attempts = 0
        retry_events = []

        def timeout_operation():
            nonlocal attempts
            attempts += 1
            raise TimeoutError("slow provider")

        with patch.object(llm_client.time, "sleep", return_value=None), patch.object(
            llm_client.random, "uniform", return_value=0
        ):
            with self.assertRaises(LLMTimeoutError) as caught:
                llm_client._run_with_retries(
                    "provider",
                    "model",
                    timeout_operation,
                    max_attempts=3,
                    on_retry=lambda attempt, maximum, reason: retry_events.append(
                        (attempt, maximum, reason)
                    ),
                    writer=False,
                )

        self.assertEqual(attempts, 3)
        self.assertEqual([event[0] for event in retry_events], [2, 3])
        self.assertEqual(caught.exception.telemetry.attempts, 3)

    def test_configuration_failure_is_not_retried(self):
        attempts = 0

        def misconfigured_operation():
            nonlocal attempts
            attempts += 1
            raise LLMConfigurationError("missing key")

        with self.assertRaises(LLMConfigurationError) as caught:
            llm_client._run_with_retries(
                "provider",
                "model",
                misconfigured_operation,
                max_attempts=3,
                on_retry=None,
                writer=False,
            )

        self.assertEqual(attempts, 1)
        self.assertEqual(caught.exception.telemetry.attempts, 1)


if __name__ == "__main__":
    unittest.main()
