# 泰州方言通（taizhou-voice）— 部署教程

泰州方言「挑战赛 + 语音识别 + 语音合成 + 音频互转」Web 应用。

> 本文档只讲**怎么部署跑起来**，项目详细介绍另见 `docs/`。
> ⚠️ 项目开发中，本教程随开发持续更新，以最新提交为准。

## 一、环境要求

### 硬件

| 场景 | GPU | 显存 | 说明 |
|---|---|---|---|
| 开发（仅 ASR 识别） | 不需要 | — | CPU 可跑，5~7 秒/条 |
| 演示（全功能含 TTS） | NVIDIA | ≥ 8GB | ASR 约 4G + TTS 约 2G |
| 训练 | NVIDIA | ≥ 16GB | 微调模型用 |

> TTS 合成**必须 GPU**，CPU 跑不了。

### 软件

| 工具 | 版本 | 用途 | 安装方式 |
|---|---|---|---|
| Python | 3.11 / 3.12 | 后端 | 系统自带或官网下载 |
| uv | 最新 | 后端包管理 | `pip install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20+ | 前端 | 官网下载或 nvm 管理 |
| pnpm | 最新 | 前端包管理 | `npm install -g pnpm` |
| ffmpeg | 任意 | 音频转码 | 见下文安装方式 |
| NVIDIA 驱动 + CUDA | 按显卡 | 仅 GPU 场景需要 | — |

### 环境隔离说明（不影响系统）

本项目**所有依赖都在项目目录内**，不会污染系统环境：

| 层 | 隔离方式 | 依赖位置 | 删掉会怎样 |
|---|---|---|---|
| Python | uv 自动创建 `.venv/` 虚拟环境 | `backend/.venv/` | Python 依赖全清，系统 Python 不受影响 |
| Node | pnpm 自动创建 `node_modules/` | `frontend/node_modules/` | Node 依赖全清，系统 Node 不受影响 |
| 模型 | 项目内 `models/` 目录 | `models/` | 模型全清，不影响其他项目 |

**简单说**：clone 下来 → `uv sync` + `pnpm install` → 所有依赖装在项目里 → 删掉项目文件夹就干净了，系统里不留任何痕迹。

> 如果系统没有 Python/Node，需要先安装。推荐用系统包管理器（apt/brew/winget）或官网安装包，装完后系统就有了，跟本项目无关。

### GPU 场景的 torch 安装（最易出错）

**pyproject.toml 不写 torch 依赖**，避免 `uv sync` 装 CPU 版。torch 由专门的脚本按 GPU 环境单独安装。

```bash
cd backend

# 第一步：装除 torch 外的所有依赖
uv sync

# 第二步：自动检测 GPU 环境，安装对应版本的 torch
bash scripts/setup-torch.sh
```

脚本会自动：
1. 检测是否有 NVIDIA GPU
2. 如果有，读取 CUDA 版本
3. 安装对应版本的 torch：
   - CUDA 12.8+（RTX 50 系列）→ nightly cu128 版
   - CUDA 12.x → cu121 版
   - CUDA 11.8+ → cu118 版
   - 无 GPU → CPU 版

**手动安装**（如果脚本不适用）：

```bash
# RTX 50 系列（CUDA 12.8）
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# RTX 20/30/40 系列（CUDA 12.1）
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 无 GPU（CPU）
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

> ⚠️ 装完 torch 后，启动后端必须用 `uv run --no-sync`，否则 uv 会把 torch 覆盖回 CPU 版。

## 二、部署步骤

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd taizhou-voice
```

**关于版本管理的说明**：

- `git clone` 只会在当前目录创建 `taizhou-voice/` 文件夹和 `.git/` 子目录，**不会影响系统全局配置**
- 所有 git 操作（commit、push 等）都限制在项目目录内，不会动到别人的 `.gitconfig` 或其他项目
- 如果不想用 git，也可以直接下载 ZIP 解压，功能完全一样
- `.gitignore` 已配置好，以下文件**不会被提交**：
  - 模型权重（`models/`）
  - 数据库文件（`*.db`）
  - 音频文件（`data/audio/`）
  - 依赖目录（`node_modules/`、`.venv/`）
  - 环境变量文件（`.env`）

> 简单说：clone 下来就是一个独立文件夹，删掉就干净了，不会在系统里留下任何痕迹。

### 2. 安装 ffmpeg（音频转码必需）

项目用 ffmpeg 将浏览器录音（webm/ogg 等）转为 16kHz WAV。**必须安装**，否则录音功能不可用。

**方式一：系统安装（推荐）**

```bash
# Ubuntu / Debian / WSL
sudo apt install ffmpeg -y

# macOS
brew install ffmpeg

# Windows（任选一种）
#   1. winget install ffmpeg
#   2. choco install ffmpeg
#   3. 去 https://ffmpeg.org/download.html 下载，解压后把 bin 目录加到 PATH
```

**方式二：仅项目使用（Windows 不想改系统 PATH）**

把 `ffmpeg.exe` 和 `ffprobe.exe` 放到项目目录下：

```
taizhou-voice/
├── bin/
│   ├── ffmpeg.exe
│   └── ffprobe.exe
├── backend/
└── frontend/
```

然后修改 `backend/app/main.py` 和 `backend/app/routers/score.py` 中的 ffmpeg 调用路径：

```python
# 改前
["ffmpeg", "-y", "-i", src_path, ...]

