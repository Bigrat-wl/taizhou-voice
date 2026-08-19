# 项目协作规则

> 决策对话（诸葛）规则已迁移到全局 `~/.config/opencode/AGENTS.md`，本文件只写 taizhou-voice 项目特有的约定。

## 开发服务器

- 开发服务器的启动与关闭**统一由用户操作**，不要由 AI 自行启动、重启或关闭。
- 后端 FastAPI / 前端 Nuxt 都是热更新的，用户需要一直开着页面观察效果；频繁启停会打断观察。
- 如需让用户查看改动，告知**用户手动运行的命令和端口**，让用户自己启动。
- 不要执行 `uv run uvicorn ...`、`pnpm dev`、`nuxt dev` 之类的启动命令，也不要 `pkill` 相关进程。

## 项目结构

- 非 monorepo：`backend/`（Python FastAPI）与 `frontend/`（Nuxt 4）平级，各自独立管理依赖。
- 前端请求 `/api/**` 在开发环境由 Nuxt devServer proxy 转发到后端 `:8000`，部署期靠后端 CORS。
- `models/` 放模型权重（不进 git），`backend/data/` 放 SQLite 库与音频文件（不进 git）。

## 技术栈约定

- 后端：Python 3.11/3.12 + FastAPI + SQLAlchemy + SQLite，包管理 uv。
- 前端：Nuxt 4 + Vue 3（Composition API + `<script setup>`）+ TypeScript + Tailwind + @nuxt/icon（Lucide），包管理 pnpm。
- 模型解耦成独立 service 层，换模型只改 service，接口与页面不动。

## 提交规范

- Conventional Commits + 中文描述：`feat` / `fix` / `chore` / `docs` / `refactor`。
- scope 标前后端：`feat(backend)` / `feat(frontend)` / `docs`。
- 模型权重、数据库文件、音频文件一律不进 git（`.gitignore` 已覆盖）。

## 文档与任务书

- 任务书（诸葛产物）放 `docs/YYYY-MM-DD-<topic>-design.md`。
- 进度追踪 `docs/YYYY-MM-DD-开发进度.md`，完成一项就更新状态与日志。
- 长期参考文档：`docs/操作手册.md`（命令/流程）、`docs/API契约.md`（接口对齐）、`docs/数据模型.md`（表结构）。

## 关键原则

- 只复用模型权重（wav2vec2-hailing / Qwen3-ASR / CosyVoice2），功能代码不参考 `hailing_asr` 与 `dialect_asr_system`。
- 音频统一 16kHz 单声道 WAV，上传后后端转码。
- 评分先沿用「识别文本 ↔ 参考文本相似度」思路，三维评分（发音/声调/口音）后置。
