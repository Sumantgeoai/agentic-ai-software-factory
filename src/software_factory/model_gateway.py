from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel

from .config import Settings
from .contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    GeneratedFile,
    RequirementSpec,
    TargetProfile,
    TaskPlan,
    WorkItem,
)
from .enterprise_fixture import (
    enterprise_application_spec,
    enterprise_architecture,
    enterprise_artifacts,
    enterprise_bundle,
    enterprise_requirements,
    enterprise_task_plan,
)
from .specification import (
    ApplicationSpec,
    BusinessRuleSpec,
    EntityFieldSpec,
    EntitySpec,
    PageSpec,
    PermissionSpec,
    RoleSpec,
    WorkflowSpec,
    WorkflowStepSpec,
)

T = TypeVar("T", bound=BaseModel)


class StructuredModel(Protocol):
    async def complete(self, schema: type[T], *, system: str, user: str) -> T: ...


class NvidiaNimGateway:
    def __init__(self, settings: Settings) -> None:
        if not settings.nvidia_api_key:
            raise ValueError("SOFTWARE_FACTORY_NVIDIA_API_KEY is required for NVIDIA provider")
        self._settings = settings

    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        payload = {
            "model": self._settings.nvidia_model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"{user}\n\nReturn only JSON matching this schema:\n"
                        f"{json.dumps(schema.model_json_schema(), separators=(',', ':'))}"
                    ),
                },
            ],
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 16_384,
        }
        headers = {"Authorization": f"Bearer {self._settings.nvidia_api_key}"}
        async with httpx.AsyncClient(timeout=self._settings.model_timeout_seconds) as client:
            response = await client.post(
                f"{self._settings.nvidia_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate(json.loads(_extract_json(content)))


def _extract_json(content: str) -> str:
    value = content.strip()
    if value.startswith("{") or value.startswith("["):
        return value
    match = re.search(r"```(?:json)?\s*(.*?)```", value, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    raise ValueError("Model response did not contain a JSON payload")


class FixtureModelGateway:
    """Deterministic gateway used by tests and zero-credential local demos."""

    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        enterprise = TargetProfile.ENTERPRISE_DOTNET_REACT.value in user
        if schema is RequirementSpec:
            value: BaseModel = enterprise_requirements() if enterprise else _lightweight_requirements()
        elif schema is ArchitectureSpec:
            value = enterprise_architecture() if enterprise else _lightweight_architecture()
        elif schema is ApplicationSpec:
            value = enterprise_application_spec() if enterprise else _lightweight_application_spec()
        elif schema is TaskPlan:
            value = enterprise_task_plan() if enterprise else _lightweight_task_plan()
        elif schema is ArtifactSet:
            value = enterprise_artifacts(system) if enterprise else _fixture_artifacts(system)
        elif schema is CodeBundle:
            value = enterprise_bundle() if enterprise else _leave_management_bundle()
        else:
            raise TypeError(f"Fixture gateway does not support {schema.__name__}")
        return schema.model_validate(value.model_dump())


def _lightweight_requirements() -> RequirementSpec:
    return RequirementSpec(
        product_name="Leave Management",
        actors=["employee", "manager", "hr"],
        functional_requirements=[
            "Employees can submit leave requests",
            "Managers can approve or reject pending requests",
            "HR can list all leave requests",
        ],
        non_functional_requirements=[
            "Input validation on every write endpoint",
            "Deterministic state transitions for leave status",
            "API tests cover submit and approval flow",
        ],
        constraints=["No external database required for the demonstration workspace"],
        acceptance_criteria=[
            "A leave request can be created",
            "A manager can approve a pending request",
            "HR can retrieve the resulting request",
            "The generated workspace test suite passes",
        ],
    )


def _lightweight_architecture() -> ArchitectureSpec:
    return ArchitectureSpec(
        summary="Single-service FastAPI application with a small browser UI and typed API.",
        backend="FastAPI / Python 3.12",
        frontend="Server-served HTML and browser fetch API",
        database="In-memory repository for the demo workspace",
        authentication="Out of scope for the generated demonstration app",
        services=["leave-api"],
        security_constraints=[
            "No arbitrary command execution",
            "All generated files remain inside the project workspace",
        ],
        decisions=[
            "Keep the generated demo dependency-light so validation is deterministic",
            "Use explicit leave status transitions",
        ],
    )


def _lightweight_application_spec() -> ApplicationSpec:
    return ApplicationSpec(
        target_profile=TargetProfile.LIGHTWEIGHT_PYTHON,
        roles=[
            RoleSpec(name="employee", description="Creates leave requests"),
            RoleSpec(name="manager", description="Decides pending requests"),
            RoleSpec(name="hr", description="Views all requests"),
        ],
        permissions=[
            PermissionSpec(
                role="employee",
                resource="leave-request",
                actions=["create", "read"],
                scope="own",
            ),
            PermissionSpec(
                role="manager",
                resource="leave-request",
                actions=["approve", "reject"],
                scope="team",
            ),
            PermissionSpec(
                role="hr",
                resource="leave-request",
                actions=["read"],
                scope="all",
            ),
        ],
        pages=[
            PageSpec(
                id="leave-list",
                route="/",
                title="Leave Management",
                allowed_roles=["employee", "manager", "hr"],
            )
        ],
        entities=[
            EntitySpec(
                name="LeaveRequest",
                fields=[
                    EntityFieldSpec(name="Id", data_type="integer"),
                    EntityFieldSpec(name="Employee", data_type="string"),
                    EntityFieldSpec(name="Days", data_type="integer"),
                    EntityFieldSpec(name="Reason", data_type="string"),
                    EntityFieldSpec(name="Status", data_type="enum"),
                ],
            )
        ],
        business_rules=[
            BusinessRuleSpec(
                id="BR-LEAVE-PENDING",
                name="Only pending leave can be decided",
                description="Approved or rejected leave cannot be decided again.",
                entity="LeaveRequest",
                trigger="approve or reject leave",
                condition="Status == Pending",
                outcome="transition status",
                allowed_roles=["manager"],
                error_code="LEAVE_NOT_PENDING",
            )
        ],
        workflows=[
            WorkflowSpec(
                name="Leave approval",
                steps=[
                    WorkflowStepSpec(
                        id="submit",
                        actor="employee",
                        action="submit leave",
                        result="pending request",
                    ),
                    WorkflowStepSpec(
                        id="decide",
                        actor="manager",
                        action="approve or reject pending leave",
                        result="decided request",
                    ),
                ],
            )
        ],
    )


def _lightweight_task_plan() -> TaskPlan:
    return TaskPlan(
        items=[
            WorkItem(
                id="DB-1",
                title="Implement leave repository",
                owner=AgentRole.DATABASE,
                acceptance_criteria=["Repository exposes deterministic CRUD operations"],
            ),
            WorkItem(
                id="API-1",
                title="Implement leave request domain and API",
                owner=AgentRole.BACKEND,
                depends_on=["DB-1"],
                acceptance_criteria=["Submit, list and approve endpoints are implemented"],
            ),
            WorkItem(
                id="UI-1",
                title="Implement minimal browser UI",
                owner=AgentRole.FRONTEND,
                depends_on=["API-1"],
                acceptance_criteria=["UI can load leave requests"],
            ),
            WorkItem(
                id="QA-1",
                title="Verify request and approval flow",
                owner=AgentRole.QA,
                depends_on=["API-1"],
                acceptance_criteria=["Automated tests pass"],
            ),
            WorkItem(
                id="OPS-1",
                title="Package a runnable release",
                owner=AgentRole.DEVOPS,
                depends_on=["QA-1"],
                acceptance_criteria=["Runtime dependencies and startup instructions are included"],
            ),
        ]
    )


def _fixture_artifacts(system: str) -> ArtifactSet:
    role = system.lower()
    if "database specialist" in role:
        return ArtifactSet(
            files=[
                GeneratedFile(path="app/__init__.py", content=""),
                GeneratedFile(
                    path="app/repository.py",
                    content=(
                        "from __future__ import annotations\n\n"
                        "from typing import Any\n\n"
                        "_records: dict[int, Any] = {}\n\n"
                        "def save(record: Any) -> None:\n    _records[record.id] = record\n\n"
                        "def get(record_id: int) -> Any | None:\n"
                        "    return _records.get(record_id)\n\n"
                        "def list_all() -> list[Any]:\n    return list(_records.values())\n"
                    ),
                ),
            ]
        )
    if "backend specialist" in role:
        return ArtifactSet(files=[GeneratedFile(path="app/main.py", content=_app_source())])
    if "frontend specialist" in role:
        return ArtifactSet(
            files=[
                GeneratedFile(
                    path="web/index.html",
                    content=(
                        "<!doctype html><html><body><main><h1>Leave Management</h1>"
                        "<button id='refresh'>Refresh</button><pre id='out'></pre>"
                        "<script>document.getElementById('refresh').onclick=async()=>{const r="
                        "await fetch('/api/leaves');document.getElementById('out').textContent="
                        "JSON.stringify(await r.json(),null,2)}</script></main></body></html>"
                    ),
                )
            ]
        )
    if "qa specialist" in role:
        return ArtifactSet(files=[GeneratedFile(path="tests/test_app.py", content=_test_source())])
    if "devops specialist" in role:
        return ArtifactSet(
            files=[
                GeneratedFile(
                    path="requirements.txt",
                    content="fastapi>=0.128,<1\nuvicorn>=0.35,<1\n",
                ),
                GeneratedFile(
                    path="README.md",
                    content=(
                        "# Leave Management\n\n"
                        "Install runtime dependencies with `pip install -r requirements.txt`, then "
                        "start the release with `uvicorn app.main:app --host "
                        "127.0.0.1 --port 8000`. Open `http://127.0.0.1:8000/` "
                        "to use the browser UI.\n"
                    ),
                ),
            ]
        )
    raise ValueError("Fixture could not identify specialist role")


def _app_source() -> str:
    return '''from __future__ import annotations

from enum import StrEnum
from itertools import count
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import repository

app = FastAPI(title="Leave Management")
_ids = count(1)
_index = Path(__file__).resolve().parents[1] / "web" / "index.html"


class LeaveStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LeaveCreate(BaseModel):
    employee: str = Field(min_length=2, max_length=100)
    days: int = Field(ge=1, le=30)
    reason: str = Field(min_length=3, max_length=500)


class LeaveDecision(BaseModel):
    status: LeaveStatus


class LeaveRecord(LeaveCreate):
    id: int
    status: LeaveStatus = LeaveStatus.PENDING


@app.get("/", include_in_schema=False)
def browser_ui() -> FileResponse:
    return FileResponse(_index)


@app.post("/api/leaves", response_model=LeaveRecord, status_code=201)
def create_leave(payload: LeaveCreate) -> LeaveRecord:
    item = LeaveRecord(id=next(_ids), **payload.model_dump())
    repository.save(item)
    return item


@app.get("/api/leaves", response_model=list[LeaveRecord])
def list_leaves() -> list[LeaveRecord]:
    return repository.list_all()


@app.patch("/api/leaves/{leave_id}", response_model=LeaveRecord)
def decide_leave(leave_id: int, payload: LeaveDecision) -> LeaveRecord:
    item = repository.get(leave_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if item.status is not LeaveStatus.PENDING:
        raise HTTPException(status_code=409, detail="Leave request already decided")
    if payload.status is LeaveStatus.PENDING:
        raise HTTPException(status_code=422, detail="Decision must approve or reject")
    updated = item.model_copy(update={"status": payload.status})
    repository.save(updated)
    return updated
'''


def _test_source() -> str:
    return '''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_browser_ui_is_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Leave Management" in response.text


def test_submit_approve_and_list_leave() -> None:
    created = client.post(
        "/api/leaves",
        json={"employee": "Asha", "days": 3, "reason": "Family event"},
    )
    assert created.status_code == 201
    leave_id = created.json()["id"]

    approved = client.patch(f"/api/leaves/{leave_id}", json={"status": "approved"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    listed = client.get("/api/leaves")
    assert listed.status_code == 200
    assert any(item["id"] == leave_id for item in listed.json())
'''


def _leave_management_bundle() -> CodeBundle:
    artifacts = [
        _fixture_artifacts("database specialist"),
        _fixture_artifacts("backend specialist"),
        _fixture_artifacts("frontend specialist"),
        _fixture_artifacts("qa specialist"),
        _fixture_artifacts("devops specialist"),
    ]
    return CodeBundle(files=[file for artifact in artifacts for file in artifact.files])
