/**
 * useRecorder —— 浏览器录音封装（方案 A：MediaRecorder → webm）。
 *
 * 挑战赛（#13）与转写页（#15）共用同一套录音逻辑，故抽成 composable。
 * - 只负责「采集→生成 Blob」，不负责上传/识别（由页面决定如何处理 Blob）。
 * - 兼容不支持 MediaRecorder 的环境（如部分桌面浏览器），对外暴露 isSupported。
 */
import { computed, shallowRef, onScopeDispose } from 'vue'

/** 录制产物的 MIME 类型（webm/opus 为 Chrome/Edge/Firefox 通用格式） */
const RECORD_MIME = 'audio/webm;codecs=opus'

export function useRecorder() {
  /** 当前是否正在录制 */
  const isRecording = shallowRef(false)
  /** 累计录制时长（秒，仅展示用） */
  const elapsed = shallowRef(0)
  /** 浏览器是否支持录音 */
  const isSupported = shallowRef(true)
  /** 录音失败/不可用的原因（为 null 表示无异常） */
  const errorMsg = shallowRef<string | null>(null)

  const isRecordingLabel = computed(() =>
    isRecording.value ? `${elapsed.value}s` : '',
  )

  let mediaRecorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let chunks: Blob[] = []
  let timer: ReturnType<typeof setInterval> | null = null
  /** 使 stop() 返回的 Promise 与本段录制绑定 */
  let resolveStop: ((blob: Blob) => void) | null = null
  let rejectStop: ((reason: Error) => void) | null = null

  function clearTimer() {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  /** 释放麦克风与录制器资源 */
  function teardown() {
    clearTimer()
    chunks = []
    resolveStop = null
    rejectStop = null
    if (mediaRecorder) {
      try {
        if (mediaRecorder.state !== 'inactive') mediaRecorder.stop()
      } catch {
        /* 忽略释放时的异常 */
      }
      mediaRecorder = null
    }
    if (stream) {
      stream.getTracks().forEach((track) => track.stop())
      stream = null
    }
  }

  /** 请求麦克风并开始录制。失败时抛出 Error（含原因）。 */
  async function start(): Promise<void> {
    if (typeof MediaRecorder === 'undefined') {
      isSupported.value = false
      errorMsg.value = '当前浏览器不支持录音，请使用上传音频或换用 Chrome/Edge。'
      throw new Error(errorMsg.value)
    }
    if (isRecording.value) return

    errorMsg.value = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      errorMsg.value = '无法访问麦克风，请检查浏览器权限设置。'
      throw new Error(errorMsg.value)
    }

    try {
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported(RECORD_MIME)
          ? RECORD_MIME
          : undefined,
      })
    } catch {
      // mimeType 组合仍可能抛错，退回默认编码
      mediaRecorder = new MediaRecorder(stream)
    }

    chunks = []
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunks.push(event.data)
    }
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, {
        type: mediaRecorder?.mimeType || RECORD_MIME,
      })
      clearTimer()
      isRecording.value = false
      elapsed.value = 0
      // 释放麦克风
      stream?.getTracks().forEach((track) => track.stop())
      stream = null
      if (resolveStop) resolveStop(blob)
      resolveStop = null
      rejectStop = null
    }
    mediaRecorder.onerror = () => {
      if (rejectStop) {
        rejectStop(new Error('录音过程中出错，请重试。'))
        resolveStop = null
        rejectStop = null
      }
      teardown()
      isRecording.value = false
      elapsed.value = 0
      errorMsg.value = '录音出错，请重试。'
    }

    mediaRecorder.start()
    isRecording.value = true
    elapsed.value = 0
    timer = setInterval(() => {
      elapsed.value += 1
    }, 1000)
  }

  /** 停止录制并返回音频 Blob（webm）。若尚未开始录制则抛出 Error。 */
  function stop(): Promise<Blob> {
    if (!isRecording.value || !mediaRecorder || mediaRecorder.state === 'inactive') {
      return Promise.reject(new Error('当前没有正在进行的录音。'))
    }

    return new Promise<Blob>((resolve, reject) => {
      resolveStop = resolve
      rejectStop = reject
      try {
        mediaRecorder!.stop()
      } catch (err) {
        reject(err instanceof Error ? err : new Error('停止录音失败。'))
        rejectStop = null
        resolveStop = null
        teardown()
      }
    })
  }

  /** 取消/放弃当前录音，不产出结果。 */
  function cancel() {
    teardown()
    isRecording.value = false
    elapsed.value = 0
  }

  onScopeDispose(() => {
    // 确保离开页面/作用域时释放麦克风
    if (isRecording.value) {
      teardown()
      isRecording.value = false
      elapsed.value = 0
    }
  })

  return {
    isRecording,
    isRecordingLabel,
    elapsed,
    isSupported,
    errorMsg,
    start,
    stop,
    cancel,
  }
}
