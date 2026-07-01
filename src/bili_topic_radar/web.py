from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import analyzer, opportunity
from .collect import collect_evidence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples"
BUILTIN_DEMO_FILES = {"evidence_mcp.json", "evidence_claudecode.json"}
AI_UNAVAILABLE_MESSAGE = "AI 分析需要在本机安装并登录 Codex CLI;证据看板不受影响"


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>B站选题撞车雷达</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0e14;
      --bg-2: #0d1117;
      --panel: rgba(255, 255, 255, 0.04);
      --panel-strong: rgba(255, 255, 255, 0.07);
      --ink: #e6edf3;
      --muted: #8b97a7;
      --soft: rgba(45, 212, 191, 0.08);
      --line: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(45, 212, 191, 0.34);
      --accent: #2dd4bf;
      --accent-strong: #22d3ee;
      --accent-soft: rgba(45, 212, 191, 0.13);
      --purple: #818cf8;
      --blue: #22d3ee;
      --green: #34d399;
      --green-bg: rgba(52, 211, 153, 0.13);
      --amber: #fbbf24;
      --amber-bg: rgba(251, 191, 36, 0.13);
      --red: #fb7185;
      --red-bg: rgba(251, 113, 133, 0.13);
      --input: #0f141c;
      --shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
      --shadow-soft: 0 12px 36px rgba(0, 0, 0, 0.24);
      --glow: 0 0 22px rgba(45, 212, 191, 0.18);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 20% -10%, rgba(45, 212, 191, 0.12), transparent 34rem),
        radial-gradient(circle at 90% 0%, rgba(129, 140, 248, 0.12), transparent 30rem),
        linear-gradient(180deg, var(--bg), var(--bg-2) 46rem, var(--bg));
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.45;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.85), rgba(0,0,0,0.2) 70%, transparent);
    }

    header {
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(45, 212, 191, 0.10), rgba(129, 140, 248, 0.08)),
        rgba(10, 14, 20, 0.72);
      border-bottom: 1px solid var(--line);
    }

    header::before,
    header::after {
      content: "";
      position: absolute;
      pointer-events: none;
    }

    header::before {
      width: 480px;
      height: 480px;
      right: max(14px, calc((100vw - 1180px) / 2));
      top: -210px;
      border-radius: 50%;
      background:
        repeating-radial-gradient(circle, rgba(34, 211, 238, 0.22) 0 1px, transparent 1px 58px),
        conic-gradient(from 310deg, transparent 0 68%, rgba(45, 212, 191, 0.20) 72%, transparent 78% 100%);
      opacity: 0.36;
      filter: blur(0.2px);
    }

    header::after {
      width: 1px;
      height: 360px;
      right: max(252px, calc((100vw - 1180px) / 2 + 240px));
      top: -150px;
      background: linear-gradient(180deg, transparent, rgba(45, 212, 191, 0.34), transparent);
      transform: rotate(52deg);
      opacity: 0.38;
    }

    main, .header-inner {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }

    .header-inner {
      padding: 30px 0 24px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: start;
      position: relative;
      z-index: 1;
    }

    h1 {
      margin: 0 0 10px;
      font-size: clamp(30px, 4vw, 44px);
      letter-spacing: 0;
      line-height: 1.12;
      background: linear-gradient(90deg, #e6edf3 0%, var(--accent-strong) 42%, var(--purple) 92%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      text-shadow: 0 0 26px rgba(34, 211, 238, 0.16);
    }

    .subtitle {
      margin: 0 0 12px;
      color: #cbd5e1;
      font-size: 17px;
      max-width: 860px;
    }

    .privacy-note {
      margin: 0;
      color: var(--muted);
      max-width: 880px;
      font-size: 13px;
    }

    main {
      padding: 20px 0 36px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
      margin-bottom: 16px;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }

    .quick-start {
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.08), rgba(129, 140, 248, 0.08)),
        var(--panel);
    }

    .quick-title {
      margin: 0;
      color: var(--ink);
      font-size: 15px;
      font-weight: 800;
    }

    .quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }

    .controls {
      display: grid;
      gap: 18px;
      padding: 18px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: minmax(230px, 0.82fr) minmax(320px, 1.18fr);
      gap: 18px;
      align-items: start;
    }

    .form-left {
      display: grid;
      gap: 16px;
      align-content: start;
    }

    .field {
      display: grid;
      gap: 8px;
      align-content: start;
    }

    .field-head {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--ink);
      font-size: 13px;
      font-weight: 600;
    }

    .required {
      color: var(--red);
      font-size: 12px;
      font-weight: 800;
    }

    .help-text {
      color: var(--muted);
      font-size: 12px;
      min-height: 18px;
    }

    .info {
      display: inline-grid;
      place-items: center;
      width: 17px;
      height: 17px;
      border: 1px solid rgba(34, 211, 238, 0.34);
      border-radius: 999px;
      color: var(--accent-strong);
      background: rgba(34, 211, 238, 0.08);
      font-size: 11px;
      font-weight: 800;
      cursor: pointer;
      line-height: 1;
    }

    .info:focus { outline: none; box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.18); }

    .infotip {
      position: absolute;
      z-index: 90;
      max-width: 300px;
      background: #0f1722;
      color: var(--ink);
      border: 1px solid var(--line-strong);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 12px;
      font-weight: 400;
      line-height: 1.55;
      box-shadow: var(--shadow);
      pointer-events: none;
    }

    .infotip[hidden] { display: none; }

    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 11px;
      color: var(--ink);
      background: var(--input);
      font: inherit;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }

    input:focus, textarea:focus, select:focus {
      outline: none;
      border-color: var(--accent-strong);
      box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.13), 0 0 22px rgba(45, 212, 191, 0.12);
    }

    input::placeholder, textarea::placeholder {
      color: #5f6d7e;
    }

    textarea {
      min-height: 92px;
      resize: vertical;
    }

    select option:disabled {
      color: #64748b;
    }

    .field-actions {
      display: flex;
      justify-content: flex-end;
    }

    .form-actions {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .submit-note {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    button {
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 10px 14px;
      color: #061014;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      min-height: 42px;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.35) inset, 0 0 18px rgba(45, 212, 191, 0.14);
    }

    button.secondary {
      color: var(--accent-strong);
      background: rgba(15, 20, 28, 0.74);
      border-color: rgba(34, 211, 238, 0.30);
    }

    button.ghost {
      min-height: 34px;
      padding: 7px 10px;
      color: var(--accent-strong);
      background: var(--accent-soft);
      border-color: rgba(45, 212, 191, 0.26);
      font-size: 13px;
    }

    button:hover {
      border-color: var(--accent-strong);
      box-shadow: 0 0 24px rgba(34, 211, 238, 0.24);
      transform: translateY(-1px);
    }
    button.secondary:hover, button.ghost:hover {
      color: #e6edf3;
      background: rgba(34, 211, 238, 0.13);
    }
    button:disabled { cursor: wait; opacity: 0.65; }

    .status {
      padding: 0 16px 14px;
      color: var(--muted);
      min-height: 22px;
    }

    .status.error { color: var(--red); }

    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .stat {
      padding: 14px 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
      min-width: 0;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }

    .stat:hover {
      transform: translateY(-2px);
      border-color: var(--line-strong);
      box-shadow: var(--shadow-soft), var(--glow);
    }

    .stat-name {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .stat-value {
      margin-top: 8px;
      font-size: 28px;
      font-weight: 800;
      overflow-wrap: anywhere;
      font-variant-numeric: tabular-nums;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      color: #f8fafc;
      text-shadow: 0 0 20px rgba(34, 211, 238, 0.18);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      width: fit-content;
      margin-top: 10px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
      border: 1px solid currentColor;
    }

    .badge.good { color: var(--green); background: var(--green-bg); box-shadow: 0 0 16px rgba(52, 211, 153, 0.16); }
    .badge.neutral { color: var(--amber); background: var(--amber-bg); box-shadow: 0 0 16px rgba(251, 191, 36, 0.14); }
    .badge.bad { color: var(--red); background: var(--red-bg); box-shadow: 0 0 16px rgba(251, 113, 133, 0.14); }

    .ai-panel {
      padding: 16px;
      display: grid;
      gap: 14px;
      background:
        linear-gradient(135deg, rgba(45, 212, 191, 0.09), rgba(129, 140, 248, 0.07)),
        var(--panel);
    }

    .ai-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 14px;
      flex-wrap: wrap;
    }

    .ai-title {
      margin: 0 0 4px;
      font-size: 18px;
      line-height: 1.25;
    }

    .ai-note,
    .ai-muted {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }

    .ai-actions {
      display: grid;
      gap: 8px;
      justify-items: end;
      min-width: min(100%, 300px);
    }

    .backend-field {
      display: grid;
      gap: 6px;
      width: 100%;
    }

    .backend-field label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    .ai-result {
      display: grid;
      gap: 14px;
    }

    .ai-verdict {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      padding-top: 2px;
    }

    .verdict-badge {
      display: inline-flex;
      align-items: center;
      width: fit-content;
      padding: 5px 9px;
      border-radius: 999px;
      font-weight: 900;
      font-size: 13px;
      border: 1px solid currentColor;
      white-space: nowrap;
    }

    .verdict-badge.do { color: var(--green); background: var(--green-bg); }
    .verdict-badge.reangle,
    .verdict-badge.delay { color: var(--amber); background: var(--amber-bg); }
    .verdict-badge.drop { color: var(--red); background: var(--red-bg); }

    .ai-verdict-text {
      color: #f8fafc;
      font-weight: 800;
    }

    .ai-summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .opportunity-window {
      display: grid;
      grid-template-columns: minmax(160px, 0.55fr) minmax(220px, 0.85fr) minmax(260px, 1.2fr);
      gap: 12px;
      align-items: stretch;
      border: 1px solid rgba(45, 212, 191, 0.22);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(45, 212, 191, 0.08), rgba(129, 140, 248, 0.05)),
        rgba(15, 20, 28, 0.70);
      padding: 12px;
    }

    .opportunity-score {
      display: grid;
      align-content: center;
      gap: 8px;
      min-width: 0;
    }

    .opportunity-score-value {
      color: #f8fafc;
      font-size: 42px;
      font-weight: 900;
      line-height: 1;
      font-variant-numeric: tabular-nums;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      text-shadow: 0 0 24px rgba(34, 211, 238, 0.20);
    }

    .opportunity-score-value small {
      color: var(--muted);
      font-size: 16px;
      font-weight: 800;
    }

    .opportunity-stage,
    .opportunity-factors,
    .opportunity-top {
      display: grid;
      gap: 8px;
      align-content: start;
      min-width: 0;
    }

    .opportunity-badges {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }

    .ow-badge {
      display: inline-flex;
      width: fit-content;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid currentColor;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
    }

    .ow-badge.good { color: var(--green); background: var(--green-bg); }
    .ow-badge.neutral { color: var(--amber); background: var(--amber-bg); }
    .ow-badge.bad { color: var(--red); background: var(--red-bg); }

    .factor-row {
      display: grid;
      grid-template-columns: 74px 1fr 36px;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    .factor-track {
      height: 8px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
    }

    .factor-fill {
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--accent-strong));
    }

    .opportunity-angle-list {
      display: grid;
      gap: 8px;
    }

    .opportunity-angle {
      display: grid;
      gap: 3px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.035);
    }

    .opportunity-angle-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: #f8fafc;
      font-weight: 900;
    }

    .opportunity-angle-head span {
      overflow-wrap: anywhere;
    }

    .opportunity-angle-score {
      flex: 0 0 auto;
      color: var(--accent-strong);
      font-variant-numeric: tabular-nums;
    }

    .ai-summary-item,
    .proposal-card,
    .gap-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(15, 20, 28, 0.66);
      padding: 12px;
      min-width: 0;
    }

    .ai-label {
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    .ai-text {
      margin: 0;
      color: #dbeafe;
    }

    .angle-list,
    .gap-list,
    .proposal-grid,
    .caveat-list {
      display: grid;
      gap: 10px;
    }

    .angle-item {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 9px;
      padding: 10px 12px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.035);
      border: 1px solid var(--line);
    }

    .angle-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-top: 6px;
      background: var(--muted);
      box-shadow: 0 0 14px currentColor;
    }

    .angle-dot.red { background: var(--red); color: var(--red); }
    .angle-dot.yellow { background: var(--amber); color: var(--amber); }
    .angle-dot.green { background: var(--green); color: var(--green); }

    .angle-name,
    .proposal-title,
    .gap-need {
      margin: 0 0 4px;
      color: #f8fafc;
      font-weight: 800;
    }

    .angle-reason,
    .proposal-meta,
    .proposal-risk,
    .gap-source {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .gap-quote {
      margin: 8px 0;
      padding: 9px 10px;
      border-left: 3px solid var(--accent);
      border-radius: 6px;
      background: rgba(45, 212, 191, 0.08);
      color: #dbeafe;
    }

    .proposal-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .proposal-card {
      display: grid;
      gap: 8px;
      align-content: start;
    }

    .competition {
      display: inline-flex;
      width: fit-content;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }

    .competition.low { color: var(--green); background: var(--green-bg); border-color: rgba(52, 211, 153, 0.30); }
    .competition.med { color: var(--amber); background: var(--amber-bg); border-color: rgba(251, 191, 36, 0.30); }
    .competition.high { color: var(--red); background: var(--red-bg); border-color: rgba(251, 113, 133, 0.30); }

    .caveat-list {
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 12px;
    }

    .ai-error {
      color: var(--red);
      font-size: 13px;
    }

    .table-wrap {
      overflow-x: auto;
      border-radius: 8px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 920px;
    }

    th, td {
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }

    th {
      position: sticky;
      top: 0;
      background: rgba(12, 17, 25, 0.92);
      color: var(--muted);
      font-size: 12px;
      text-transform: none;
      white-space: nowrap;
      user-select: none;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }

    th.sortable {
      cursor: pointer;
    }

    .th-label {
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    tbody tr:hover {
      background: rgba(34, 211, 238, 0.05);
    }

    a {
      color: var(--blue);
      text-decoration: none;
      font-weight: 700;
    }

    a:hover { text-decoration: underline; }

    .title-cell {
      width: 36%;
      min-width: 320px;
    }

    .queries {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .tag {
      border: 1px solid rgba(34, 211, 238, 0.24);
      border-radius: 999px;
      padding: 2px 7px;
      background: rgba(34, 211, 238, 0.08);
      color: #b7ecf4;
      font-size: 12px;
    }

    .expand {
      width: 42px;
      min-height: 32px;
      padding: 4px 0;
      color: var(--accent-strong);
      background: rgba(15, 20, 28, 0.74);
      box-shadow: none;
    }

    .expand:hover {
      color: #e6edf3;
    }

    .comments {
      background: rgba(15, 20, 28, 0.76);
      color: var(--ink);
    }

    .comment-list {
      margin: 0;
      padding: 2px 0;
      list-style: none;
      display: grid;
      gap: 8px;
    }

    .comment {
      display: grid;
      gap: 3px;
      padding: 8px 10px;
      border-left: 3px solid rgba(45, 212, 191, 0.70);
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.045);
    }

    .comment.hot {
      border-left-color: var(--amber);
      background: rgba(251, 191, 36, 0.10);
      font-weight: 700;
      box-shadow: inset 0 0 0 1px rgba(251, 191, 36, 0.08);
    }

    .comment-meta {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }

    .comment.hot .comment-meta {
      color: var(--amber);
      font-weight: 800;
    }

    .empty {
      padding: 20px;
      color: var(--muted);
      text-align: center;
    }

    dialog {
      width: min(720px, calc(100% - 28px));
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0;
      color: var(--ink);
      background: rgba(10, 14, 20, 0.88);
      box-shadow: var(--shadow), var(--glow);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
    }

    dialog::backdrop {
      background: rgba(2, 6, 12, 0.72);
    }

    .tutorial {
      padding: 20px;
    }

    .tutorial-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }

    .tutorial h2 {
      margin: 0;
      font-size: 24px;
    }

    .tutorial h3 {
      margin: 18px 0 8px;
      font-size: 16px;
    }

    .tutorial p, .tutorial li {
      color: #cbd5e1;
    }

    .tutorial ol, .tutorial ul {
      padding-left: 22px;
    }

    .icon-button {
      width: 38px;
      min-height: 38px;
      padding: 0;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.04);
      border-color: var(--line);
      box-shadow: none;
    }

    .icon-button:hover {
      color: #e6edf3;
    }

    @media (max-width: 880px) {
      main, .header-inner {
        width: min(100% - 20px, 1180px);
      }

      .header-inner {
        grid-template-columns: 1fr;
      }

      .quick-start {
        align-items: stretch;
        flex-direction: column;
      }

      .quick-actions {
        justify-content: stretch;
      }

      .quick-actions button {
        flex: 1 1 220px;
      }

      .controls {
        grid-template-columns: 1fr;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }

      .stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .ai-summary-grid,
      .proposal-grid,
      .opportunity-window {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 520px) {
      .stats {
        grid-template-columns: 1fr;
      }
    }

    :root {
      --bg: #0b1119;
      --bg-2: #101823;
      --panel: rgba(20, 30, 43, 0.74);
      --panel-strong: rgba(24, 36, 50, 0.88);
      --ink: #edf2f7;
      --muted: #91a0b4;
      --line: rgba(255, 255, 255, 0.09);
      --line-strong: rgba(212, 168, 87, 0.38);
      --accent: #d4a857;
      --accent-strong: #f0d08b;
      --accent-soft: rgba(212, 168, 87, 0.15);
      --blue: #75a7d9;
      --green: #52c896;
      --green-bg: rgba(82, 200, 150, 0.13);
      --amber: #d4a857;
      --amber-bg: rgba(212, 168, 87, 0.15);
      --red: #ef6f72;
      --red-bg: rgba(239, 111, 114, 0.15);
      --input: rgba(15, 23, 33, 0.88);
      --shadow: 0 36px 110px rgba(0, 0, 0, 0.46);
      --shadow-soft: 0 18px 54px rgba(0, 0, 0, 0.28);
      --glow: 0 0 34px rgba(212, 168, 87, 0.16);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    }

    [hidden] { display: none !important; }

    body {
      overflow-x: hidden;
      background:
        radial-gradient(circle at 50% 14%, rgba(212, 168, 87, 0.10), transparent 34rem),
        radial-gradient(circle at 10% 8%, rgba(117, 167, 217, 0.10), transparent 28rem),
        linear-gradient(180deg, var(--bg), var(--bg-2) 38rem, var(--bg));
    }

    body::after {
      content: "";
      position: fixed;
      inset: -20%;
      z-index: -1;
      pointer-events: none;
      background:
        radial-gradient(circle at 28% 28%, rgba(212, 168, 87, 0.10), transparent 24rem),
        radial-gradient(circle at 72% 18%, rgba(117, 167, 217, 0.08), transparent 26rem);
      filter: blur(8px);
      opacity: 0.84;
      animation: ambientBreath 9s var(--ease) infinite alternate;
    }

    .ambient-grid {
      position: fixed;
      inset: 0;
      z-index: -2;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.024) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.024) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: radial-gradient(circle at 50% 20%, rgba(0,0,0,0.9), transparent 72%);
    }

    header { display: none; }

    .hero-stage,
    .loading-stage {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 32px 16px;
      position: relative;
    }

    .hero-shell {
      width: min(960px, 100%);
      display: grid;
      gap: 30px;
      justify-items: center;
      text-align: center;
      animation: stageIn 0.58s var(--ease) both;
    }

    .eyebrow {
      margin: 0 0 12px;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.12em;
    }

    .hero-copy h1 {
      margin: 0;
      color: #f7fafc;
      background: none;
      -webkit-background-clip: initial;
      background-clip: initial;
      font-size: clamp(46px, 9vw, 96px);
      line-height: 0.98;
      text-shadow: 0 22px 70px rgba(0, 0, 0, 0.42), 0 0 34px rgba(212, 168, 87, 0.12);
    }

    .hero-copy .subtitle {
      max-width: 760px;
      margin: 18px auto 0;
      color: #bec9d8;
      font-size: clamp(16px, 2vw, 20px);
    }

    .privacy-note {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .hero-form {
      width: min(780px, 100%);
    }

    .hero-input-card {
      position: relative;
      display: grid;
      gap: 16px;
      padding: clamp(18px, 3vw, 26px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 28px;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.12), transparent 18rem) border-box,
        linear-gradient(180deg, rgba(20, 29, 41, 0.86), rgba(10, 16, 24, 0.90)) padding-box;
      box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(26px) saturate(1.08);
      -webkit-backdrop-filter: blur(26px) saturate(1.08);
      animation: floatCard 5.6s var(--ease) infinite alternate;
    }

    .hero-primary-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }

    .hero-keyword {
      min-height: 62px;
      border-radius: 18px;
      padding: 0 20px;
      font-size: clamp(18px, 3vw, 26px);
      font-weight: 800;
      background: rgba(15, 23, 33, 0.88);
      border-color: rgba(255, 255, 255, 0.12);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }

    input:focus, textarea:focus, select:focus {
      border-color: rgba(240, 208, 139, 0.86);
      box-shadow: 0 0 0 4px rgba(212, 168, 87, 0.13), 0 0 30px rgba(212, 168, 87, 0.12);
    }

    button {
      border-color: rgba(212, 168, 87, 0.76);
      border-radius: 8px;
      color: #121820;
      background: linear-gradient(180deg, #e7c27c, var(--accent));
      box-shadow: 0 10px 28px rgba(212, 168, 87, 0.17), inset 0 1px 0 rgba(255, 255, 255, 0.34);
      transition: transform 0.22s var(--ease), border-color 0.22s ease, box-shadow 0.22s ease, background 0.22s ease;
    }

    .hero-submit {
      min-height: 62px;
      padding: 0 26px;
      border-radius: 18px;
      white-space: nowrap;
      font-size: 16px;
      font-weight: 900;
    }

    button:hover {
      border-color: rgba(240, 208, 139, 0.92);
      transform: translateY(-3px);
      box-shadow: 0 18px 42px rgba(212, 168, 87, 0.24), 0 0 34px rgba(212, 168, 87, 0.16);
    }

    button.secondary,
    button.ghost {
      color: #d9e2ee;
      background: rgba(255, 255, 255, 0.055);
      border-color: var(--line);
      box-shadow: none;
    }

    button.secondary:hover,
    button.ghost:hover {
      color: #f2d89f;
      background: rgba(212, 168, 87, 0.11);
      border-color: rgba(212, 168, 87, 0.38);
    }

    .hero-secondary-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .hero-advanced {
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.035);
      text-align: left;
    }

    .hero-advanced summary {
      cursor: pointer;
      padding: 14px 16px;
      color: #efd8a8;
      font-size: 13px;
      font-weight: 900;
    }

    .advanced-grid {
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 12px;
      padding: 0 16px 16px;
    }

    .hero-status {
      min-height: 18px;
      color: var(--muted);
      font-size: 13px;
    }

    .loading-shell {
      width: min(760px, 100%);
      display: grid;
      gap: 24px;
      padding: clamp(22px, 4vw, 34px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 28px;
      background: linear-gradient(180deg, rgba(20, 29, 41, 0.88), rgba(10, 16, 24, 0.92));
      box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(26px);
      -webkit-backdrop-filter: blur(26px);
      animation: stageIn 0.44s var(--ease) both;
    }

    .loading-title {
      margin: 0;
      font-size: clamp(28px, 5vw, 46px);
      line-height: 1.06;
    }

    .loading-copy {
      margin: 8px 0 0;
      color: #aebbd0;
    }

    .progress-track {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      box-shadow: inset 0 1px 1px rgba(0, 0, 0, 0.24);
    }

    .progress-fill {
      width: var(--progress, 8%);
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #c89943, #f0d08b);
      box-shadow: 0 0 22px rgba(212, 168, 87, 0.36);
      transition: width 0.62s var(--ease);
    }

    .loading-steps {
      display: grid;
      gap: 10px;
    }

    .loading-step {
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 46px;
      padding: 10px 12px;
      border: 1px solid rgba(255, 255, 255, 0.09);
      border-radius: 14px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.035);
      transition: color 0.24s ease, border-color 0.24s ease, background 0.24s ease, transform 0.24s var(--ease);
    }

    .loading-step b {
      display: grid;
      place-items: center;
      flex: 0 0 30px;
      height: 30px;
      border-radius: 50%;
      color: #b7c3d4;
      background: rgba(10, 16, 24, 0.92);
      border: 1px solid rgba(255, 255, 255, 0.14);
      font-family: var(--mono);
    }

    .loading-step.active,
    .loading-step.done {
      color: #efd8a8;
      border-color: rgba(212, 168, 87, 0.34);
      background: rgba(212, 168, 87, 0.08);
      transform: translateY(-1px);
    }

    .loading-step.active b,
    .loading-step.done b {
      color: #151a20;
      border-color: rgba(212, 168, 87, 0.78);
      background: linear-gradient(180deg, #f2d490, var(--accent));
      box-shadow: 0 0 0 5px rgba(212, 168, 87, 0.12), 0 12px 26px rgba(212, 168, 87, 0.22);
    }

    .loading-step.active b {
      animation: pulseDot 1.5s ease-in-out infinite;
    }

    .loading-status {
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
    }

    main.dashboard {
      width: min(1180px, calc(100% - 32px));
      padding: 28px 0 42px;
      opacity: 1;
      transform: none;
    }

    .dashboard-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 18px;
      margin-bottom: 18px;
    }

    .dashboard-title {
      margin: 0;
      color: #f7fafc;
      background: none;
      -webkit-background-clip: initial;
      background-clip: initial;
      font-size: clamp(30px, 4vw, 48px);
      line-height: 1.08;
      text-shadow: 0 16px 54px rgba(0, 0, 0, 0.36), 0 0 28px rgba(212, 168, 87, 0.10);
    }

    .dashboard-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .panel,
    .stat,
    .ai-summary-item,
    .proposal-card,
    .gap-item {
      border-color: var(--line);
      background: var(--panel);
      box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.055);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
    }

    .status-panel {
      padding: 14px 16px;
      background: linear-gradient(90deg, rgba(212, 168, 87, 0.09), rgba(117, 167, 217, 0.055)), var(--panel);
    }

    .status {
      padding: 0;
    }

    .stat-value,
    .opportunity-score-value {
      font-family: var(--mono);
      color: #f2d89f;
      text-shadow: 0 0 22px rgba(212, 168, 87, 0.16);
    }

    .factor-fill {
      background: linear-gradient(90deg, #c89943, #f0d08b);
    }

    .gap-quote {
      border-left-color: var(--accent);
      background: rgba(212, 168, 87, 0.08);
    }

    .tag {
      border-color: rgba(212, 168, 87, 0.26);
      background: rgba(212, 168, 87, 0.08);
      color: #efd8a8;
    }

    .dashboard .reveal-section {
      opacity: 0;
      transform: translateY(18px);
    }

    .dashboard.revealed .reveal-section {
      animation: revealSection 0.58s var(--ease) both;
      animation-delay: var(--delay, 0ms);
    }

    .dashboard.revealed .reveal-section:nth-of-type(2) { --delay: 80ms; }
    .dashboard.revealed .reveal-section:nth-of-type(3) { --delay: 160ms; }
    .dashboard.revealed .reveal-section:nth-of-type(4) { --delay: 240ms; }
    .dashboard.revealed .reveal-section:nth-of-type(5) { --delay: 320ms; }

    @keyframes ambientBreath {
      from { transform: scale(1) translate3d(0, 0, 0); opacity: 0.60; }
      to { transform: scale(1.06) translate3d(0, -10px, 0); opacity: 0.92; }
    }

    @keyframes floatCard {
      from { transform: translateY(0); }
      to { transform: translateY(-10px); }
    }

    @keyframes stageIn {
      from { opacity: 0; transform: translateY(22px) scale(0.985); filter: blur(6px); }
      to { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
    }

    @keyframes revealSection {
      from { opacity: 0; transform: translateY(22px); filter: blur(5px); }
      to { opacity: 1; transform: translateY(0); filter: blur(0); }
    }

    @keyframes pulseDot {
      0%, 100% { box-shadow: 0 0 0 5px rgba(212, 168, 87, 0.12), 0 12px 26px rgba(212, 168, 87, 0.22); }
      50% { box-shadow: 0 0 0 9px rgba(212, 168, 87, 0.05), 0 12px 34px rgba(212, 168, 87, 0.30); }
    }

    @media (max-width: 760px) {
      .hero-primary-row,
      .advanced-grid,
      .dashboard-top {
        grid-template-columns: 1fr;
        display: grid;
      }

      .hero-submit,
      .dashboard-actions button {
        width: 100%;
      }

      .dashboard-actions {
        justify-content: stretch;
      }
    }
  </style>
</head>
<body>
  <div class="ambient-grid"></div>

  <section id="hero-stage" class="hero-stage" aria-label="选题入口">
    <div class="hero-shell">
      <div class="hero-copy">
        <p class="eyebrow">BILIBILI TOPIC DUE DILIGENCE</p>
        <h1>选题撞车雷达</h1>
        <p class="subtitle">做视频前先扫一遍同题,看撞不撞车、哪个角度没人做。</p>
        <p class="privacy-note">只读公开数据,不登录,不发布。</p>
      </div>

      <form id="collect-form" class="hero-form">
        <div class="hero-input-card">
          <div class="hero-primary-row">
            <div class="field">
              <div class="field-head">
                <label for="keyword">选题关键词</label>
                <span class="required">*必填*</span>
                <span class="info" tabindex="0" role="button" data-tip="雷达会拿这个词去 B站 搜同主题视频。用观众真正会搜的词最准。">i</span>
              </div>
              <input id="keyword" class="hero-keyword" name="keyword" required placeholder="例如:MCP、Claude Code、机械键盘、露营">
            </div>
            <button id="collect-button" class="hero-submit" type="submit">开始尽调</button>
          </div>

          <div class="hero-secondary-row">
            <button id="demo-mcp-button" class="secondary" type="button">看示例:MCP</button>
            <button id="demo-claudecode-button" class="secondary" type="button">看示例:Claude Code</button>
          </div>

          <details class="hero-advanced">
            <summary>高级采集设置</summary>
            <div class="advanced-grid">
              <div class="field">
                <div class="field-head">
                  <label for="top-comments">抓多少热评</label>
                  <span class="info" tabindex="0" role="button" data-tip="评论区是金矿——观众喊的需求就是你视频的差异化方向。数字越大越慢。">i</span>
                </div>
                <div class="help-text">默认 10,最高 50</div>
                <input id="top-comments" name="top_comments" type="number" min="0" max="50" value="10">
              </div>
              <div class="field">
                <div class="field-head">
                  <label for="extra">额外搜索词(可选)</label>
                  <span class="info" tabindex="0" role="button" data-tip="同一个题,观众搜法不同(教程/实战/入门/原理…)。多给几个词,覆盖更全、角度地图更准。">i</span>
                </div>
                <div class="help-text">观众可能用的其他搜法,帮你搜得更全</div>
                <textarea id="extra" name="extra_queries" placeholder="MCP 教程&#10;MCP 实战&#10;MCP 原理"></textarea>
                <div class="field-actions">
                  <button id="suffix-button" class="ghost" type="button">+ 自动加常见后缀</button>
                </div>
              </div>
            </div>
          </details>
          <div id="hero-status" class="hero-status">真实请求 B站 通常需要 30-60 秒。</div>
        </div>
      </form>
    </div>
  </section>

  <section id="loading-stage" class="loading-stage" aria-label="采集中" hidden>
    <div class="loading-shell">
      <div>
        <p class="eyebrow">COLLECTING PUBLIC SIGNALS</p>
        <h2 class="loading-title">正在扫同题证据</h2>
        <p id="loading-copy" class="loading-copy">搜索、评论和统计正在汇总。</p>
      </div>
      <div class="progress-track" aria-hidden="true">
        <div id="loading-fill" class="progress-fill"></div>
      </div>
      <div class="loading-steps">
        <div class="loading-step active" data-step="0"><b>1</b><span>搜索同题视频</span></div>
        <div class="loading-step" data-step="1"><b>2</b><span>拉取高赞评论</span></div>
        <div class="loading-step" data-step="2"><b>3</b><span>汇总证据</span></div>
      </div>
      <div id="loading-status" class="loading-status">正在建立采集任务。</div>
    </div>
  </section>

  <main id="dashboard" class="dashboard" hidden>
    <div class="dashboard-top">
      <div>
        <p class="eyebrow">BILIBILI EVIDENCE BOARD</p>
        <h1 class="dashboard-title">尽调结果</h1>
        <p class="subtitle">撞车雷达、评论真需求、机会窗口和 AI 智能分析都在这里。</p>
      </div>
      <div class="dashboard-actions">
        <button id="restart-button" class="secondary" type="button">重新选题</button>
        <button id="tutorial-button" class="secondary" type="button">使用教程</button>
      </div>
    </div>

    <section class="panel status-panel reveal-section">
      <div id="status" class="status">输入一个选题点&quot;开始尽调&quot;,或点&quot;看示例&quot;先体验。</div>
    </section>

    <section id="stats" class="stats reveal-section" aria-label="统计卡"></section>

    <section id="ai-analysis" class="panel ai-panel reveal-section" aria-label="AI 智能分析"></section>

    <section class="panel reveal-section">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
              <th class="sortable" data-key="title">标题</th>
              <th class="sortable" data-key="author">UP主</th>
              <th class="sortable" data-key="play">播放</th>
              <th class="sortable" data-key="pubdate">发布日期</th>
              <th class="sortable" data-key="age_days"><span class="th-label">视频年龄 <span class="info" tabindex="0" role="button" data-tip="距今多少天发布。">i</span></span></th>
              <th data-key="queries_hit"><span class="th-label">命中搜索词 <span class="info" tabindex="0" role="button" data-tip="这个视频在你哪几个搜索词里出现,命中越多越是核心结果。">i</span></span></th>
            </tr>
          </thead>
          <tbody id="tbody">
            <tr><td class="empty" colspan="7">👆 输入一个选题点&quot;开始扫描&quot;,或点上方&quot;看示例&quot;先体验。</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <dialog id="tutorial-dialog">
    <div class="tutorial">
      <div class="tutorial-head">
        <h2>怎么用这个雷达?</h2>
        <button id="tutorial-close" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>

      <h3>这是什么</h3>
      <p>做视频前的&quot;选题尽调&quot;。输入一个选题,它扫遍 B站 同主题视频,告诉你:竞争多不多、哪个角度还空着、观众在评论区求什么。</p>

      <h3>三步用法</h3>
      <ol>
        <li><strong>输入选题</strong> —— 填一个关键词(再可选填几个额外搜法),点「开始扫描」。懒得想?直接点上面的「看示例」秒看效果。</li>
        <li><strong>读结果</strong> —— 顶部 5 个数字是&quot;竞争态势&quot;;下面表格是所有同主题视频(可按播放/日期排序);点 ➕ 展开看每个视频的高赞评论(观众的真实需求)。</li>
        <li><strong>拿去出报告</strong> —— 把这些&quot;证据&quot;交给 Claude(bilibili-topic-radar skill),它会做角度聚类、挖评论缺口,给你 <strong>3 个差异化选题方案 + 做/不做建议</strong>。</li>
      </ol>

      <h3>怎么快速读那几个数</h3>
      <ul>
        <li>近90天占比<strong>高</strong> → 这个题正在升温,值得做。</li>
        <li>头部垄断度<strong>高</strong> → 流量被几个大 UP 吃光,新人难出头,慎入。</li>
        <li>中位播放远低于最高播放 → 长尾严重,多数视频其实没什么量。</li>
      </ul>

      <h3>重要</h3>
      <p>原始统计只展示&quot;原料证据&quot;,<strong>不做 AI 判断</strong>;需要角度/缺口/三方案时,点击统计卡下方的 AI 智能分析,由本地 GPT-5 读取证据后生成结论。</p>
    </div>
  </dialog>

  <script>
    const state = {
      pack: null,
      sourceFile: null,
      analysis: null,
      analysisNotice: "",
      analysisLoading: false,
      analysisError: "",
      aiBackends: [],
      selectedBackend: "codex",
      sortKey: "play",
      sortDir: "desc",
      expanded: new Set(),
      mode: "hero",
    };

    const $ = (id) => document.getElementById(id);
    const statusEl = $("status");
    const heroStage = $("hero-stage");
    const loadingStage = $("loading-stage");
    const dashboard = $("dashboard");
    const heroStatus = $("hero-status");
    const loadingStatus = $("loading-status");
    const loadingCopy = $("loading-copy");
    const loadingFill = $("loading-fill");
    const loadingSteps = Array.from(document.querySelectorAll(".loading-step"));
    const tbody = $("tbody");
    const statsEl = $("stats");
    const aiEl = $("ai-analysis");
    const collectButton = $("collect-button");
    const tutorialDialog = $("tutorial-dialog");
    let loadingTimer = null;
    let loadingStartedAt = 0;

    const statCopy = {
      total_unique_videos: {
        label: "相关视频数",
        tooltip: "全站找到多少个同主题视频。",
      },
      near_90d_ratio: {
        label: "近90天占比",
        tooltip: "近三个月新视频占比。越高=题在升温、新人也有机会;越低=热度过了。",
      },
      top3_play_share: {
        label: "头部垄断度",
        tooltip: "播放最高的 3 个视频吃掉了多少总播放。越高=被大 UP 垄断、新人越难出头。",
      },
      max_play: {
        label: "最高播放",
        tooltip: "这个题里跑得最好的视频播放量。",
      },
      median_play: {
        label: "中位播放",
        tooltip: "一半视频低于这个数。和\\"最高播放\\"差距越大=越长尾(多数视频没量)。",
      },
    };

    const verdictCopy = {
      do: "✅建议做",
      reangle: "✏️改角度",
      delay: "⏳延后",
      drop: "⛔放弃",
    };

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", isError);
      if (state.mode === "hero") {
        heroStatus.textContent = text;
        heroStatus.style.color = isError ? "var(--red)" : "var(--muted)";
      }
      if (state.mode === "loading") {
        loadingStatus.textContent = text;
        loadingStatus.style.color = isError ? "var(--red)" : "var(--muted)";
      }
    }

    function setMode(mode) {
      state.mode = mode;
      heroStage.hidden = mode !== "hero";
      loadingStage.hidden = mode !== "loading";
      dashboard.hidden = mode !== "dashboard";
      document.body.className = `stage-${mode}`;
    }

    function clearLoadingMotion() {
      if (loadingTimer) window.clearInterval(loadingTimer);
      loadingTimer = null;
    }

    function paintLoading(progress, activeStep) {
      loadingFill.style.setProperty("--progress", `${Math.max(8, Math.min(100, progress))}%`);
      loadingSteps.forEach((step, index) => {
        step.classList.toggle("done", index < activeStep);
        step.classList.toggle("active", index === activeStep);
      });
    }

    function beginLoadingMotion(keyword, scanCount) {
      clearLoadingMotion();
      loadingStartedAt = Date.now();
      loadingCopy.textContent = `正在尽调「${keyword}」,覆盖 ${scanCount} 个搜索词。`;
      paintLoading(10, 0);
      setMode("loading");
      setStatus("正在搜索同题视频,随后会拉取高赞评论并汇总证据。");
      loadingTimer = window.setInterval(() => {
        const elapsed = Date.now() - loadingStartedAt;
        const activeStep = elapsed > 28000 ? 2 : elapsed > 11000 ? 1 : 0;
        const base = activeStep === 0 ? 10 : activeStep === 1 ? 42 : 70;
        const drift = Math.min(activeStep === 2 ? 18 : 24, Math.floor(elapsed / 900));
        paintLoading(Math.min(92, base + drift), activeStep);
        if (activeStep === 0) setStatus("搜索同题视频中,正在收集标题、UP主、播放和发布时间。");
        else if (activeStep === 1) setStatus("拉取高赞评论中,重点看观众真实需求和追问。");
        else setStatus("汇总证据中,正在计算撞车态势和机会窗口。");
      }, 1600);
    }

    function finishLoadingMotion() {
      clearLoadingMotion();
      paintLoading(100, 2);
      loadingSteps.forEach((step) => {
        step.classList.add("done");
        step.classList.remove("active");
      });
    }

    function revealDashboard() {
      setMode("dashboard");
      dashboard.classList.remove("revealed");
      void dashboard.offsetWidth;
      dashboard.classList.add("revealed");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function returnToHero(message = "真实请求 B站 通常需要 30-60 秒。", isError = false) {
      clearLoadingMotion();
      setMode("hero");
      collectButton.disabled = false;
      heroStatus.textContent = message;
      heroStatus.style.color = isError ? "var(--red)" : "var(--muted)";
      $("keyword").focus();
    }

    function formatInt(value) {
      const number = Number(value || 0);
      return new Intl.NumberFormat("zh-CN").format(number);
    }

    function formatRatio(value) {
      const number = Number(value || 0);
      return `${(number * 100).toFixed(1)}%`;
    }

    function formatDate(value) {
      const ts = Number(value || 0);
      if (!ts) return "-";
      return new Date(ts * 1000).toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
    }

    function formatAge(value) {
      if (value === null || value === undefined || value === "") return "-";
      return `${formatInt(value)} 天`;
    }

    function statValue(key, value) {
      if (key.endsWith("_ratio") || key.endsWith("_share")) return formatRatio(value);
      return formatInt(value);
    }

    function statBadge(key, value) {
      const number = Number(value || 0);
      if (key === "near_90d_ratio") {
        if (number >= 0.5) return ["good", "🔥上升期"];
        if (number >= 0.3) return ["neutral", "持续产出"];
        return ["bad", "📉降温·成熟"];
      }
      if (key === "top3_play_share") {
        if (number >= 0.45) return ["bad", "头部锁死·难挤"];
        if (number >= 0.35) return ["neutral", "中等"];
        return ["good", "流量分散·好进"];
      }
      return null;
    }

    function infoIcon(text) {
      const icon = document.createElement("span");
      icon.className = "info";
      icon.tabIndex = 0;
      icon.title = text;
      icon.textContent = "i";
      return icon;
    }

    function sectionTitle(text) {
      const title = document.createElement("p");
      title.className = "ai-label";
      title.textContent = text;
      return title;
    }

    function renderAiAnalysis() {
      const head = document.createElement("div");
      head.className = "ai-head";

      const intro = document.createElement("div");
      const title = document.createElement("h2");
      title.className = "ai-title";
      title.textContent = "🤖 AI 智能分析";
      const note = document.createElement("p");
      note.className = "ai-note";
      note.textContent = "本结论由你选择的 AI 后端生成,仅供参考。";
      intro.append(title, note);

      const actions = document.createElement("div");
      actions.className = "ai-actions";
      const backendField = document.createElement("div");
      backendField.className = "backend-field";
      const backendLabel = document.createElement("label");
      backendLabel.htmlFor = "ai-backend";
      backendLabel.textContent = "AI 后端";
      const backendSelect = document.createElement("select");
      backendSelect.id = "ai-backend";
      backendSelect.disabled = state.analysisLoading;
      for (const backend of state.aiBackends) {
        const option = document.createElement("option");
        option.value = backend.key;
        option.textContent = backend.available
          ? backend.label
          : `${backend.label}（不可用:${backend.reason || "未配置"}）`;
        option.disabled = !backend.available;
        if (backend.key === state.selectedBackend) option.selected = true;
        backendSelect.append(option);
      }
      backendSelect.addEventListener("change", () => {
        state.selectedBackend = backendSelect.value;
      });
      backendField.append(backendLabel, backendSelect);

      const action = document.createElement("button");
      action.type = "button";
      action.textContent = state.analysisLoading
        ? "分析中..."
        : "🤖 让 AI 给出建议和结论(约 30-60 秒)";
      action.disabled = state.analysisLoading || !state.pack;
      action.addEventListener("click", runAiAnalysis);
      actions.append(backendField, action);
      head.append(intro, actions);

      const children = [head];
      if (!state.pack) {
        const muted = document.createElement("p");
        muted.className = "ai-muted";
        muted.textContent = "先加载示例或完成一次扫描后再分析。";
        children.push(muted);
      }
      if (state.analysisError) {
        const error = document.createElement("div");
        error.className = "ai-error";
        error.textContent = state.analysisError;
        children.push(error);
      }
      if (state.analysisNotice) {
        const notice = document.createElement("p");
        notice.className = "ai-muted";
        notice.textContent = state.analysisNotice + " ";
        const link = document.createElement("a");
        link.href = "README.md#选择-ai-后端";
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "怎么配置后端";
        notice.append(link);
        children.push(notice);
      }
      if (state.analysis) {
        children.push(renderAiResult(state.analysis));
      }
      aiEl.replaceChildren(...children);
    }

    function renderAiResult(result) {
      const wrap = document.createElement("div");
      wrap.className = "ai-result";

      const verdict = document.createElement("div");
      verdict.className = "ai-verdict";
      const badge = document.createElement("span");
      badge.className = `verdict-badge ${result.verdict || ""}`;
      badge.textContent = verdictCopy[result.verdict] || result.verdict || "AI 判断";
      const verdictText = document.createElement("span");
      verdictText.className = "ai-verdict-text";
      verdictText.textContent = result.verdict_text || "";
      verdict.append(badge, verdictText);

      const summary = document.createElement("div");
      summary.className = "ai-summary-grid";
      summary.append(summaryItem("态势", result.situation), summaryItem("时机", result.timing));

      wrap.append(verdict, summary);
      const opportunityWindow = renderOpportunityWindow(result.opportunity_window);
      if (opportunityWindow) wrap.append(opportunityWindow);
      wrap.append(renderAngles(result.angles || []));
      wrap.append(renderGaps(result.gaps || []));
      wrap.append(renderProposals(result.proposals || []));
      wrap.append(renderCaveats(result.caveats || []));
      return wrap;
    }

    function renderOpportunityWindow(windowData) {
      if (!windowData || typeof windowData !== "object") return null;
      const section = document.createElement("section");
      section.className = "opportunity-window";

      const score = Math.max(0, Math.min(100, Math.round(Number(windowData.score || 0))));
      const scorePanel = document.createElement("div");
      scorePanel.className = "opportunity-score";
      scorePanel.append(sectionTitle("机会窗口"));
      const scoreValue = document.createElement("div");
      scoreValue.className = "opportunity-score-value";
      scoreValue.append(document.createTextNode(String(score)), document.createElement("small"));
      scoreValue.lastChild.textContent = " / 100";
      const scoreBadge = document.createElement("span");
      scoreBadge.className = `ow-badge ${opportunityTone(score)}`;
      scoreBadge.textContent = windowData.label || "-";
      scorePanel.append(scoreValue, scoreBadge);

      const stagePanel = document.createElement("div");
      stagePanel.className = "opportunity-stage";
      stagePanel.append(sectionTitle("阶段"));
      const badges = document.createElement("div");
      badges.className = "opportunity-badges";
      const stage = (windowData.lifecycle && windowData.lifecycle.stage) || "谨慎观察";
      const stageBadge = document.createElement("span");
      stageBadge.className = `ow-badge ${stageTone(stage)}`;
      stageBadge.textContent = stage;
      badges.append(stageBadge);
      const reason = document.createElement("p");
      reason.className = "ai-muted";
      reason.textContent = (windowData.lifecycle && windowData.lifecycle.reason) || "";
      stagePanel.append(badges, reason, renderFactorBars(windowData.factors || {}));

      const topPanel = document.createElement("div");
      topPanel.className = "opportunity-top";
      topPanel.append(sectionTitle("现在最该做"));
      const list = document.createElement("div");
      list.className = "opportunity-angle-list";
      const ranked = Array.isArray(windowData.ranked_angles) ? windowData.ranked_angles.slice(0, 3) : [];
      if (ranked.length === 0) {
        const empty = document.createElement("p");
        empty.className = "ai-muted";
        empty.textContent = "暂无可排序角度。";
        list.append(empty);
      }
      for (const angle of ranked) {
        const item = document.createElement("article");
        item.className = "opportunity-angle";
        const head = document.createElement("div");
        head.className = "opportunity-angle-head";
        const name = document.createElement("span");
        name.textContent = `${angle.rank || "-"} · ${angle.name || angle.proposal_title || "-"}`;
        const angleScore = document.createElement("strong");
        angleScore.className = "opportunity-angle-score";
        angleScore.textContent = `${Math.round(Number(angle.score || 0))}`;
        head.append(name, angleScore);
        const why = document.createElement("p");
        why.className = "proposal-meta";
        why.textContent = angle.why_now || "";
        item.append(head, why);
        if (angle.risk) {
          const risk = document.createElement("p");
          risk.className = "proposal-risk";
          risk.textContent = `风险: ${angle.risk}`;
          item.append(risk);
        }
        list.append(item);
      }
      topPanel.append(list);

      section.append(scorePanel, stagePanel, topPanel);
      return section;
    }

    function renderFactorBars(factors) {
      const names = [
        ["freshness", "活跃度"],
        ["headroom", "头部空间"],
        ["angle_vacancy", "角度空缺"],
        ["real_demand", "真需求"],
      ];
      const wrap = document.createElement("div");
      wrap.className = "opportunity-factors";
      for (const [key, label] of names) {
        const value = Math.max(0, Math.min(100, Math.round(Number(factors[key] || 0))));
        const row = document.createElement("div");
        row.className = "factor-row";
        const labelEl = document.createElement("span");
        labelEl.textContent = label;
        const track = document.createElement("div");
        track.className = "factor-track";
        const fill = document.createElement("div");
        fill.className = "factor-fill";
        fill.style.width = `${value}%`;
        track.append(fill);
        const valueEl = document.createElement("span");
        valueEl.textContent = String(value);
        row.append(labelEl, track, valueEl);
        wrap.append(row);
      }
      return wrap;
    }

    function opportunityTone(score) {
      if (score >= 60) return "good";
      if (score >= 40) return "neutral";
      return "bad";
    }

    function stageTone(stage) {
      if (stage === "上升" || stage === "爆发") return "good";
      if (stage === "衰退") return "bad";
      return "neutral";
    }

    function summaryItem(label, text) {
      const item = document.createElement("div");
      item.className = "ai-summary-item";
      const name = sectionTitle(label);
      const body = document.createElement("p");
      body.className = "ai-text";
      body.textContent = text || "-";
      item.append(name, body);
      return item;
    }

    function renderAngles(angles) {
      const section = document.createElement("section");
      section.append(sectionTitle("角度地图"));
      const list = document.createElement("div");
      list.className = "angle-list";
      if (angles.length === 0) {
        const empty = document.createElement("p");
        empty.className = "ai-muted";
        empty.textContent = "暂无角度判断。";
        list.append(empty);
      }
      for (const angle of angles) {
        const item = document.createElement("div");
        item.className = "angle-item";
        const dot = document.createElement("span");
        dot.className = `angle-dot ${angle.saturation || ""}`;
        const body = document.createElement("div");
        const name = document.createElement("p");
        name.className = "angle-name";
        name.textContent = angle.name || "-";
        const reason = document.createElement("p");
        reason.className = "angle-reason";
        reason.textContent = angle.reason || "";
        body.append(name, reason);
        item.append(dot, body);
        list.append(item);
      }
      section.append(list);
      return section;
    }

    function renderGaps(gaps) {
      const section = document.createElement("section");
      section.append(sectionTitle("观众缺口"));
      const list = document.createElement("div");
      list.className = "gap-list";
      if (gaps.length === 0) {
        const empty = document.createElement("p");
        empty.className = "ai-muted";
        empty.textContent = "未发现可引用的评论缺口。";
        list.append(empty);
      }
      for (const gap of gaps) {
        const item = document.createElement("article");
        item.className = "gap-item";
        const need = document.createElement("p");
        need.className = "gap-need";
        need.textContent = gap.need || "-";
        const quote = document.createElement("blockquote");
        quote.className = "gap-quote";
        quote.textContent = gap.evidence_quote || "";
        const source = document.createElement("p");
        source.className = "gap-source";
        source.textContent = `👍 ${formatInt(gap.evidence_likes)} · 来源 ${gap.source_title || "-"}`;
        item.append(need, quote, source);
        list.append(item);
      }
      section.append(list);
      return section;
    }

    function renderProposals(proposals) {
      const section = document.createElement("section");
      section.append(sectionTitle("选题方案"));
      const grid = document.createElement("div");
      grid.className = "proposal-grid";
      if (proposals.length === 0) {
        const empty = document.createElement("p");
        empty.className = "ai-muted";
        empty.textContent = "AI 建议不硬凑方案。";
        grid.append(empty);
      }
      for (const proposal of proposals) {
        const card = document.createElement("article");
        card.className = "proposal-card";
        const title = document.createElement("p");
        title.className = "proposal-title";
        title.textContent = proposal.title || "-";
        const competition = document.createElement("span");
        competition.className = `competition ${proposal.competition || ""}`;
        competition.textContent = `竞争度 ${proposal.competition || "-"}`;
        const angle = document.createElement("p");
        angle.className = "proposal-meta";
        angle.textContent = `角度: ${proposal.angle || "-"}`;
        const why = document.createElement("p");
        why.className = "ai-text";
        why.textContent = proposal.why || "";
        const audience = document.createElement("p");
        audience.className = "proposal-meta";
        audience.textContent = `受众: ${proposal.audience || "-"}`;
        const risk = document.createElement("p");
        risk.className = "proposal-risk";
        risk.textContent = `风险: ${proposal.risk || "-"}`;
        card.append(title, competition, angle, why, audience, risk);
        grid.append(card);
      }
      section.append(grid);
      return section;
    }

    function renderCaveats(caveats) {
      const section = document.createElement("section");
      section.append(sectionTitle("数据可信度"));
      const list = document.createElement("ul");
      list.className = "caveat-list";
      const items = caveats.length ? caveats : ["无额外提示。"];
      for (const text of items) {
        const item = document.createElement("li");
        item.textContent = text;
        list.append(item);
      }
      section.append(list);
      return section;
    }

    function renderStats(pack) {
      const stats = [
        ["total_unique_videos", pack.total_unique_videos],
        ["near_90d_ratio", pack.near_90d_ratio],
        ["top3_play_share", pack.top3_play_share],
        ["max_play", pack.max_play],
        ["median_play", pack.median_play],
      ];
      statsEl.replaceChildren(...stats.map(([key, value]) => {
        const card = document.createElement("article");
        card.className = "stat";
        const name = document.createElement("div");
        name.className = "stat-name";
        const copy = statCopy[key];
        name.append(document.createTextNode(copy.label), infoIcon(copy.tooltip));
        const val = document.createElement("div");
        val.className = "stat-value";
        val.textContent = statValue(key, value);
        card.append(name, val);
        const badgeSpec = statBadge(key, value);
        if (badgeSpec) {
          const badge = document.createElement("div");
          badge.className = `badge ${badgeSpec[0]}`;
          badge.textContent = badgeSpec[1];
          card.append(badge);
        }
        return card;
      }));
    }

    function sortedVideos() {
      const videos = [...((state.pack && state.pack.videos) || [])];
      const dir = state.sortDir === "asc" ? 1 : -1;
      return videos.sort((a, b) => {
        const left = a[state.sortKey];
        const right = b[state.sortKey];
        if (typeof left === "number" && typeof right === "number") return (left - right) * dir;
        return String(left ?? "").localeCompare(String(right ?? ""), "zh-CN") * dir;
      });
    }

    function td(text) {
      const cell = document.createElement("td");
      cell.textContent = text;
      return cell;
    }

    function renderTable() {
      if (!state.pack || !state.pack.videos || state.pack.videos.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.className = "empty";
        cell.colSpan = 7;
        cell.textContent = "👆 输入一个选题点\\"开始扫描\\",或点上方\\"看示例\\"先体验。";
        row.append(cell);
        tbody.replaceChildren(row);
        return;
      }

      const rows = [];
      for (const video of sortedVideos()) {
        const row = document.createElement("tr");

        const expandCell = document.createElement("td");
        const expand = document.createElement("button");
        expand.className = "expand";
        expand.type = "button";
        expand.title = "点 + 看这个视频的高赞评论";
        expand.textContent = state.expanded.has(video.bvid) ? "−" : "+";
        expand.addEventListener("click", () => {
          if (state.expanded.has(video.bvid)) state.expanded.delete(video.bvid);
          else state.expanded.add(video.bvid);
          renderTable();
        });
        expandCell.append(expand);

        const titleCell = document.createElement("td");
        titleCell.className = "title-cell";
        const link = document.createElement("a");
        link.href = `https://www.bilibili.com/video/${video.bvid}`;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = video.title || video.bvid;
        titleCell.append(link);

        const queriesCell = document.createElement("td");
        const queries = document.createElement("div");
        queries.className = "queries";
        for (const query of video.queries_hit || []) {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = query;
          queries.append(tag);
        }
        queriesCell.append(queries);

        row.append(
          expandCell,
          titleCell,
          td(video.author || "-"),
          td(formatInt(video.play)),
          td(formatDate(video.pubdate)),
          td(formatAge(video.age_days)),
          queriesCell,
        );
        rows.push(row);

        if (state.expanded.has(video.bvid)) {
          const commentRow = document.createElement("tr");
          const commentCell = document.createElement("td");
          commentCell.className = "comments";
          commentCell.colSpan = 7;
          const list = document.createElement("ul");
          list.className = "comment-list";
          const comments = (state.pack.comments_by_bvid || {})[video.bvid] || [];
          if (comments.length === 0) {
            const item = document.createElement("li");
            item.className = "comment";
            item.textContent = "无热评数据";
            list.append(item);
          } else {
            for (const comment of comments) {
              const item = document.createElement("li");
              const hot = Number(comment.like || 0) >= 100;
              item.className = hot ? "comment hot" : "comment";
              const message = document.createElement("div");
              message.textContent = comment.message || "";
              const meta = document.createElement("div");
              meta.className = "comment-meta";
              meta.textContent = `${comment.uname || "匿名"} · 👍 ${formatInt(comment.like)} 赞`;
              item.append(message, meta);
              list.append(item);
            }
          }
          commentCell.append(list);
          commentRow.append(commentCell);
          rows.push(commentRow);
        }
      }
      tbody.replaceChildren(...rows);
    }

    function renderPack(pack, sourceFile = null) {
      state.pack = pack;
      state.sourceFile = sourceFile;
      state.analysis = null;
      state.analysisNotice = "";
      state.analysisError = "";
      state.analysisLoading = false;
      state.expanded.clear();
      renderStats(pack);
      renderAiAnalysis();
      renderTable();
      const count = pack.total_unique_videos ?? ((pack.videos || []).length);
      setStatus(`已加载 ${count} 个视频；查询词：${(pack.queries || []).join(" / ") || "-"}`);
      finishLoadingMotion();
      revealDashboard();
    }

    async function loadAiBackends() {
      try {
        const backends = await fetchJson("/api/ai-backends");
        state.aiBackends = Array.isArray(backends) ? backends : [];
        const selected = state.aiBackends.find((backend) => backend.selected);
        const fallback = state.aiBackends.find((backend) => backend.available) || state.aiBackends[0];
        state.selectedBackend = (selected || fallback || { key: "codex" }).key;
      } catch (error) {
        state.aiBackends = [
          { key: "codex", label: "Codex(本地)", available: false, reason: "无法读取后端状态" },
        ];
        state.selectedBackend = "codex";
      }
      renderAiAnalysis();
    }

    async function fetchJson(url, options) {
      const response = await fetch(url, options);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.error || `HTTP ${response.status}`);
      }
      return body;
    }

    async function runAiAnalysis() {
      if (!state.pack || state.analysisLoading) return;
      state.analysisLoading = true;
      state.analysisNotice = "";
      state.analysisError = "";
      renderAiAnalysis();
      const selected = state.aiBackends.find((backend) => backend.key === state.selectedBackend);
      setStatus(`AI 分析中... ${selected ? selected.label : state.selectedBackend} 正在读证据,通常需要 30-60 秒。`);
      try {
        const payload = state.sourceFile ? { file: state.sourceFile } : { pack: state.pack };
        payload.backend = state.selectedBackend;
        const result = await fetchJson("/api/analyze", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (result.available === false) {
          state.analysisNotice = result.message || result.error || "AI 后端不可用;证据看板不受影响";
          state.analysis = null;
          setStatus(state.analysisNotice);
        } else {
          state.analysis = result;
          setStatus("AI 分析完成。");
        }
      } catch (error) {
        state.analysisError = error.message || String(error);
        setStatus(state.analysisError, true);
      } finally {
        state.analysisLoading = false;
        renderAiAnalysis();
      }
    }

    renderAiAnalysis();
    loadAiBackends();

    $("collect-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      collectButton.disabled = true;
      const extra = $("extra").value.split("\\n").map((item) => item.trim()).filter(Boolean);
      const keyword = $("keyword").value.trim();
      const scanCount = (keyword ? 1 : 0) + extra.length;
      beginLoadingMotion(keyword, scanCount);
      try {
        const payload = {
          keyword,
          extra_queries: extra,
          top_comments: Number($("top-comments").value || 10),
        };
        const pack = await fetchJson("/api/collect", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        });
        renderPack(pack);
      } catch (error) {
        const message = error.message || String(error);
        setStatus(message, true);
        returnToHero(message, true);
      } finally {
        collectButton.disabled = false;
      }
    });

    async function loadDemo(filename, label) {
      clearLoadingMotion();
      setStatus(`加载示例:${label}...`);
      try {
        renderPack(await fetchJson(`/api/evidence?file=${encodeURIComponent(filename)}`), filename);
      } catch (error) {
        const message = error.message || String(error);
        setStatus(message, true);
        returnToHero(message, true);
      }
    }

    $("demo-mcp-button").addEventListener("click", () => {
      loadDemo("evidence_mcp.json", "MCP");
    });

    $("demo-claudecode-button").addEventListener("click", () => {
      loadDemo("evidence_claudecode.json", "Claude Code");
    });

    $("restart-button").addEventListener("click", () => {
      returnToHero();
    });

    // 支持 ?demo=mcp / ?demo=claudecode / ?demo=evidence_xxx.json 自动载入(可分享预览链接)
    (() => {
      const demo = new URLSearchParams(location.search).get("demo");
      if (!demo) return;
      const map = {
        mcp: ["evidence_mcp.json", "MCP"],
        claudecode: ["evidence_claudecode.json", "Claude Code"],
      };
      const [file, label] = map[demo] || [demo, demo];
      loadDemo(file, label);
    })();

    $("suffix-button").addEventListener("click", () => {
      const keyword = $("keyword").value.trim();
      if (!keyword) {
        $("keyword").focus();
        setStatus("先填一个选题关键词,再自动加常见后缀。", true);
        return;
      }
      const suffixes = ["教程", "实战", "入门", "原理", "配置"];
      const current = $("extra").value.split("\\n").map((item) => item.trim()).filter(Boolean);
      for (const suffix of suffixes) {
        const query = `${keyword} ${suffix}`;
        if (!current.includes(query)) current.push(query);
      }
      $("extra").value = current.join("\\n");
      setStatus("已自动补上常见搜法,可以直接开始扫描。");
    });

    for (const head of document.querySelectorAll("th.sortable")) {
      head.addEventListener("click", () => {
        const key = head.dataset.key;
        if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        else {
          state.sortKey = key;
          state.sortDir = key === "title" || key === "author" ? "asc" : "desc";
        }
        renderTable();
      });
    }

    $("tutorial-button").addEventListener("click", () => {
      if (typeof tutorialDialog.showModal === "function") tutorialDialog.showModal();
      else tutorialDialog.setAttribute("open", "");
    });

    $("tutorial-close").addEventListener("click", () => {
      tutorialDialog.close();
    });

    tutorialDialog.addEventListener("click", (event) => {
      if (event.target === tutorialDialog) tutorialDialog.close();
    });

    // ⓘ 点击固定 / 悬停临时 显示解释浮层;点外部或滚动关闭
    (() => {
      const tip = document.createElement("div");
      tip.className = "infotip";
      tip.hidden = true;
      document.body.appendChild(tip);
      let owner = null, pinned = false;

      function place(el) {
        const text = el.getAttribute("data-tip");
        if (!text) return;
        tip.textContent = text;
        tip.hidden = false;
        const r = el.getBoundingClientRect();
        tip.style.top = (window.scrollY + r.bottom + 8) + "px";
        const left = window.scrollX + r.left;
        tip.style.left = left + "px";
        const margin = 12;
        const maxLeft = window.scrollX + document.documentElement.clientWidth - tip.offsetWidth - margin;
        if (left > maxLeft) tip.style.left = Math.max(margin, maxLeft) + "px";
        owner = el;
      }
      function hide() { tip.hidden = true; owner = null; pinned = false; }

      document.addEventListener("click", (event) => {
        const info = event.target.closest(".info");
        if (info) {
          event.stopPropagation();
          if (pinned && owner === info) { hide(); return; }
          place(info); pinned = true;
        } else if (!event.target.closest(".infotip")) {
          hide();
        }
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && event.target.classList && event.target.classList.contains("info")) {
          event.preventDefault();
          if (pinned && owner === event.target) hide();
          else { place(event.target); pinned = true; }
        } else if (event.key === "Escape") { hide(); }
      });
      document.addEventListener("mouseover", (event) => {
        const info = event.target.closest(".info");
        if (info && !pinned) place(info);
      });
      document.addEventListener("mouseout", (event) => {
        const info = event.target.closest(".info");
        if (info && !pinned) hide();
      });
      window.addEventListener("scroll", () => { if (owner && pinned) place(owner); else if (owner) hide(); }, { passive: true });
    })();
  </script>
