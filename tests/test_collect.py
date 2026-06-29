from __future__ import annotations

from bili_topic_radar import collect
from bili_topic_radar.models import Comment, VideoCard

# bvids must match the real ^BV[0-9A-Za-z]{10}$ format — collect.py skips
# malformed ids (e.g. numeric course-card ids) before fetching comments.


def _video(bvid: str, play: int, pubdate: int) -> VideoCard:
    return VideoCard(
        bvid=bvid,
        title=f"title {bvid}",
        desc="",
        play=play,
        danmaku=0,
        like=None,
        duration=0,
        pubdate=pubdate,
        author="up",
        mid=1,
    )


class FakeClient:
    def __init__(self) -> None:
        self.comment_calls: list[tuple[str, int]] = []

    async def search_topic(self, keyword: str, limit: int = 30) -> list[VideoCard]:
        del limit
        now = 1_700_000_000
        results = {
            "MCP": [
                _video("BVold1000000", 300, now - 100 * collect.SECONDS_PER_DAY),
                _video("BVlow1000000", 100, now - 10 * collect.SECONDS_PER_DAY),
            ],
            "MCP教程": [
                _video("BVold1000000", 300, now - 100 * collect.SECONDS_PER_DAY),
                _video("BVmid1000000", 600, now - 20 * collect.SECONDS_PER_DAY),
            ],
            "MCP实战": [
                _video("BVtop1000000", 1000, now - 5 * collect.SECONDS_PER_DAY),
            ],
        }
        return results[keyword]

    async def get_video_hot_comments(self, bvid: str, limit: int = 20) -> list[Comment]:
        self.comment_calls.append((bvid, limit))
        return [Comment(message=f"comment {bvid}", like=1, ctime=0, uname="viewer")]


async def test_collect_evidence_dedupes_queries_and_stats(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(collect, "BilibiliClient", lambda: fake_client)

    pack = await collect.collect_evidence(
        "MCP",
        extra_queries=["MCP教程", "MCP实战"],
        top_comments=2,
        now=1_700_000_000,
    )

    assert pack.total_unique_videos == 4
    assert pack.near_90d_count == 3
    assert pack.near_90d_ratio == 0.75
    assert pack.top3_play_share == 0.95
    assert pack.max_play == 1000
    assert pack.median_play == 450.0
    assert [video.bvid for video in pack.videos] == ["BVtop1000000", "BVmid1000000", "BVold1000000", "BVlow1000000"]

    old_video = next(video for video in pack.videos if video.bvid == "BVold1000000")
    assert old_video.queries_hit == ["MCP", "MCP教程"]
    assert old_video.play == 300
    assert old_video.age_days == 100

    assert list(pack.comments_by_bvid) == ["BVtop1000000", "BVmid1000000"]
    assert fake_client.comment_calls == [("BVtop1000000", 2), ("BVmid1000000", 2)]


async def test_collect_evidence_to_dict_is_json_ready(monkeypatch) -> None:
    fake_client = FakeClient()
    monkeypatch.setattr(collect, "BilibiliClient", lambda: fake_client)

    pack = await collect.collect_evidence("MCP", top_comments=1, now=1_700_000_000)
    data = pack.to_dict()

    assert data["queries"] == ["MCP"]
    assert data["videos"][0]["queries_hit"] == ["MCP"]
    assert data["videos"][0]["age_days"] == 100
    assert list(data["comments_by_bvid"]) == ["BVold1000000"]
