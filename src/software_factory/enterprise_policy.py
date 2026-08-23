from __future__ import annotations

from .contracts import ArtifactSet, CodeBundle, GeneratedFile
from .enterprise_authorization import (
    LEAVE_SERVICE,
    MANAGER_SCOPE_DOMAIN,
    MANAGER_SCOPE_TESTS,
    PROGRAM,
)

_BACKEND_BUILD_POLICY = GeneratedFile(
    path="backend/Directory.Build.props",
    content='''<Project>
  <ItemGroup Condition="'$(MSBuildProjectName)' == 'LeaveManagement.Api'">
    <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="8.0.29" />
  </ItemGroup>
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
        for required in (_BACKEND_BUILD_POLICY, MANAGER_SCOPE_DOMAIN, LEAVE_SERVICE, PROGRAM):
            _replace(files, required)
    if "qa specialist" in role:
        for required in (_QA_USINGS, MANAGER_SCOPE_TESTS):
            _replace(files, required)
    return ArtifactSet(files=files)


def apply_enterprise_bundle_policy(bundle: CodeBundle) -> CodeBundle:
    files = list(bundle.files)
    for required in (
        _BACKEND_BUILD_POLICY,
        _QA_USINGS,
        MANAGER_SCOPE_DOMAIN,
        LEAVE_SERVICE,
        PROGRAM,
        MANAGER_SCOPE_TESTS,
    ):
        _replace(files, required)
    return CodeBundle(files=files)
