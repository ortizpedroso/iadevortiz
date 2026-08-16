from pkf.workflow.tasks import TaskTracker


def test_task_tracker_build_tree(tmp_path):
    tracker = TaskTracker(tmp_path)
    tracker.reset_for_build("demo-spec", ["frontend", "backend"])
    data = tracker.to_list()
    assert data
    assert data[0]["id"] == "T1"
    assert any(c["id"] == "T2" for c in data[0]["children"])
