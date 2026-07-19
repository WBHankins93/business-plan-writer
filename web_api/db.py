from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from web_api.config import PROJECT_ROOT, database_url


class Base(DeclarativeBase):
    pass


DATABASE_URL = database_url()

# Neon uses SSL by default; keep pool_pre_ping for stale connections.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def migration_state(db_engine: Engine | None = None) -> tuple[bool, str | None, str]:
    """Return whether the connected database is at the repository migration head."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    assert expected is not None
    selected_engine = db_engine or engine
    try:
        with selected_engine.connect() as connection:
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # no schema or unavailable database both mean not ready
        return False, None, expected
    return current == expected, current, expected


class RunStore:
    """Persistence boundary for run state, progress, and audit events."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def create(self, *, run_id: str, client_slug: str, intake: dict, artifact_path: str) -> None:
        from web_api.models import Run, RunEvent

        progress = initial_progress()
        with self.session_factory() as db:
            run = Run(
                id=run_id,
                client_slug=client_slug,
                status="queued",
                intake_json=intake,
                progress_json=progress,
                artifact_path=artifact_path,
            )
            db.add(run)
            db.add(RunEvent(run_id=run_id, kind="status", status="queued", message="Run queued."))
            db.commit()

    def get(self, run_id: str):
        from web_api.models import Run

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return None
            db.expunge(run)
            return run

    def transition(self, run_id: str, status: str, message: str) -> None:
        from web_api.models import Run, RunEvent

        now = datetime.now(UTC).replace(tzinfo=None)
        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = status
            if status == "running" and run.started_at is None:
                run.started_at = now
            if status in {"succeeded", "failed"}:
                run.finished_at = now
            db.add(RunEvent(run_id=run_id, kind="status", status=status, message=message))
            db.commit()

    def record_progress(self, run_id: str, event: dict[str, Any]) -> None:
        from web_api.models import Run, RunEvent

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            progress = [dict(item) for item in (run.progress_json or initial_progress())]
            step = str(event.get("step", ""))
            event_type = str(event.get("event_type", ""))
            public_message = _public_progress_message(step, event_type)
            for item in progress:
                if item["name"] == step:
                    item.update(
                        status=_progress_status(event_type),
                        message=public_message,
                        occurred_at=event.get("occurred_at"),
                    )
                    if event.get("attempt") is not None:
                        item["attempt"] = event["attempt"]
                    break
            run.progress_json = progress
            db.add(
                RunEvent(
                    run_id=run_id,
                    kind="progress",
                    step=step,
                    event_type=event_type,
                    message=public_message,
                    details_json=event,
                )
            )
            db.commit()

    def succeed(self, run_id: str, result: dict) -> None:
        from web_api.models import Run, RunEvent

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = "succeeded"
            run.result_json = result
            run.error_code = None
            run.error_message = None
            run.error_details = None
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            db.add(
                RunEvent(
                    run_id=run_id,
                    kind="status",
                    status="succeeded",
                    message="Run completed.",
                )
            )
            db.commit()

    def fail(
        self,
        run_id: str,
        *,
        code: str,
        message: str,
        operator_details: str,
    ) -> None:
        from web_api.models import Run, RunEvent

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = "failed"
            run.error_code = code
            run.error_message = message
            run.error_details = operator_details[-8000:]
            run.finished_at = datetime.now(UTC).replace(tzinfo=None)
            db.add(
                RunEvent(
                    run_id=run_id,
                    kind="status",
                    status="failed",
                    message=message,
                )
            )
            db.commit()

    def events(self, run_id: str) -> list[dict[str, Any]]:
        from web_api.models import RunEvent

        with self.session_factory() as db:
            events = db.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.id)
            ).all()
            return [
                {
                    "kind": event.kind,
                    "status": event.status,
                    "step": event.step,
                    "event_type": event.event_type,
                    "message": event.message,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ]


def initial_progress() -> list[dict[str, Any]]:
    return [
        {"step": index, "name": name, "label": label, "status": "pending"}
        for index, (name, label) in enumerate(
            [
                ("validator", "Validation"),
                ("market", "Market"),
                ("financial", "Financials"),
                ("writer", "Draft"),
                ("critic", "Review"),
            ],
            start=1,
        )
    ]


def _progress_status(event_type: str) -> str:
    return {
        "started": "running",
        "retrying": "running",
        "completed": "complete",
        "failed": "failed",
        "skipped": "skipped",
    }.get(event_type, "pending")


def _public_progress_message(step: str, event_type: str) -> str:
    label = step.replace("_", " ").title() or "Pipeline step"
    return {
        "started": f"{label} started.",
        "retrying": f"{label} is retrying.",
        "completed": f"{label} completed.",
        "failed": f"{label} failed.",
        "skipped": f"{label} skipped.",
    }.get(event_type, f"{label} updated.")
