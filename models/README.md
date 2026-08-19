# 模型目录

模型权重文件（几 GB）**不进 git**，需单独放置。

## 目录规范

```
models/
├── asr/
│   └── asr-v1.0/
│       ├── model.yaml    # 必填元数据（见 docs/模型集成规范）
│       └── ...权重文件
└── tts/
    └── tts-v2.0/
        ├── model.yaml
        └── ...权重文件
```

## 模型来源

| 模型 | 现成文件位置 | 大小 |
|---|---|---|
| Qwen3-ASR 微调成品 | `/home/rat/dialect_asr_system/finetune/output/final/` | 3.9G |
| CosyVoice2 微调成品 | `/home/rat/dialect_asr_system/tts/output/final/` | 3.8G |

把模型目录拷贝到这里，并按 `docs/2026-08-19-模型集成规范.md` 补一个 `model.yaml`。
