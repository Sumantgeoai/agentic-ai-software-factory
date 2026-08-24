from __future__ import annotations

from dataclasses import dataclass

from .contracts import RequirementSpec, TargetProfile
from .specification import (
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


@dataclass(frozen=True, slots=True)
class ScenarioFixture:
    key: str
    requirements: RequirementSpec
    application_spec: ApplicationSpec


def _field_equals(field: str, value: str) -> RuleConditionSpec:
    return RuleConditionSpec(
        left=RuleOperandSpec(field=field),
        operator="eq",
        right=RuleOperandSpec(value=value),
    )


def _field_not_equals(field: str, value: str) -> RuleConditionSpec:
    return RuleConditionSpec(
        left=RuleOperandSpec(field=field),
        operator="ne",
        right=RuleOperandSpec(value=value),
    )


def _leave() -> ScenarioFixture:
    requirements = RequirementSpec(
        product_name="Leave Management",
        actors=["employee", "manager", "hr"],
        functional_requirements=[
            "Employees submit and view their own leave requests",
            "Managers decide requests for their teams",
            "HR views organization-wide reporting",
        ],
        non_functional_requirements=["Backend authorization is authoritative"],
        constraints=["Use enterprise-dotnet-react"],
        acceptance_criteria=["Role-scoped leave workflow is enforced"],
    )
    spec = ApplicationSpec(
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
        roles=[
            RoleSpec(name="employee", description="Creates own requests"),
            RoleSpec(name="manager", description="Decides team requests"),
            RoleSpec(name="hr", description="Views organization reporting"),
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
            PermissionSpec(
                role="hr",
                resource="leave-request",
                actions=["read"],
                scope="all",
            ),
        ],
        pages=[
            PageSpec(
                id="dashboard",
                route="/",
                title="Dashboard",
                allowed_roles=["employee", "manager", "hr"],
            ),
            PageSpec(
                id="my-leaves",
                route="/leaves",
                title="My Leaves",
                allowed_roles=["employee"],
            ),
            PageSpec(
                id="approvals",
                route="/approvals",
                title="Approvals",
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
                name="Pending decision",
                description="Only pending requests can be decided.",
                entity="LeaveRequest",
                trigger="approve or reject",
                condition=_field_equals("Status", "Pending"),
                outcome="allow decision",
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
                        action="submit request",
                        result="pending request",
                    ),
                    WorkflowStepSpec(
                        id="decide",
                        actor="manager",
                        action="decide team request",
                        result="approved or rejected request",
                    ),
                ],
            )
        ],
    )
    return ScenarioFixture("leave", requirements, spec)


def _complaint() -> ScenarioFixture:
    requirements = RequirementSpec(
        product_name="Citizen Complaint Portal",
        actors=["citizen", "officer", "supervisor"],
        functional_requirements=[
            "Citizens create and track complaints",
            "Officers work assigned complaints",
            "Supervisors monitor all complaints and reassign work",
        ],
        non_functional_requirements=["Complaint history must be auditable"],
        constraints=["Use enterprise-dotnet-react"],
        acceptance_criteria=["Complaint access respects own/team/all scope"],
    )
    spec = ApplicationSpec(
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
        roles=[
            RoleSpec(name="citizen", description="Creates and tracks own complaints"),
            RoleSpec(name="officer", description="Works assigned complaints"),
            RoleSpec(name="supervisor", description="Oversees the complaint operation"),
        ],
        permissions=[
            PermissionSpec(
                role="citizen",
                resource="complaint",
                actions=["create", "read"],
                scope="own",
                scope_binding=ScopeBindingSpec(
                    entity="Complaint",
                    record_field="CitizenId",
                    claim_type="sub",
                ),
            ),
            PermissionSpec(
                role="officer",
                resource="complaint",
                actions=["read", "update"],
                scope="team",
                scope_binding=ScopeBindingSpec(
                    entity="Complaint",
                    record_field="AssignedOfficerId",
                    claim_type="team_officer_id",
                ),
            ),
            PermissionSpec(
                role="supervisor",
                resource="complaint",
                actions=["read", "update", "assign"],
                scope="all",
            ),
        ],
        pages=[
            PageSpec(
                id="dashboard",
                route="/",
                title="Dashboard",
                allowed_roles=["citizen", "officer", "supervisor"],
            ),
            PageSpec(
                id="my-complaints",
                route="/complaints",
                title="My Complaints",
                allowed_roles=["citizen"],
            ),
            PageSpec(
                id="work-queue",
                route="/work",
                title="Work Queue",
                allowed_roles=["officer"],
            ),
            PageSpec(
                id="operations",
                route="/operations",
                title="Operations",
                allowed_roles=["supervisor"],
            ),
        ],
        entities=[
            EntitySpec(
                name="Complaint",
                fields=[
                    EntityFieldSpec(name="Id", data_type="uuid"),
                    EntityFieldSpec(name="CitizenId", data_type="uuid"),
                    EntityFieldSpec(name="Title", data_type="string"),
                    EntityFieldSpec(name="Description", data_type="string"),
                    EntityFieldSpec(name="Status", data_type="enum"),
                    EntityFieldSpec(
                        name="AssignedOfficerId",
                        data_type="uuid",
                        required=False,
                        nullable=True,
                    ),
                ],
            )
        ],
        business_rules=[
            BusinessRuleSpec(
                id="BR-COMPLAINT-CLOSED",
                name="Closed complaint immutable",
                description="Closed complaints cannot be edited by normal workflow.",
                entity="Complaint",
                trigger="update complaint",
                condition=_field_not_equals("Status", "Closed"),
                outcome="allow update",
                allowed_roles=["officer", "supervisor"],
                error_code="COMPLAINT_CLOSED",
            )
        ],
        workflows=[
            WorkflowSpec(
                name="Complaint resolution",
                steps=[
                    WorkflowStepSpec(
                        id="submit",
                        actor="citizen",
                        action="submit complaint",
                        result="open complaint",
                    ),
                    WorkflowStepSpec(
                        id="resolve",
                        actor="officer",
                        action="resolve assigned complaint",
                        result="resolved complaint",
                    ),
                ],
            )
        ],
    )
    return ScenarioFixture("complaint", requirements, spec)


