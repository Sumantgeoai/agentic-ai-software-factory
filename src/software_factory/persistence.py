from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Connection, Engine

from .contracts import AuditEvent, FactoryRun, StoredRun

metadata = MetaData()

runs = Table(
    "factory_runs",
    metadata,
    Column("project_id", String(36), primary_key=True),
    Column("status", String(20), nullable=False),
    Column("request", Text, nullable=False),
    Column("result_json", Text),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(36), nullable=False, index=True),
    Column("actor", String(50), nullable=False),
    Column("event_type", String(80), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class DatabaseRunStore:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            db_path = database_url.removeprefix("sqlite:///")
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self.engine: Engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            self.engine = create_engine(database_url, pool_pre_ping=True)

    def initialize(self) -> None:
        metadata.create_all(self.engine)

    def start_run(self, project_id: UUID, request: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                runs.insert().values(
                    project_id=str(project_id),
                    status="running",
                    request=request,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._append_event(
                connection,
                project_id,
                "service",
                "run.started",
                {"request_length": len(request)},
                now=now,
            )

    def complete_run(self, result: FactoryRun) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                runs.update()
                .where(runs.c.project_id == str(result.project_id))
                .values(
                    status="completed",
                    result_json=result.model_dump_json(),
                    error=None,
                    updated_at=now,
                )
            )
            self._append_event(
                connection,
                result.project_id,
                "service",
                "run.completed",
                {
                    "approved": result.review.approved,
                    "release_created": result.release is not None,
                    "repair_attempts": result.repair_attempts,
                },
                now=now,
            )

    def fail_run(self, project_id: UUID, error: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                runs.update()
                .where(runs.c.project_id == str(project_id))
                .values(status="failed", error=error, updated_at=now)
            )
            self._append_event(
                connection,
                project_id,
                "service",
                "run.failed",
                {"error": error[:2_000]},
                now=now,
            )

    def append_event(
        self,
        project_id: UUID | str,
        actor: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        with self.engine.begin() as connection:
            self._append_event(connection, project_id, actor, event_type, payload or {})

    @staticmethod
    def _append_event(
        connection: Connection,
        project_id: UUID | str,
        actor: str,
        event_type: str,
        payload: dict[str, object],
        *,
        now: datetime | None = None,
    ) -> None:
        connection.execute(
            audit_events.insert().values(
                project_id=str(project_id),
                actor=actor,
                event_type=event_type,
                payload_json=json.dumps(payload, separators=(",", ":"), default=str),
                created_at=now or datetime.now(UTC),
            )
        )

    def get_run(self, project_id: UUID) -> StoredRun | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(runs).where(runs.c.project_id == str(project_id))
            ).mappings().first()
        if row is None:
            return None
        result = FactoryRun.model_validate_json(row["result_json"]) if row["result_json"] else None
        return StoredRun(
            project_id=UUID(row["project_id"]),
            status=row["status"],
            request=row["request"],
            result=result,
            error=row["error"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        )

    def list_events(self, project_id: UUID) -> list[AuditEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(audit_events)
                .where(audit_events.c.project_id == str(project_id))
                .order_by(audit_events.c.id)
            ).mappings().all()
        return [
            AuditEvent(
                id=row["id"],
                project_id=UUID(row["project_id"]),
                actor=row["actor"],
                event_type=row["event_type"],
                payload=json.loads(row["payload_json"]),
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        ]
