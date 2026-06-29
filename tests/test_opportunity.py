from __future__ import annotations

from bili_topic_radar import opportunity


def _video(age_days: int | None, play: int = 100, pubdate: int = 1_700_000_000) -> dict[str, object]:
    return {
        "bvid": f"BV{age_days}{play}",
        "title": "demo",
        "play": play,
        "pubdate": pubdate,
        "age_days": age_days,
    }


def _pack(videos: list[dict[str, object]] | None = None, **stats) -> dict[str, object]:
    data: dict[str, object] = {
        "keyword": "MCP",
        "near_90d_ratio": 0.0,
        "top3_play_share": 0.0,
        "videos": videos if videos is not None else [],
    }
    data.update(stats)
    return data


def _analysis(**extra) -> dict[str, object]:
    data: dict[str, object] = {
        "angles": [],
        "gaps": [],
        "proposals": [],
    }
    data.update(extra)
    return data


def test_score_formula_factors_and_label() -> None:
    result = opportunity.evaluate(
        _pack(near_90d_ratio=0.65, top3_play_share=0.35),
        _analysis(
            angles=[
                {"name": "实战", "saturation": "green", "reason": ""},
                {"name": "避坑", "saturation": "yellow", "reason": ""},
                {"name": "入门", "saturation": "red", "reason": ""},
            ],
            gaps=[
                {"need": "案例", "evidence_quote": "", "evidence_likes": 1, "source_title": ""},
                {"need": "避坑", "evidence_quote": "", "evidence_likes": 1, "source_title": ""},
            ],
        ),
    )

    assert result["factors"] == {
        "freshness": 100,
        "headroom": 100,
        "angle_vacancy": 50,
        "real_demand": 67,
    }
    assert result["score"] == 81
    assert result["label"] == "强窗口"
    assert result["method_version"] == "v0.3"


def test_lifecycle_decline_burst_nascent_rising_saturated_default() -> None:
    cases = [
        ("衰退", [_video(220, 100) for _ in range(8)] + [_video(120, 50) for _ in range(2)]),
        ("爆发", [_video(10, 100) for _ in range(4)] + [_video(120, 40) for _ in range(6)]),
        ("萌芽", [_video(60, 100) for _ in range(4)] + [_video(120, 100) for _ in range(2)]),
        ("上升", [_video(60, 100) for _ in range(5)] + [_video(120, 100) for _ in range(5)]),
        ("饱和", [_video(220, 100) for _ in range(6)] + [_video(120, 70) for _ in range(4)]),
        ("谨慎观察", [_video(100, 100) for _ in range(7)] + [_video(220, 40) for _ in range(3)]),
    ]

    for expected_stage, videos in cases:
        result = opportunity.evaluate(_pack(videos), _analysis())
        assert result["lifecycle"]["stage"] == expected_stage


def test_lifecycle_skips_course_cards_without_pubdate_or_age() -> None:
    result = opportunity.evaluate(
        _pack(
            [
                _video(None, 10_000, pubdate=0),
                _video(12, 100),
                _video(200, 100),
            ]
        ),
        _analysis(),
    )

    metrics = result["lifecycle"]["metrics"]
    assert metrics["top25_valid_count"] == 2
    assert metrics["top25_recent_30_ratio"] == 0.5


def test_angle_ranking_uses_proposals_and_pushes_red_down() -> None:
    result = opportunity.evaluate(
        _pack([_video(60, 100) for _ in range(6)] + [_video(120, 100) for _ in range(4)]),
        _analysis(
            angles=[
                {"name": "入门科普", "saturation": "red", "reason": "挤爆了"},
                {"name": "项目实战", "saturation": "green", "reason": "还有空位"},
                {"name": "避坑排错", "saturation": "yellow", "reason": "有人做但不多"},
            ],
            gaps=[
                {"need": "真实案例", "evidence_quote": "想看真实案例", "evidence_likes": 10, "source_title": ""},
                {"need": "项目拆解", "evidence_quote": "求项目拆解", "evidence_likes": 8, "source_title": ""},
            ],
            proposals=[
                {
                    "title": "MCP 真实案例项目拆解",
                    "angle": "项目实战",
                    "why": "回应真实案例和项目拆解需求",
                    "audience": "",
                    "competition": "low",
                    "risk": "案例要可复现",
                },
                {
                    "title": "MCP 是什么",
                    "angle": "入门科普",
                    "why": "入门搜索量大",
                    "audience": "",
                    "competition": "low",
                    "risk": "红海",
                },
            ],
        ),
    )

    ranked = result["ranked_angles"]
    assert ranked[0]["name"] == "项目实战"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["score"] > ranked[1]["score"]
    assert ranked[1]["name"] == "入门科普"
    assert ranked[1]["saturation"] == "red"


def test_boundaries_clamp_and_empty_inputs_are_stable() -> None:
    result = opportunity.evaluate(
        _pack(near_90d_ratio=-1, top3_play_share=2),
        _analysis(angles=[{"name": "入门", "saturation": "red", "reason": ""}]),
    )

    assert result["score"] == 0
    assert result["label"] == "不建议"
    assert result["factors"]["freshness"] == 0
    assert result["factors"]["headroom"] == 0
    assert result["lifecycle"]["stage"] == "谨慎观察"
    assert result["ranked_angles"][0]["score"] < 30
