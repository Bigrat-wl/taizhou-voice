<script setup lang="ts">
import { computed, shallowRef, useTemplateRef } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'

const item = navItems.find((n) => n.to === '/transcribe')!

// —— 录音（方案 A：MediaRecorder → webm）——
const {
  isRecording,
  isRecordingLabel,
  isSupported,
  errorMsg: recorderError,
  start: startRecording,
  stop: stopRecording,
} = useRecorder()

const fileInput = useTemplateRef<HTMLInputElement>('fileInput')

/** 待转写音频：录音 Blob 或上传的文件 */
const pendingBlob = shallowRef<Blob | null>(null)
const pendingName = shallowRef('')

/** 待转写音频的临时播放地址（随 pendingBlob 自动创建/释放） */
const { url: previewUrl } = useBlobUrl(pendingBlob)

/** 识别状态 */
const recognizing = shallowRef(false)
/** 识别结果文本（谐音字） */
const resultText = shallowRef('')
/** 普通话翻译结果 */
const resultMandarin = shallowRef('')
/** 请求错误信息（后端 detail 或本地提示） */
const errorText = shallowRef('')

/** 是否有可提交的音频 */
const hasAudio = computed(() => pendingBlob.value !== null)
/** 录音或识别进行中时禁用按钮 */
const busy = computed(() => isRecording.value || recognizing.value)

/** 将 Blob 作为当前待提交音频（记录文件名） */
function setPending(blob: Blob, name: string) {
  pendingBlob.value = blob
  pendingName.value = name
  resultText.value = ''
  resultMandarin.value = ''
  errorText.value = ''
}

/** 开始 / 结束录音 */
async function toggleRecording() {
  if (isRecording.value) {
    try {
      const blob = await stopRecording()
      setPending(blob, `录音-${new Date().toLocaleTimeString('zh-CN', { hour12: false })}.webm`)
    } catch (err) {
      errorText.value = err instanceof Error ? err.message : '录音失败。'
    }
    return
  }
  try {
    await startRecording()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '无法开始录音。'
  }
}

/** 选择上传文件 */
function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  setPending(file, file.name)
}

/** 提交到 POST /api/asr，展示普通话文本 */
async function transcribe() {
  if (!pendingBlob.value || recognizing.value) return

  recognizing.value = true
  errorText.value = ''
  resultText.value = ''
  resultMandarin.value = ''
  try {
    const form = new FormData()
    form.append('audio', pendingBlob.value, pendingName.value)
    const data = await $fetch<{ text: string; mandarin?: string; language?: string }>('/api/asr', {
      method: 'POST',
      body: form,
    })
    resultText.value = data.text
    resultMandarin.value = data.mandarin || ''
  } catch (err) {
    errorText.value = getErrorDetail(err, '识别失败，请稍后重试。')
  } finally {
    recognizing.value = false
  }
}

