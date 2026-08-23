from __future__ import annotations

from .contracts import ArtifactSet, CodeBundle, GeneratedFile
from .enterprise_authorization import (
    LEAVE_SERVICE,
    MANAGER_SCOPE_DOMAIN,
    MANAGER_SCOPE_TESTS,
    PROGRAM,
)
from .enterprise_stack import (
    API_PROJECT,
    BACKEND_DOCKERFILE,
    FRONTEND_DOCKERFILE,
    FRONTEND_PACKAGE,
    STACK_CONTRACT_TEST,
    TEST_PROJECT,
)

_BACKEND_BUILD_POLICY = GeneratedFile(
    path="backend/Directory.Build.props",
    content='''<Project>
  <PropertyGroup>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
''',
)

_QA_USINGS = GeneratedFile(
    path="backend/LeaveManagement.Tests/Usings.cs",
    content="global using Xunit;\n",
)


def _replace(files: list[GeneratedFile], replacement: GeneratedFile) -> None:
    for index, item in enumerate(files):
        if item.path == replacement.path:
            files[index] = replacement
            return
    files.append(replacement)


def apply_enterprise_artifact_policy(artifacts: ArtifactSet, system: str) -> ArtifactSet:
    files = list(artifacts.files)
    role = system.lower()
    if "backend specialist" in role:
        for required in (
            _BACKEND_BUILD_POLICY,
            API_PROJECT,
            MANAGER_SCOPE_DOMAIN,
            LEAVE_SERVICE,
            PROGRAM,
        ):
            _replace(files, required)
    if "frontend specialist" in role:
        _replace(files, FRONTEND_PACKAGE)
    if "qa specialist" in role:
        for required in (
            _QA_USINGS,
            TEST_PROJECT,
            MANAGER_SCOPE_TESTS,
            STACK_CONTRACT_TEST,
        ):
            _replace(files, required)
    if "devops specialist" in role:
        for required in (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE):
            _replace(files, required)
    return ArtifactSet(files=files)


def apply_enterprise_bundle_policy(bundle: CodeBundle) -> CodeBundle:
    files = list(bundle.files)
    for required in (
        _BACKEND_BUILD_POLICY,
        _QA_USINGS,
        API_PROJECT,
        TEST_PROJECT,
        BACKEND_DOCKERFILE,
        FRONTEND_PACKAGE,
        FRONTEND_DOCKERFILE,
        STACK_CONTRACT_TEST,
        MANAGER_SCOPE_DOMAIN,
        LEAVE_SERVICE,
        PROGRAM,
        MANAGER_SCOPE_TESTS,
    ):
        _replace(files, required)
    return CodeBundle(files=files)
