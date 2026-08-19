<script setup lang="ts">
import { ref, shallowRef, computed } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'

const item = navItems.find((n) => n.to === '/challenge')!

// ── 句子数据 ──
interface Sentence { id: number; text: string; dialect_text: string }
const sentences = ref<Sentence[]>([])
const loadingSentences = shallowRef(false)
const sentencesError = shallowRef('')

// ── 逐句状态 ──
interface SentenceState {
  phase: 'idle' | 'recording' | 'recorded' | 'submitting' | 'scored'
  blob: Blob | null
  fileName: string
  score: number | null
  transcript: string
  reference: string
  error: string
}

const states = ref<Record<number, SentenceState>>({})

function getState(id: number): SentenceState {
  if (!states.value[id]) {
    states.value[id] = {
      phase: 'idle',
      blob: null,
      fileName: '',
      score: null,
      transcript: '',
      reference: '',
      error: '',
    }
  }
  return states.value[id]
}

// ── 当前操作的句子 id（驱动录音 composable） ──
const activeId = shallowRef<number | null>(null)

// ── 录音 composable ──
const {
  isRecording,
  isRecordingLabel,
  isSupported,
  errorMsg: recorderError,
  start: startRecording,
  stop: stopRecording,
} = useRecorder()

// ── 试听（当前激活句子的 blob） ──
const activeBlob = computed(() => (activeId.value != null ? getState(activeId.value).blob : null))
const { url: previewUrl } = useBlobUrl(activeBlob)

// ── 认证 ──
const { token, isLoggedIn } = useAuth()
const authHeaders = computed(() =>
  token.value ? { Authorization: `Bearer ${token.value}` } : {},
)

// ── 进度 ──
const scoredCount = computed(() =>
  sentences.value.filter((s) => getState(s.id).phase === 'scored').length,
)
const progressPct = computed(() =>
  sentences.value.length === 0 ? 0 : Math.round((scoredCount.value / sentences.value.length) * 100),
)

// ── 加载句子 ──
async function loadSentences() {
  loadingSentences.value = true
  sentencesError.value = ''
  states.value = {}
  activeId.value = null
  try {
    const data = await $fetch<{ sentences: Sentence[] }>('/api/sentences', {
      query: { n: 5 },
    })
    sentences.value = data.sentences
  } catch (err) {
    sentencesError.value = getErrorDetail(err, '获取句子失败，请稍后重试。')
  } finally {
    loadingSentences.value = false
  }
}

// ── 录音开始/结束 ──
async function toggleRecording(id: number) {
  const s = getState(id)
  s.error = ''

  if (isRecording.value && activeId.value === id) {
    // 停止当前录音
    try {
      const blob = await stopRecording()
      activeId.value = id
      s.blob = blob
      s.fileName = `challenge-${id}-${Date.now()}.webm`
      s.phase = 'recorded'
      s.score = null
      s.transcript = ''
      s.reference = ''
    } catch (err) {
      s.error = err instanceof Error ? err.message : '录音失败'
    }
    return
  }

  // 开始新录音
  activeId.value = id
  s.blob = null
  s.score = null
  s.transcript = ''
  s.reference = ''
  s.phase = 'recording'
  try {
    await startRecording()
  } catch (err) {
    s.error = err instanceof Error ? err.message : '无法开始录音'
    s.phase = 'idle'
  }
}

// ── 提交评分 ──
async function submitScore(id: number) {
  const s = getState(id)
  if (!s.blob || s.phase === 'submitting') return
  if (!isLoggedIn.value) {
    s.error = '请先登录后再提交评分'
    return
  }

  s.phase = 'submitting'
  s.error = ''

  try {
    const form = new FormData()
    form.append('audio', s.blob, s.fileName)
    form.append('sentence_id', String(id))

    const data = await $fetch<{ score: number; transcript: string; reference: string }>(
      '/api/score',
      {
        method: 'POST',
        body: form,
        headers: authHeaders.value,
      },
    )
    s.score = data.score
    s.transcript = data.transcript
    s.reference = data.reference
    s.phase = 'scored'
  } catch (err) {
    s.error = getErrorDetail(err, '评分提交失败，请稍后重试。')
    s.phase = 'recorded'
  }
}

// ── 跳过当前句子 ──
function skipSentence(id: number) {
  const s = getState(id)
  s.phase = 'idle'
  s.blob = null
  s.score = null
  s.error = ''
}

// ── 重新录制 ──
function retrySentence(id: number) {
  const s = getState(id)
  s.phase = 'idle'
  s.blob = null
  s.score = null
  s.transcript = ''
  s.reference = ''
  s.error = ''
}

