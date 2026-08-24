from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import RequirementSpec
from .specification import ApplicationSpec


_WORD = re.compile(r"[A-Za-z0-9]+")


def _words(value: str) -> list[str]:
    return _WORD.findall(value)


def _pascal(value: str) -> str:
    parts = _words(value)
    if not parts:
        raise ValueError("Project name must contain at least one alphanumeric character")
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _kebab(value: str) -> str:
    parts = _words(value)
    if not parts:
        raise ValueError("Project name must contain at least one alphanumeric character")
    return "-".join(part.lower() for part in parts)


@dataclass(frozen=True, slots=True)
class EnterpriseProjectModel:
    product_name: str
    product_pascal: str
    product_slug: str
    api_project: str
    test_project: str
    root_namespace: str
    frontend_package: str

    @classmethod
    def from_spec(
        cls,
        requirements: RequirementSpec,
        application_spec: ApplicationSpec,
    ) -> EnterpriseProjectModel:
        if not application_spec.roles:
            raise ValueError("Application specification requires at least one role")
        product_pascal = _pascal(requirements.product_name)
        product_slug = _kebab(requirements.product_name)
        return cls(
            product_name=requirements.product_name,
            product_pascal=product_pascal,
            product_slug=product_slug,
            api_project=f"{product_pascal}.Api",
            test_project=f"{product_pascal}.Tests",
            root_namespace=product_pascal,
            frontend_package=f"{product_slug}-web",
        )

    def api_path(self, relative: str) -> str:
        return f"backend/{self.api_project}/{relative.lstrip('/')}"

    def test_path(self, relative: str) -> str:
        return f"backend/{self.test_project}/{relative.lstrip('/')}"
