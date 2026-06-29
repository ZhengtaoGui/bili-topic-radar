from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class VideoCard:
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class Comment:
    message: str
    like: int
    ctime: int
    uname: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
