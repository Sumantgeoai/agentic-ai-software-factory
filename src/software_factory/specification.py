from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .contracts import TargetProfile


RuleScalar = str | int | float | bool
_CRUD_OPERATIONS = {"create", "read", "update", "delete"}


def _resource_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", entity_name).lower()


class RoleSpec(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    description: str


class ScopeBindingSpec(BaseModel):
    entity: str = Field(pattern=r"^[A-Z][A-Za-z0-9]{1,63}$")
    record_field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    claim_type: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:/-]{0,127}$")


class PermissionSpec(BaseModel):
    role: str
    resource: str
    actions: list[str] = Field(min_length=1)
    scope: Literal["own", "team", "all"]
    scope_binding: ScopeBindingSpec | None = None


class PageSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    route: str
    title: str
    allowed_roles: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)


class EntityFieldSpec(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    data_type: Literal[
        "string",
        "integer",
        "decimal",
        "boolean",
        "date",
        "datetime",
        "uuid",
        "enum",
    ]
    required: bool = True
    nullable: bool = False


class EntitySpec(BaseModel):
    name: str = Field(pattern=r"^[A-Z][A-Za-z0-9]{1,63}$")
    fields: list[EntityFieldSpec] = Field(min_length=1)


class RuleOperandSpec(BaseModel):
    field: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    value: RuleScalar | None = None

    @model_validator(mode="after")
    def validate_exactly_one_source(self) -> RuleOperandSpec:
        if (self.field is None) == (self.value is None):
            raise ValueError("Rule operand must define exactly one of field or value")
        return self


class RuleConditionSpec(BaseModel):
    left: RuleOperandSpec
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte"]
    right: RuleOperandSpec


class FieldMutationSpec(BaseModel):
    field: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    source: Literal["literal", "input"]
    value: RuleScalar | None = None
    input_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$",
    )

    @model_validator(mode="after")
    def validate_source(self) -> FieldMutationSpec:
        if self.source == "literal":
            if self.value is None or self.input_name is not None:
                raise ValueError("Literal mutation requires value and no input_name")
        elif self.input_name is None or self.value is not None:
            raise ValueError("Input mutation requires input_name and no literal value")
        return self


class EntityActionSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    entity: str = Field(pattern=r"^[A-Z][A-Za-z0-9]{1,63}$")
    permission_action: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    mutations: list[FieldMutationSpec] = Field(min_length=1)


class BusinessRuleSpec(BaseModel):
    id: str = Field(pattern=r"^BR-[A-Z0-9-]+$")
    name: str
    description: str
    entity: str
    trigger: str
    condition: RuleConditionSpec | str
    outcome: str
    allowed_roles: list[str] = Field(default_factory=list)
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    enforcement: Literal["backend"] = "backend"
    applies_to: list[str] = Field(default_factory=list)


class WorkflowStepSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    actor: str
    action: str
    result: str
    action_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]{1,63}$")


class WorkflowSpec(BaseModel):
    name: str
    steps: list[WorkflowStepSpec] = Field(min_length=1)


