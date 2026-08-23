from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _origins(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    model_provider: str = "fixture"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    workspace_root: Path = Path("workspaces")
    allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    model_timeout_seconds: float = 90.0
    command_timeout_seconds: float = 60.0
    max_repair_attempts: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_provider=os.getenv("SOFTWARE_FACTORY_MODEL_PROVIDER", "fixture").strip().lower(),
            nvidia_api_key=os.getenv("SOFTWARE_FACTORY_NVIDIA_API_KEY") or None,
            nvidia_base_url=os.getenv(
                "SOFTWARE_FACTORY_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
            ).rstrip("/"),
            nvidia_model=os.getenv(
                "SOFTWARE_FACTORY_NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"
            ),
            workspace_root=Path(os.getenv("SOFTWARE_FACTORY_WORKSPACE_ROOT", "workspaces")),
            allowed_origins=_origins(
                os.getenv("SOFTWARE_FACTORY_ALLOWED_ORIGINS", "http://localhost:5173")
            ),
            model_timeout_seconds=float(os.getenv("SOFTWARE_FACTORY_MODEL_TIMEOUT_SECONDS", "90")),
            command_timeout_seconds=float(
                os.getenv("SOFTWARE_FACTORY_COMMAND_TIMEOUT_SECONDS", "60")
            ),
            max_repair_attempts=int(os.getenv("SOFTWARE_FACTORY_MAX_REPAIR_ATTEMPTS", "2")),
        )
