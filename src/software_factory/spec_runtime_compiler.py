from __future__ import annotations

from .contracts import AgentRole, ArtifactSet, CodeBundle, GeneratedFile, RequirementSpec
from .project_model import EnterpriseProjectModel
from .spec_action_renderer import render_application_program
from .spec_policy_renderer import (
    render_business_rules,
    render_rule_tests,
    render_scope_tests,
)
from .spec_renderer import render_enterprise_bundle
from .spec_runtime_renderer import (
    _docker_files,
    _frontend_bootstrap,
    _migration,
    _python_contract,
    _replace,
    _test_project,
)
from .spec_scope_renderer import render_resource_scopes
from .specification import ApplicationSpec


def render_enterprise_runtime_bundle(
    requirements: RequirementSpec,
    spec: ApplicationSpec,
) -> CodeBundle:
    """Compile validated enterprise specification into governed source artifacts.

    LLM reasoning ends at the typed specification boundary. Source, authorization,
    tests and deployment artifacts are rendered deterministically from that contract.
    """

    model = EnterpriseProjectModel.from_spec(requirements, spec)
    base = render_enterprise_bundle(requirements, spec)
    files = list(base.files)
    _replace(files, render_business_rules(model, spec))
    _replace(files, render_resource_scopes(model, spec))
    _replace(files, render_application_program(model, spec))
    _replace(files, _migration(model, spec))
    _replace(files, _test_project(model))
    _replace(files, render_rule_tests(model, spec))
    _replace(files, render_scope_tests(model, spec))
    _replace(
        files,
        GeneratedFile(
            path=model.test_path("Usings.cs"),
            content="global using Xunit;\n",
        ),
    )
    for file in _frontend_bootstrap(requirements):
        _replace(files, file)
    for file in _docker_files(model, requirements):
        _replace(files, file)
    _replace(files, _python_contract(model, spec))
    _replace(
        files,
        GeneratedFile(
            path="application-spec.json",
            content=spec.model_dump_json(indent=2) + "\n",
        ),
    )
    return CodeBundle(files=files)


def render_enterprise_role_artifacts(
    role: AgentRole,
    requirements: RequirementSpec,
    spec: ApplicationSpec,
) -> ArtifactSet:
    bundle = render_enterprise_runtime_bundle(requirements, spec)
    model = EnterpriseProjectModel.from_spec(requirements, spec)
    files = [file for file in bundle.files if _owned_by_role(file, model, role)]
    return ArtifactSet(files=files)


def _owned_by_role(
    file: GeneratedFile,
    model: EnterpriseProjectModel,
    role: AgentRole,
) -> bool:
    path = file.path
    if role is AgentRole.DATABASE:
        return path.startswith(model.api_path("Infrastructure/"))
    if role is AgentRole.BACKEND:
        return path.startswith(f"backend/{model.api_project}/") and (
            "/Infrastructure/" not in path
            and f"backend/{model.test_project}/" not in path
            and not path.endswith("/Dockerfile")
        )
    if role is AgentRole.FRONTEND:
        return path.startswith("frontend/") and path != "frontend/Dockerfile"
    if role is AgentRole.QA:
        return path.startswith(f"backend/{model.test_project}/") or path.startswith("tests/")
    if role is AgentRole.DEVOPS:
        return (
            path.endswith("/Dockerfile")
            or path in {"frontend/Dockerfile", "docker-compose.yml", "README.generated.md"}
            or path == "application-spec.json"
        )
    raise ValueError(f"Unsupported enterprise specialist role: {role.value}")