/** 清空当前音频 */
function reset() {
  pendingBlob.value = null
  pendingName.value = ''
  resultText.value = ''
  resultMandarin.value = ''
  errorText.value = ''
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <!-- 页头 -->
    <section class="mb-8 text-center">
      <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
        <Icon :name="item.icon" class="h-7 w-7" />
      </span>
      <h1 class="mt-4 text-2xl font-bold text-slate-900">{{ item.label }}</h1>
      <p class="mx-auto mt-2 max-w-md text-slate-500">
        录制或上传一段方言语音，转成普通话文本。
      </p>
    </section>

    <div class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <!-- 输入区：录音 / 上传 -->
      <section class="p-6">
        <div class="flex flex-col gap-4 sm:flex-row">
          <!-- 录音 -->
          <div class="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
            <button
              type="button"
              :disabled="!isSupported"
              class="flex h-16 w-16 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
              :class="isRecording ? 'bg-rose-500 hover:bg-rose-600' : 'bg-sky-500 hover:bg-sky-600'"
              @click="toggleRecording"
            >
              <Icon v-if="isRecording" name="lucide:square" class="h-6 w-6" />
              <Icon v-else name="lucide:mic" class="h-7 w-7" />
            </button>
            <p class="text-sm font-medium text-slate-700">
              {{ isRecording ? `录音中 ${isRecordingLabel}` : (isSupported ? '点击录音' : '不支持录音') }}
            </p>
            <p v-if="isSupported && !isRecording" class="text-xs text-slate-400">
              用麦克风录一段方言
            </p>
          </div>

          <div class="flex items-center justify-center text-slate-400">
            <span class="text-sm">或</span>
          </div>

          <!-- 上传 -->
          <div class="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
            <label
              for="audio-file"
              class="flex h-16 w-16 cursor-pointer items-center justify-center rounded-full bg-indigo-500 text-white shadow transition hover:bg-indigo-600"
            >
              <Icon name="lucide:upload" class="h-7 w-7" />
            </label>
            <input
              id="audio-file"
              ref="fileInput"
              type="file"
              accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a,.wma,.aac,.webm"
              class="hidden"
              @change="onFileChange"
            />
            <p class="text-sm font-medium text-slate-700">上传音频</p>
            <p class="text-xs text-slate-400">wav / mp3 / webm / m4a 等</p>
          </div>
        </div>

        <p v-if="recorderError" class="mt-4 text-center text-sm text-rose-500">
          {{ recorderError }}
        </p>
        <p v-if="errorText" class="mt-4 text-center text-sm text-rose-500">
          {{ errorText }}
        </p>

        <!-- 已选音频 + 操作 -->
        <div v-if="hasAudio" class="mt-5 rounded-xl bg-sky-50 p-4">
          <p class="flex items-center gap-2 text-sm text-slate-700">
            <Icon name="lucide:file-audio" class="h-4 w-4 text-sky-600" />
            <span class="truncate font-medium">{{ pendingName }}</span>
            <span class="shrink-0 text-xs text-slate-400">
              {{ (pendingBlob!.size / 1024).toFixed(1) }} KB
            </span>
          </p>
          <!-- 试听回放 -->
          <audio
            v-if="previewUrl"
            :src="previewUrl"
            controls
            preload="metadata"
            class="mt-3 h-11 w-full"
          ></audio>
          <div class="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              :disabled="busy"
              class="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              @click="transcribe"
            >
              <Icon v-if="recognizing" name="lucide:loader-circle" class="h-4 w-4 animate-spin" />
              <Icon v-else name="lucide:arrow-right" class="h-4 w-4" />
              {{ recognizing ? '识别中…' : '开始识别' }}
            </button>
            <button
              type="button"
              :disabled="busy"
              class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
              @click="reset"
            >
              重新选择
            </button>
          </div>
        </div>
      </section>

      <!-- 结果区 -->
      <section v-if="resultText || resultMandarin" class="border-t border-slate-200 bg-slate-50 p-6">
        <!-- 普通话翻译（主） -->
        <div v-if="resultMandarin" class="mb-4">
          <p class="mb-2 flex items-center gap-2 text-sm font-medium text-slate-600">
            <Icon name="lucide:languages" class="h-4 w-4 text-emerald-600" />
            普通话翻译
          </p>
          <p class="rounded-xl bg-white p-4 text-lg leading-relaxed text-slate-900 shadow-inner">
            {{ resultMandarin }}
          </p>
        </div>
        <!-- 谐音文字（次） -->
        <div>
          <p class="mb-2 flex items-center gap-2 text-sm font-medium text-slate-600">
            <Icon name="lucide:file-text" class="h-4 w-4 text-sky-600" />
            方言谐音文字
          </p>
          <p class="rounded-xl bg-white p-4 text-base leading-relaxed text-slate-700 shadow-inner">
            {{ resultText }}
          </p>
        </div>
      </section>
    </div>
  </div>
</template>
