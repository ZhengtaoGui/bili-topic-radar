from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


AI_PROMPT = """你是一个懂行的老朋友,帮一个普通 B站 UP 主判断这个选题该不该做。下面是同主题视频 + 高赞评论 + 几个数字。

**只输出一个 JSON 对象,不要任何额外文字,不要 markdown 代码围栏。**

【最重要:怎么说话】
- **说人话**。能用大白话就别用术语。别写"可靠性审计、供应链风险、选型、显性需求、生态、赋能"这种词。万一非用一个专业词(比如 FastMCP),顺手一句话说清它是啥。
- **短,删废话**。每个字段一两句话说完,把套话、铺垫、"综上所述"全删掉。能 10 个字说清就别用 20 个字。
- **直接**。先说能不能做、做哪个,再说为啥。别绕弯子。
- **像朋友聊天**,用"你""观众""别做""可以做""趁早"这种口吻,不要像写商业报告。

【怎么判断】
1. 先把明显跑题的视频剔掉(广词搜出来的无关货,比如主题不符、纯英文同名、卖课的课程卡),在 caveats 里用一句话说剔了啥。只看真正相关的。
2. 角度地图:把相关视频按"怎么切的"分类(入门、配置教程、实战、踩坑避雷、对比、讲原理…按实际叫法)。每类标:red=挤爆了、yellow=有人做但旧或不强、green=没人做。每类配一句大白话理由。
3. 观众真正想要啥(这步最容易判错,你要当个怀疑论者):挖的是"真能做成一期视频的内容需求"。**一条评论赞再高,也不等于真需求。** 先把下面这些噪声坚决过滤掉,绝不当缺口:
   - 玩梗/打趣/接龙/黑话(比如"给心心""AI识片酱"这类纯玩梗,不是想看的内容)
   - 吐槽/抱怨/感慨/说教(比如骂风气、抒情、阴阳怪气,他们没在说想看啥)
   - 求资源/求获取/问"怎么过审"(这不是选题方向,而且别去满足它,直接忽略)
   - 搜索带偏的吐槽、跑题、纯夸、纯骂、广告
   一个判断办法:把这条"需求"想象成一个视频标题——要是正经 UP 主根本做不出、或压根不该做,那它就不是缺口。
   剩下的才算:need 用一句大白话说观众到底想看啥(短),并摘真实评论原文(evidence_quote)+ 赞数(evidence_likes)+ 哪个视频下的(source_title),不许编。**宁缺毋滥**:要是评论翻来覆去都是玩梗和吐槽、挖不到真需求,gaps 就少给甚至给空数组,并在 caveats 里直说"评论大多是玩梗/吐槽,没挖到真实选题需求"。
4. 给 3 个能做的选题:每个写 title(标题方向,别教标题党)、angle(什么角度)、why(填哪个空、或踩中哪条真需求,一句话)、audience(给谁看)、competition(low/med/high)、risk(最大的坑,一句话)。**方案必须扎在第2步的真空缺或第3步的真需求上,别拿玩梗、吐槽、求资源当方案。** 要是这题真饱和又没空子、或评论里全是玩梗没真需求,就少给几个甚至不给,直接在 verdict 劝退——诚实劝退比硬凑强。
5. verdict:do(可以做)/reangle(别做原来那个角度、换一个)/delay(先放放)/drop(别做)。verdict_text 像朋友拍板那样一句话:做不做、做哪个、还来不来得及。
6. 不教标题党、不吹播放量,也不教怎么过审/规避平台审核,不把擦边、软色情、求资源当选题方向。时机看两点:近90天占比高=还在火;头部前三吃掉的播放占比高=大 UP 把流量占了、新人难出头。

严格输出这个 JSON 结构(字段都要有,列表可为空):
{
  "verdict": "do|reangle|delay|drop",
  "verdict_text": "一句中文结论",
  "situation": "态势结论一句话",
  "timing": "时机判断一句话",
  "angles": [{"name":"入门科普","saturation":"red|yellow|green","reason":"..."}],
  "gaps": [{"need":"...","evidence_quote":"评论原文","evidence_likes":123,"source_title":"来源视频标题"}],
  "proposals": [{"title":"...","angle":"...","why":"...","audience":"...","competition":"low|med|high","risk":"..."}],
  "caveats": ["剔除了哪些噪声/样本是否充足/..."]
}

证据如下:
```
{evidence}
```"""


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "verdict",
        "verdict_text",
        "situation",
        "timing",
        "angles",
        "gaps",
        "proposals",
        "caveats",
    ],
    "properties": {
        "verdict": {"type": "string", "enum": ["do", "reangle", "delay", "drop"]},
        "verdict_text": {"type": "string"},
        "situation": {"type": "string"},
        "timing": {"type": "string"},
        "angles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "saturation", "reason"],
                "properties": {
                    "name": {"type": "string"},
                    "saturation": {"type": "string", "enum": ["red", "yellow", "green"]},
                    "reason": {"type": "string"},
                },
            },
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["need", "evidence_quote", "evidence_likes", "source_title"],
                "properties": {
                    "need": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "evidence_likes": {"type": "integer"},
                    "source_title": {"type": "string"},
                },
            },
        },
        "proposals": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "angle", "why", "audience", "competition", "risk"],
                "properties": {
                    "title": {"type": "string"},
                    "angle": {"type": "string"},
                    "why": {"type": "string"},
                    "audience": {"type": "string"},
                    "competition": {"type": "string", "enum": ["low", "med", "high"]},
                    "risk": {"type": "string"},
                },
            },
        },
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
}