def _asset() -> ScenarioFixture:
    requirements = RequirementSpec(
        product_name="Asset Inspection Manager",
        actors=["inspector", "supervisor", "asset_manager"],
        functional_requirements=[
            "Inspectors record asset inspections",
            "Supervisors review team inspections",
            "Asset managers view portfolio status",
        ],
        non_functional_requirements=["Inspection records use durable PostgreSQL persistence"],
        constraints=["Use enterprise-dotnet-react"],
        acceptance_criteria=["Inspection workflow and role scopes are explicit"],
    )
    spec = ApplicationSpec(
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
        roles=[
            RoleSpec(name="inspector", description="Creates inspections"),
            RoleSpec(name="supervisor", description="Reviews team inspections"),
            RoleSpec(name="asset_manager", description="Views all asset condition results"),
        ],
        permissions=[
            PermissionSpec(
                role="inspector",
                resource="inspection",
                actions=["create", "read", "update"],
                scope="own",
                scope_binding=ScopeBindingSpec(
                    entity="Inspection",
                    record_field="InspectorId",
                    claim_type="sub",
                ),
            ),
            PermissionSpec(
                role="supervisor",
                resource="inspection",
                actions=["read", "approve", "reject"],
                scope="team",
                scope_binding=ScopeBindingSpec(
                    entity="Inspection",
                    record_field="InspectorId",
                    claim_type="team_inspector_id",
                ),
            ),
            PermissionSpec(
                role="asset_manager",
                resource="inspection",
                actions=["read"],
                scope="all",
            ),
        ],
        pages=[
            PageSpec(
                id="dashboard",
                route="/",
                title="Dashboard",
                allowed_roles=["inspector", "supervisor", "asset_manager"],
            ),
            PageSpec(
                id="inspections",
                route="/inspections",
                title="My Inspections",
                allowed_roles=["inspector"],
            ),
            PageSpec(
                id="review",
                route="/review",
                title="Review Queue",
                allowed_roles=["supervisor"],
            ),
            PageSpec(
                id="portfolio",
                route="/portfolio",
                title="Asset Portfolio",
                allowed_roles=["asset_manager"],
            ),
        ],
        entities=[
            EntitySpec(
                name="Inspection",
                fields=[
                    EntityFieldSpec(name="Id", data_type="uuid"),
                    EntityFieldSpec(name="AssetId", data_type="uuid"),
                    EntityFieldSpec(name="InspectorId", data_type="uuid"),
                    EntityFieldSpec(name="InspectionDate", data_type="date"),
                    EntityFieldSpec(name="ConditionScore", data_type="decimal"),
                    EntityFieldSpec(name="Status", data_type="enum"),
                ],
            )
        ],
        business_rules=[
            BusinessRuleSpec(
                id="BR-INSPECTION-PENDING",
                name="Only submitted inspections can be reviewed",
                description="Only submitted inspections can transition through review.",
                entity="Inspection",
                trigger="approve or reject inspection",
                condition=_field_equals("Status", "Submitted"),
                outcome="allow decision",
                allowed_roles=["supervisor"],
                error_code="INSPECTION_NOT_SUBMITTED",
            )
        ],
        workflows=[
            WorkflowSpec(
                name="Inspection review",
                steps=[
                    WorkflowStepSpec(
                        id="record",
                        actor="inspector",
                        action="record inspection",
                        result="submitted inspection",
                    ),
                    WorkflowStepSpec(
                        id="review",
                        actor="supervisor",
                        action="review inspection",
                        result="approved or rejected inspection",
                    ),
                ],
            )
        ],
    )
    return ScenarioFixture("asset", requirements, spec)


SCENARIOS: tuple[ScenarioFixture, ...] = (_leave(), _complaint(), _asset())


def scenario_for_request(request: str) -> ScenarioFixture:
    text = request.lower()
    if "complaint" in text or "ticket" in text:
        return SCENARIOS[1]
    if "asset" in text or "inspection" in text or "inventory" in text:
        return SCENARIOS[2]
    if "leave" in text:
        return SCENARIOS[0]
    raise ValueError(
        "Deterministic fixture mode supports the named acceptance scenarios only; "
        "use an LLM provider for arbitrary domain specifications."
    )
