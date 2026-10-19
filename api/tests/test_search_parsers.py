"""离线解析：B 站 API 映射 + 抖音 Bing HTML。"""
from __future__ import annotations

from app.search.bilibili import _map_row
from app.search.douyin import _parse_bing_html


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


def test_douyin_parse_bing_html_dedupes() -> None:
    html = """
    <a href="https://www.douyin.com/video/7123456789012345678">clip</a>
    <script>"https:\\/\\/www.douyin.com\\/video\\/7123456789012345678"</script>
    <a href="https://www.douyin.com/video/7987654321098765432" title="第二支视频标题够长">x</a>
    """
    items = _parse_bing_html(html, limit=10)
    assert len(items) == 2
    assert items[0].platform == "douyin"
    assert "7123456789012345678" in items[0].url
