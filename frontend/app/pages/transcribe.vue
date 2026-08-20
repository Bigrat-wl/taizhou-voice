<script setup lang="ts">
import { computed, onMounted, onUnmounted, shallowRef, useTemplateRef } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'

definePageMeta({ fullHeight: true })

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

/** 测试用例列表（参考 dialect_asr_system 项目的27句平行语料） */
const testCases = [
  { name: '钱1', file: '钱1.WAV', dialect: '你个曾吃饭啊？吃过啊了，你吃的什尼啊？', mandarin: '你吃饭了吗？吃了，你吃的什么啊？' },
  { name: '陈5', file: '陈5.WAV', dialect: '你早上吃滴什尼啊？鱼汤面、烫干丝，海黄包在！', mandarin: '你早上吃的什么啊？鱼汤面、烫干丝、蟹黄包！' },
  { name: '孙3', file: '孙3.WAV', dialect: '你个嗲嗲呢？他在外头哒寡呢！', mandarin: '你爷爷呢？他在外面聊天呢！' },
  { name: '周2', file: '周2.WAV', dialect: '砸个雅立睡得个惬意啊，隔壁有人在杠桑', mandarin: '昨天夜里睡得不舒服啊，隔壁有人在吵架' },
  { name: '陈9', file: '陈9.WAV', dialect: '秋拿个爬爬凳啊坐我旁边啊！', mandarin: '就拿个小凳子做我旁边啊！' },
]

/** 下拉菜单是否打开 */
const tcDropdownOpen = shallowRef(false)
const tcDropdownRef = useTemplateRef<HTMLElement>('tcDropdown')

/** 点击外部关闭下拉菜单 */
function onTcClickOutside(e: MouseEvent) {
  if (tcDropdownRef.value && !tcDropdownRef.value.contains(e.target as Node)) {
    tcDropdownOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onTcClickOutside))
onUnmounted(() => document.removeEventListener('click', onTcClickOutside))

/** 试听中的测试用例文件名 */
const previewingTc = shallowRef('')

/** 试听/停止试听测试用例 */
async function togglePreview(tc: typeof testCases[0]) {
  if (previewingTc.value === tc.file) {
    previewingTc.value = ''
    return
  }
  previewingTc.value = tc.file
}

/** 停止试听 */
function stopPreviewTc() {
  previewingTc.value = ''
}

