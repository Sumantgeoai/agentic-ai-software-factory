from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AgentRole(StrEnum):
    PRODUCT_OWNER = "product_owner"
    ARCHITECT = "architect"
    PLANNER = "planner"
    BACKEND = "backend"
    QA = "qa"
    REVIEWER = "reviewer"


class ProjectRequest(BaseModel):
    request: str = Field(min_length=20, max_length=8_000)


class RequirementSpec(BaseModel):
    product_name: str
    actors: list[str]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    constraints: list[str]
    acceptance_criteria: list[str]


class ArchitectureSpec(BaseModel):
    summary: str
    backend: str
    frontend: str
    database: str
    authentication: str
    services: list[str]
    security_constraints: list[str]
    decisions: list[str]


class WorkItem(BaseModel):
    id: str = Field(pattern=r"^[A-Z]+-\d+$")
    title: str
    owner: AgentRole
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]


class TaskPlan(BaseModel):
    items: list[WorkItem]

    @field_validator("items")
    @classmethod
    def validate_dependencies(cls, items: list[WorkItem]) -> list[WorkItem]:
        ids = {item.id for item in items}
        for item in items:
            unknown = set(item.depends_on) - ids
            if unknown:
                raise ValueError(f"Unknown task dependencies for {item.id}: {sorted(unknown)}")
        return items


class GeneratedFile(BaseModel):
    path: str
    content: str = Field(max_length=200_000)

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("Generated file path must be a safe relative POSIX path")
        return value


class CodeBundle(BaseModel):
    files: list[GeneratedFile] = Field(min_length=1, max_length=100)
    validation_commands: list[Literal["compile", "test"]] = Field(
        default_factory=lambda: ["compile", "test"], min_length=1
    )


class CommandEvidence(BaseModel):
    command: str
    return_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def passed(self) -> bool:
        return self.return_code == 0


class ExecutionEvidence(BaseModel):
    workspace: str
    files_written: list[str]
    commands: list[CommandEvidence]

    @property
    def passed(self) -> bool:
        return bool(self.commands) and all(command.passed for command in self.commands)


class QualityReport(BaseModel):
    passed: bool
    summary: str
    failures: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    approved: bool
    summary: str
    risks: list[str] = Field(default_factory=list)


class FactoryRun(BaseModel):
    project_id: UUID
    requirements: RequirementSpec
    architecture: ArchitectureSpec
    plan: TaskPlan
    execution: ExecutionEvidence
    quality: QualityReport
    review: ReviewDecision
    repair_attempts: int = Field(ge=0)


class ToolRequest(BaseModel):
    name: str
    arguments: dict[str, Any]
    idempotency_key: str


class ToolResult(BaseModel):
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
