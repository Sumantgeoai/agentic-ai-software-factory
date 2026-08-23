from __future__ import annotations

from .contracts import ArtifactSet, CodeBundle, GeneratedFile

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


def apply_enterprise_artifact_policy(artifacts: ArtifactSet, system: str) -> ArtifactSet:
    files = list(artifacts.files)
    role = system.lower()
    if "backend specialist" in role:
        files.append(_BACKEND_BUILD_POLICY)
    if "qa specialist" in role:
        files.append(_QA_USINGS)
    return ArtifactSet(files=files)


def apply_enterprise_bundle_policy(bundle: CodeBundle) -> CodeBundle:
    files = list(bundle.files)
    for required in (_BACKEND_BUILD_POLICY, _QA_USINGS):
        if not any(file.path == required.path for file in files):
            files.append(required)
    return CodeBundle(files=files)
