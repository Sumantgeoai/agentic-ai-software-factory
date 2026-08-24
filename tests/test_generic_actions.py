from software_factory.project_model import EnterpriseProjectModel
from software_factory.scenario_fixtures import SCENARIOS
from software_factory.spec_runtime_compiler import render_enterprise_runtime_bundle


def _scenario(key: str):
    return next(item for item in SCENARIOS if item.key == key)


def _program(key: str) -> str:
    scenario = _scenario(key)
    model = EnterpriseProjectModel.from_spec(
        scenario.requirements,
        scenario.application_spec,
    )
    bundle = render_enterprise_runtime_bundle(
        scenario.requirements,
        scenario.application_spec,
    )
    return next(file.content for file in bundle.files if file.path == model.api_path("Program.cs"))


def test_leave_and_asset_decisions_are_compiled_from_action_specs() -> None:
    leave = _program("leave")
    asset = _program("asset")

    assert 'MapPost("/api/leave-requests/{id}/approve"' in leave
    assert 'MapPost("/api/leave-requests/{id}/reject"' in leave
    assert 'existing.Status = "Approved";' in leave
    assert "BusinessRules.EnsureBRLEAVEPENDING(existing, user);" in leave

    assert 'MapPost("/api/inspections/{id}/approve"' in asset
    assert 'MapPost("/api/inspections/{id}/reject"' in asset
    assert 'existing.Status = "Rejected";' in asset
    assert "BusinessRules.EnsureBRINSPECTIONPENDING(existing, user);" in asset


def test_complaint_assign_action_compiles_typed_request_and_mutation() -> None:
    program = _program("complaint")

    assert 'MapPost("/api/complaints/{id}/assign"' in program
    assert "AssignComplaintRequest payload" in program
    assert "public sealed record AssignComplaintRequest(Guid? OfficerId);" in program
    assert "existing.AssignedOfficerId = payload.OfficerId;" in program
    assert "ResourceScopes.EnsureComplaintAssignScope(existing, user);" in program
    assert "BusinessRules.EnsureBRCOMPLAINTCLOSED(existing, user);" in program


def test_generic_update_does_not_mutate_scope_or_action_owned_fields() -> None:
    program = _program("complaint")
    update_block = program.split('MapPut("/api/complaints/{id}"', 1)[1].split(
        'RequireAuthorization("ComplaintUpdate")', 1
    )[0]

    assert "existing.Title = item.Title;" in update_block
    assert "existing.Description = item.Description;" in update_block
    assert "existing.CitizenId = item.CitizenId;" not in update_block
    assert "existing.AssignedOfficerId = item.AssignedOfficerId;" not in update_block