</body>
</html>
"""


async def index(request: Request) -> HTMLResponse:
    del request
    return HTMLResponse(HTML)


async def api_collect(request: Request) -> JSONResponse:
    try:
        payload = await _read_payload(request)
        keyword = str(payload.get("keyword", "")).strip()
        extra_queries = _split_extra_queries(payload.get("extra_queries"))
        top_comments = _parse_top_comments(payload.get("top_comments", 10))
        if not keyword:
            return JSONResponse({"error": "keyword must not be empty"}, status_code=400)
        if top_comments < 0:
            return JSONResponse({"error": "top_comments must be >= 0"}, status_code=400)

        pack = await collect_evidence(
            keyword,
            extra_queries=extra_queries,
            top_comments=top_comments,
        )
        return JSONResponse(_to_jsonable(pack))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"collect failed: {exc}"}, status_code=500)


async def api_evidence(request: Request) -> JSONResponse:
    filename = request.query_params.get("file", "evidence_mcp.json")
    try:
        path = _resolve_evidence_file(filename)
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": f"file not found: {filename}"}, status_code=404)
    except json.JSONDecodeError as exc:
        return JSONResponse({"error": f"invalid json: {exc}"}, status_code=400)
    return JSONResponse(data)


async def api_ai_backends(request: Request) -> JSONResponse:
    del request
    selected = analyzer.resolve_backend()
    items = []
    for item in analyzer.backend_status():
        row = dict(item)
        row["selected"] = row.get("key") == selected
        items.append(row)
    return JSONResponse(items)


async def api_analyze(request: Request) -> JSONResponse:
    try:
        payload = await _read_payload(request)
        backend = analyzer.resolve_backend(payload.get("backend"))
        if "pack" in payload:
            pack = payload["pack"]
            if not isinstance(pack, dict):
                return JSONResponse({"error": "pack must be an object"}, status_code=400)
        elif "file" in payload:
            filename = str(payload.get("file") or "")
            path = _resolve_evidence_file(filename)
            pack = json.loads(path.read_text(encoding="utf-8"))
        else:
            return JSONResponse({"error": "body must include file or pack"}, status_code=400)

        status = _status_for_backend(backend)
        if status is not None and not status.get("available"):
            reason = str(status.get("reason") or AI_UNAVAILABLE_MESSAGE)
            message = f"{status.get('label') or backend} 后端不可用:{reason};证据看板不受影响"
            return JSONResponse({"available": False, "error": message, "message": message})

        result = analyzer.analyze_evidence(pack, backend=backend)
        return JSONResponse(opportunity.merge_result(pack, result))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse({"error": "file not found"}, status_code=404)
    except json.JSONDecodeError as exc:
        return JSONResponse({"error": f"invalid json: {exc}"}, status_code=400)
    except RuntimeError as exc:
        message = f"{exc};证据看板不受影响"
        return JSONResponse({"available": False, "error": message, "message": message})
    except Exception as exc:
        return JSONResponse({"error": f"analyze failed: {exc}"}, status_code=500)


def _status_for_backend(backend: str) -> dict[str, object] | None:
    for item in analyzer.backend_status():
        if item.get("key") == backend:
            return item
    return None


def _resolve_evidence_file(filename: str) -> Path:
    path = Path(filename)
    if path.name != filename or not filename.startswith("evidence_") or not filename.endswith(".json"):
        raise ValueError("file must be a local evidence_*.json filename")
    if filename in BUILTIN_DEMO_FILES:
        return EXAMPLES_DIR / filename
    return Path.cwd() / filename


async def _read_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("json body must be an object")
        return payload
    form = await request.form()
    return dict(form)


def _split_extra_queries(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.splitlines()
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [str(value)]
    queries: list[str] = []
    for item in raw_items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    return queries


def _parse_top_comments(value: object) -> int:
    if value is None or value == "":
        return 10
    return int(value)


def _to_jsonable(value: object) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        data = value.to_dict()
    elif isinstance(value, dict):
        data = value
    else:
        raise TypeError(f"unsupported collect result: {type(value)!r}")
    if not isinstance(data, dict):
        raise TypeError("collect result must serialize to a dict")
    return data


app = Starlette(
    debug=False,
    routes=[
        Route("/", index, methods=["GET"]),
        Route("/api/collect", api_collect, methods=["POST"]),
        Route("/api/evidence", api_evidence, methods=["GET"]),
        Route("/api/ai-backends", api_ai_backends, methods=["GET"]),
        Route("/api/analyze", api_analyze, methods=["POST"]),
    ],
)


def main() -> None:
    uvicorn.run("bili_topic_radar.web:app", host="127.0.0.1", port=8848, log_level="info")


if __name__ == "__main__":
    main()