class ApplicationSpec(BaseModel):
    target_profile: TargetProfile
    roles: list[RoleSpec] = Field(min_length=1)
    permissions: list[PermissionSpec] = Field(default_factory=list)
    pages: list[PageSpec] = Field(min_length=1)
    entities: list[EntitySpec] = Field(min_length=1)
    actions: list[EntityActionSpec] = Field(default_factory=list)
    business_rules: list[BusinessRuleSpec] = Field(default_factory=list)
    workflows: list[WorkflowSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> ApplicationSpec:
        roles = {role.name for role in self.roles}
        entities = {entity.name for entity in self.entities}
        entity_fields = {
            entity.name: {field.name: field for field in entity.fields} for entity in self.entities
        }
        actions_by_id = {action.id: action for action in self.actions}
        action_ids = set(actions_by_id)
        rule_ids = {rule.id for rule in self.business_rules}

        duplicate_roles = len(roles) != len(self.roles)
        duplicate_pages = len({page.id for page in self.pages}) != len(self.pages)
        duplicate_actions = len(action_ids) != len(self.actions)
        duplicate_rules = len(rule_ids) != len(self.business_rules)
        if duplicate_roles or duplicate_pages or duplicate_actions or duplicate_rules:
            raise ValueError("Application specification identifiers must be unique")

        if self.target_profile is TargetProfile.ENTERPRISE_DOTNET_REACT:
            self._validate_enterprise_entities(entity_fields)

        for page in self.pages:
            if not page.route.startswith("/"):
                raise ValueError(f"Page route must start with '/': {page.route}")
            unknown = set(page.allowed_roles) - roles
            if unknown:
                raise ValueError(f"Unknown page roles for {page.id}: {sorted(unknown)}")

        for permission in self.permissions:
            if permission.role not in roles:
                raise ValueError(f"Unknown permission role: {permission.role}")
            if self.target_profile is TargetProfile.ENTERPRISE_DOTNET_REACT:
                if permission.scope in {"own", "team"} and permission.scope_binding is None:
                    raise ValueError(
                        f"Scoped enterprise permission requires scope_binding: "
                        f"{permission.role}/{permission.resource}"
                    )
                if permission.scope_binding is not None:
                    self._validate_scope_binding(permission, entities, entity_fields)

        for action in self.actions:
            if action.id in _CRUD_OPERATIONS:
                raise ValueError(f"Custom action cannot shadow CRUD operation: {action.id}")
            if action.entity not in entities:
                raise ValueError(f"Unknown entity action target for {action.id}: {action.entity}")
            fields = entity_fields[action.entity]
            for mutation in action.mutations:
                if mutation.field not in fields:
                    raise ValueError(f"Unknown mutation field for {action.id}: {mutation.field}")
                if mutation.field == "Id":
                    raise ValueError(f"Custom action cannot mutate entity Id: {action.id}")
            resource = _resource_name(action.entity)
            allowed = any(
                permission.resource == resource
                and action.permission_action in permission.actions
                for permission in self.permissions
            )
            if not allowed:
                raise ValueError(
                    f"Entity action has no matching permission: "
                    f"{action.id}/{action.permission_action}"
                )

        for rule in self.business_rules:
            if rule.entity not in entities:
                raise ValueError(f"Unknown business-rule entity for {rule.id}: {rule.entity}")
            unknown = set(rule.allowed_roles) - roles
            if unknown:
                raise ValueError(f"Unknown business-rule roles for {rule.id}: {sorted(unknown)}")
            if self.target_profile is TargetProfile.ENTERPRISE_DOTNET_REACT:
                self._validate_enterprise_rule(rule, entity_fields, actions_by_id)

        for workflow in self.workflows:
            for step in workflow.steps:
                if step.actor not in roles:
                    raise ValueError(f"Unknown workflow actor: {step.actor}")
                if step.action_id is not None:
                    action = actions_by_id.get(step.action_id)
                    if action is None:
                        raise ValueError(f"Unknown workflow action: {step.action_id}")
                    resource = _resource_name(action.entity)
                    actor_allowed = any(
                        permission.role == step.actor
                        and permission.resource == resource
                        and action.permission_action in permission.actions
                        for permission in self.permissions
                    )
                    if not actor_allowed:
                        raise ValueError(
                            f"Workflow actor lacks action permission: "
                            f"{step.actor}/{step.action_id}"
                        )
        return self

    @staticmethod
    def _validate_enterprise_entities(
        entity_fields: dict[str, dict[str, EntityFieldSpec]],
    ) -> None:
        for entity, fields in entity_fields.items():
            id_field = fields.get("Id")
            if id_field is None:
                raise ValueError(f"Enterprise entity requires Id field: {entity}")
            if id_field.data_type not in {"uuid", "string", "integer"}:
                raise ValueError(
                    f"Enterprise entity Id must be uuid, string, or integer: {entity}.Id"
                )
            if id_field.nullable or not id_field.required:
                raise ValueError(f"Enterprise entity Id must be required: {entity}.Id")

    @staticmethod
    def _validate_scope_binding(
        permission: PermissionSpec,
        entities: set[str],
        entity_fields: dict[str, dict[str, EntityFieldSpec]],
    ) -> None:
        binding = permission.scope_binding
        assert binding is not None
        if binding.entity not in entities:
            raise ValueError(
                f"Unknown scope-binding entity for {permission.role}/"
                f"{permission.resource}: {binding.entity}"
            )
        field = entity_fields[binding.entity].get(binding.record_field)
        if field is None:
            raise ValueError(
                f"Unknown scope-binding field for {permission.role}/"
                f"{permission.resource}: {binding.record_field}"
            )
        if field.data_type not in {"uuid", "string", "integer"}:
            raise ValueError(
                "Scope-binding fields must use uuid, string, or integer types: "
                f"{binding.entity}.{binding.record_field}"
            )

    def _validate_enterprise_rule(
        self,
        rule: BusinessRuleSpec,
        entity_fields: dict[str, dict[str, EntityFieldSpec]],
        actions_by_id: dict[str, EntityActionSpec],
    ) -> None:
        if isinstance(rule.condition, str):
            raise ValueError(f"Enterprise business rule requires typed condition for {rule.id}")
        if not rule.applies_to:
            raise ValueError(f"Enterprise business rule requires applies_to for {rule.id}")
        unknown_targets = set(rule.applies_to) - (_CRUD_OPERATIONS | set(actions_by_id))
        if unknown_targets:
            raise ValueError(
                f"Unknown business-rule operation for {rule.id}: {sorted(unknown_targets)}"
            )
        resource = _resource_name(rule.entity)
        for operation in rule.applies_to:
            if operation in _CRUD_OPERATIONS:
                exists = any(
                    permission.resource == resource and operation in permission.actions
                    for permission in self.permissions
                )
                if not exists:
                    raise ValueError(
                        f"Business rule targets unavailable CRUD operation: {rule.id}/{operation}"
                    )
            else:
                action = actions_by_id[operation]
                if action.entity != rule.entity:
                    raise ValueError(
                        f"Business rule action targets another entity: {rule.id}/{operation}"
                    )
        fields = entity_fields[rule.entity]
        for operand in (rule.condition.left, rule.condition.right):
            if operand.field is not None and operand.field not in fields:
                raise ValueError(f"Unknown rule-condition field for {rule.id}: {operand.field}")
