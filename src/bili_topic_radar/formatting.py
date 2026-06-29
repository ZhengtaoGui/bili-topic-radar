from __future__ import annotations

import json
from typing import Iterable

from .models import Comment, VideoCard


def videos_to_json(videos: Iterable[VideoCard]) -> str:
    return json.dumps([video.to_dict() for video in videos], ensure_ascii=False, indent=2)


def comments_to_json(comments: Iterable[Comment]) -> str:
    return json.dumps([comment.to_dict() for comment in comments], ensure_ascii=False, indent=2)


def videos_to_markdown(videos: Iterable[VideoCard]) -> str:
    rows = [
        "| BVID | 标题 | UP主 | 播放 | 弹幕 | 点赞 | 时长(s) | 发布 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for video in videos:
        rows.append(
            "| {bvid} | {title} | {author} | {play} | {danmaku} | {like} | {duration} | {pubdate} |".format(
                bvid=video.bvid,
                title=_escape_cell(video.title),
                author=_escape_cell(video.author),
                play=video.play,
                danmaku=video.danmaku,
                like="" if video.like is None else video.like,
                duration=video.duration,
                pubdate=video.pubdate,
            )
        )
    return "\n".join(rows)


def comments_to_markdown(comments: Iterable[Comment]) -> str:
    rows = ["| 点赞 | 时间 | 用户 | 评论 |", "|---:|---:|---|---|"]
    for comment in comments:
        rows.append(
            f"| {comment.like} | {comment.ctime} | {_escape_cell(comment.uname)} | {_escape_cell(comment.message)} |"
        )
    return "\n".join(rows)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
