# v1 发布计划(傻瓜一键包 + 开源仓库)

目标:用户拿到仓库后,**双击/一条命令就能跑起来看板**;能访问 B站 时可扫新选题;装了 Codex 且登录了就能用 AI 智能分析;**没装 Codex 也不崩**,证据看板照常用。

分工:Codex 做工程(脚本/降级/整理),Claude 写文档(README/教程/LICENSE)。

---

## 一、目标目录结构(Codex 负责搬动 + 改引用)

```
bili-topic-radar/
├── README.md            # Claude 写
├── 使用教程.md           # Claude 写(图文 step-by-step)
├── DESIGN.md            # 保留,标成"设计背景/路线图"
├── CHANGELOG.md         # Codex 建(v0.1.0 首发条目)
├── LICENSE              # Claude 写(MIT)
├── pyproject.toml / uv.lock
├── scripts/
│   ├── start.command    # Mac 双击启动(Finder 里双击就跑)
│   └── start.sh         # 通用 shell 启动
├── examples/
│   ├── evidence_mcp.json
│   ├── evidence_claudecode.json
│   └── reports/         # radar-*.md 样例报告
├── docs/dev/            # 开发过程文档(本文件 + 三个 spec)
│   ├── RELEASE_PLAN.md
│   ├── web_redesign_spec.md
│   ├── web_dark_theme_spec.md
│   └── ai_analyzer_spec.md
├── src/bili_topic_radar/...
├── skills/bilibili-topic-radar/SKILL.md
└── tests/
```

搬动动作:
- `evidence_mcp.json` / `evidence_claudecode.json` → `examples/`
- `reports/radar-*.md` → `examples/reports/`
- `web_redesign_spec.md` / `web_dark_theme_spec.md` / `ai_analyzer_spec.md` → `docs/dev/`
- **改代码引用**:demo 加载(`?demo=mcp/claudecode`、`/api/evidence`)要从 `examples/` 读内置 demo;用户自己 collect 生成的 `evidence_*.json` 仍可放根目录或指定路径。

## 二、`.gitignore`(Codex)

```
.venv/
.uv-cache/
__pycache__/
*.pyc
.pytest_cache/
.cache/
/reports/          # 用户自己生成的报告
/evidence_*.json   # 用户自己扫描生成的证据包(examples/ 里的样例不受影响)
/tmp_*.json
```

## 三、一键启动脚本(Codex 重点)

`scripts/start.sh`(`start.command` 内容相同,仅供 Mac 双击):
1. cd 到仓库根目录(`cd "$(dirname "$0")/.."`)。
2. 检查 `uv`:没有就打印一句安装提示(`curl -LsSf https://astral.sh/uv/install.sh | sh`)并退出,**不要**自动装(避免惊吓用户)。
3. `uv sync`(网络慢提示加 `UV_HTTP_TIMEOUT=600`);再 `uv pip install -e . --no-deps`。
4. 起 web:`PYTHONPATH=src .venv/bin/python -m bili_topic_radar.web`(后台);
5. 等 2 秒,`open http://127.0.0.1:8848`(Mac)/ `xdg-open`(Linux)/ 提示用户手动打开。
6. 友好提示三行:看板地址、按 Ctrl+C 停、AI 分析需要本机 Codex(没有也能用看板)。
7. 退出时清理后台进程(trap)。

脚本要 `chmod +x`。开头加注释说明用途。**Claude 会 live 实测这个脚本并修。**

## 四、优雅降级(Codex,Claude 会 live 验证)

AI 分析依赖本机 codex。要做到没 codex 也不崩:
1. `analyzer.py` 加 `codex_available() -> bool`:`shutil.which("codex")` 是否存在(可再轻量跑 `codex login status` 判断是否登录,失败就当不可用,别卡太久)。
2. `/api/analyze`:调用前先 `codex_available()`;不可用就返回**友好 JSON**(HTTP 200,带 `available: false` + 一句中文说明:"AI 分析需要在本机安装并登录 Codex CLI;证据看板不受影响"),**不要抛 500**。
3. 前端 AI 卡片:拿到 `available:false` 就显示这句友好提示 + 一个"怎么装 Codex"的链接位(指向 README 对应小节),而不是报错红字。
4. 可选:页面加载时 GET 一个轻量 `/api/ai_status` 显示 AI 是否就绪——非必须,v1 在点击时处理即可。

## 五、版本/收尾(Codex)

- `pyproject.toml` version 保持 `0.1.0`,`description` 改成面向用户的一句话(去掉 "MVP")。
- `CHANGELOG.md`:`## 0.1.0 — 首发`,列核心能力(撞车雷达 / 评论真需求挖掘 / 本地 Codex AI 判断 / 深色看板 / 只读零账号)。
- 所有测试继续通过;`README` 里的命令路径与新结构一致。

## 六、README 定位(Claude 写,记录在此对齐)

一句话:**做视频前的本地选题尽调工具——先查这题撞不撞车,再从高赞评论挖观众没被满足的真需求,最后可选用本机 Codex 给出 做/改角度/延后/放弃 的判断。**

它不是:B站热榜 / 标题党生成器 / 承诺播放量的玄学 / 爬你账号的运营后台。
它独特在:撞车雷达 + 评论真需求挖掘(不是只看播放) + 本地 AI 判断(证据先落本机) + 可降级(没 Codex 也能用) + 只读公开数据(不登录不发东西)。

README 结构:定位 → 截图 → 适合谁 → 你能得到什么 → 快速开始(一键脚本) → 代理设置 → AI 智能分析说明(需 Codex) → 常见问题 → 数据与隐私 → 开发/测试 → 路线图。
