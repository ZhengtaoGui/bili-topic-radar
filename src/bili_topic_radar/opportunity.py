from __future__ import annotations

import math
import re
from dataclasses import asdict
from typing import Any


METHOD_VERSION = "v0.3"

SPACE_SCORE = {"green": 100, "yellow": 55, "red": 5}
COMPETITION_SCORE = {"low": 100, "med": 65, "high": 30}
SATURATION_COMPETITION = {"green": "low", "yellow": "med", "red": "high"}
LIFECYCLE_FIT = {
    "爆发": {"green": 100, "yellow": 85, "red": 45},
    "上升": {"green": 95, "yellow": 75, "red": 35},
    "萌芽": {"green": 80, "yellow": 60, "red": 25},
    "饱和": {"green": 70, "yellow": 45, "red": 15},
    "衰退": {"green": 45, "yellow": 25, "red": 5},
    "谨慎观察": {"green": 65, "yellow": 45, "red": 20},
}


def evaluate(pack: dict[str, Any] | object, analysis: dict[str, Any] | object, now=None) -> dict[str, Any]:
    del now
    pack_data = _to_dict(pack)
    analysis_data = _to_dict(analysis)

    factors = _score_factors(pack_data, analysis_data)
    score = round(
        0.30 * factors["freshness"]
        + 0.25 * factors["headroom"]
        + 0.25 * factors["angle_vacancy"]
        + 0.20 * factors["real_demand"]
    )
    lifecycle = _lifecycle(pack_data)
    return {
        "score": int(_clamp(score, 0, 100)),
        "label": _score_label(score),
        "factors": factors,
        "lifecycle": lifecycle,
        "ranked_angles": _ranked_angles(analysis_data, lifecycle["stage"]),
        "method_version": METHOD_VERSION,
    }


def merge_result(
    pack: dict[str, Any] | object,
    analysis: dict[str, Any] | object,
    now=None,
) -> dict[str, Any]:
    result = _to_dict(analysis)
    result["opportunity_window"] = evaluate(pack, analysis, now=now)
    return result


def _score_factors(pack: dict[str, Any], analysis: dict[str, Any]) -> dict[str, int]:
    near_90d_ratio = _number(pack.get("near_90d_ratio"))
    top3_play_share = _number(pack.get("top3_play_share"))
    angles = _list(analysis.get("angles"))
    green_count = sum(1 for item in angles if _saturation(item) == "green")
    yellow_count = sum(1 for item in angles if _saturation(item) == "yellow")
    gap_count = len(_list(analysis.get("gaps")))
    return {
        "freshness": round(100 * _clamp((near_90d_ratio - 0.15) / 0.50, 0, 1)),
        "headroom": round(100 * _clamp((0.75 - top3_play_share) / 0.40, 0, 1)),
        "angle_vacancy": round(100 * _clamp((green_count + 0.5 * yellow_count) / 3, 0, 1)),
        "real_demand": round(100 * _clamp(gap_count / 3, 0, 1)),
    }


def _score_label(score: int | float) -> str:
    if score >= 80:
        return "强窗口"
    if score >= 60:
        return "可做"
    if score >= 40:
        return "谨慎做"
    return "不建议"


def _lifecycle(pack: dict[str, Any]) -> dict[str, Any]:
    videos = _valid_top25_videos(pack)
    total_count = len(videos)
    total_play = sum(_play(video) for video in videos)
    recent_30 = [video for video in videos if 0 <= _age_days(video) <= 30]
    recent_90 = [video for video in videos if 0 <= _age_days(video) <= 90]
    old_180 = [video for video in videos if _age_days(video) >= 180]

    metrics = {
        "top25_valid_count": total_count,
        "top25_recent_30_ratio": _safe_ratio(len(recent_30), total_count),
        "top25_recent_90_ratio": _safe_ratio(len(recent_90), total_count),
        "top25_recent_90_play_share": _safe_ratio(sum(_play(video) for video in recent_90), total_play),
        "top25_old_180_play_share": _safe_ratio(sum(_play(video) for video in old_180), total_play),
    }

    stage, reason = _lifecycle_stage(metrics)
    return {"stage": stage, "reason": reason, "metrics": metrics}


def _lifecycle_stage(metrics: dict[str, float | int]) -> tuple[str, str]:
    valid_count = int(metrics["top25_valid_count"])
    recent_30_ratio = float(metrics["top25_recent_30_ratio"])
    recent_90_ratio = float(metrics["top25_recent_90_ratio"])
    recent_90_play_share = float(metrics["top25_recent_90_play_share"])
    old_180_play_share = float(metrics["top25_old_180_play_share"])

    if valid_count == 0:
        return "谨慎观察", "有效发布日期太少,先别只靠时机判断。"
    if old_180_play_share >= 0.70 and recent_90_ratio <= 0.25:
        return "衰退", "老视频吃掉主要播放,近90天新内容占比低。"
    if recent_30_ratio >= 0.30 and recent_90_play_share >= 0.50:
        return "爆发", "近30天密集出新,近90天视频也拿到主要播放。"
    if valid_count <= 8 and recent_90_ratio >= 0.50 and old_180_play_share < 0.25:
        return "萌芽", "样本还少但新视频占比高,题目刚开始长出来。"
    if recent_90_ratio >= 0.45 and recent_90_play_share >= 0.35:
        return "上升", "近90天仍在持续出新,新视频能分到播放。"
    if old_180_play_share >= 0.55:
        return "饱和", "老头部视频占位明显,新内容进入成本偏高。"
    return "谨慎观察", "新旧内容信号混合,窗口还需要结合角度空缺看。"


