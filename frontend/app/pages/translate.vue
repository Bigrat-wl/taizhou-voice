<script setup lang="ts">
import { computed, nextTick, shallowRef, useTemplateRef } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'
import { getErrorDetail } from '~/utils/error'
import type { TranslateEntry } from '~/components/translate/TranslateTimelineItem.vue'

definePageMeta({ fullHeight: true })

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
/** 正在处理的翻译方向（用于区分两个按钮的状态） */
const processingDir = shallowRef<'tz2pt' | 'pt2tz' | null>(null)
const errorText = shallowRef('')

/** 翻译结果时间线（从旧到新） */
const entries = shallowRef<TranslateEntry[]>([])
const timelineRef = useTemplateRef<HTMLElement>('timeline')
async function scrollToBottom() {
  await nextTick()
  timelineRef.value?.scrollTo({ top: timelineRef.value.scrollHeight, behavior: 'smooth' })
}

/** 是否有任一录音正在录制 */
const anyRecording = computed(() => tz.isRecording.value || pt.isRecording.value)
/** 是否正在处理（识别或合成） */
const isProcessing = computed(() => phase.value !== 'idle')
/** 是否可操作（非录制中且非处理中） */
const idle = computed(() => !anyRecording.value && !isProcessing.value)

// ── 每个方向独立的提交按钮文案（解决「分不清哪个方向在处理」） ──
const DIRECTION_LABEL: Record<string, string> = {
  tz2pt: '泰州话→普通话',
  pt2tz: '普通话→泰州话',
}
const PHASE_LABEL: Record<string, string> = {
  recognizing: '识别中…',
  synthesizing: '合成中…',
}

const tzSubmitLabel = computed(() => {
  if (processingDir.value === 'tz2pt' && phase.value !== 'idle')
    return `${DIRECTION_LABEL.tz2pt} ${PHASE_LABEL[phase.value]}`
  return '识别翻译'
})
const ptSubmitLabel = computed(() => {
  if (processingDir.value === 'pt2tz' && phase.value !== 'idle')
    return `${DIRECTION_LABEL.pt2tz} ${PHASE_LABEL[phase.value]}`
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
  processingDir.value = direction

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

    // ── 完成：加入时间线（追加到末尾） ──
    entries.value = [
      ...entries.value,
      {
        direction,
        text: recognizedText,
        audioUrl,
        ttsError,
        time: formatTime(),
      },
    ]
    scrollToBottom()

    // 清空已提交的 blob
    if (direction === 'tz2pt') tzBlob.value = null
    else ptBlob.value = null
  } catch (err) {
    errorText.value = getErrorDetail(err, '处理失败，请稍后重试。')
  } finally {
    phase.value = 'idle'
    processingDir.value = null
  }
}
</script>

