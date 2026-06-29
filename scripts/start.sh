#!/usr/bin/env sh
# One-command launcher for the local Bilibili topic radar web dashboard.

set -eu

cd "$(dirname "$0")/.."

WEB_PID=""

cleanup() {
  if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if ! command -v uv >/dev/null 2>&1; then
  echo "未找到 uv。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "正在同步依赖。如果网络较慢,可重试: UV_HTTP_TIMEOUT=600 scripts/start.sh"
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-600}"
uv sync
uv pip install -e . --no-deps

PYTHONPATH=src .venv/bin/python -m bili_topic_radar.web &
WEB_PID=$!

sleep 2

URL="http://127.0.0.1:8848"
if command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
else
  echo "请手动打开: $URL"
fi

echo "看板地址: $URL"
echo "按 Ctrl+C 停止。"
echo "AI 分析需要本机 Codex CLI;没有也能用证据看板。"

wait "$WEB_PID"