/** 根据分数返回 Tailwind 色值类（背景 + 文字 + 边框） */
function scoreColor(score: number): string {
  if (score >= 90) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (score >= 60) return 'bg-amber-50 text-amber-700 border-amber-200'
  return 'bg-rose-50 text-rose-700 border-rose-200'
}

/** 分数等级标签 */
function scoreLabel(score: number): string {
  if (score >= 90) return '优秀'
  if (score >= 60) return '中等'
  return '不及格'
}

/** 分数对应的圆形背景色 */
function scoreBadgeColor(score: number): string {
  if (score >= 90) return 'bg-emerald-500'
  if (score >= 60) return 'bg-amber-500'
  return 'bg-rose-500'
}

// 页面加载时获取句子
onMounted(loadSentences)
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <!-- 页头 -->
    <section class="mb-8 text-center">
      <span class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-600">
        <Icon :name="item.icon" class="h-7 w-7" />
      </span>
      <h1 class="mt-4 text-2xl font-bold text-slate-900">{{ item.label }}</h1>
      <p class="mx-auto mt-2 max-w-md text-slate-500">
        挑战方言发音！听句子、录音、提交评分，看看你能拿多少分。
      </p>
    </section>

    <!-- 未登录提示 -->
    <div v-if="!isLoggedIn" class="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
      <p class="text-sm text-amber-700">
        <Icon name="lucide:log-in" class="mr-1 inline h-4 w-4" />
        评分功能需要登录，
        <NuxtLink to="/login?redirect=/challenge" class="font-semibold underline hover:text-amber-800">
          点此登录
        </NuxtLink>
        或
        <NuxtLink to="/register?redirect=/challenge" class="font-semibold underline hover:text-amber-800">
          注册新账号
        </NuxtLink>
      </p>
    </div>

    <!-- 进度条 -->
    <div v-if="sentences.length > 0" class="mb-6">
      <div class="flex items-center justify-between text-sm text-slate-600">
        <span class="font-medium">已完成 {{ scoredCount }} / {{ sentences.length }}</span>
        <span>{{ progressPct }}%</span>
      </div>
      <div class="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          class="h-full rounded-full bg-indigo-500 transition-all duration-500"
          :style="{ width: `${progressPct}%` }"
        ></div>
      </div>
    </div>

    <!-- 句子列表为空 -->
    <div
      v-if="!loadingSentences && sentences.length === 0 && !sentencesError"
      class="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm"
    >
      <Icon name="lucide:list-music" class="mx-auto h-12 w-12 text-slate-300" />
      <p class="mt-4 text-slate-500">暂无句子，点击下方按钮加载挑战题</p>
      <button
        type="button"
        class="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        @click="loadSentences"
      >
        <Icon name="lucide:refresh-cw" class="h-4 w-4" />
        刷新句子
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loadingSentences" class="py-16 text-center">
      <Icon name="lucide:loader-circle" class="mx-auto h-8 w-8 animate-spin text-indigo-500" />
      <p class="mt-3 text-sm text-slate-500">正在加载句子…</p>
    </div>

    <!-- 错误 -->
    <p v-if="sentencesError" class="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-center text-sm text-rose-600">
      {{ sentencesError }}
    </p>

    <!-- 句子卡片列表 -->
    <div v-if="sentences.length > 0" class="flex flex-col gap-4">
      <div
        v-for="(sentence, idx) in sentences"
        :key="sentence.id"
        class="overflow-hidden rounded-2xl border bg-white shadow-sm transition"
        :class="
          getState(sentence.id).phase === 'scored'
            ? scoreColor(getState(sentence.id).score!)
            : 'border-slate-200'
        "
      >
        <!-- 句子头 -->
        <div class="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600">
                {{ idx + 1 }}
              </span>
              <p class="truncate text-base font-semibold text-slate-900">{{ sentence.text }}</p>
            </div>
            <p class="mt-1 pl-8 text-sm text-slate-500">
              <span class="font-medium text-amber-600">方言：</span>{{ sentence.dialect_text }}
            </p>
          </div>
          <!-- 分数徽章 -->
          <div
            v-if="getState(sentence.id).score != null"
            class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-bold text-white shadow"
            :class="scoreBadgeColor(getState(sentence.id).score!)"
          >
            {{ getState(sentence.id).score }}
          </div>
        </div>

        <!-- 操作区 -->
        <div class="px-5 py-4">
          <!-- idle / recording / recorded / submitting / scored -->
          <div class="flex flex-col gap-3">
            <!-- 录音按钮行 -->
            <div
              v-if="getState(sentence.id).phase !== 'scored'"
              class="flex flex-wrap items-center gap-3"
            >
              <button
                type="button"
                :disabled="!isSupported || (isRecording && activeId !== sentence.id)"
                class="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-40"
                :class="
                  isRecording && activeId === sentence.id
                    ? 'bg-rose-500 hover:bg-rose-600'
                    : 'bg-indigo-500 hover:bg-indigo-600'
                "
                @click="toggleRecording(sentence.id)"
              >
                <Icon
                  v-if="isRecording && activeId === sentence.id"
                  name="lucide:square"
                  class="h-4 w-4"
                />
                <Icon v-else name="lucide:mic" class="h-4 w-4" />
                {{
                  isRecording && activeId === sentence.id
                    ? `停止录音 ${isRecordingLabel}`
                    : getState(sentence.id).phase === 'recorded'
                      ? '重新录制'
                      : '开始录音'
                }}
              </button>

              <!-- 提交评分 -->
              <button
                v-if="getState(sentence.id).phase === 'recorded' && getState(sentence.id).blob"
                type="button"
                :disabled="getState(sentence.id).phase === 'submitting' || !isLoggedIn"
                class="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                @click="submitScore(sentence.id)"
              >
                <Icon
                  v-if="getState(sentence.id).phase === 'submitting'"
                  name="lucide:loader-circle"
                  class="h-4 w-4 animate-spin"
                />
                <Icon v-else name="lucide:send" class="h-4 w-4" />
                {{ getState(sentence.id).phase === 'submitting' ? '评分中…' : '提交评分' }}
              </button>

              <!-- 跳过 -->
              <button
                v-if="getState(sentence.id).phase !== 'submitting'"
                type="button"
                class="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                @click="skipSentence(sentence.id)"
              >
                <Icon name="lucide:skip-forward" class="h-3.5 w-3.5" />
                跳过
              </button>
            </div>

            <!-- scored 操作 -->
            <div v-if="getState(sentence.id).phase === 'scored'" class="flex flex-wrap items-center gap-3">
              <button
                type="button"
                class="flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
                @click="retrySentence(sentence.id)"
              >
                <Icon name="lucide:refresh-cw" class="h-4 w-4" />
                再试一次
              </button>
            </div>

            <!-- 录音错误 -->
            <p
              v-if="recorderError && activeId === sentence.id"
              class="text-sm text-rose-500"
            >
              {{ recorderError }}
            </p>

            <!-- 句子级错误 -->
            <p v-if="getState(sentence.id).error" class="text-sm text-rose-500">
              {{ getState(sentence.id).error }}
            </p>

            <!-- 试听回放（已录制 or 已评分时显示） -->
            <div
              v-if="
                (getState(sentence.id).phase === 'recorded' || getState(sentence.id).phase === 'scored')
                && getState(sentence.id).blob
                && activeId === sentence.id
                && previewUrl
              "
              class="rounded-xl bg-slate-50 p-3"
            >
              <p class="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <Icon name="lucide:file-audio" class="h-3.5 w-3.5" />
                试听回放
              </p>
              <audio
                :src="previewUrl"
                controls
                preload="metadata"
                class="h-9 w-full"
              ></audio>
            </div>

            <!-- 评分结果详情 -->
            <div
              v-if="getState(sentence.id).phase === 'scored' && getState(sentence.id).score != null"
              class="mt-1 rounded-xl border p-4"
              :class="scoreColor(getState(sentence.id).score!)"
            >
              <div class="mb-2 flex items-center gap-2">
                <Icon name="lucide:circle-check" class="h-5 w-5" />
                <span class="text-sm font-semibold">
                  {{ scoreLabel(getState(sentence.id).score!) }} · {{ getState(sentence.id).score }} 分
                </span>
              </div>
              <div class="space-y-1 text-sm">
                <p>
                  <span class="font-medium">识别文本：</span>
                  {{ getState(sentence.id).transcript || '—' }}
                </p>
                <p>
                  <span class="font-medium">参考文本：</span>
                  {{ getState(sentence.id).reference || sentence.text }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部操作 -->
    <div v-if="sentences.length > 0" class="mt-8 flex justify-center gap-3">
      <button
        type="button"
        class="flex items-center gap-2 rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
        @click="loadSentences"
      >
        <Icon name="lucide:refresh-cw" class="h-4 w-4" />
        换一批句子
      </button>
    </div>
  </div>
</template>