/** 加载测试用例到待识别区 */
function loadTestCase(tc: typeof testCases[0]) {
  fetch(`/data/audio/samples/${tc.file}`)
    .then(r => { if (!r.ok) throw new Error(); return r.blob() })
    .then(blob => setPending(blob, tc.file))
    .catch(() => { errorText.value = '加载测试音频失败。' })
}

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
  <div class="flex h-full flex-col px-4 pb-4 max-w-6xl mx-auto w-full">
    <!-- 页头（紧凑） -->
    <section class="py-2 text-center shrink-0">
      <span class="mx-auto flex h-7 w-7 items-center justify-center rounded-lg bg-sky-100 text-sky-600">
        <Icon :name="item.icon" class="h-3.5 w-3.5" />
      </span>
      <h1 class="mt-0.5 text-lg font-bold text-slate-900">{{ item.label }}</h1>
    </section>

    <!-- 主体：flex-1 填满剩余空间 -->
    <div class="flex flex-1 min-h-0 flex-col gap-3">
      <!-- 测试用例下拉菜单 -->
      <div ref="tcDropdown" class="relative shrink-0">
        <button
          type="button"
          class="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-slate-50"
          @click="tcDropdownOpen = !tcDropdownOpen"
        >
          <span class="flex items-center gap-2">
            <Icon name="lucide:flask-conical" class="h-4 w-4 text-amber-500" />
            测试用例
            <span class="text-xs font-normal text-slate-400">（{{ testCases.length }} 句）</span>
          </span>
          <Icon
            name="lucide:chevron-down"
            class="h-4 w-4 text-slate-400 transition-transform duration-200"
            :class="{ 'rotate-180': tcDropdownOpen }"
          />
        </button>
        <!-- 下拉列表 -->
        <div
          v-show="tcDropdownOpen"
          class="absolute left-0 top-full z-10 mt-1 w-full max-h-72 overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-lg"
        >
          <div
            v-for="tc in testCases"
            :key="tc.file"
            class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 transition hover:bg-sky-50"
            @click="loadTestCase(tc); tcDropdownOpen = false"
          >
            <!-- 试听按钮 -->
            <button
              type="button"
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition"
              :class="previewingTc === tc.file
                ? 'bg-sky-500 text-white'
                : 'bg-slate-100 text-slate-500 hover:bg-sky-100 hover:text-sky-600'"
              :title="previewingTc === tc.file ? '停止' : '试听'"
              @click.stop="togglePreview(tc)"
            >
              <Icon
                :name="previewingTc === tc.file ? 'lucide:pause' : 'lucide:play'"
                class="h-3 w-3"
              />
            </button>
            <!-- 文本信息 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="shrink-0 text-xs font-semibold text-slate-700">{{ tc.name }}</span>
                <span class="truncate text-xs text-slate-500">{{ tc.dialect }}</span>
              </div>
              <p class="truncate pl-[2.75rem] text-[11px] text-slate-400">→ {{ tc.mandarin }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入操作区 + 试听回放 -->
      <div class="shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm px-4 py-2.5">
        <div class="flex items-center gap-3">
          <!-- 录音按钮 -->
          <button
            type="button"
            :disabled="!isSupported"
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow transition disabled:cursor-not-allowed disabled:opacity-40"
            :class="isRecording ? 'bg-rose-500 hover:bg-rose-600' : 'bg-sky-500 hover:bg-sky-600'"
            @click="toggleRecording"
          >
            <Icon v-if="isRecording" name="lucide:square" class="h-3.5 w-3.5" />
            <Icon v-else name="lucide:mic" class="h-3.5 w-3.5" />
          </button>
          <p class="text-xs font-medium text-slate-600 shrink-0">
            {{ isRecording ? `录音中 ${isRecordingLabel}` : (isSupported ? '录音' : '不支持') }}
          </p>

          <div class="h-4 w-px bg-slate-200 shrink-0" />

          <!-- 上传按钮 -->
          <label
            for="audio-file"
            class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full bg-indigo-500 text-white shadow transition hover:bg-indigo-600"
          >
            <Icon name="lucide:upload" class="h-3.5 w-3.5" />
          </label>
          <input
            id="audio-file"
            ref="fileInput"
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a,.wma,.aac,.webm"
            class="hidden"
            @change="onFileChange"
          />

          <!-- 文件名 / 状态 -->
          <div class="flex min-w-0 flex-1 items-center gap-2 text-xs text-slate-500">
            <template v-if="hasAudio">
              <Icon name="lucide:file-audio" class="h-3.5 w-3.5 shrink-0 text-sky-500" />
              <span class="truncate">{{ pendingName }}</span>
              <span class="shrink-0 text-slate-400">{{ (pendingBlob!.size / 1024).toFixed(1) }} KB</span>
            </template>
            <template v-else>
              <span>{{ isRecording ? '录音中…' : '选择音频文件或点击录音' }}</span>
            </template>
          </div>

          <!-- 操作按钮 -->
          <template v-if="hasAudio">
            <button
              type="button"
              :disabled="busy"
              class="flex shrink-0 items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              @click="transcribe"
            >
              <Icon v-if="recognizing" name="lucide:loader-circle" class="h-3.5 w-3.5 animate-spin" />
              <Icon v-else name="lucide:arrow-right" class="h-3.5 w-3.5" />
              {{ recognizing ? '识别中…' : '识别' }}
            </button>
            <button
              type="button"
              :disabled="busy"
              class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-50 shrink-0"
              @click="reset"
            >
              重选
            </button>
          </template>
        </div>

        <!-- 错误提示 -->
        <div class="min-h-[1rem]">
          <p v-show="recorderError" class="text-center text-xs text-rose-500">{{ recorderError }}</p>
          <p v-show="errorText" class="text-center text-xs text-rose-500">{{ errorText }}</p>
        </div>

        <!-- 试听回放（v-show + height 过渡，避免布局跳动） -->
        <div class="overflow-hidden transition-all duration-200" :style="{ height: hasAudio && previewUrl ? '44px' : '0px' }">
          <audio
            v-show="hasAudio && previewUrl"
            :src="previewUrl"
            controls
            preload="metadata"
            class="h-9 w-full"
          ></audio>
        </div>
      </div>

      <!-- 结果区：flex-1 填满剩余全部高度（页面核心） -->
      <div class="flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <!-- 区域标题 -->
        <div class="flex shrink-0 items-center gap-2 border-b border-slate-100 px-5 py-2">
          <Icon name="lucide:scan-text" class="h-4 w-4 text-sky-500" />
          <span class="text-sm font-medium text-slate-600">识别结果</span>
          <span v-if="resultText || resultMandarin" class="text-xs text-slate-400">（{{ resultMandarin ? '普通话翻译 + ' : '' }}方言谐音）</span>
        </div>
        <div class="flex-1 min-h-0 overflow-y-auto p-6">
          <template v-if="resultText || resultMandarin">
            <!-- 普通话翻译（主） -->
            <div v-if="resultMandarin" class="mb-6">
              <p class="mb-2 flex items-center gap-2 text-sm font-medium text-slate-500">
                <Icon name="lucide:languages" class="h-4 w-4 text-emerald-500" />
                普通话翻译
              </p>
              <p class="rounded-xl bg-emerald-50/50 border border-emerald-100 p-5 text-xl leading-relaxed text-slate-900">
                {{ resultMandarin }}
              </p>
            </div>
            <!-- 谐音文字（次） -->
            <div>
              <p class="mb-2 flex items-center gap-2 text-sm font-medium text-slate-500">
                <Icon name="lucide:file-text" class="h-4 w-4 text-sky-500" />
                方言谐音文字
              </p>
              <p class="rounded-xl bg-sky-50/50 border border-sky-100 p-5 text-lg leading-relaxed text-slate-700">
                {{ resultText }}
              </p>
            </div>
          </template>
          <template v-else>
            <div class="flex flex-col items-center justify-center h-full text-center">
              <Icon name="lucide:music" class="mx-auto h-12 w-12 text-slate-200" />
              <p class="mt-4 text-base text-slate-400">录音或上传音频后，识别结果会出现在这里</p>
              <p class="mt-1 text-xs text-slate-300">支持泰州方言的谐音转写与普通话翻译</p>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
