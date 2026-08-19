# 泰州方言通后端

FastAPI + Qwen3-ASR（CPU, float32）。

## 安装

```bash
cd backend && uv sync
```

## 启动

```bash
cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 调用

```bash
curl -X POST http://127.0.0.1:8000/api/asr -F "audio=@/path/to/audio.wav"
```
