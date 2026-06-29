from __future__ import annotations

import json

from starlette.testclient import TestClient

from bili_topic_radar import analyzer
from bili_topic_radar.web import app


def _fake_pack(video_count: int = 30) -> dict[str, object]:
    videos = []
    comments_by_bvid = {}
    for index in range(video_count):
        bvid = f"BVmock{index:04d}"
        videos.append(
            {
                "bvid": bvid,
                "title": f"video {index}",
                "desc": f"SECRET_DESC_{index}",
                "author": f"up {index}",
                "play": 1000 - index,
                "age_days": index,
                "queries_hit": ["MCP", "MCP 实战"],
            }
        )
        if index < 2:
            comments_by_bvid[bvid] = [
                {
                    "message": f"想看真实项目拆解 {index}",
                    "like": 100 + index,
                    "uname": "viewer",
                }
            ]
    return {
        "keyword": "MCP",
        "queries": ["MCP", "MCP 实战"],
        "total_unique_videos": video_count,
        "near_90d_ratio": 0.6,
        "top3_play_share": 0.4,
        "max_play": 1000,
        "median_play": 500,
        "videos": videos,
        "comments_by_bvid": comments_by_bvid,
    }


def _analysis_payload() -> dict[str, object]:
    return {
        "verdict": "reangle",
        "verdict_text": "别做泛入门,改做真实项目拆解。",
        "situation": "入门内容偏多,实战拆解仍有空间。",
        "timing": "近90天占比高,但头部垄断中等。",
        "angles": [
            {"name": "入门科普", "saturation": "red", "reason": "数量多且播放集中。"},
            {"name": "项目实战", "saturation": "green", "reason": "评论反复要案例。"},
        ],
        "gaps": [
            {
                "need": "真实项目拆解",
                "evidence_quote": "想看真实项目拆解 0",
                "evidence_likes": 100,
                "source_title": "video 0",
            }
        ],
        "proposals": [
            {
                "title": "用一个真实项目讲清 MCP 落地",
                "angle": "项目实战",
                "why": "填补评论里的案例需求",
                "audience": "已经知道概念但不会落地的人",
                "competition": "med",
                "risk": "需要真实可复现案例",
            }
        ],
        "caveats": ["样本来自搜索结果,可能有广词噪声。"],
    }


def test_analyze_evidence_parses_noisy_fenced_codex_output(monkeypatch) -> None:
    captured = {}

    def fake_run_codex(prompt: str, schema_path=None) -> str:
        captured["prompt"] = prompt
        del schema_path
        return "codex log\n```json\n" + json.dumps(_analysis_payload(), ensure_ascii=False) + "\n```\nbye"

    monkeypatch.setattr(analyzer, "_run_codex", fake_run_codex)

    result = analyzer.analyze_evidence(_fake_pack(), backend="codex")

    assert result.verdict == "reangle"
    assert result.backend == "codex"
    assert result.angles[1].name == "项目实战"
    assert result.gaps[0].evidence_likes == 100
    assert result.proposals[0].competition == "med"
    assert "SECRET_DESC" not in captured["prompt"]


def test_condense_evidence_drops_desc_truncates_videos_and_keeps_stats_comments() -> None:
    text = analyzer.condense_evidence(_fake_pack(30))

    assert "SECRET_DESC" not in text
    assert text.count('"title":') == 25
    assert '"title":"video 24"' in text
    assert '"title":"video 25"' not in text
    assert "total_unique_videos: 30" in text
    assert "near_90d_ratio: 0.6" in text
    assert "top3_play_share: 0.4" in text
    assert "想看真实项目拆解 0" in text
    assert '"source_title":"video 0"' in text


def test_api_analyze_returns_mock_result(monkeypatch) -> None:
    expected = analyzer.AnalysisResult(
        verdict="do",
        verdict_text="可以做,切项目实战。",
        situation="仍有实战缺口。",
        timing="窗口期尚可。",
        angles=[analyzer.AngleBucket(name="项目实战", saturation="green", reason="供给少。")],
        gaps=[
            analyzer.CommentGap(
                need="案例",
                evidence_quote="想看真实项目拆解 0",
                evidence_likes=100,
                source_title="video 0",
            )
        ],
        proposals=[],
        caveats=["离线 mock。"],
        backend="codex",
    )
    seen = {}

    def fake_analyze(pack, backend="codex", now=None):
        seen["pack"] = pack
        seen["backend"] = backend
        seen["now"] = now
        return expected

    monkeypatch.setattr(analyzer, "codex_available", lambda: True)
    monkeypatch.setattr(analyzer, "analyze_evidence", fake_analyze)

    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"pack": _fake_pack(1)})

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "do"
    assert data["angles"][0]["name"] == "项目实战"
    assert seen["pack"]["keyword"] == "MCP"
    assert seen["backend"] == "codex"


def test_api_analyze_returns_friendly_unavailable_when_codex_missing(monkeypatch) -> None:
    monkeypatch.setattr(analyzer, "codex_available", lambda: False)

    with TestClient(app) as client:
        response = client.post("/api/analyze", json={"pack": _fake_pack(1)})

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert "Codex CLI" in data["message"]
    assert "证据看板不受影响" in data["message"]
