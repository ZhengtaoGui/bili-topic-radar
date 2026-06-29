# AI 智能分析层设计稿(给 Codex 实现)

把"扫描后给建议和结论"用**真 AI 判断**实现。v1 后端 = **本地 Codex CLI(GPT-5)**,零 key 零花费。
做成可插拔(以后能切 Claude/DeepSeek API),但 v1 只实现 codex 后端。

Claude 负责提示词 + schema(下方);Codex 负责 analyzer.py 管道、/api/analyze 端点、前端渲染、离线 mock 测试。
**codex 真实调用的 live 验证由 Claude 做**(你的沙箱跑不了嵌套 codex,只写代码 + mock 测试)。

---

## 一、新增 `src/bili_topic_radar/analyzer.py`

### 1. 数据结构(dataclass + to_dict)

```python
@dataclass
class AngleBucket:      # 角度
    name: str
    saturation: str     # "red" | "yellow" | "green"
    reason: str

@dataclass
class CommentGap:       # 评论缺口(必须带证据)
    need: str
    evidence_quote: str
    evidence_likes: int
    source_title: str

@dataclass
class Proposal:         # 选题方案
    title: str
    angle: str
    why: str
    audience: str
    competition: str    # "low" | "med" | "high"
    risk: str

@dataclass
class AnalysisResult:
    verdict: str        # "do" | "reangle" | "delay" | "drop"
    verdict_text: str   # 中文一句话结论
    situation: str      # 态势结论一句话
    timing: str         # 时机判断
    angles: list[AngleBucket]
    gaps: list[CommentGap]
    proposals: list[Proposal]   # 0-3 个(可少于3甚至0=建议放弃)
    caveats: list[str]          # 数据可信度/噪声提示
    backend: str                # "codex" / "claude" / "deepseek"
```

### 2. `analyze_evidence(pack: dict, backend="codex", now=None) -> AnalysisResult`