<template>
  <!-- CSS Grid 三行：录音卡片(紧凑) → 预览行(固定高度，v-show 切换不跳动) → 结果区(撑满) -->
  <div class="grid h-full grid-rows-[auto_auto_1fr] px-4 pb-4 w-full gap-2">
    <!-- ① 录音卡片：仅 mic 按钮 + 标签，一行搞定 -->
    <div class="shrink-0 space-y-2">
      <section class="py-1 text-center">
        <span class="mx-auto flex h-6 w-6 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
          <Icon :name="item.icon" class="h-3 w-3" />
        </span>
        <h1 class="mt-0.5 text-base font-bold text-slate-900">{{ item.label }}</h1>
      </section>
      <div class="grid grid-cols-2 gap-3">
        <!-- 泰州话 -->
        <div class="flex items-center gap-2.5 rounded-xl border border-dashed border-amber-300 bg-amber-50/50 px-3 py-2.5">
          <button
            type="button"
            :disabled="!tz.isSupported.value || (!idle && !tz.isRecording.value)"
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="tz.isRecording.value ? 'bg-rose-500 hover:bg-rose-600' : 'bg-amber-500 hover:bg-amber-600'"
            @click="toggleTzRecording"
          >
            <Icon v-if="tz.isRecording.value" name="lucide:square" class="h-3.5 w-3.5" />
            <Icon v-else name="lucide:mic" class="h-4 w-4" />
          </button>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-amber-700 truncate">
              {{ tz.isRecording.value ? `录音中 ${tz.isRecordingLabel.value}` : '泰州话' }}
            </p>
            <p v-if="tz.errorMsg.value" class="text-xs text-rose-500 truncate">{{ tz.errorMsg.value }}</p>
          </div>
        </div>
        <!-- 普通话 -->
        <div class="flex items-center gap-2.5 rounded-xl border border-dashed border-sky-300 bg-sky-50/50 px-3 py-2.5">
          <button
            type="button"
            :disabled="!pt.isSupported.value || (!idle && !pt.isRecording.value)"
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="pt.isRecording.value ? 'bg-rose-500 hover:bg-rose-600' : 'bg-sky-500 hover:bg-sky-600'"
            @click="togglePtRecording"
          >
            <Icon v-if="pt.isRecording.value" name="lucide:square" class="h-3.5 w-3.5" />
            <Icon v-else name="lucide:mic" class="h-4 w-4" />
          </button>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-sky-700 truncate">
              {{ pt.isRecording.value ? `录音中 ${pt.isRecordingLabel.value}` : '普通话' }}
            </p>
            <p v-if="pt.errorMsg.value" class="text-xs text-rose-500 truncate">{{ pt.errorMsg.value }}</p>
          </div>
        </div>
      </div>
      <div class="min-h-0">
        <p v-show="errorText" class="rounded-lg bg-rose-50 p-2 text-center text-sm text-rose-600">{{ errorText }}</p>
      </div>
    </div>

    <!-- ② 预览行（常驻，始终占位，不跳动） -->
    <div class="grid grid-cols-2 gap-3">
      <!-- 泰州话预览 -->
      <div class="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 min-h-[2.75rem]">
        <template v-if="tzBlob && !tz.isRecording.value">
          <audio v-if="tzPreviewUrl" :src="tzPreviewUrl" controls preload="metadata" class="h-8 min-w-0 flex-1"></audio>
          <button
            type="button"
            :disabled="isProcessing"
            class="flex h-8 shrink-0 items-center gap-1 rounded-lg bg-amber-500 px-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
            @click="submit('tz2pt')"
          >
            <Icon v-if="isProcessing && processingDir === 'tz2pt'" name="lucide:loader-circle" class="h-3 w-3 animate-spin" />
            <Icon v-else name="lucide:arrow-right" class="h-3 w-3" />
            <span class="truncate">{{ tzSubmitLabel }}</span>
          </button>
        </template>
      </div>
      <!-- 普通话预览 -->
      <div class="flex items-center gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 min-h-[2.75rem]">
        <template v-if="ptBlob && !pt.isRecording.value">
          <audio v-if="ptPreviewUrl" :src="ptPreviewUrl" controls preload="metadata" class="h-8 min-w-0 flex-1"></audio>
          <button
            type="button"
            :disabled="isProcessing"
            class="flex h-8 shrink-0 items-center gap-1 rounded-lg bg-sky-500 px-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            @click="submit('pt2tz')"
          >
            <Icon v-if="isProcessing && processingDir === 'pt2tz'" name="lucide:loader-circle" class="h-3 w-3 animate-spin" />
            <Icon v-else name="lucide:arrow-right" class="h-3 w-3" />
            <span class="truncate">{{ ptSubmitLabel }}</span>
          </button>
        </template>
      </div>
    </div>

    <!-- ③ 结果区：flex-1 撑满剩余高度 -->
    <div class="flex flex-col min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <!-- 结果标题（固定不压缩） -->
      <div class="shrink-0 px-5 pt-3 pb-1.5">
        <h2 class="flex items-center gap-2 text-base font-semibold text-slate-700">
          <Icon name="lucide:list" class="h-4.5 w-4.5 text-violet-500" />
          转写结果
          <span v-if="entries.length > 0" class="ml-auto text-xs font-normal text-slate-400">
            {{ entries.length }} 条
          </span>
        </h2>
      </div>
      <!-- 滚动区域 -->
      <div ref="timeline" class="flex-1 min-h-0 overflow-y-auto px-5 pb-4">
        <template v-if="entries.length > 0">
          <div class="space-y-0">
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
        </template>
        <template v-else>
          <div class="flex flex-col items-center justify-center py-12">
            <Icon name="lucide:message-circle" class="mx-auto h-10 w-10 text-slate-300" />
            <p class="mt-3 text-sm text-slate-400">录一句试试，识别结果会出现在这里</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