def _ranked_angles(analysis: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    angles = [item for item in _list(analysis.get("angles")) if isinstance(item, dict)]
    gaps = [item for item in _list(analysis.get("gaps")) if isinstance(item, dict)]
    proposals = [item for item in _list(analysis.get("proposals")) if isinstance(item, dict)]
    source_items = proposals if proposals else angles
    ranked = []

    for item in source_items:
        angle = _match_angle(item, angles) if proposals else item
        saturation = _saturation(angle)
        competition = _competition(item, saturation)
        demand_count = _associated_demand_count(item, angle, gaps)
        space_score = SPACE_SCORE.get(saturation, 5)
        demand_score = 100 if demand_count >= 2 else 70 if demand_count == 1 else 20
        competition_score = COMPETITION_SCORE.get(competition, 30)
        lifecycle_fit = LIFECYCLE_FIT.get(stage, LIFECYCLE_FIT["谨慎观察"]).get(saturation, 20)
        score = round(
            0.35 * space_score
            + 0.25 * demand_score
            + 0.20 * competition_score
            + 0.20 * lifecycle_fit
        )
        name = str((angle or {}).get("name") or item.get("angle") or item.get("name") or "")
        ranked.append(
            {
                "name": name,
                "score": int(_clamp(score, 0, 100)),
                "saturation": saturation,
                "proposal_title": str(item.get("title") or ""),
                "why_now": str(item.get("why") or (angle or {}).get("reason") or ""),
                "risk": str(item.get("risk") or ""),
            }
        )

    ranked.sort(key=lambda row: (-int(row["score"]), _saturation_order(str(row["saturation"])), row["name"]))
    for index, row in enumerate(ranked[:5], start=1):
        row["rank"] = index
    return ranked[:5]


def _match_angle(item: dict[str, Any], angles: list[dict[str, Any]]) -> dict[str, Any]:
    if not angles:
        return {}
    target = _norm_text(item.get("angle") or item.get("title") or item.get("name"))
    if not target:
        return angles[0]

    best = angles[0]
    best_score = -1.0
    for angle in angles:
        name = _norm_text(angle.get("name"))
        if not name:
            score = 0.0
        elif name == target:
            score = 1.0
        elif name in target or target in name:
            score = 0.9
        else:
            score = _char_jaccard(name, target)
        if score > best_score:
            best = angle
            best_score = score
    return best


def _associated_demand_count(
    item: dict[str, Any],
    angle: dict[str, Any] | None,
    gaps: list[dict[str, Any]],
) -> int:
    haystack = _norm_text(
        " ".join(
            str(part or "")
            for part in (
                item.get("title"),
                item.get("angle"),
                item.get("why"),
                (angle or {}).get("name"),
                (angle or {}).get("reason"),
            )
        )
    )
    if not haystack:
        return 0

    count = 0
    for gap in gaps:
        need = _norm_text(gap.get("need"))
        quote = _norm_text(gap.get("evidence_quote"))
        if not need and not quote:
            continue
        if (need and need in haystack) or (quote and quote in haystack):
            count += 1
        elif need and _char_jaccard(need, haystack) >= 0.32:
            count += 1
    return count


def _valid_top25_videos(pack: dict[str, Any]) -> list[dict[str, Any]]:
    videos = []
    for item in _list(pack.get("videos"))[:25]:
        if not isinstance(item, dict):
            continue
        age_days = item.get("age_days")
        pubdate = _number(item.get("pubdate"))
        if pubdate <= 0 or age_days is None:
            continue
        age = _number(age_days)
        if not math.isfinite(age) or age < 0:
            continue
        videos.append(item)
    return videos


def _competition(item: dict[str, Any], saturation: str) -> str:
    raw = str(item.get("competition") or "").strip().lower()
    if raw in COMPETITION_SCORE:
        return raw
    return SATURATION_COMPETITION.get(saturation, "high")


def _saturation(item: object) -> str:
    if not isinstance(item, dict):
        return "red"
    value = str(item.get("saturation") or "").strip().lower()
    return value if value in SPACE_SCORE else "red"


def _saturation_order(value: str) -> int:
    return {"green": 0, "yellow": 1, "red": 2}.get(value, 3)


def _play(video: dict[str, Any]) -> int:
    return max(0, round(_number(video.get("play"))))


def _age_days(video: dict[str, Any]) -> int:
    return round(_number(video.get("age_days")))


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    denominator = _number(denominator)
    if denominator <= 0:
        return 0.0
    return _clamp(_number(numerator) / denominator, 0, 1)


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _clamp(value: int | float, lower: int | float, upper: int | float) -> float:
    number = _number(value)
    return min(max(number, lower), upper)


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _to_dict(value: dict[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        if isinstance(data, dict):
            return data
    try:
        data = asdict(value)
    except TypeError:
        data = None
    if isinstance(data, dict):
        return data
    raise TypeError(f"unsupported opportunity input: {type(value)!r}")


def _norm_text(value: object) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def _char_jaccard(left: str, right: str) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)
