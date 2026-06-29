from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Sequence

from .client import BilibiliClient
from .models import Comment, VideoCard

SECONDS_PER_DAY = 86_400
NEAR_90D_DAYS = 90


@dataclass(slots=True)
class EvidenceVideo:
    bvid: str
    title: str
    desc: str
    play: int
    danmaku: int
    like: int | None
    duration: int
    pubdate: int
    author: str
    mid: int | None
    queries_hit: list[str]
    age_days: int | None

    @classmethod
    def from_video(cls, video: VideoCard, queries_hit: list[str], now_ts: int) -> "EvidenceVideo":
        return cls(
            **video.to_dict(),
            queries_hit=queries_hit,
            age_days=_age_days(video.pubdate, now_ts),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class EvidencePack:
    keyword: str
    extra_queries: list[str]
    queries: list[str]
    collected_at: int
    total_unique_videos: int
    near_90d_count: int
    near_90d_ratio: float
    top3_play_share: float
    max_play: int
    median_play: float
    videos: list[EvidenceVideo]
    comments_by_bvid: dict[str, list[Comment]]

    def to_dict(self) -> dict[str, object]:
        return {
            "keyword": self.keyword,
            "extra_queries": self.extra_queries,
            "queries": self.queries,
            "collected_at": self.collected_at,
            "total_unique_videos": self.total_unique_videos,
            "near_90d_count": self.near_90d_count,
            "near_90d_ratio": self.near_90d_ratio,
            "top3_play_share": self.top3_play_share,
            "max_play": self.max_play,
            "median_play": self.median_play,
            "videos": [video.to_dict() for video in self.videos],
            "comments_by_bvid": {
                bvid: [comment.to_dict() for comment in comments]
                for bvid, comments in self.comments_by_bvid.items()
            },
        }


async def collect_evidence(
    keyword: str,
    extra_queries: Sequence[str] | None = None,
    top_comments: int = 12,
    now: int | float | datetime | None = None,
) -> EvidencePack:
    now_ts = _timestamp(now)
    queries = _build_queries(keyword, extra_queries)
    client = BilibiliClient()

    videos_by_bvid: dict[str, VideoCard] = {}
    queries_by_bvid: dict[str, list[str]] = {}
    for query in queries:
        results = await client.search_topic(query)
        for video in results:
            if not video.bvid:
                continue
            if video.bvid not in videos_by_bvid:
                videos_by_bvid[video.bvid] = video
                queries_by_bvid[video.bvid] = []
            elif video.play > videos_by_bvid[video.bvid].play:
                videos_by_bvid[video.bvid] = video
            if query not in queries_by_bvid[video.bvid]:
                queries_by_bvid[video.bvid].append(query)

    sorted_videos = sorted(videos_by_bvid.values(), key=lambda video: video.play, reverse=True)
    evidence_videos = [
        EvidenceVideo.from_video(video, queries_by_bvid[video.bvid], now_ts)
        for video in sorted_videos
    ]

    comment_video_limit = max(0, top_comments)
    comments_by_bvid: dict[str, list[Comment]] = {}
    skipped = 0
    for video in sorted_videos[:comment_video_limit]:
        # Search can return non-standard cards (ads / 课堂 / 番剧) whose bvid
        # is malformed; a single bad video must not abort the whole run.
        if not _looks_like_bvid(video.bvid):
            skipped += 1
            continue
        try:
            comments_by_bvid[video.bvid] = await client.get_video_hot_comments(
                video.bvid,
                limit=max(1, top_comments),
            )
        except Exception:
            skipped += 1
            continue
    if skipped:
        print(f"[collect] skipped {skipped} video(s) with bad bvid / comment errors")

    stats = _mechanical_stats(evidence_videos)
    return EvidencePack(
        keyword=queries[0],
        extra_queries=queries[1:],
        queries=queries,
        collected_at=now_ts,
        videos=evidence_videos,
        comments_by_bvid=comments_by_bvid,
        **stats,
    )


_BVID_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")


def _looks_like_bvid(bvid: str) -> bool:
    return bool(bvid) and bool(_BVID_RE.match(bvid))


def _build_queries(keyword: str, extra_queries: Sequence[str] | None) -> list[str]:
    queries: list[str] = []
    for query in [keyword, *(extra_queries or [])]:
        cleaned = query.strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    if not queries:
        raise ValueError("keyword must not be empty")
    return queries


def _timestamp(value: int | float | datetime | None) -> int:
    if value is None:
        return int(time.time())
    if isinstance(value, datetime):
        return int(value.timestamp())
    return int(value)


def _age_days(pubdate: int, now_ts: int) -> int | None:
    if pubdate <= 0:
        return None
    return int((now_ts - pubdate) // SECONDS_PER_DAY)


def _mechanical_stats(videos: list[EvidenceVideo]) -> dict[str, int | float]:
    plays = [video.play for video in videos]
    total_unique_videos = len(videos)
    near_90d_count = sum(
        1
        for video in videos
        if video.age_days is not None and 0 <= video.age_days <= NEAR_90D_DAYS
    )
    total_play = sum(plays)
    return {
        "total_unique_videos": total_unique_videos,
        "near_90d_count": near_90d_count,
        "near_90d_ratio": near_90d_count / total_unique_videos if total_unique_videos else 0.0,
        "top3_play_share": sum(plays[:3]) / total_play if total_play else 0.0,
        "max_play": max(plays) if plays else 0,
        "median_play": float(median(plays)) if plays else 0.0,
    }


def _summary(pack: EvidencePack) -> str:
    commented_videos = len(pack.comments_by_bvid)
    total_comments = sum(len(comments) for comments in pack.comments_by_bvid.values())
    return "\n".join(
        [
            f"queries: {len(pack.queries)}",
            f"total_unique_videos: {pack.total_unique_videos}",
            f"near_90d_count: {pack.near_90d_count}",
            f"near_90d_ratio: {pack.near_90d_ratio:.3f}",
            f"top3_play_share: {pack.top3_play_share:.3f}",
            f"max_play: {pack.max_play}",
            f"median_play: {pack.median_play:g}",
            f"commented_videos: {commented_videos}",
            f"total_comments: {total_comments}",
        ]
    )


async def _amain(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect a reproducible Bilibili topic evidence pack.")
    parser.add_argument("keyword")
    parser.add_argument("--extra", nargs="*", default=None, help="Extra search queries.")
    parser.add_argument("--top-comments", type=int, default=12)
    parser.add_argument("--out", type=Path, default=Path("evidence.json"))
    args = parser.parse_args(argv)

    pack = await collect_evidence(
        args.keyword,
        extra_queries=args.extra,
        top_comments=args.top_comments,
    )
    args.out.write_text(
        json.dumps(pack.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(_summary(pack))
    print(f"wrote: {args.out}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
