<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'
import { getErrorDetail } from '~/utils/error'
import type { TranslateEntry } from '~/components/translate/TranslateTimelineItem.vue'

const item = navItems.find((n) => n.to === '/translate')!

// ── 泰州话录音 ──
const tz = useRecorder()
const tzBlob = shallowRef<Blob | null>(null)
const { url: tzPreviewUrl } = useBlobUrl(tzBlob)

// ── 普通话录音 ──
const pt = useRecorder()
const ptBlob = shallowRef<Blob | null>(null)
const { url: ptPreviewUrl } = useBlobUrl(ptBlob)

// ── 处理阶段：idle → recognizing → synthesizing → idle ──
const phase = shallowRef<'idle' | 'recognizing' | 'synthesizing'>('idle')
const errorText = shallowRef('')

/** 翻译结果时间线（最新在前） */
const entries = shallowRef<TranslateEntry[]>([])

/** 是否有任一录音正在录制 */
const anyRecording = computed(() => tz.isRecording.value || pt.isRecording.value)
/** 是否正在处理（识别或合成） */
const isProcessing = computed(() => phase.value !== 'idle')
/** 是否可操作（非录制中且非处理中） */
const idle = computed(() => !anyRecording.value && !isProcessing.value)

/** 提交按钮文案 */
const submitLabel = computed(() => {
  if (phase.value === 'recognizing') return '识别中…'
  if (phase.value === 'synthesizing') return '合成中…'
  return '识别翻译'
})

