from pathlib import Path
from uuid import uuid4

from software_factory.persistence import DatabaseRunStore


def test_run_store_persists_status_and_audit(tmp_path: Path) -> None:
    store = DatabaseRunStore(f"sqlite:///{tmp_path / 'factory.db'}")
    store.initialize()
    project_id = uuid4()
    store.start_run(project_id, "Build a governed example application for a persistence test")
    store.append_event(project_id, "planner", "plan.created", {"task_count": 3})

    run = store.get_run(project_id)
    events = store.list_events(project_id)

    assert run is not None and run.status == "running"
    assert [event.event_type for event in events] == ["run.started", "plan.created"]
    assert events[1].payload == {"task_count": 3}
