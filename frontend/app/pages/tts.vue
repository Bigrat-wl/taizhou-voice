<script setup lang="ts">
import { ref, computed } from 'vue'
import { navItems } from '~/composables/useNav'
import { getErrorDetail } from '~/utils/error'

const item = navItems.find((n) => n.to === '/tts')!

// —— 输入文本 ——
const inputText = ref('')
const MAX_TEXT_LENGTH = 200

// —— 合成状态 ——
const synthesizing = ref(false)
const audioUrl = ref<string | null>(null)
const errorText = ref('')
const successMsg = ref('')

/** 是否有可提交的文本 */
const hasText = computed(() => inputText.value.trim().length > 0)
/** 是否超出长度限制 */
const isOverLimit = computed(() => inputText.value.length > MAX_TEXT_LENGTH)
/** 是否可提交 */
const canSubmit = computed(() => hasText.value && !isOverLimit.value && !synthesizing.value)
/** 剩余字符数 */
const remainingChars = computed(() => MAX_TEXT_LENGTH - inputText.value.length)

/** 调用 POST /api/tts 合成语音 */
async function synthesize() {
  if (!canSubmit.value) return

  synthesizing.value = true
  errorText.value = ''
  successMsg.value = ''

  // 清除旧的音频 URL
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = null
  }

  try {
    const data = await $fetch<{ audio_url: string }>('/api/tts', {
      method: 'POST',
      body: { text: inputText.value.trim() },
    })

    // audio_url 是后端返回的相对路径，需要拼接完整 URL
    const fullUrl = data.audio_url.startsWith('http')
      ? data.audio_url
      : `${window.location.origin}${data.audio_url}`

    audioUrl.value = fullUrl
    successMsg.value = '合成成功！'
  } catch (err) {
    errorText.value = getErrorDetail(err, '语音合成失败，请稍后重试。')
  } finally {
    synthesizing.value = false
  }
}

/** 清空输入和结果 */
function reset() {
  inputText.value = ''
  errorText.value = ''
  successMsg.value = ''
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = null
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <!-- 页头 -->
    <section class="mb-8 text-center">
      <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600">
        <Icon :name="item.icon" class="h-7 w-7" />
      </span>
      <h1 class="mt-4 text-2xl font-bold text-slate-900">{{ item.label }}</h1>
      <p class="mx-auto mt-2 max-w-md text-slate-500">
        输入普通话文本，合成为泰州方言语音。
      </p>
    </section>

    <div class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <!-- 输入区：文本输入 -->
      <section class="p-6">
        <div class="flex flex-col gap-4">
          <!-- 文本输入框 -->
          <div>
            <label for="tts-text" class="mb-2 block text-sm font-medium text-slate-700">
              输入文本
            </label>
            <textarea
              id="tts-text"
              v-model="inputText"
              rows="4"
              :maxlength="MAX_TEXT_LENGTH + 10"
              placeholder="请输入要合成的文本，例如：今朝天气老好"
              class="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              :class="{ 'border-rose-300 focus:border-rose-500 focus:ring-rose-200': isOverLimit }"
            />
            <p class="mt-1 flex items-center justify-between text-xs">
              <span :class="isOverLimit ? 'text-rose-500' : 'text-slate-400'">
                {{ inputText.length }} / {{ MAX_TEXT_LENGTH }}
              </span>
              <span v-if="remainingChars < 0" class="text-rose-500">
                超出 {{ -remainingChars }} 字
              </span>
            </p>
          </div>

          <!-- 错误信息 -->
          <p v-if="errorText" class="rounded-lg bg-rose-50 p-3 text-center text-sm text-rose-600">
            {{ errorText }}
          </p>

          <!-- 操作按钮 -->
          <div class="flex flex-wrap gap-3">
            <button
              type="button"
              :disabled="!canSubmit"
              class="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              @click="synthesize"
            >
              <Icon v-if="synthesizing" name="lucide:loader-circle" class="h-4 w-4 animate-spin" />
              <Icon v-else name="lucide:volume-2" class="h-4 w-4" />
              {{ synthesizing ? '合成中…' : '合成语音' }}
            </button>
            <button
              type="button"
              :disabled="synthesizing"
              class="rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-50"
              @click="reset"
            >
              清空
            </button>
          </div>
        </div>
      </section>

      <!-- 结果区：音频播放 -->
      <section v-if="audioUrl || successMsg" class="border-t border-slate-200 bg-slate-50 p-6">
        <p v-if="successMsg" class="mb-3 flex items-center gap-2 text-sm font-medium text-emerald-600">
          <Icon name="lucide:check-circle" class="h-4 w-4" />
          {{ successMsg }}
        </p>
        <p class="mb-2 text-sm font-medium text-slate-600">
          <Icon name="lucide:headphones" class="mr-1 inline h-4 w-4 text-emerald-600" />
          合成音频
        </p>
        <audio
          v-if="audioUrl"
          :src="audioUrl"
          controls
          preload="metadata"
          class="h-12 w-full"
        ></audio>
      </section>
    </div>
  </div>
</template>
