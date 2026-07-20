from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, Callable

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from web_api.config import PROJECT_ROOT, database_url


LEGACY_PROFILE_ID = "00000000-0000-0000-0000-000000000000"
LEGACY_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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


class ProfileStore:
    """Profile lifecycle operations; authentication credentials live elsewhere."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def create(self, profile_id: str):
        from web_api.models import Profile

        with self.session_factory() as db:
            profile = Profile(id=profile_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
            db.expunge(profile)
            return profile

    def schedule_deletion(
        self,
        profile_id: str,
        *,
        retention_days: int = 30,
        now: datetime | None = None,
    ) -> bool:
        """Soft-delete an account and all projects for later storage-aware purging."""
        from web_api.models import Profile, Project

        deleted_at = now or utc_now_naive()
        purge_after = deleted_at + timedelta(days=retention_days)
        with self.session_factory() as db:
            profile = db.get(Profile, profile_id)
            if profile is None:
                return False
            profile.deletion_requested_at = deleted_at
            profile.purge_after = purge_after
            projects = db.scalars(select(Project).where(Project.owner_id == profile_id)).all()
            for project in projects:
                project.deleted_at = deleted_at
                project.purge_after = purge_after
            db.commit()
            return True


class ProjectStore:
    """Owner-scoped project operations and the soft-delete retention boundary."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def create(self, owner_id: str, *, title: str = "Untitled business"):
        from web_api.models import Profile, Project

        with self.session_factory() as db:
            if db.get(Profile, owner_id) is None:
                raise ValueError("Owner profile does not exist")
            project = Project(owner_id=owner_id, title=title[:160] or "Untitled business")
            db.add(project)
            db.commit()
            db.refresh(project)
            db.expunge(project)
            return project

    def get_owned(self, project_id: str, owner_id: str, *, include_deleted: bool = False):
        from web_api.models import Project

        filters = [Project.id == project_id, Project.owner_id == owner_id]
        if not include_deleted:
            filters.append(Project.deleted_at.is_(None))
        with self.session_factory() as db:
            project = db.scalar(select(Project).where(*filters))
            if project is None:
                return None
            db.expunge(project)
            return project

    def list_owned(self, owner_id: str) -> list:
        from web_api.models import Project

        with self.session_factory() as db:
            projects = db.scalars(
                select(Project)
                .where(Project.owner_id == owner_id, Project.deleted_at.is_(None))
                .order_by(Project.updated_at.desc())
            ).all()
            for project in projects:
                db.expunge(project)
            return list(projects)

    def schedule_deletion(
        self,
        project_id: str,
        owner_id: str,
        *,
        retention_days: int = 30,
        now: datetime | None = None,
    ) -> bool:
        from web_api.models import Project

        deleted_at = now or utc_now_naive()
        with self.session_factory() as db:
            project = db.scalar(
                select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
            )
            if project is None:
                return False
            project.deleted_at = deleted_at
            project.purge_after = deleted_at + timedelta(days=retention_days)
            db.commit()
            return True

    def due_for_purge(self, *, now: datetime | None = None) -> list:
        """List tombstoned projects whose external artifacts should be deleted."""
        from web_api.models import Project

        cutoff = now or utc_now_naive()
        with self.session_factory() as db:
            projects = db.scalars(
                select(Project).where(
                    Project.deleted_at.is_not(None),
                    Project.purge_after <= cutoff,
                )
            ).all()
            for project in projects:
                db.expunge(project)
            return list(projects)

    def purge(self, project_id: str) -> bool:
        """Hard-delete metadata after the caller has removed external artifacts."""
        from web_api.models import Project

        with self.session_factory() as db:
            project = db.get(Project, project_id)
            if project is None or project.deleted_at is None:
                return False
            db.delete(project)
            db.commit()
            return True


