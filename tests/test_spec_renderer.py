from software_factory.scenario_fixtures import SCENARIOS
from software_factory.spec_renderer import render_enterprise_bundle


def _file_map(index: int) -> dict[str, str]:
    scenario = SCENARIOS[index]
    bundle = render_enterprise_bundle(scenario.requirements, scenario.application_spec)
    return {item.path: item.content for item in bundle.files}


def test_renderer_derives_distinct_backend_projects() -> None:
    leave = _file_map(0)
    complaint = _file_map(1)
    asset = _file_map(2)

    assert "backend/LeaveManagement.Api/LeaveManagement.Api.csproj" in leave
    assert "backend/CitizenComplaintPortal.Api/CitizenComplaintPortal.Api.csproj" in complaint
    assert "backend/AssetInspectionManager.Api/AssetInspectionManager.Api.csproj" in asset


def test_renderer_generates_entities_and_routes_from_spec() -> None:
    complaint = _file_map(1)
    asset = _file_map(2)

    assert "backend/CitizenComplaintPortal.Api/Domain/Complaint.cs" in complaint
    assert "CitizenId" in complaint["backend/CitizenComplaintPortal.Api/Domain/Complaint.cs"]
    assert 'path="/operations"' in complaint["frontend/src/App.tsx"]

    assert "backend/AssetInspectionManager.Api/Domain/Inspection.cs" in asset
    assert "ConditionScore" in asset["backend/AssetInspectionManager.Api/Domain/Inspection.cs"]
    assert 'path="/portfolio"' in asset["frontend/src/App.tsx"]


def test_non_leave_outputs_do_not_inherit_leave_domain_source() -> None:
    complaint = _file_map(1)
    asset = _file_map(2)

    complaint_text = "\n".join(complaint.values())
    asset_text = "\n".join(asset.values())
    assert "LeaveManagement" not in complaint_text
    assert "LeaveRequest" not in complaint_text
    assert "LeaveManagement" not in asset_text
    assert "LeaveRequest" not in asset_text
