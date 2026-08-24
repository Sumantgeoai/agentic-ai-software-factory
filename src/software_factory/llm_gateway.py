from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel

from .config import Settings

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