class IntakeDraftStore:
    """Owner-scoped persistence for the one mutable intake draft per project."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def save_owned(
        self,
        *,
        project_id: str,
        owner_id: str,
        data: dict,
        current_step: int,
    ):
        from web_api.models import IntakeDraft, Project

        with self.session_factory() as db:
            project = db.scalar(
                select(Project).where(
                    Project.id == project_id,
                    Project.owner_id == owner_id,
                    Project.deleted_at.is_(None),
                )
            )
            if project is None:
                return None
            draft = db.scalar(select(IntakeDraft).where(IntakeDraft.project_id == project_id))
            if draft is None:
                draft = IntakeDraft(project_id=project_id)
                db.add(draft)
            draft.data_json = data
            draft.current_step = max(0, current_step)
            draft.updated_at = utc_now_naive()
            project.updated_at = draft.updated_at
            db.commit()
            db.refresh(draft)
            db.expunge(draft)
            return draft

    def get_owned(self, project_id: str, owner_id: str):
        from web_api.models import IntakeDraft, Project

        with self.session_factory() as db:
            draft = db.scalar(
                select(IntakeDraft)
                .join(Project, Project.id == IntakeDraft.project_id)
                .where(
                    IntakeDraft.project_id == project_id,
                    Project.owner_id == owner_id,
                    Project.deleted_at.is_(None),
                )
            )
            if draft is None:
                return None
            db.expunge(draft)
            return draft


class RunStore:
    """Persistence boundary for execution state, artifacts, and audit events."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def create(
        self,
        *,
        run_id: str,
        client_slug: str,
        intake: dict,
        artifact_path: str | None = None,
        provider: str = "unrecorded",
        model: str = "unrecorded",
        configuration: dict | None = None,
    ) -> None:
        """Compatibility path for the existing single-key API.

        The beta-owned path is ``create_owned``. The obsolete artifact_path argument
        is accepted temporarily but deliberately not persisted.
        """
        del artifact_path
        from web_api.models import IntakeDraft, Profile, Project

        with self.session_factory() as db:
            if db.get(Profile, LEGACY_PROFILE_ID) is None:
                db.add(Profile(id=LEGACY_PROFILE_ID))
                db.flush()
            project = db.get(Project, LEGACY_PROJECT_ID)
            if project is None:
                project = Project(
                    id=LEGACY_PROJECT_ID,
                    owner_id=LEGACY_PROFILE_ID,
                    title="Legacy API project",
                )
                db.add(project)
                db.flush()
            draft = db.scalar(
                select(IntakeDraft).where(IntakeDraft.project_id == LEGACY_PROJECT_ID)
            )
            if draft is None:
                db.add(IntakeDraft(project_id=LEGACY_PROJECT_ID, data_json=intake))
            else:
                draft.data_json = intake
                draft.updated_at = utc_now_naive()
            self._add_run(
                db,
                run_id=run_id,
                project_id=LEGACY_PROJECT_ID,
                client_slug=client_slug,
                intake=intake,
                provider=provider,
                model=model,
                configuration=configuration or {},
            )
            db.commit()

    def create_owned(
        self,
        *,
        run_id: str,
        project_id: str,
        owner_id: str,
        client_slug: str,
        provider: str,
        model: str,
        configuration: dict,
    ) -> bool:
        """Create a run from the owner's saved draft and snapshot it immutably."""
        from web_api.models import IntakeDraft, Project

        with self.session_factory() as db:
            draft = db.scalar(
                select(IntakeDraft)
                .join(Project, Project.id == IntakeDraft.project_id)
                .where(
                    IntakeDraft.project_id == project_id,
                    Project.owner_id == owner_id,
                    Project.deleted_at.is_(None),
                )
            )
            if draft is None:
                return False
            self._add_run(
                db,
                run_id=run_id,
                project_id=project_id,
                client_slug=client_slug,
                intake=dict(draft.data_json),
                provider=provider,
                model=model,
                configuration=dict(configuration),
            )
            db.commit()
            return True

    @staticmethod
    def _add_run(
        db: Session,
        *,
        run_id: str,
        project_id: str,
        client_slug: str,
        intake: dict,
        provider: str,
        model: str,
        configuration: dict,
    ) -> None:
        from web_api.models import Run, RunEvent

        _reject_secret_configuration(configuration)
        db.add(
            Run(
                id=run_id,
                project_id=project_id,
                client_slug=client_slug,
                status="queued",
                input_snapshot_json=intake,
                progress_json=initial_progress(),
                provider=provider,
                model=model,
                configuration_json=configuration,
            )
        )
        db.add(RunEvent(run_id=run_id, kind="status", status="queued", message="Run queued."))

    def get(self, run_id: str):
        from web_api.models import Run

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return None
            db.expunge(run)
            return run

    def get_owned(self, run_id: str, owner_id: str):
        from web_api.models import Project, Run

        with self.session_factory() as db:
            run = db.scalar(
                select(Run)
                .join(Project, Project.id == Run.project_id)
                .where(
                    Run.id == run_id,
                    Project.owner_id == owner_id,
                    Project.deleted_at.is_(None),
                )
            )
            if run is None:
                return None
            db.expunge(run)
            return run

    def transition(self, run_id: str, status: str, message: str) -> None:
        from web_api.models import Run, RunEvent

        now = utc_now_naive()
        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = status
            if status == "running" and run.started_at is None:
                run.started_at = now
            if status in {"succeeded", "failed"}:
                run.started_at = run.started_at or now
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
        from web_api.models import Artifact, Entitlement, Revision, Run, RunEvent

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = "succeeded"
            run.output_summary_json = {
                key: value
                for key, value in result.items()
                if key not in {"artifact_files", "draft_file"}
            }
            run.error_code = None
            run.error_message = None
            run.error_details = None
            run.started_at = run.started_at or utc_now_naive()
            run.finished_at = utc_now_naive()
            if run.entitlement_id:
                entitlement = db.get(Entitlement, run.entitlement_id)
                if (
                    entitlement is not None
                    and entitlement.status == "reserved"
                    and entitlement.reserved_run_id == run_id
                ):
                    entitlement.status = "consumed"
                    entitlement.reserved_run_id = None
                    entitlement.consumed_at = utc_now_naive()

            artifact_specs = []
            draft_file = result.get("draft_file")
            if draft_file:
                artifact_specs.append(("draft", draft_file, "text/markdown"))
            for artifact_type, filename in result.get("artifact_files", {}).items():
                if filename:
                    content_type = {
                        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "pdf": "application/pdf",
                    }.get(artifact_type, "application/octet-stream")
                    artifact_specs.append((artifact_type, filename, content_type))

            original_draft = None
            for artifact_type, filename, content_type in artifact_specs:
                artifact = Artifact(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    artifact_type=artifact_type,
                    storage_provider="filesystem",
                    storage_key=f"{run_id}/{PurePosixPath(filename).name}",
                    content_type=content_type,
                )
                db.add(artifact)
                if artifact_type == "draft":
                    original_draft = artifact
            if original_draft is not None:
                db.add(
                    Revision(
                        run_id=run_id,
                        artifact_id=original_draft.id,
                        revision_number=0,
                    )
                )
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
        from web_api.models import Entitlement, Run, RunEvent

        with self.session_factory() as db:
            run = db.scalar(select(Run).where(Run.id == run_id))
            if run is None:
                return
            run.status = "failed"
            run.error_code = code
            run.error_message = message
            run.error_details = operator_details[-8000:]
            run.started_at = run.started_at or utc_now_naive()
            run.finished_at = utc_now_naive()
            if run.entitlement_id:
                entitlement = db.get(Entitlement, run.entitlement_id)
                if (
                    entitlement is not None
                    and entitlement.status == "reserved"
                    and entitlement.reserved_run_id == run_id
                ):
                    entitlement.status = "available"
                    entitlement.reserved_run_id = None
            db.add(
                RunEvent(run_id=run_id, kind="status", status="failed", message=message)
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

    def artifacts(self, run_id: str) -> list:
        from web_api.models import Artifact

        with self.session_factory() as db:
            artifacts = db.scalars(
                select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
            ).all()
            for artifact in artifacts:
                db.expunge(artifact)
            return list(artifacts)

    def artifact_for_filename(self, run_id: str, filename: str):
        from web_api.models import Artifact

        storage_key = f"{run_id}/{PurePosixPath(filename).name}"
        with self.session_factory() as db:
            artifact = db.scalar(
                select(Artifact).where(
                    Artifact.run_id == run_id,
                    Artifact.storage_provider == "filesystem",
                    Artifact.storage_key == storage_key,
                )
            )
            if artifact is None:
                return None
            db.expunge(artifact)
            return artifact

    def create_revision(
        self,
        *,
        run_id: str,
        owner_id: str,
        storage_provider: str,
        storage_key: str,
        content_type: str = "text/markdown",
    ):
        from web_api.models import Artifact, Entitlement, Project, Revision, Run

        with self.session_factory() as db:
            owned_run = db.scalar(
                select(Run)
                .join(Project, Project.id == Run.project_id)
                .where(
                    Run.id == run_id,
                    Project.owner_id == owner_id,
                    Project.deleted_at.is_(None),
                )
            )
            if owned_run is None:
                return None
            entitlement = (
                db.get(Entitlement, owned_run.entitlement_id)
                if owned_run.entitlement_id
                else None
            )
            if entitlement is not None:
                if entitlement.status != "consumed":
                    raise ValueError("Paid entitlement is not eligible for revision")
                if entitlement.revisions_used >= entitlement.revision_limit:
                    raise ValueError("Paid revision limit reached")
            parent = db.scalar(
                select(Revision)
                .where(Revision.run_id == run_id)
                .order_by(Revision.revision_number.desc())
                .limit(1)
            )
            if parent is None:
                raise ValueError("An original draft must exist before adding a revision")
            artifact = Artifact(
                run_id=run_id,
                artifact_type="draft",
                storage_provider=storage_provider,
                storage_key=storage_key,
                content_type=content_type,
            )
            db.add(artifact)
            db.flush()
            revision = Revision(
                run_id=run_id,
                artifact_id=artifact.id,
                parent_revision_id=parent.id,
                revision_number=parent.revision_number + 1,
            )
            db.add(revision)
            if entitlement is not None:
                entitlement.revisions_used += 1
            db.commit()
            db.refresh(revision)
            db.expunge(revision)
            return revision


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


def _reject_secret_configuration(value: object, path: tuple[str, ...] = ()) -> None:
    """Prevent accidental persistence of credentials in auditable run configuration."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if (
                normalized in {"secret", "password", "credential", "credentials"}
                or normalized.endswith("_secret")
                or normalized.endswith("_password")
                or normalized.endswith("_api_key")
                or normalized.endswith("_access_token")
            ):
                location = ".".join((*path, str(key)))
                raise ValueError(f"Run configuration cannot contain secrets: {location}")
            _reject_secret_configuration(child, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secret_configuration(child, (*path, str(index)))


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
