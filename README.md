# B站选题撞车雷达 · Bilibili Topic Radar

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![status](https://img.shields.io/badge/version-0.1.0-brightgreen)
![readonly](https://img.shields.io/badge/data-read--only-success)

> 做视频之前的本地选题尽调工具。输入一个选题想法,它会扫遍 B站 同主题视频,
> 判断**撞不撞车**、哪个角度**还没人做**,并从高赞评论里挖出观众**没被满足的真实需求**;
> 可选调用本机 AI 给出 **做 / 改角度 / 延后 / 放弃** 的判断。

**纯只读公开数据 —— 不登录账号、不发任何内容、零封号风险。**

![看板](docs/screenshots/dashboard.png)

---

## 为什么需要它

选题是创作里投入产出比最悬的一步:做完才发现满地同题视频、流量被头部锁死,几天白干。
避免撞车需要的信息其实都在 B站 公开数据里,只是没人有精力逐条去查。本工具把这份尽调自动化,
并把"原始数据"提炼成**可执行的判断**。

| | 热榜工具 | 本工具 |
|---|---|---|
| 回答的问题 | "现在什么火" | "**你这题还有没有空子,该怎么切**" |
| 评论 | 不看 | **挖高赞评论里的真实需求(过滤玩梗/吐槽)** |
| AI 判断 | 无 | **本地 AI 给做/改/延/弃建议** |
| 数据 | — | 只读公开数据,不碰账号 |

## 核心能力

- **撞车雷达** —— 同题视频数量、播放分布、近 90 天活跃度、头部垄断度,一眼看清竞争态势。
- **评论真需求挖掘** —— 不只看播放量,从高赞评论提炼观众反复求、却没人做的内容点;自动过滤玩梗、吐槽、求资源等噪声。
- **本地 AI 判断(可选)** —— 证据先落本机,再交给本机 [Codex CLI](https://github.com/openai/codex)(GPT-5)产出结论、角度地图、三套差异化选题方案。无需 API key、零额外成本。
- **优雅降级** —— 未安装 AI 也能用证据看板;AI 仅作为增强项。

## 工作原理

```
关键词 ──▶ [采集层] 搜索 + 去重 + 拉热评 ──▶ 证据包 ──▶ [AI 分析] 读证据做判断 ──▶ 选题建议
          确定性程序(collect.py)          evidence.json   本机 Codex(analyzer.py)
```

1. **采集层**(`collect.py`):用 `bilibili-api` 调公开搜索/评论接口(WBI 签名、限流、本地缓存),把视频与热评聚合成证据包。纯程序,不含 AI。
2. **AI 分析**(`analyzer.py`):把证据浓缩后交给本机 Codex,用结构化输出(`--output-schema`)产出固定格式的判断——剔噪、角度聚类、缺口挖掘、生成方案。
3. **看板**(`web.py`):深色 Web 界面,可视化证据并触发 AI 分析。

技术栈:Python 3.11+ · `bilibili-api-python` · Starlette · 本机 Codex CLI(可选)。

---

## 快速开始

### 环境要求

- **Python 3.11+** 与 **[uv](https://docs.astral.sh/uv/)**。未安装 uv:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **访问 B站**:在中国大陆以外通常需本地代理(见「代理配置」)。
- **(可选)AI 分析**:需安装并登录 [Codex CLI](https://github.com/openai/codex);不安装亦可使用看板。

### 启动

```bash
git clone git@github.com:ZhengtaoGui/bili-topic-radar.git
cd bili-topic-radar
./scripts/start.sh           # macOS 亦可在 Finder 双击 scripts/start.command
```

脚本自动安装依赖、启动服务并打开浏览器至 **http://127.0.0.1:8848**。
首次使用可直接点击页面上的 **「看示例:MCP」** 即时查看效果。

详细图文步骤见 **[使用教程.md](使用教程.md)**。

---

## 代理配置(访问 B站)

本工具基于 `httpx`,会自动读取系统代理环境变量。在中国大陆以外,请先开启本地代理并确保设置:

```bash
export ALL_PROXY=socks5://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

SOCKS 代理依赖 `socksio`(已包含在依赖中)。中国大陆直连用户通常无需代理。

## AI 智能分析说明

看板中的 **「AI 智能分析」** 会将刚采集的证据交给本机 Codex,产出一句话结论、角度地图、观众真需求与三套选题方案。

- 后端使用本机 **Codex CLI(GPT-5)**:`codex login` 登录一次即可,**无需额外 API key、零额外成本**。
- 未安装 Codex 时,点击会给出友好提示,证据看板不受影响。
- 单次分析约 30–60 秒;结论仅供参考。
- `analyzer.py` 预留 Claude / DeepSeek API 后端接口(规划中)。

---

## 常见问题

**扫描很慢?** 采集会真实请求 B站 并限速(每次间隔 1.5–2 秒),单次约 30–60 秒;结果会缓存,重复查询很快。

**搜出无关视频?** 广词检索会引入噪声;AI 分析会主动剔除并在「数据提醒」中说明。

**会被封号吗?** 不会。全程只读公开数据,不登录、不发布任何内容。

## 数据与隐私

- 仅读取 B站 公开数据(搜索、视频信息、公开评论),**不登录账号**。
- 数据缓存于本地 `.cache/bili-topic-radar`(可用 `BILI_TOPIC_RADAR_CACHE` 自定义路径)。
- AI 分析在**本机**运行,证据不上传第三方服务器。

## 开发与测试

```bash
uv sync --extra dev
PYTHONPATH=src .venv/bin/python -m pytest -q                              # 测试(全离线)
PYTHONPATH=src .venv/bin/python -m bili_topic_radar.probe "MCP"           # 连通性探针
PYTHONPATH=src .venv/bin/python -m bili_topic_radar.collect "MCP" --out evidence.json   # 采集
PYTHONPATH=src .venv/bin/python -m bili_topic_radar.analyze evidence.json # AI 分析(需 Codex)
```

项目结构:`src/`(采集层、看板、分析器)· `examples/`(内置示例)· `skills/`(MCP skill)· `tests/`。

## 路线图

- **v0.1(当前)**:撞车雷达 · 评论真需求挖掘 · 本地 Codex AI 判断 · 深色看板 · 一键启动。
- **v0.2**:扫描后自动分析 · 一键导出 Markdown 报告 · 可选 Claude / DeepSeek API 后端。
- **v1.0**:机会分打分 · 选题生命周期/时机预测 · 持续监控预警 · 跨平台先行指标。

## 许可

[MIT](LICENSE)。选题判断仅供参考,使用者自行决策。

---

<sub>由 Claude + Codex 协作开发。</sub>
