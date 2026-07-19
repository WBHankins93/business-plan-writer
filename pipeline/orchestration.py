"""Observable in-process orchestration for the five agent services."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable

from agents.critic import CriticService
from agents.financial_checker import FinancialService
from agents.market_builder import MarketService
from agents.plan_writer import WriterService
from agents.validator import ValidatorService
from llm_client import LLMRequestError
from pipeline.contracts import (
    CriticInput,
    EventType,
    FailureRecord,
    FinancialInput,
    MarketInput,
    ModelCallTelemetry,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
    ProgressEvent,
    ServiceResult,
    StepName,
    ValidatorInput,
    WriterInput,
    utc_now,
)


EventSink = Callable[[ProgressEvent], None]


class OrchestrationService:
    """Own service ordering, parallel fan-out, failure state, and one revision pass."""

    def __init__(
        self,
        *,
        validator: Any | None = None,
        market: Any | None = None,
        financial: Any | None = None,
        writer: Any | None = None,
        critic: Any | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.validator = validator or ValidatorService()
        self.market = market or MarketService()
        self.financial = financial or FinancialService()
        self.writer = writer or WriterService()
        self.critic = critic or CriticService()
        self.event_sink = event_sink

    def execute(self, request: PipelineRequest) -> PipelineResult:
        events: list[ProgressEvent] = []
        telemetry: list[ModelCallTelemetry] = []
        failures: list[FailureRecord] = []
        state_lock = Lock()

        def emit(
            step: StepName,
            event_type: EventType,
            message: str = "",
            *,
            attempt: int | None = None,
            details: dict[str, Any] | None = None,
        ) -> None:
            event = ProgressEvent(
                run_id=request.run_id,
                step=step,
                event_type=event_type,
                occurred_at=utc_now(),
                attempt=attempt,
                message=message,
                details=details or {},
            )
            with state_lock:
                events.append(event)
            if self.event_sink:
                self.event_sink(event)

        def invoke(
            step: StepName,
            operation: Callable[[Callable[[int, int, str], None]], ServiceResult[Any]],
            *,
            details: dict[str, Any] | None = None,
        ) -> ServiceResult[Any] | None:
            emit(step, EventType.STARTED, f"{step.value} started", details=details)

            def on_retry(attempt: int, max_attempts: int, reason: str) -> None:
                emit(
                    step,
                    EventType.RETRYING,
                    reason,
                    attempt=attempt,
                    details={"max_attempts": max_attempts, **(details or {})},
                )

            try:
                result = operation(on_retry)
            except Exception as exc:  # service boundary converts all failures to records
                call_telemetry = getattr(exc, "telemetry", None)
                with state_lock:
                    if call_telemetry is not None:
                        if isinstance(call_telemetry, tuple):
                            telemetry.extend(call_telemetry)
                        else:
                            telemetry.append(call_telemetry)
                    failures.append(
                        FailureRecord(
                            step=step,
                            reason=str(exc),
                            error_type=type(exc).__name__,
                            retryable=isinstance(exc, (LLMRequestError, TimeoutError)),
                        )
                    )
                emit(step, EventType.FAILED, str(exc), details=details)
                return None
            with state_lock:
                telemetry.extend(result.telemetry)
            emit(step, EventType.COMPLETED, f"{step.value} completed", details=details)
            return result

        validation_result = invoke(
            StepName.VALIDATOR,
            lambda retry: self.validator.execute(
                ValidatorInput(request.raw_intake), on_retry=retry
            ),
        )
        if validation_result is None:
            return self._result(request, PipelineStatus.FAILED, events, telemetry, failures)
        validation = validation_result.value

        if not validation.ready_for_pipeline and not request.allow_unready:
            for step in (StepName.MARKET, StepName.FINANCIAL, StepName.WRITER, StepName.CRITIC):
                emit(step, EventType.SKIPPED, "intake is not ready")
            return self._result(
                request,
                PipelineStatus.INCOMPLETE_INTAKE,
                events,
                telemetry,
                failures,
                validation=validation,
            )

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="business-plan-analysis") as pool:
            market_future = pool.submit(
                invoke,
                StepName.MARKET,
                lambda retry: self.market.execute(MarketInput(validation), on_retry=retry),
            )
            financial_future = pool.submit(
                invoke,
                StepName.FINANCIAL,
                lambda retry: self.financial.execute(FinancialInput(validation), on_retry=retry),
            )
            market_result = market_future.result()
            financial_result = financial_future.result()

        if market_result is None or financial_result is None:
            emit(StepName.WRITER, EventType.SKIPPED, "parallel analysis failed")
            emit(StepName.CRITIC, EventType.SKIPPED, "draft was not produced")
            return self._result(
                request,
                PipelineStatus.FAILED,
                events,
                telemetry,
                failures,
                validation=validation,
                market=market_result.value if market_result else None,
                financial=financial_result.value if financial_result else None,
            )

        market = market_result.value
        financial = financial_result.value
        writer_result = invoke(
            StepName.WRITER,
            lambda retry: self.writer.execute(
                WriterInput(validation=validation, market=market, financial=financial),
                on_retry=retry,
            ),
            details={"revision_number": 0},
        )
        if writer_result is None:
            emit(StepName.CRITIC, EventType.SKIPPED, "draft was not produced")
            return self._result(
                request,
                PipelineStatus.FAILED,
                events,
                telemetry,
                failures,
                validation=validation,
                market=market,
                financial=financial,
            )
        draft = writer_result.value
        initial_draft = draft

        critic_result = invoke(
            StepName.CRITIC,
            lambda retry: self.critic.execute(
                CriticInput(validation=validation, market=market, financial=financial, draft=draft),
                on_retry=retry,
            ),
            details={"revision_number": 0},
        )
        if critic_result is None:
            return self._result(
                request,
                PipelineStatus.FAILED,
                events,
                telemetry,
                failures,
                validation=validation,
                market=market,
                financial=financial,
                draft=draft,
                draft_history=(initial_draft,),
            )
        critique = critic_result.value
        revisions = []
        critique_history = [critique]

        should_revise = (
            request.revise_on_critic
            and request.max_revision_passes == 1
            and critique.requires_revision
        )
        if should_revise:
            revision_result = invoke(
                StepName.REVISION,
                lambda retry: self.writer.execute(
                    WriterInput(
                        validation=validation,
                        market=market,
                        financial=financial,
                        prior_draft=draft.markdown,
                        revision_notes=critique.revision_notes,
                        revision_number=1,
                    ),
                    on_retry=retry,
                ),
                details={"revision_number": 1},
            )
            if revision_result is None:
                return self._result(
                    request,
                    PipelineStatus.FAILED,
                    events,
                    telemetry,
                    failures,
                    validation=validation,
                    market=market,
                    financial=financial,
                    draft=draft,
                    draft_history=(initial_draft,),
                    critique=critique,
                    critique_history=tuple(critique_history),
                )
            draft = revision_result.value
            revisions.append(draft)
            revised_critic_result = invoke(
                StepName.CRITIC,
                lambda retry: self.critic.execute(
                    CriticInput(
                        validation=validation,
                        market=market,
                        financial=financial,
                        draft=draft,
                    ),
                    on_retry=retry,
                ),
                details={"revision_number": 1},
            )
            if revised_critic_result is None:
                return self._result(
                    request,
                    PipelineStatus.FAILED,
                    events,
                    telemetry,
                    failures,
                    validation=validation,
                    market=market,
                    financial=financial,
                    draft=draft,
                    draft_history=(initial_draft, draft),
                    critique=critique,
                    revisions=tuple(revisions),
                    critique_history=tuple(critique_history),
                )
            critique = revised_critic_result.value
            critique_history.append(critique)
        else:
            emit(StepName.REVISION, EventType.SKIPPED, "revision not requested or not required")

        return self._result(
            request,
            PipelineStatus.COMPLETED,
            events,
            telemetry,
            failures,
            validation=validation,
            market=market,
            financial=financial,
            draft=draft,
            draft_history=(initial_draft, draft) if revisions else (initial_draft,),
            critique=critique,
            revisions=tuple(revisions),
            critique_history=tuple(critique_history),
        )

    @staticmethod
    def _result(
        request: PipelineRequest,
        status: PipelineStatus,
        events: list[ProgressEvent],
        telemetry: list[ModelCallTelemetry],
        failures: list[FailureRecord],
        **outputs: Any,
    ) -> PipelineResult:
        return PipelineResult(
            run_id=request.run_id,
            status=status,
            events=tuple(events),
            telemetry=tuple(telemetry),
            failures=tuple(failures),
            **outputs,
        )
