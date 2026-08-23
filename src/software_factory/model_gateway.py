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
    CodeBundle,
    GeneratedFile,
    RequirementSpec,
    TaskPlan,
    WorkItem,
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
        del system, user
        if schema is RequirementSpec:
            value = RequirementSpec(
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
        elif schema is ArchitectureSpec:
            value = ArchitectureSpec(
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
        elif schema is TaskPlan:
            value = TaskPlan(
                items=[
                    WorkItem(
                        id="APP-1",
                        title="Implement leave request domain and API",
                        owner=AgentRole.BACKEND,
                        acceptance_criteria=["Submit, list and approve endpoints are implemented"],
                    ),
                    WorkItem(
                        id="QA-1",
                        title="Verify request and approval flow",
                        owner=AgentRole.QA,
                        depends_on=["APP-1"],
                        acceptance_criteria=["Automated tests pass"],
                    ),
                ]
            )
        elif schema is CodeBundle:
            value = _leave_management_bundle()
        else:
            raise TypeError(f"Fixture gateway does not support {schema.__name__}")
        return schema.model_validate(value.model_dump())


def _leave_management_bundle() -> CodeBundle:
    app_source = '''from __future__ import annotations

from enum import StrEnum
from itertools import count

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Leave Management")
_ids = count(1)
_leaves: dict[int, "LeaveRecord"] = {}


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


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html><html><body><main><h1>Leave Management</h1>
    <p>Use the API to submit and review leave requests.</p>
    <button onclick=\"loadLeaves()\">Refresh</button><pre id=\"out\"></pre>
    <script>async function loadLeaves(){const r=await fetch('/api/leaves');
    document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}</script>
    </main></body></html>"""


@app.post("/api/leaves", response_model=LeaveRecord, status_code=201)
def create_leave(payload: LeaveCreate) -> LeaveRecord:
    item = LeaveRecord(id=next(_ids), **payload.model_dump())
    _leaves[item.id] = item
    return item


@app.get("/api/leaves", response_model=list[LeaveRecord])
def list_leaves() -> list[LeaveRecord]:
    return list(_leaves.values())


@app.patch("/api/leaves/{leave_id}", response_model=LeaveRecord)
def decide_leave(leave_id: int, payload: LeaveDecision) -> LeaveRecord:
    item = _leaves.get(leave_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if item.status is not LeaveStatus.PENDING:
        raise HTTPException(status_code=409, detail="Leave request already decided")
    if payload.status is LeaveStatus.PENDING:
        raise HTTPException(status_code=422, detail="Decision must approve or reject")
    updated = item.model_copy(update={"status": payload.status})
    _leaves[leave_id] = updated
    return updated
'''
    test_source = '''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
    return CodeBundle(
        files=[
            GeneratedFile(path="app/__init__.py", content=""),
            GeneratedFile(path="app/main.py", content=app_source),
            GeneratedFile(path="tests/test_app.py", content=test_source),
            GeneratedFile(
                path="README.md",
                content=(
                    "# Leave Management\n\nGenerated release candidate. Run with "
                    "`uvicorn app.main:app --reload`.\n"
                ),
            ),
        ],
        validation_commands=["compile", "test"],
    )