BACKENDS = ("codex", "claude", "openai-compatible")


@dataclass(slots=True)
class AngleBucket:
    name: str
    saturation: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class CommentGap:
    need: str
    evidence_quote: str
    evidence_likes: int
    source_title: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class Proposal:
    title: str
    angle: str
    why: str
    audience: str
    competition: str
    risk: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisResult:
    verdict: str
    verdict_text: str
    situation: str
    timing: str
    angles: list[AngleBucket]
    gaps: list[CommentGap]
    proposals: list[Proposal]
    caveats: list[str]
    backend: str

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "verdict_text": self.verdict_text,
            "situation": self.situation,
            "timing": self.timing,
            "angles": [angle.to_dict() for angle in self.angles],
            "gaps": [gap.to_dict() for gap in self.gaps],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "caveats": list(self.caveats),
            "backend": self.backend,
        }


def codex_available() -> bool:
    if shutil.which("codex") is None:
        return False
    try:
        completed = subprocess.run(
            ["codex", "login", "status"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def resolve_backend(requested=None) -> str:
    backend = (requested or os.environ.get("BILI_RADAR_AI_BACKEND") or "codex").strip()
    if backend == "auto":
        backend = _auto_pick()
    if backend == "deepseek":
        backend = "openai-compatible"
    return backend


def _auto_pick() -> str:
    if codex_available():
        return "codex"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("OPENAI_API_KEY") and os.environ.get("BILI_RADAR_OPENAI_MODEL"):
        return "openai-compatible"
    return "codex"


def backend_status() -> list[dict[str, object]]:
    anthropic_sdk = importlib.util.find_spec("anthropic") is not None
    openai_sdk = importlib.util.find_spec("openai") is not None
    has_anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    has_openai_model = bool(os.environ.get("BILI_RADAR_OPENAI_MODEL"))
    codex_ok = codex_available()
    return [
        {
            "key": "codex",
            "label": "Codex(本地)",
            "available": codex_ok,
            "reason": "" if codex_ok else "请在本机安装并登录 Codex CLI",
        },
        {
            "key": "claude",
            "label": "Claude",
            "available": anthropic_sdk and has_anthropic_key,
            "reason": _missing_reason(
                [
                    (anthropic_sdk, "anthropic SDK"),
                    (has_anthropic_key, "ANTHROPIC_API_KEY"),
                ]
            ),
        },
        {
            "key": "openai-compatible",
            "label": "OpenAI 兼容",
            "available": openai_sdk and has_openai_key and has_openai_model,
            "reason": _missing_reason(
                [
                    (openai_sdk, "openai SDK"),
                    (has_openai_key, "OPENAI_API_KEY"),
                    (has_openai_model, "BILI_RADAR_OPENAI_MODEL"),
                ]
            ),
        },
    ]


def _missing_reason(checks: list[tuple[bool, str]]) -> str:
    missing = [name for ok, name in checks if not ok]
    return "" if not missing else "缺少 " + "、".join(missing)


def analyze_evidence(pack: dict[str, Any] | object, backend: str | None = None, now: object = None) -> AnalysisResult:
    backend = resolve_backend(backend)
    evidence = condense_evidence(pack, now=now)
    prompt = AI_PROMPT.replace("{evidence}", evidence)
    runners: dict[str, Callable[[str], str]] = {
        "codex": _run_codex,
        "claude": _run_claude,
        "openai-compatible": _run_openai_compatible,
    }
    if backend not in runners:
        raise ValueError(f"unsupported analyzer backend: {backend}")
    raw = runners[backend](prompt)
    data = _loads_first_json_object(raw)
    return _analysis_from_dict(data, backend=backend)


def condense_evidence(pack: dict[str, Any] | object, now: object = None) -> str:
    data = _pack_to_dict(pack)
    videos = list(data.get("videos") or [])[:25]
    comments_by_bvid = data.get("comments_by_bvid") or {}
    if not isinstance(comments_by_bvid, dict):
        comments_by_bvid = {}

    lines = [
        f"keyword: {data.get('keyword', '')}",
        f"queries: {', '.join(str(item) for item in data.get('queries') or [])}",
    ]
    if now is not None:
        lines.append(f"analysis_now: {now}")
    lines.extend(
        [
            "stats:",
            f"- total_unique_videos: {data.get('total_unique_videos', 0)}",
            f"- near_90d_ratio: {data.get('near_90d_ratio', 0)}",
            f"- top3_play_share: {data.get('top3_play_share', 0)}",
            f"- max_play: {data.get('max_play', 0)}",
            f"- median_play: {data.get('median_play', 0)}",
            "videos_top25:",
        ]
    )

    title_by_bvid: dict[str, str] = {}
    for index, video_obj in enumerate(videos, start=1):
        if not isinstance(video_obj, dict):
            continue
        bvid = str(video_obj.get("bvid") or "")
        title = str(video_obj.get("title") or "")
        title_by_bvid[bvid] = title
        queries_hit = video_obj.get("queries_hit") or []
        if not isinstance(queries_hit, list):
            queries_hit = [queries_hit]
        video = {
            "title": title,
            "author": video_obj.get("author"),
            "play": video_obj.get("play"),
            "age_days": video_obj.get("age_days"),
            "queries_hit": queries_hit,
        }
        lines.append(f"{index}. {json.dumps(video, ensure_ascii=False, separators=(',', ':'))}")

    lines.append("comments_by_bvid:")
    for bvid, comments_obj in comments_by_bvid.items():
        if not isinstance(comments_obj, list):
            continue
        source_title = title_by_bvid.get(str(bvid)) or _find_video_title(data, str(bvid))
        lines.append(f"- {bvid} / {source_title}")
        for comment_obj in comments_obj:
            if not isinstance(comment_obj, dict):
                continue
            comment = {
                "message": comment_obj.get("message", ""),
                "like": comment_obj.get("like", 0),
                "source_title": source_title,
            }
            lines.append(f"  - {json.dumps(comment, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines)


def _run_codex(prompt: str, schema_path: str | Path | None = None) -> str:
    out_path = None
    owned_schema_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as out_file:
            out_path = Path(out_file.name)

        if schema_path is None:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".schema.json", delete=False) as schema_file:
                json.dump(ANALYSIS_SCHEMA, schema_file, ensure_ascii=False, indent=2)
                owned_schema_path = Path(schema_file.name)
            schema_file_path = owned_schema_path
        else:
            schema_file_path = Path(schema_path)

        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "-s",
            "read-only",
            "-o",
            str(out_path),
            "--output-schema",
            str(schema_file_path),
            "-",
        ]
        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=240,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("codex exec timed out after 240s") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            reason = stderr or stdout or f"exit code {completed.returncode}"
            raise RuntimeError(f"codex exec failed: {reason}")
        return out_path.read_text(encoding="utf-8")
    finally:
        for path in (out_path, owned_schema_path):
            if path is not None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def _structured_schema() -> dict:
    # Claude/部分 OpenAI 结构化输出不支持数组长度/数值约束,递归剥掉
    import copy
    drop = {"maxItems", "minItems", "minimum", "maximum", "multipleOf", "minLength", "maxLength"}

    def clean(node):
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items() if k not in drop}
        if isinstance(node, list):
            return [clean(x) for x in node]
        return node

    return clean(copy.deepcopy(ANALYSIS_SCHEMA))