# 改后
import os
FFMPEG = os.path.join(os.path.dirname(__file__), "..", "..", "bin", "ffmpeg.exe")
[FFMPEG, "-y", "-i", src_path, ...]
```

> 或者用 Python 包 `imageio-ffmpeg`（自带 ffmpeg），但需改代码调用方式。

### 3. 放置模型文件

模型权重（几 GB）**不进 git**，需单独拷贝到 `models/`：

```
models/
├── asr/
│   └── final/              # Qwen3-ASR 微调成品
│       ├── config.json
│       ├── model.safetensors
│       ├── tokenizer.json
│       └── ...
└── tts/
    └── final/              # CosyVoice2 微调成品
        ├── llm.pt
        ├── flow.pt
        └── hipt.pt
```

**模型来源**：从开发机 `/home/rat/dialect_asr_system/` 目录拷贝：

```
开发机路径                          → 项目内路径
─────────────────────────────────────────────────
dialect_asr_system/finetune/output/final  → models/asr/final/
dialect_asr_system/tts/output/final       → models/tts/final/
```

### 4. 配置模型路径

修改 `backend/app/main.py` 中的默认路径，指向项目内的 `models/` 目录：

```python
# 改前（硬编码开发机路径）
MODEL_DIR = os.getenv("QWEN3_ASR_MODEL_DIR", "/home/rat/dialect_asr_system/finetune/output/final")
TTS_MODEL_DIR = os.getenv("TTS_MODEL_DIR", "/home/rat/dialect_asr_system/tts/output/final")

# 改后（指向项目内 models/ 目录）
_model_root = os.path.join(os.path.dirname(__file__), "..", "..", "models")
MODEL_DIR = os.getenv("QWEN3_ASR_MODEL_DIR", os.path.join(_model_root, "asr", "final"))
TTS_MODEL_DIR = os.getenv("TTS_MODEL_DIR", os.path.join(_model_root, "tts", "final"))
```

同步修改 `backend/app/services/asr_service.py` 和 `backend/app/services/tts_service.py` 中的默认路径。

> 这样改完后，不需要设置任何环境变量，只要把模型放到 `models/` 目录即可。

### 5. 启动后端

```bash
cd backend
uv sync                             # 第一步：装除 torch 外的所有依赖
bash scripts/setup-torch.sh         # 第二步：按 GPU 环境装 torch
uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000  # 第三步：启动（--no-sync 防止覆盖 torch）
```

验证：

```bash
curl http://127.0.0.1:8000/health
```

### 6. 初始化数据（首次 / 删库重建后必做）

后端需要种子数据才能正常运行，包括句子库和测试账号：

```bash
cd backend

# 导入 27 句参考句子
uv run python -m app.seed_sentences

# 创建测试账号 test@test.com / 123456
uv run python scripts/seed_test_user.py
```

> ⚠️ 删除 `backend/data/` 下的 SQLite 数据库后，必须重新执行上述命令。

### 7. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

浏览器访问 `http://localhost:3000`。

### 8. Windows 部署完整流程（汇总）

```powershell
# 1. 克隆仓库
git clone <仓库地址>
cd taizhou-voice

# 2. 安装 ffmpeg（任选一种）
winget install ffmpeg
# 或把 ffmpeg.exe 放到 bin/ 目录（见上文）

# 3. 放置模型（从开发机拷贝）
# models/asr/final/  ← 开发机的 dialect_asr_system/finetune/output/final
# models/tts/final/  ← 开发机的 dialect_asr_system/tts/output/final

# 4. 修改默认路径（见第4步）

# 5. 安装后端依赖 + 配置 torch
cd backend
pip install uv
uv sync
bash scripts/setup-torch.sh   # 自动检测 GPU，安装对应版本 torch

# 6. 安装前端依赖
cd ..\frontend
npm install -g pnpm
pnpm install

# 7. 初始化数据
cd ..\backend
uv run --no-sync python -m app.seed_sentences
uv run --no-sync python scripts\seed_test_user.py

# 8. 启动后端（--no-sync 防止 uv 覆盖 torch）
uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000

# 9. 启动前端（新终端）
cd ..\frontend
pnpm dev
```

## 三、常见问题

- **`import torch` 报 `_ARRAY_API not found`**：numpy 版本与 torch 不匹配，用 torch 2.7.1 配 numpy 1.x。
- **TTS 不可用**：TTS 需要 GPU，确认 `nvidia-smi` 能显示显卡。
- **`uv run` 后 torch 变回 CPU 版**：必须用 `uv run --no-sync`，否则 uv 会按 pyproject.toml 重新安装依赖。
- **浏览器录音无反应**：允许麦克风权限；确认后端已装 ffmpeg。
- **浏览器录音格式是 webm**：正常现象，后端会自动调用 ffmpeg 转码为 16kHz WAV，无需前端处理。
- **前端代理 404**：Nuxt 4 使用 `nitro.devProxy` 配置代理（不是 `devServer.proxy`），检查 `nuxt.config.ts` 的 `nitro` 字段。
- **删库重建后功能异常**：数据库重建后必须重新 seed（参考第六步），否则句子库为空、无测试账号。
- **Windows 下 ffmpeg 找不到**：确认 ffmpeg 在 PATH 中，或按「方式二」放到项目 `bin/` 目录。
- **Windows 路径问题**：代码中用 `os.path.join()` 拼接路径，Windows/Linux 通用，无需手动处理斜杠。