/** 格式化当前时间 */
function formatTime(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

// ── 泰州话录音操作 ──
async function toggleTzRecording() {
  if (tz.isRecording.value) {
    try {
      const blob = await tz.stop()
      tzBlob.value = blob
    } catch (err) {
      errorText.value = err instanceof Error ? err.message : '录音失败'
    }
    return
  }
  tzBlob.value = null
  errorText.value = ''
  try {
    await tz.start()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '无法开始录音'
  }
}

// ── 普通话录音操作 ──
async function togglePtRecording() {
  if (pt.isRecording.value) {
    try {
      const blob = await pt.stop()
      ptBlob.value = blob
    } catch (err) {
      errorText.value = err instanceof Error ? err.message : '录音失败'
    }
    return
  }
  ptBlob.value = null
  errorText.value = ''
  try {
    await pt.start()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '无法开始录音'
  }
}

/**
 * 识别翻译：录完一句处理一句（非流式）。
 * 阶段 1: recognizing — POST /api/asr 识别语音
 * 阶段 2: synthesizing — POST /api/tts 合成方言译文
 * 完成后加入时间线。
 */
async function submit(direction: 'tz2pt' | 'pt2tz') {
  const blob = direction === 'tz2pt' ? tzBlob.value : ptBlob.value
  if (!blob || isProcessing.value) return

  errorText.value = ''

  try {
    // ── 阶段 1：识别 ──
    phase.value = 'recognizing'
    const form = new FormData()
    form.append('audio', blob, `${direction}-${formatTime()}.webm`)
    const asrResult = await $fetch<{ text: string; language?: string }>('/api/asr', {
      method: 'POST',
      body: form,
    })

    const recognizedText = asrResult.text?.trim()
    if (!recognizedText) {
      errorText.value = '未识别到有效语音内容'
      return
    }

    // ── 阶段 2：合成 ──
    phase.value = 'synthesizing'
    let audioUrl: string | null = null
    let ttsError: string | null = null
    try {
      const ttsResult = await $fetch<{ audio_url: string }>('/api/tts', {
        method: 'POST',
        body: { text: recognizedText },
      })
      audioUrl = ttsResult.audio_url.startsWith('http')
        ? ttsResult.audio_url
        : `${window.location.origin}${ttsResult.audio_url}`
    } catch (ttsErr) {
      ttsError = getErrorDetail(ttsErr, '语音合成失败')
    }

    // ── 完成：加入时间线 ──
    entries.value = [
      {
        direction,
        text: recognizedText,
        audioUrl,
        ttsError,
        time: formatTime(),
      },
      ...entries.value,
    ]

    // 清空已提交的 blob
    if (direction === 'tz2pt') tzBlob.value = null
    else ptBlob.value = null
  } catch (err) {
    errorText.value = getErrorDetail(err, '处理失败，请稍后重试。')
  } finally {
    phase.value = 'idle'
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <!-- 页头 -->
    <section class="mb-8 text-center">
      <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
        <Icon :name="item.icon" class="h-7 w-7" />
      </span>
      <h1 class="mt-4 text-2xl font-bold text-slate-900">{{ item.label }}</h1>
      <p class="mx-auto mt-2 max-w-md text-slate-500">
        录一句泰州话或普通话，识别后合成方言译文并播放。
      </p>
    </section>

    <!-- 上区：左右两个录音按钮 -->
    <div class="mb-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <section class="p-6">
        <div class="grid gap-6 sm:grid-cols-2">
          <!-- 左：泰州话（amber） -->
          <div class="flex flex-col items-center gap-3 rounded-xl border border-dashed border-amber-300 bg-amber-50/50 p-5">
            <button
              type="button"
              :disabled="!tz.isSupported.value || (!idle && !tz.isRecording.value)"
              class="flex h-16 w-16 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
              :class="tz.isRecording.value ? 'bg-rose-500 hover:bg-rose-600' : 'bg-amber-500 hover:bg-amber-600'"
              @click="toggleTzRecording"
            >
              <Icon v-if="tz.isRecording.value" name="lucide:square" class="h-6 w-6" />
              <Icon v-else name="lucide:mic" class="h-7 w-7" />
            </button>
            <p class="text-sm font-semibold text-amber-700">
              {{ tz.isRecording.value ? `录音中 ${tz.isRecordingLabel.value}` : '泰州话' }}
            </p>
            <p v-if="tz.errorMsg.value" class="text-xs text-rose-500">{{ tz.errorMsg.value }}</p>

            <!-- 录音完成 → 试听 + 识别翻译 -->
            <template v-if="tzBlob && !tz.isRecording.value">
              <p class="flex items-center gap-2 text-xs text-slate-500">
                <Icon name="lucide:file-audio" class="h-3.5 w-3.5 text-amber-600" />
                {{ (tzBlob.size / 1024).toFixed(1) }} KB
              </p>
              <audio v-if="tzPreviewUrl" :src="tzPreviewUrl" controls preload="metadata" class="h-9 w-full"></audio>
              <button
                type="button"
                :disabled="isProcessing"
                class="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
                @click="submit('tz2pt')"
              >
                <Icon v-if="isProcessing" name="lucide:loader-circle" class="h-4 w-4 animate-spin" />
                <Icon v-else name="lucide:arrow-right" class="h-4 w-4" />
                {{ submitLabel }}
              </button>
            </template>
          </div>

          <!-- 右：普通话（sky） -->
          <div class="flex flex-col items-center gap-3 rounded-xl border border-dashed border-sky-300 bg-sky-50/50 p-5">
            <button
              type="button"
              :disabled="!pt.isSupported.value || (!idle && !pt.isRecording.value)"
              class="flex h-16 w-16 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
              :class="pt.isRecording.value ? 'bg-rose-500 hover:bg-rose-600' : 'bg-sky-500 hover:bg-sky-600'"
              @click="togglePtRecording"
            >
              <Icon v-if="pt.isRecording.value" name="lucide:square" class="h-6 w-6" />
              <Icon v-else name="lucide:mic" class="h-7 w-7" />
            </button>
            <p class="text-sm font-semibold text-sky-700">
              {{ pt.isRecording.value ? `录音中 ${pt.isRecordingLabel.value}` : '普通话' }}
            </p>
            <p v-if="pt.errorMsg.value" class="text-xs text-rose-500">{{ pt.errorMsg.value }}</p>

            <!-- 录音完成 → 试听 + 识别翻译 -->
            <template v-if="ptBlob && !pt.isRecording.value">
              <p class="flex items-center gap-2 text-xs text-slate-500">
                <Icon name="lucide:file-audio" class="h-3.5 w-3.5 text-sky-600" />
                {{ (ptBlob.size / 1024).toFixed(1) }} KB
              </p>
              <audio v-if="ptPreviewUrl" :src="ptPreviewUrl" controls preload="metadata" class="h-9 w-full"></audio>
              <button
                type="button"
                :disabled="isProcessing"
                class="flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                @click="submit('pt2tz')"
              >
                <Icon v-if="isProcessing" name="lucide:loader-circle" class="h-4 w-4 animate-spin" />
                <Icon v-else name="lucide:arrow-right" class="h-4 w-4" />
                {{ submitLabel }}
              </button>
            </template>
          </div>
        </div>

        <!-- 全局错误 -->
        <p v-if="errorText" class="mt-4 rounded-lg bg-rose-50 p-3 text-center text-sm text-rose-600">
          {{ errorText }}
        </p>
      </section>
    </div>

    <!-- 下区：转写结果时间线 -->
    <div v-if="entries.length > 0" class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <section class="p-6">
        <h2 class="mb-4 flex items-center gap-2 text-base font-semibold text-slate-700">
          <Icon name="lucide:list" class="h-4.5 w-4.5 text-violet-500" />
          转写结果
        </h2>
        <div>
          <TranslateTimelineItem
            v-for="(entry, idx) in entries"
            :key="idx"
            :direction="entry.direction"
            :text="entry.text"
            :audio-url="entry.audioUrl"
            :tts-error="entry.ttsError"
            :time="entry.time"
          />
        </div>
      </section>
    </div>

    <!-- 空状态 -->
    <div v-else class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 py-12 text-center">
      <Icon name="lucide:message-circle" class="mx-auto h-10 w-10 text-slate-300" />
      <p class="mt-3 text-sm text-slate-400">录一句试试，识别结果会出现在这里</p>
    </div>
  </div>
</template>
