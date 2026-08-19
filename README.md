# 泰州方言通（taizhou-voice）

泰州方言的「挑战赛 + 语音识别 + 语音合成 + 音频互转」Web 应用。基于 Qwen3-ASR（识别）与 CosyVoice2（合成）模型，挑战赛以游戏化方式收集方言语音数据。

## 功能

| 功能 | 说明 | 依赖模型 |
|---|---|---|
| 挑战赛 | 刷句子 → 录音 → 评分 → 排行榜 | Qwen3-ASR |
| 转写 | 方言语音 → 普通话文本 | Qwen3-ASR |
| TTS | 文本 → 方言语音 | CosyVoice2 |
| 音频互转 | 方言语音 ↔ 普通话音频 | Qwen3-ASR + CosyVoice2 |

## 技术栈

- 前端：Nuxt 4 + Vue 3
- 后端：FastAPI (Python)
- 数据库：SQLite + SQLAlchemy
- 音频存储：本地目录（后期迁腾讯云 COS）
- 模型：Qwen3-ASR-1.7B（识别）、CosyVoice2-0.5B（合成）

## 目录结构（目标）

```
taizhou-voice/
├── README.md              # 本文件
├── .gitignore
├── docs/                  # 设计文档
├── backend/               # FastAPI 后端
│   ├── requirements.txt
│   ├── config.py          # 设备/精度/模型路径 配置（换环境只改这里）
│   ├── app.py             # 服务入口
│   └── services/          # AI 模型封装（识别/合成/评分）
├── frontend/              # Nuxt 4 前端
└── models/                # 模型权重文件（几 GB，不进 git）
    ├── asr/               # Qwen3-ASR 各版本
    └── tts/               # CosyVoice2 各版本
```

## 环境要求

### 硬件

| 场景 | GPU | 显存 | 说明 |
|---|---|---|---|
| 开发（仅 ASR） | 不需要 | — | CPU 可跑识别，5~7 秒/条 |
| 演示（全功能） | NVIDIA | ≥ 8GB | ASR 约 4G + TTS 约 2G |
| 训练 | NVIDIA | ≥ 16GB | 微调模型用 |

> TTS 合成**必须 GPU**，CPU 跑不了。

### 软件

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | 3.11 / 3.12 | 后端 |
| uv | 最新 | 包管理 + 虚拟环境 |
| Node.js | 20+ | 前端 |
| ffmpeg | 任意 | 录音转 16kHz 单声道 WAV |
| NVIDIA 驱动 + CUDA | 见下方 | GPU 场景必需 |

### GPU 场景的 torch 安装（关键）

GPU 版 torch 必须匹配显卡的 CUDA 版本，这是最容易出错的地方。三种装法二选一（以实际 `nvidia-smi` 显示的 CUDA 版本为准）：

```bash
# CUDA 11.8 的显卡
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1 的显卡
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu121

# 无 GPU（CPU 推理）
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu
```

## 部署流程（拿到代码 → 跑起来）

### 第 1 步：克隆仓库

```bash
git clone <仓库地址>
cd taizhou-voice
```

### 第 2 步：安装系统依赖

```bash
# Ubuntu / Debian / WSL
sudo apt install ffmpeg -y

# macOS
brew install ffmpeg
```

### 第 3 步：放置模型文件

模型文件（几 GB）**不进 git**，需单独拷贝到 `models/` 目录：

```
models/
├── asr/
│   └── asr-v1.0/           # Qwen3-ASR 微调成品
│       ├── config.json
│       ├── model.safetensors
│       ├── model.yaml      # 元数据（契约，见 docs）
│       └── ...
└── tts/
    └── tts-v2.0/           # CosyVoice2 微调成品
        ├── llm.pt
        ├── flow.pt
        ├── hift.pt
        ├── model.yaml
        └── ...
```

> 模型目录规范与 `model.yaml` 字段说明见 `docs/` 下的《模型集成规范》。

### 第 4 步：安装后端依赖

```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate

# 先按环境装 torch（见上文「GPU 场景的 torch 安装」）
uv pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cpu

# 再装其余依赖
uv pip install -r requirements.txt
```

### 第 5 步：改配置（换环境只改这一个文件）

编辑 `backend/config.py`：

```python
INFERENCE = {
    "device": "cpu",        # 改成 "cuda:0"（有 GPU 时）
    "dtype": "float32",     # 改成 "bfloat16"（有 GPU 时）
}

MODEL_DIR = "models"        # 模型根目录
ACTIVE_ASR = "asr-v1.0"     # 当前激活的 ASR 版本
ACTIVE_TTS = "tts-v2.0"     # 当前激活的 TTS 版本
```

### 第 6 步：启动后端

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

验证：

```bash
curl http://127.0.0.1:8000/api/health
```

### 第 7 步：启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:3000`。

## 模型更换与版本管理（简述）

1. 新模型放到 `models/asr/` 或 `models/tts/` 下，附 `model.yaml` 元数据
2. 改 `config.py` 里的 `ACTIVE_ASR` / `ACTIVE_TTS` 指向新版本
3. 重启后端即可，代码无需改动

旧版本保留在磁盘上不删除，可随时改回激活指针回滚。详见 `docs/` 下的《模型集成规范》。

## 常见问题

- **`import torch` 报 `_ARRAY_API not found`**：numpy 版本不对，用 torch 2.7.1 配 numpy 1.x。
- **TTS 接口报「TTS 服务不可用」**：TTS 需要 GPU，确认 `nvidia-smi` 能显示显卡，且 `config.py` 里 `device` 已改 `cuda:0`。
- **浏览器录音无反应**：浏览器需允许麦克风权限；后端需已装 ffmpeg。
- **换电脑跑不起来**：先检查 torch 是否装成和显卡匹配的 CUDA 版本（见「GPU 场景的 torch 安装」）。
