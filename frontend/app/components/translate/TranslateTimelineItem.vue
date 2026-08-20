<script setup lang="ts">
import { shallowRef } from 'vue'

export interface TranslateEntry {
  /** 来源语言方向 */
  direction: 'tz2pt' | 'pt2tz'
  /** ASR 识别文本 */
  text: string
  /** TTS 合成音频 URL（可能为 null，若 TTS 失败） */
  audioUrl: string | null
  /** TTS 失败时的错误信息 */
  ttsError?: string | null
  /** 时间戳 */
  time: string
}

defineProps<TranslateEntry>()

const playing = shallowRef(false)
const audioEl = shallowRef<HTMLAudioElement | null>(null)

function togglePlay() {
  if (!audioEl.value) return
  if (playing.value) {
    audioEl.value.pause()
    audioEl.value.currentTime = 0
    playing.value = false
  } else {
    void audioEl.value.play()
    playing.value = true
  }
}

function onEnded() {
  playing.value = false
}
</script>

<template>
  <div class="flex gap-3">
    <!-- 时间线圆点 + 竖线 -->
    <div class="flex flex-col items-center">
      <div
        class="mt-1.5 h-3 w-3 shrink-0 rounded-full"
        :class="direction === 'tz2pt' ? 'bg-amber-400' : 'bg-sky-400'"
      ></div>
      <div class="w-px flex-1 bg-slate-200"></div>
    </div>

    <!-- 内容 -->
    <div class="flex-1 pb-6">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <!-- 标题：语言方向 + 时间 -->
          <div class="flex items-center gap-2">
            <span
              class="text-sm font-bold"
              :class="direction === 'tz2pt' ? 'text-amber-600' : 'text-sky-600'"
            >
              {{ direction === 'tz2pt' ? '泰州话' : '普通话' }}
            </span>
            <span class="text-xs text-slate-400">{{ time }}</span>
          </div>
          <!-- 识别文字（翻译结果） -->
          <p class="mt-1 text-base leading-relaxed text-slate-800">{{ text }}</p>
          <!-- TTS 失败提示 -->
          <p v-if="ttsError" class="mt-1 flex items-center gap-1 text-xs text-rose-400">
            <Icon name="lucide:alert-circle" class="h-3 w-3" />
            {{ ttsError }}
          </p>
        </div>

        <!-- 播放按钮（有音频时显示） -->
        <button
          v-if="audioUrl"
          type="button"
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50"
          :class="{ 'border-emerald-300 bg-emerald-50 text-emerald-600': playing }"
          title="播放译文语音"
          @click="togglePlay"
        >
          <Icon
            v-if="playing"
            name="lucide:volume-2"
            class="h-4 w-4"
          />
          <Icon v-else name="lucide:play" class="h-4 w-4" />
        </button>
      </div>

      <!-- audio 元素（有音频时渲染） -->
      <audio
        v-if="audioUrl"
        ref="audioEl"
        :src="audioUrl"
        preload="none"
        class="hidden"
        @ended="onEnded"
      ></audio>
    </div>
  </div>
</template>
