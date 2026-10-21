"""VectorStore factory + document hash."""
from __future__ import annotations

import pytest

from app.vector.store import VectorStoreError, make_vector_store


def test_make_vector_store_qdrant():
    store = make_vector_store(
        backend="qdrant",
        qdrant_url="http://127.0.0.1:6333",
        qdrant_collection="notebooks",
    )
    assert store is not None


def test_make_vector_store_pending_raises():
    with pytest.raises(VectorStoreError):
        make_vector_store(
            backend="pending",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection="notebooks",
        )
