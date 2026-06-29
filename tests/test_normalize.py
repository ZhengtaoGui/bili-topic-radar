from bili_topic_radar.normalize import clean_text, normalize_comment, normalize_video_card, parse_count, parse_duration


def test_parse_count_chinese_units() -> None:
    assert parse_count("1.2万") == 12000
    assert parse_count("3亿") == 300000000
    assert parse_count("4,321") == 4321
    assert parse_count("--") == 0


def test_normalize_video_card_search_shape() -> None:
    raw = {
        "bvid": "BV1xx411c7mD",
        "title": "<em class=\"keyword\">MCP</em> 入门",
        "description": "A &amp; B",
        "play": "1.2万",
        "video_review": "345",
        "duration": "03:21",
        "pubdate": 1710000000,
        "author": "测试UP",
        "mid": "42",
    }

    card = normalize_video_card(raw)

    assert card.title == "MCP 入门"
    assert card.desc == "A & B"
    assert card.play == 12000
    assert card.danmaku == 345
    assert card.duration == 201
    assert card.mid == 42


def test_normalize_comment_reply_shape() -> None:
    raw = {
        "content": {"message": "求一个端到端 demo"},
        "like": "1.5万",
        "ctime": 1710000000,
        "member": {"uname": "观众"},
    }

    comment = normalize_comment(raw)

    assert clean_text(comment.message) == "求一个端到端 demo"
    assert comment.like == 15000
    assert comment.uname == "观众"
