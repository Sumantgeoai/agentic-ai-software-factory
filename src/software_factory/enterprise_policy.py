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


def apply_enterprise_artifact_policy(artifacts: ArtifactSet, system: str) -> ArtifactSet:
    files = list(artifacts.files)
    if "backend specialist" in system.lower():
        files.append(_BACKEND_BUILD_POLICY)
    return ArtifactSet(files=files)


def apply_enterprise_bundle_policy(bundle: CodeBundle) -> CodeBundle:
    files = list(bundle.files)
    if not any(file.path == _BACKEND_BUILD_POLICY.path for file in files):
        files.append(_BACKEND_BUILD_POLICY)
    return CodeBundle(files=files)