流程:
1. **浓缩证据**(省 token):只取 keyword、queries、核心统计(total_unique_videos / near_90d_ratio / top3_play_share / max_play / median_play)、**前 25 个视频**(只留 title / author / play / age_days / queries_hit,**丢掉 desc**)、以及 comments_by_bvid(每条 message+like+来源视频 title)。拼成一段可读文本(不是原始大 JSON)。
2. 用下方【AI 提示词】+ 浓缩证据,组成完整 prompt。
3. 调后端拿到**纯 JSON 文本**,解析成 AnalysisResult。
4. 解析要健壮:从输出里**提取第一个完整 JSON 对象**(codex 可能夹杂日志/说明),用 `re` 找 `{...}` 或剥掉 ```json 围栏;失败则抛清晰错误。

### 3. codex 后端 `_run_codex(prompt, schema_path=None) -> str`

**Claude 已实测 `codex exec` 的确切用法,照这个写:**

- 用 `subprocess.run`,非交互、只读、可在非 git 目录跑:
  `codex exec --skip-git-repo-check -s read-only -o <out_file> --output-schema <schema_file> -` ,prompt 从 **stdin** 传入(避免超长参数/引号问题)。
- `--output-schema <schema_file>`:写一个**临时 JSON Schema 文件**(就是 §四 schema 的 JSON Schema 版,描述 AnalysisResult 的形状),codex 会让最终回复严格符合它 → 直接拿到干净 JSON。
- `-o <out_file>`:codex 把**最终消息**写到这个文件;我们读它,而不是 parse 嘈杂的 stdout。
- 设超时(如 240s);非 0 退出或超时抛带原因异常。
- 用 `tempfile` 建 out_file / schema_file,用完清理。
- 读 out_file 内容返回;analyzer 再做一层健壮 JSON 提取兜底(剥围栏/抓第一个 `{…}`)。

> 即便有 --output-schema,仍保留健壮解析兜底,以防 codex 版本差异。

> 可插拔:留 `_run_claude` / `_run_deepseek` 的 stub(`raise NotImplementedError("v2")`),`backend` 选择走字典分发。v1 只实现 codex。

### 4. CLI(便于 Claude 实测)

`python -m bili_topic_radar.analyze evidence_mcp.json` → 读证据包、跑分析、漂亮打印 AnalysisResult(JSON)。

---

## 二、Web 集成(web.py)

- 新增路由 `POST /api/analyze`:body `{file: "evidence_mcp.json"}` 或直接 `{pack: {...}}`。读/收证据包 → `analyze_evidence` → 返回 `to_dict()`。失败返回 `{error}`,前端可读。
- 这是**慢操作**(codex 要几十秒),前端要有 loading 态。
- 前端:在统计卡下方、视频表上方,加一块 **「🤖 AI 智能分析」** 卡:
  - 默认显示一个按钮「🤖 让 AI 给出建议和结论(用本地 GPT-5,约 30-60 秒)」。
  - 点击 → 调 `/api/analyze`(用当前已加载的 pack 的来源;示例用 file=evidence_xxx.json,扫描结果用 pack)。
  - 返回后渲染(深色科技风,沿用现有 token):
    - 顶部:**总判断徽章**(do=绿「✅建议做」/ reangle=琥珀「✏️改角度」/ delay=琥珀「⏳延后」/ drop=红「⛔放弃」)+ verdict_text。
    - 态势结论 situation、时机 timing。
    - 角度地图:每个 angle 一个带色点(red/yellow/green)的条目 + reason。
    - 观众缺口:每条 need + 引用块(「evidence_quote」👍 evidence_likes · 来源 source_title)。
    - 三方案:卡片(title / angle / why / 受众 / 竞争度 / 风险)。
    - 数据可信度:caveats 列表(灰色小字)。
  - 标注一行小字:本结论由 AI(本地 GPT-5)生成,仅供参考。

> 不改现有 /api/collect、/api/evidence 和数据契约;不引新依赖(subprocess 是标准库);test_web.py 继续通过。

---

## 三、离线测试(不依赖网络/codex)

`tests/test_analyzer.py`:
- monkeypatch `analyzer._run_codex` 返回一段**固定的合法 JSON 字符串**(含围栏/前后噪声,测健壮解析)。
- 断言 `analyze_evidence(fake_pack)` 正确解析出 verdict / angles / gaps / proposals。
- 测"浓缩证据"函数:丢了 desc、截断到 25 个视频、保留统计与评论。
- web:加一个 `/api/analyze` 用 monkeypatch 的 analyzer 返回 mock 结果,断言 200 + JSON。
- 全部用 `PYTHONPATH=src .venv/bin/python -m pytest -q`,不打网络、不跑真 codex。

---

## 四、【AI 提示词】(原样用,analyzer 拼在浓缩证据前面)

```
你是「B站选题撞车雷达」的资深选题分析师。下面给你一个选题的调研证据(同主题视频 + 高赞评论 + 统计)。请据此做选题判断。

**只输出一个 JSON 对象,不要任何额外文字,不要 markdown 代码围栏。**

判断规则:
1. 先剔除明显不相关的视频(广词召回的噪声,如主题不符、纯英文同名概念、课程卡),在 caveats 里说明剔除了什么。只基于真正相关的视频判断。
2. 角度聚类:把相关视频按"切入角度"归类(如 入门科普/实战教程/踩坑避雷/对比评测/深度原理/资讯解读 等,按实际命名)。每类判断饱和度:red=饱和(多且新、头部强)、yellow=半饱和(旧或无头部)、green=空缺;各给一句理由。
3. 评论缺口:从高赞评论里挖"观众反复想要、但没人做"的需求。**每条必须引用真实评论原文(evidence_quote)+ 赞数(evidence_likes)+ 来源视频标题(source_title)**,不许编造需求。
4. 三个差异化选题方案:每个写清 title(标题方向,不是标题党)、angle(角度)、why(填哪个空缺/踩中哪条评论)、audience(受众)、competition(low/med/high)、risk(主要风险)。若该题已饱和且无缺口,可少于3个甚至给0个并在 verdict 建议放弃——诚实劝退比硬凑更有价值。
5. verdict:do(值得做)/reangle(别做原角度、改个角度)/delay(延后)/drop(放弃);verdict_text 用一句中文说清做不做、走哪个角度、窗口期。
6. 不教标题党、不承诺播放量。时机判断结合"近90天占比"(高=上升)和"头部垄断度 top3_play_share"(高=新人难出头)。

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
```
（analyzer 在此拼接浓缩证据文本）
```
