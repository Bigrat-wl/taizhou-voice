"""冒烟测试：不启动服务器，直接验证模型加载 + 识别一条音频。"""

import sys
import time

sys.path.insert(0, "/home/rat/taizhou-voice/backend")

from app.services.asr_service import Qwen3ASRService  # noqa: E402

AUDIO = "/home/rat/dialect_asr_system/data/audio/周1.WAV"


def main() -> None:
    service = Qwen3ASRService()
    t0 = time.time()
    service.load()
    print(f"[smoke] model loaded in {time.time() - t0:.1f}s", flush=True)

    t0 = time.time()
    text = service.transcribe_file(AUDIO)
    print(f"[smoke] transcribe in {time.time() - t0:.1f}s", flush=True)
    print(f"[smoke] RESULT: {text!r}", flush=True)
    assert text.strip(), "识别结果为空"
    print("[smoke] OK", flush=True)


if __name__ == "__main__":
    main()