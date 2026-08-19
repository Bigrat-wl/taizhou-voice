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

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | 3.11 / 3.12 | 后端 |
| uv | 最新 | 后端包管理 |
| Node.js | 20+ | 前端 |
| ffmpeg | 任意 | 音频转码 |
| NVIDIA 驱动 + CUDA | 按显卡 | 仅 GPU 场景需要 |

### GPU 场景的 torch 安装（最易出错）

GPU 版 torch 必须匹配显卡的 CUDA 版本。按 `nvidia-smi` 显示的 CUDA 版本选一种：

```bash
# CUDA 11.8
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu121

# 无 GPU（CPU）
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu
```

## 二、部署步骤

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd taizhou-voice
```

### 2. 装系统依赖（ffmpeg）

```bash
# Ubuntu / Debian / WSL
sudo apt install ffmpeg -y

# macOS
brew install ffmpeg
```

### 3. 放置模型文件

模型权重（几 GB）**不进 git**，需单独拷贝到 `models/`：

```
models/
├── asr/
│   └── asr-v1.0/          # Qwen3-ASR 微调成品（含 model.yaml）
└── tts/
    └── tts-v2.0/          # CosyVoice2 微调成品（含 model.yaml）
```

`model.yaml` 字段规范见 `docs/`《模型集成规范》。

### 4. 启动后端

```bash
cd backend
uv sync                     # 按 pyproject.toml 安装依赖
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

可用环境变量覆盖模型与设备（默认 CPU）：

```bash
QWEN3_ASR_MODEL_DIR=/path/to/model ASR_DEVICE=cuda:0 uv run uvicorn app.main:app --port 8000
```

验证：

```bash
curl http://127.0.0.1:8000/health
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:3000`。

## 三、常见问题

- **`import torch` 报 `_ARRAY_API not found`**：numpy 版本与 torch 不匹配，用 torch 2.7.1 配 numpy 1.x。
- **TTS 不可用**：TTS 需要 GPU，确认 `nvidia-smi` 能显示显卡，且后端用 `ASR_DEVICE=cuda:0` 启动。
- **浏览器录音无反应**：允许麦克风权限；确认后端已装 ffmpeg。
- **换电脑跑不起来**：先查 torch 是否装成与显卡匹配的 CUDA 版本（见上文）。
