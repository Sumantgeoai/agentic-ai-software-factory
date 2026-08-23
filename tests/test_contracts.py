import pytest
from pydantic import ValidationError

from software_factory.contracts import AgentRole, GeneratedFile, TaskPlan, WorkItem


def test_generated_file_rejects_workspace_escape() -> None:
    with pytest.raises(ValidationError):
        GeneratedFile(path="../secrets.txt", content="nope")


def test_task_plan_rejects_unknown_dependency() -> None:
    with pytest.raises(ValidationError):
        TaskPlan(
            items=[
                WorkItem(
                    id="APP-1",
                    title="Build API",
                    owner=AgentRole.BACKEND,
                    depends_on=["APP-0"],
                    acceptance_criteria=["Build passes"],
                )
            ]
        )
