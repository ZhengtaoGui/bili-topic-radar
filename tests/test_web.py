from __future__ import annotations

from starlette.testclient import TestClient

from bili_topic_radar import collect
from bili_topic_radar.models import Comment, VideoCard
from bili_topic_radar.web import app


class FakeClient:
    async def search_topic(self, keyword: str, limit: int = 30) -> list[VideoCard]:
        del limit
        return [
            VideoCard(
                bvid="BVweb1000000",
                title=f"{keyword} demo",
                desc="",
                play=1234,
                danmaku=8,
                like=99,
                duration=180,
                pubdate=1_700_000_000,
                author="demo-up",
                mid=42,
            )
        ]

    async def get_video_hot_comments(self, bvid: str, limit: int = 20) -> list[Comment]:
        return [
            Comment(
                message=f"hot comment for {bvid}",
                like=77,
                ctime=1_700_000_100,
                uname="viewer",
            )
        ]


def test_web_index_returns_html() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "B站选题撞车雷达" in response.text
    assert "选题关键词" in response.text
    assert "怎么用这个雷达?" in response.text
    assert "不做 AI 判断" in response.text


def test_api_collect_returns_evidence_pack_with_mock_client(monkeypatch) -> None:
    monkeypatch.setattr(collect, "BilibiliClient", FakeClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/collect",
            json={
                "keyword": "MCP",
                "extra_queries": ["MCP 实战"],
                "top_comments": 1,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["keyword"] == "MCP"
    assert data["queries"] == ["MCP", "MCP 实战"]
    assert data["total_unique_videos"] == 1
    assert data["videos"][0]["bvid"] == "BVweb1000000"
    assert data["comments_by_bvid"]["BVweb1000000"][0]["message"] == "hot comment for BVweb1000000"


def test_api_evidence_reads_existing_demo_file() -> None:
    with TestClient(app) as client:
        response = client.get("/api/evidence?file=evidence_mcp.json")

    assert response.status_code == 200
    data = response.json()
    assert data["keyword"] == "MCP"
    assert data["total_unique_videos"] > 0
