#!/bin/bash
# setup-torch.sh — 自动检测 GPU 环境，安装对应版本的 torch
#
# 用法：cd backend && bash scripts/setup-torch.sh
#
# 逻辑：
#   1. 检查 nvidia-smi 是否可用（有 GPU）
#   2. 如果有 GPU，读取 CUDA 版本
#   3. 根据 CUDA 版本选择对应的 torch 源
#   4. 用 uv pip install 安装（覆盖 pyproject.toml 里的 torch）

set -e

echo "=== Torch 环境自动配置 ==="

# 尝试获取 GPU 信息
GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null || true)

if [ -z "$GPU_INFO" ]; then
    echo "未检测到 NVIDIA GPU，安装 CPU 版 torch"
    INDEX_URL="https://download.pytorch.org/whl/cpu"
else
    echo "检测到 GPU: $GPU_INFO"
    
    # 获取 CUDA 版本（从 nvidia-smi 输出中提取）
    CUDA_VERSION=$(nvidia-smi | grep -oP 'CUDA Version: \K[0-9]+\.[0-9]+' 2>/dev/null || true)
    
    if [ -z "$CUDA_VERSION" ]; then
        echo "无法检测 CUDA 版本，回退到 CPU 版"
        INDEX_URL="https://download.pytorch.org/whl/cpu"
    else
        echo "CUDA 版本: $CUDA_VERSION"
        
        # 根据 CUDA 主版本选择 torch 源
        CUDA_MAJOR=$(echo "$CUDA_VERSION" | cut -d. -f1)
        CUDA_MINOR=$(echo "$CUDA_VERSION" | cut -d. -f2)
        
        if [ "$CUDA_MAJOR" -ge 12 ]; then
            echo "CUDA 12.x → 安装 cu121 版 torch"
            INDEX_URL="https://download.pytorch.org/whl/cu121"
        elif [ "$CUDA_MAJOR" -ge 11 ] && [ "$CUDA_MINOR" -ge 8 ]; then
            echo "CUDA 11.8+ → 安装 cu118 版 torch"
            INDEX_URL="https://download.pytorch.org/whl/cu118"
        else
            echo "CUDA 版本过低 ($CUDA_VERSION)，回退到 CPU 版"
            INDEX_URL="https://download.pytorch.org/whl/cpu"
        fi
    fi
fi

echo ""
echo "安装源: $INDEX_URL"
echo "安装中..."

uv pip install torch torchaudio --index-url "$INDEX_URL"

echo ""
echo "=== 验证 ==="
uv run python -c "
import torch
print(f'PyTorch 版本: {torch.__version__}')
print(f'CUDA 可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'CUDA 版本: {torch.version.cuda}')
"
