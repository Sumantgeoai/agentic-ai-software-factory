import pytest
from pydantic import ValidationError

from software_factory.contracts import ProjectRequest, TargetProfile
from software_factory.specification import (
    ApplicationSpec,
    BusinessRuleSpec,
    EntityFieldSpec,
    EntitySpec,
    PageSpec,
    PermissionSpec,
    RoleSpec,
    RuleConditionSpec,
    RuleOperandSpec,
    ScopeBindingSpec,
    WorkflowSpec,
    WorkflowStepSpec,
)


def _spec() -> ApplicationSpec:
    return ApplicationSpec(
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
        roles=[
            RoleSpec(name="employee", description="Creates and tracks own leave requests"),
            RoleSpec(name="manager", description="Approves team leave requests"),
            RoleSpec(name="hr", description="Administers leave policy and reporting"),
        ],
        permissions=[
            PermissionSpec(
                role="employee",
                resource="leave-request",
                actions=["create", "read"],
                scope="own",
                scope_binding=ScopeBindingSpec(
                    entity="LeaveRequest",
                    record_field="EmployeeId",
                    claim_type="sub",
                ),
            ),
            PermissionSpec(
                role="manager",
                resource="leave-request",
                actions=["read", "approve", "reject"],
                scope="team",
                scope_binding=ScopeBindingSpec(
                    entity="LeaveRequest",
                    record_field="EmployeeId",
                    claim_type="team_employee_id",
                ),
            ),
        ],
        pages=[
            PageSpec(
                id="my-leaves",
                route="/leaves",
                title="My Leaves",
                allowed_roles=["employee"],
            ),
            PageSpec(
                id="approval-queue",
                route="/approvals",
                title="Approval Queue",
                allowed_roles=["manager"],
            ),
            PageSpec(
                id="reports",
                route="/reports",
                title="Reports",
                allowed_roles=["hr"],
            ),
        ],
        entities=[
            EntitySpec(
                name="LeaveRequest",
                fields=[
                    EntityFieldSpec(name="Id", data_type="uuid"),
                    EntityFieldSpec(name="EmployeeId", data_type="uuid"),
                    EntityFieldSpec(name="StartDate", data_type="date"),
                    EntityFieldSpec(name="EndDate", data_type="date"),
                    EntityFieldSpec(name="Status", data_type="enum"),
                ],
            )
        ],
        business_rules=[
            BusinessRuleSpec(
                id="BR-LEAVE-PENDING",
                name="Only pending leave can be decided",
                description="Approved or rejected leave requests cannot be decided again.",
                entity="LeaveRequest",
                trigger="approve or reject leave request",
                condition=RuleConditionSpec(
                    left=RuleOperandSpec(field="Status"),
                    operator="eq",
                    right=RuleOperandSpec(value="Pending"),
                ),
                outcome="transition to Approved or Rejected",
                allowed_roles=["manager"],
                error_code="LEAVE_NOT_PENDING",
            )
        ],
        workflows=[
            WorkflowSpec(
                name="Leave approval",
                steps=[
                    WorkflowStepSpec(
                        id="submit",
                        actor="employee",
                        action="submit leave request",
                        result="pending leave request",
                    ),
                    WorkflowStepSpec(
                        id="approve",
                        actor="manager",
                        action="approve pending request",
                        result="approved leave request",
                    ),
                ],
            )
        ],
    )


def test_project_request_accepts_enterprise_target_profile() -> None:
    request = ProjectRequest(
        request="Build an employee leave management application with role-based approval.",
        target_profile="enterprise-dotnet-react",
    )
    assert request.target_profile is TargetProfile.ENTERPRISE_DOTNET_REACT


def test_application_spec_validates_cross_references() -> None:
    spec = _spec()
    assert spec.target_profile is TargetProfile.ENTERPRISE_DOTNET_REACT
    assert spec.business_rules[0].enforcement == "backend"
    assert not isinstance(spec.business_rules[0].condition, str)
    assert spec.permissions[0].scope_binding is not None
    assert {page.route for page in spec.pages} == {"/leaves", "/approvals", "/reports"}


def test_application_spec_rejects_unknown_role_reference() -> None:
    payload = _spec().model_dump()
    payload["pages"][0]["allowed_roles"] = ["unknown-role"]
    with pytest.raises(ValidationError, match="Unknown page roles"):
        ApplicationSpec.model_validate(payload)


def test_enterprise_spec_rejects_unbound_own_or_team_permission() -> None:
    payload = _spec().model_dump()
    payload["permissions"][0]["scope_binding"] = None
    with pytest.raises(ValidationError, match="requires scope_binding"):
        ApplicationSpec.model_validate(payload)


def test_enterprise_spec_rejects_unknown_scope_field() -> None:
    payload = _spec().model_dump()
    payload["permissions"][0]["scope_binding"]["record_field"] = "UnknownField"
    with pytest.raises(ValidationError, match="Unknown scope-binding field"):
        ApplicationSpec.model_validate(payload)


def test_enterprise_spec_rejects_free_form_business_rule_condition() -> None:
    payload = _spec().model_dump()
    payload["business_rules"][0]["condition"] = "Status == Pending"
    with pytest.raises(ValidationError, match="requires typed condition"):
        ApplicationSpec.model_validate(payload)
