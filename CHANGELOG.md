# CHANGELOG

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
