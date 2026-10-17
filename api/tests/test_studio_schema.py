from app.db.base import Base
from app.models.studio import (  # noqa: F401
    Agent,
    Skill,
    StudioArtifact,
    StudioCapability,
    StudioTask,
)


def test_studio_tables_and_note_flag_exist():
    names = set(Base.metadata.tables)
    assert {
        "skills",
        "agents",
        "studio_capabilities",
        "studio_tasks",
        "studio_artifacts",
    } <= names
    assert "selected_for_chat" in Base.metadata.tables["notes"].c
    assert Base.metadata.tables["notes"].c.selected_for_chat.default.arg is True
