from datetime import datetime

from app.models.schemas import PlanTask, ProjectPlan, TaskStatus
from app.services.plan_manager import PlanManager


def test_render_and_parse_roundtrip(tmp_path):
    plan = ProjectPlan(
        project_name="demo",
        description="a demo project",
        architecture="modular",
        dependencies=["fastapi", "uvicorn"],
        tasks=[
            PlanTask(id="T01", title="Create main", file_path="app/main.py"),
            PlanTask(id="T02", title="Add tests", file_path="tests/test_x.py", depends_on=["T01"]),
        ],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    md = PlanManager.render(plan)
    assert "demo" in md
    assert "T01" in md and "T02" in md
    parsed = PlanManager.parse(md)
    assert parsed.project_name == "demo"
    ids = sorted(t.id for t in parsed.tasks)
    assert ids == ["T01", "T02"]
    assert all(t.status == TaskStatus.PENDING for t in parsed.tasks)
