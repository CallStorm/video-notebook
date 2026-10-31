"""离线解析：B 站 API 映射。"""
from __future__ import annotations

from app.search.bilibili import _map_row


def test_bilibili_map_row_strips_em_tags() -> None:
    item = _map_row(
        {
            "bvid": "BV1xx411c7mD",
            "title": "Hello <em class=\"keyword\">World</em>",
            "author": "up",
            "mid": 123,
            "play": 99,
            "duration": "1:02",
            "pic": "//i0.hdslb.com/bfs/archive/x.jpg",
            "description": "desc",
        }
    )
    assert item is not None
    assert item.id == "BV1xx411c7mD"
    assert item.title == "Hello World"
    assert item.duration == 62
    assert item.thumbnail and item.thumbnail.startswith("https:")
    assert item.uploader_url == "https://space.bilibili.com/123"
