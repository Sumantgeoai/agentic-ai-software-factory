from __future__ import annotations

from .contracts import ArchitectureSpec, TargetProfile


def apply_architecture_profile(
    profile: TargetProfile,
    architecture: ArchitectureSpec,
) -> ArchitectureSpec:
    if profile is not TargetProfile.ENTERPRISE_DOTNET_REACT:
        return architecture

    decisions = list(architecture.decisions)
    current_stack_decision = (
        "Use the governed enterprise-dotnet-react baseline: .NET 10, React 19, "
        "TypeScript 7, React Router 7, Vite 8 and PostgreSQL 16."
    )
    if current_stack_decision not in decisions:
        decisions.append(current_stack_decision)

    return architecture.model_copy(
        update={
            "summary": (
                "Modular ASP.NET Core Web API on .NET 10 with backend-enforced authorization "
                "and domain rules, a React 19/TypeScript SPA, and PostgreSQL 16 persistence "
                "behind EF Core 10/Npgsql."
            ),
            "backend": "ASP.NET Core Web API / .NET 10",
            "frontend": "React 19 + TypeScript 7 + React Router 7 + Vite 8",
            "database": "PostgreSQL 16 with EF Core 10/Npgsql and explicit migrations",
            "authentication": "OIDC/JWT bearer authentication with backend role policies",
            "decisions": decisions,
        }
    )
