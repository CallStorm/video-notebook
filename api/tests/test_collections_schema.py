from app.db.base import Base
from app.models.collection import Collection, CollectionNotebook  # noqa: F401


def test_collection_tables_exist():
    names = set(Base.metadata.tables)
    assert {"collections", "collection_notebooks"} <= names
    cols = Base.metadata.tables["collections"].c
    assert {"id", "owner_id", "name", "icon"} <= {c.name for c in cols}
    link = Base.metadata.tables["collection_notebooks"].c
    assert {"collection_id", "notebook_id", "added_at"} <= {c.name for c in link}