def _run_claude(prompt: str) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Claude 后端需要 anthropic SDK,请运行: uv sync --extra ai-claude"
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("Claude 后端需要环境变量 ANTHROPIC_API_KEY")
    model = os.environ.get("BILI_RADAR_CLAUDE_MODEL", "claude-opus-4-8")
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        output_config={"format": {"type": "json_schema", "schema": _structured_schema()}},
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
    )


def _run_openai_compatible(prompt: str) -> str:
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI 兼容后端需要 openai SDK,请运行: uv sync --extra ai-openai"
        ) from exc
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI 兼容后端需要环境变量 OPENAI_API_KEY")
    model = os.environ.get("BILI_RADAR_OPENAI_MODEL")
    if not model:
        raise RuntimeError(
            "请设置 BILI_RADAR_OPENAI_MODEL(如 gpt-4o / deepseek-chat / moonshot-v1-8k / glm-4)"
        )
    base_url = os.environ.get("BILI_RADAR_OPENAI_BASE_URL") or None  # 不填=OpenAI 官方
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    try:
        resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
    except Exception:
        # 个别兼容服务不支持 response_format,退回纯文本 + 健壮解析
        resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _loads_first_json_object(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{", cleaned)
    if not match:
        raise ValueError("AI output did not contain a JSON object")
    start = match.start()
    end = _find_json_object_end(cleaned, start)
    if end is None:
        raise ValueError("AI output contained an incomplete JSON object")
    snippet = cleaned[start:end]
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI output JSON parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("AI output JSON root must be an object")
    return data


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.IGNORECASE | re.DOTALL)
    if fence:
        return fence.group(1)
    return stripped


def _find_json_object_end(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _analysis_from_dict(data: dict[str, Any], backend: str) -> AnalysisResult:
    try:
        return AnalysisResult(
            verdict=str(data["verdict"]),
            verdict_text=str(data["verdict_text"]),
            situation=str(data["situation"]),
            timing=str(data["timing"]),
            angles=[
                AngleBucket(
                    name=str(item["name"]),
                    saturation=str(item["saturation"]),
                    reason=str(item["reason"]),
                )
                for item in _list(data.get("angles"))
                if isinstance(item, dict)
            ],
            gaps=[
                CommentGap(
                    need=str(item["need"]),
                    evidence_quote=str(item["evidence_quote"]),
                    evidence_likes=int(item["evidence_likes"]),
                    source_title=str(item["source_title"]),
                )
                for item in _list(data.get("gaps"))
                if isinstance(item, dict)
            ],
            proposals=[
                Proposal(
                    title=str(item["title"]),
                    angle=str(item["angle"]),
                    why=str(item["why"]),
                    audience=str(item["audience"]),
                    competition=str(item["competition"]),
                    risk=str(item["risk"]),
                )
                for item in _list(data.get("proposals"))
                if isinstance(item, dict)
            ],
            caveats=[str(item) for item in _list(data.get("caveats"))],
            backend=backend,
        )
    except KeyError as exc:
        raise ValueError(f"AI output missing required field: {exc.args[0]}") from exc


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _pack_to_dict(pack: dict[str, Any] | object) -> dict[str, Any]:
    if isinstance(pack, dict):
        return pack
    if hasattr(pack, "to_dict"):
        data = pack.to_dict()
        if isinstance(data, dict):
            return data
    raise TypeError(f"unsupported evidence pack: {type(pack)!r}")


def _find_video_title(data: dict[str, Any], bvid: str) -> str:
    for video in data.get("videos") or []:
        if isinstance(video, dict) and video.get("bvid") == bvid:
            return str(video.get("title") or "")
    return ""


def _amain(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a Bilibili topic evidence pack with local Codex.")
    parser.add_argument("evidence", type=Path, help="Path to evidence_*.json or another evidence pack JSON.")
    parser.add_argument("--backend", choices=["codex", "claude", "openai-compatible", "auto", "deepseek"])
    args = parser.parse_args(argv)

    pack = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = analyze_evidence(pack, backend=args.backend, now=int(time.time()))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(_amain())


if __name__ == "__main__":
    main()
