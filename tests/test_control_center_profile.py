from pathlib import Path


def test_control_center_sends_selected_target_profile() -> None:
    source = Path("apps/control-center/src/App.tsx").read_text(encoding="utf-8")

    assert 'useState<TargetProfile>("enterprise-dotnet-react")' in source
    assert 'value="enterprise-dotnet-react"' in source
    assert "JSON.stringify({ request, target_profile: targetProfile })" in source
