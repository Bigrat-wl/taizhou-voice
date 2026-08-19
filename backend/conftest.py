"""pytest 共享配置：将 backend 根目录加入 sys.path，保证 `import app` 可用。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
