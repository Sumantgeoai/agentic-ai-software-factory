from software_factory.project_model import EnterpriseProjectModel
from software_factory.scenario_fixtures import SCENARIOS, scenario_for_request


def test_project_names_are_derived_from_each_scenario() -> None:
    models = [
        EnterpriseProjectModel.from_spec(item.requirements, item.application_spec)
        for item in SCENARIOS
    ]

    assert [model.api_project for model in models] == [
        "LeaveManagement.Api",
        "CitizenComplaintPortal.Api",
        "AssetInspectionManager.Api",
    ]
    assert [model.frontend_package for model in models] == [
        "leave-management-web",
        "citizen-complaint-portal-web",
        "asset-inspection-manager-web",
    ]
    assert len({model.root_namespace for model in models}) == 3


def test_fixture_scenarios_are_independent_application_specs() -> None:
    leave, complaint, asset = SCENARIOS

    assert leave.application_spec.entities[0].name == "LeaveRequest"
    assert complaint.application_spec.entities[0].name == "Complaint"
    assert asset.application_spec.entities[0].name == "Inspection"
    assert {role.name for role in complaint.application_spec.roles} == {
        "citizen",
        "officer",
        "supervisor",
    }
    assert {page.route for page in asset.application_spec.pages} >= {
        "/inspections",
        "/review",
        "/portfolio",
    }


def test_scenario_selection_is_only_a_fixture_concern() -> None:
    assert scenario_for_request("Build a citizen complaint portal").key == "complaint"
    assert scenario_for_request("Create an asset inspection workflow").key == "asset"
    assert scenario_for_request("Build leave management").key == "leave"
