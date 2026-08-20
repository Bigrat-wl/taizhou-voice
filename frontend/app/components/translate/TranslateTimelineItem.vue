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
  <!-- 泰州话靠左，普通话靠右，像 QQ 聊天 -->
  <div class="flex py-2" :class="direction === 'tz2pt' ? 'justify-start' : 'justify-end'">
    <div class="max-w-[75%]">
      <!-- 气泡 -->
      <div
        class="rounded-2xl px-4 py-2.5 shadow-sm"
        :class="
          direction === 'tz2pt'
            ? 'bg-amber-100 text-amber-900 rounded-bl-sm'
            : 'bg-sky-100 text-sky-900 rounded-br-sm'
        "
      >
        <!-- 标签 + 时间 -->
        <div class="flex items-center gap-2 mb-1">
          <span
            class="text-xs font-bold"
            :class="direction === 'tz2pt' ? 'text-amber-600' : 'text-sky-600'"
          >
            {{ direction === 'tz2pt' ? '泰州话' : '普通话' }}
          </span>
          <span class="text-[10px] text-slate-400">{{ time }}</span>
        </div>
        <!-- 文字 -->
        <p class="text-sm leading-relaxed">{{ text }}</p>
        <!-- TTS 失败提示 -->
        <p v-if="ttsError" class="mt-1 flex items-center gap-1 text-xs text-rose-400">
          <Icon name="lucide:alert-circle" class="h-3 w-3" />
          {{ ttsError }}
        </p>
      </div>

      <!-- 播放按钮 + 音频 -->
      <div v-if="audioUrl" class="mt-1.5 flex items-center gap-2" :class="direction === 'tz2pt' ? '' : 'justify-end'">
        <button
          type="button"
          class="flex h-7 items-center gap-1 rounded-full border px-2 text-xs transition"
          :class="
            playing
              ? 'border-emerald-300 bg-emerald-50 text-emerald-600'
              : direction === 'tz2pt'
                ? 'border-amber-200 bg-white text-amber-600 hover:bg-amber-50'
                : 'border-sky-200 bg-white text-sky-600 hover:bg-sky-50'
          "
          @click="togglePlay"
        >
          <Icon v-if="playing" name="lucide:volume-2" class="h-3 w-3" />
          <Icon v-else name="lucide:play" class="h-3 w-3" />
          {{ playing ? '播放中' : '播放译文' }}
        </button>
      </div>

      <!-- audio 元素 -->
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
