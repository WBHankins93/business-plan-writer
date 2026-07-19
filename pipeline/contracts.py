"""Typed records passed between business-plan pipeline services."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Mapping, TypeVar
from uuid import uuid4


JsonObject = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StepName(str, Enum):
    VALIDATOR = "validator"
    MARKET = "market"
    FINANCIAL = "financial"
    WRITER = "writer"
    CRITIC = "critic"
    REVISION = "revision"


class EventType(str, Enum):
    STARTED = "started"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE_INTAKE = "incomplete_intake"


@dataclass(frozen=True)
class RawIntake:
    """Caller-provided input, retained separately from normalized data."""

    data: Mapping[str, Any]


@dataclass(frozen=True)
class NormalizedIntake:
    """Validated copy used by downstream services."""

    data: Mapping[str, Any]


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelCallTelemetry:
    provider: str
    model: str
    duration_ms: int
    attempts: int
    usage: ModelUsage = field(default_factory=ModelUsage)
    estimated_cost_usd: float | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    run_id: str
    step: StepName
    event_type: EventType
    occurred_at: datetime
    attempt: int | None = None
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        payload = asdict(self)
        payload["step"] = self.step.value
        payload["event_type"] = self.event_type.value
        payload["occurred_at"] = self.occurred_at.isoformat()
        return payload


@dataclass(frozen=True)
class FailureRecord:
    step: StepName
    reason: str
    error_type: str
    retryable: bool
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ValidationReport:
    completeness_score: int
    summary: str
    typed_issues: tuple[str, ...] = ()
    cross_field_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidatorInput:
    raw_intake: RawIntake


@dataclass(frozen=True)
class ValidatorOutput:
    normalized_intake: NormalizedIntake
    validation_report: ValidationReport
    completeness_score: int
    ready_for_pipeline: bool
    quality_assessment: str
    actionability_assessment: str
    missing_required: tuple[Mapping[str, Any], ...] = ()
    thin_fields: tuple[Mapping[str, Any], ...] = ()
    inferred_fields: tuple[Mapping[str, Any], ...] = ()
    writer_notes: tuple[Mapping[str, Any], ...] = ()
    contradictions: tuple[Mapping[str, Any], ...] = ()
    raw_agent_output: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketInput:
    validation: ValidatorOutput


@dataclass(frozen=True)
class MarketOutput:
    narrative: str
    industry_overview: str
    target_segments: tuple[str, ...]
    geographic_market: str
    market_opportunity: str
    market_timing: str
    gtm_and_traction: str
    assumptions_and_risks: tuple[str, ...]
    unsupported_claims: tuple[str, ...]
    raw_agent_output: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinancialInput:
    validation: ValidatorOutput


@dataclass(frozen=True)
class FinancialOutput:
    overall_credibility: str
    revenue_validation: Mapping[str, Any]
    expense_validation: Mapping[str, Any]
    break_even_validation: Mapping[str, Any]
    funding_validation: Mapping[str, Any]
    cash_flow_risks: tuple[str, ...]
    assumption_quality: Mapping[str, Any]
    runway_sensitivity: Mapping[str, Any]
    strengths: tuple[str, ...]
    writer_notes: tuple[str, ...]
    summary_narrative: str
    raw_agent_output: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WriterInput:
    validation: ValidatorOutput
    market: MarketOutput
    financial: FinancialOutput
    prior_draft: str | None = None
    revision_notes: str | None = None
    revision_number: int = 0


@dataclass(frozen=True)
class WriterOutput:
    markdown: str
    agent_key: str
    revision_number: int
    uncertainty_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CriticInput:
    validation: ValidatorOutput
    market: MarketOutput
    financial: FinancialOutput
    draft: WriterOutput


@dataclass(frozen=True)
class CriticOutput:
    confidence_score: int
    approval_status: str
    scores: Mapping[str, float]
    strengths: tuple[str, ...]
    critical_issues: tuple[Mapping[str, Any], ...]
    primary_risks: tuple[str, ...]
    fatal_flaws: tuple[str, ...]
    assumptions_requiring_validation: tuple[str, ...]
    sections_to_revise: tuple[str, ...]
    overall_assessment: str
    recommendation: str
    revision_notes: str
    requires_revision: bool
    raw_agent_output: Mapping[str, Any] = field(default_factory=dict)


T = TypeVar("T")


@dataclass(frozen=True)
class ServiceResult(Generic[T]):
    value: T
    telemetry: tuple[ModelCallTelemetry, ...] = ()


@dataclass(frozen=True)
class PipelineRequest:
    raw_intake: RawIntake
    allow_unready: bool = False
    revise_on_critic: bool = False
    max_revision_passes: int = 1
    run_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.max_revision_passes < 0 or self.max_revision_passes > 1:
            raise ValueError("max_revision_passes must be 0 or 1")


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    status: PipelineStatus
    validation: ValidatorOutput | None = None
    market: MarketOutput | None = None
    financial: FinancialOutput | None = None
    draft: WriterOutput | None = None
    draft_history: tuple[WriterOutput, ...] = ()
    critique: CriticOutput | None = None
    revisions: tuple[WriterOutput, ...] = ()
    critique_history: tuple[CriticOutput, ...] = ()
    telemetry: tuple[ModelCallTelemetry, ...] = ()
    events: tuple[ProgressEvent, ...] = ()
    failures: tuple[FailureRecord, ...] = ()
