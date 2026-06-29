# CHANGELOG

## 0.3.0 — 机会窗口雷达

- 新增确定性 `opportunity_window`:机会分、四因子拆解、生命周期阶段和角度机会排序。
- Web AI 结果区新增机会窗口卡片,展示大号机会分、阶段、因子条和现在最该做的 Top 3 角度。
- `/api/analyze` 与 CLI 分析输出追加可选顶层字段 `opportunity_window`,不改变 `AnalysisResult` 必填字段。
- 补充机会窗口单元测试,覆盖公式、生命周期、排序和空数据边界。

## 0.2.0 — 多后端 AI

- 多后端 AI 分析器:可选 `codex`(本地默认)/ `claude`(Anthropic)/ `openai-compatible`(OpenAI、DeepSeek、Kimi、GLM、Ollama,靠 base_url+model+key)。
- 后端可在网页下拉选择,或用环境变量 `BILI_RADAR_AI_BACKEND` / CLI `--backend` 指定;不可用时显示原因。
- 隐私默认本地:默认 `codex`,不会因为环境里有 API key 就自动把证据发到云端,云端后端需显式选择。
- `anthropic` / `openai` 作为可选依赖(`ai-claude` / `ai-openai` extras),按需安装。
- 新增 `.env.example` 与「选择 AI 后端」文档。

## 0.1.0 — 首发

- 撞车雷达:扫描同主题视频,展示竞争规模、近90天占比、头部垄断度和播放分布。
- 评论真需求挖掘:抓取高赞评论,帮助判断观众真正想看的缺口。
- 本地 Codex AI 判断:可选使用本机 Codex CLI 生成做/改角度/延后/放弃建议。
- 深色看板:提供本地 Web 看板、示例数据和可分享的 demo 链接。
- 只读零账号:只读取公开数据,不需要登录 B站,不发布或修改任何内容。
