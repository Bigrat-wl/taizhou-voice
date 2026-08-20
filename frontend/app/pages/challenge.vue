<script setup lang="ts">
import { ref, shallowRef, computed } from 'vue'
import { navItems } from '~/composables/useNav'
import { useRecorder } from '~/composables/useRecorder'
import { useBlobUrl } from '~/composables/useBlobUrl'

definePageMeta({ fullHeight: true })

const item = navItems.find((n) => n.to === '/challenge')!

// ── 视图切换 ──
type View = 'entry' | 'random' | 'sentences' | 'sentence-detail'
const currentView = shallowRef<View>('entry')
const viewStack = shallowRef<View[]>([])

function pushView(v: View) {
  viewStack.value = [...viewStack.value, currentView.value]
  currentView.value = v
}
function popView() {
  const stack = [...viewStack.value]
  currentView.value = stack.pop() ?? 'entry'
  viewStack.value = stack
}

// ── 句子数据 ──
interface Sentence { id: number; text: string; dialect_text: string }
interface RankingItem { recording_id: number; nickname: string; audio_url: string; like_count: number; liked_by_me: boolean }

// ── 随机挑战 ──
const randomSentences = ref<Sentence[]>([])
const loadingRandom = shallowRef(false)
const randomError = shallowRef('')
const currentIndex = shallowRef(0)
const currentSentence = computed(() => randomSentences.value[currentIndex.value] ?? null)
const isLastSentence = computed(() => currentIndex.value >= randomSentences.value.length - 1)

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
    states.value[id] = { phase: 'idle', blob: null, fileName: '', score: null, transcript: '', reference: '', error: '' }
  }
  return states.value[id]
}

// ── 句子广场 ──
const allSentences = ref<Sentence[]>([])
const loadingAll = shallowRef(false)
const allError = shallowRef('')

// ── 句子详情 ──
const detailSentence = shallowRef<Sentence | null>(null)
const detailRankings = ref<RankingItem[]>([])
const loadingDetail = shallowRef(false)
const detailError = shallowRef('')

// ── 录音 ──
const { isRecording, isRecordingLabel, isSupported, errorMsg: recorderError, start: startRecording, stop: stopRecording } = useRecorder()
const activeId = shallowRef<number | null>(null)
const activeBlob = computed(() => (activeId.value != null ? getState(activeId.value).blob : null))
const { url: previewUrl } = useBlobUrl(activeBlob)

// ── 认证 ──
const { token, isLoggedIn } = useAuth()
const authHeaders = computed(() => token.value ? { Authorization: `Bearer ${token.value}` } : {})

// ── 进度（随机挑战） ──
const scoredCount = computed(() => randomSentences.value.filter(s => getState(s.id).phase === 'scored').length)
const progressPct = computed(() => randomSentences.value.length === 0 ? 0 : Math.round((scoredCount.value / randomSentences.value.length) * 100))
const allDone = computed(() => randomSentences.value.length > 0 && scoredCount.value === randomSentences.value.length)
const totalScore = computed(() => randomSentences.value.reduce((sum, s) => sum + (getState(s.id).score ?? 0), 0))
const avgScore = computed(() => scoredCount.value === 0 ? 0 : Math.round(totalScore.value / scoredCount.value))

// ── 分数辅助 ──
function scoreColor(s: number) { return s >= 90 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : s >= 60 ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-rose-50 text-rose-700 border-rose-200' }
function scoreLabel(s: number) { return s >= 90 ? '优秀' : s >= 60 ? '中等' : '不及格' }
function scoreBadge(s: number) { return s >= 90 ? 'bg-emerald-500' : s >= 60 ? 'bg-amber-500' : 'bg-rose-500' }
function scoreText(s: number) { return s >= 90 ? 'text-emerald-600' : s >= 60 ? 'text-amber-600' : 'text-rose-600' }
function formatTime(iso: string) { try { return new Date(iso).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' }) } catch { return '' } }

// ═══════════════════════════════════════════════
// 随机挑战
// ═══════════════════════════════════════════════
async function loadRandom() {
  loadingRandom.value = true; randomError.value = ''; states.value = {}; activeId.value = null; currentIndex.value = 0
  try {
    const data = await $fetch<{ sentences: Sentence[] }>('/api/sentences', { query: { n: 5 } })
    randomSentences.value = data.sentences
  } catch (err) { randomError.value = getErrorDetail(err, '获取句子失败') }
  finally { loadingRandom.value = false }
}

function enterRandom() { pushView('random'); loadRandom() }

async function toggleRecording(id: number) {
  const s = getState(id); s.error = ''
  if (isRecording.value && activeId.value === id) {
    try { const blob = await stopRecording(); activeId.value = id; s.blob = blob; s.fileName = `challenge-${id}-${Date.now()}.webm`; s.phase = 'recorded'; s.score = null; s.transcript = ''; s.reference = '' }
    catch (err) { s.error = err instanceof Error ? err.message : '录音失败' }
    return
  }
  activeId.value = id; s.blob = null; s.score = null; s.transcript = ''; s.reference = ''; s.phase = 'recording'
  try { await startRecording() } catch (err) { s.error = err instanceof Error ? err.message : '无法开始录音'; s.phase = 'idle' }
}

async function submitScore(id: number) {
  const s = getState(id); if (!s.blob || s.phase === 'submitting') return
  if (!isLoggedIn.value) { s.error = '请先登录'; return }
  s.phase = 'submitting'; s.error = ''
  try {
    const form = new FormData(); form.append('audio', s.blob, s.fileName); form.append('sentence_id', String(id))
    const data = await $fetch<{ score: number; transcript: string; reference: string }>('/api/score', { method: 'POST', body: form, headers: authHeaders.value })
    s.score = data.score; s.transcript = data.transcript; s.reference = data.reference; s.phase = 'scored'
  } catch (err) { s.error = getErrorDetail(err, '评分失败'); s.phase = 'recorded' }
}

function goNext() { if (!isLastSentence.value) { currentIndex.value++; activeId.value = null } }

function resetSentence(id: number) {
  const s = getState(id); s.phase = 'idle'; s.blob = null; s.score = null; s.transcript = ''; s.reference = ''; s.error = ''
}

// ═══════════════════════════════════════════════
// 句子广场
// ═══════════════════════════════════════════════
async function loadAllSentences() {
  loadingAll.value = true; allError.value = ''
  try {
    const data = await $fetch<{ sentences: Sentence[] }>('/api/sentences', { query: { n: 50 } })
    allSentences.value = data.sentences
  } catch (err) { allError.value = getErrorDetail(err, '获取句子失败') }
  finally { loadingAll.value = false }
}

function enterSentences() { pushView('sentences'); loadAllSentences() }

// ═══════════════════════════════════════════════
// 句子详情
// ═══════════════════════════════════════════════
async function loadSentenceDetail(s: Sentence) {
  detailSentence.value = s; loadingDetail.value = true; detailError.value = ''; detailRankings.value = []; activeId.value = null
  // 重置该句的录音状态
  states.value[s.id] = { phase: 'idle', blob: null, fileName: '', score: null, transcript: '', reference: '', error: '' }
  try {
    const data = await $fetch<{ sentence: Sentence; items: RankingItem[] }>(`/api/sentences/${s.id}/recordings`)
    detailRankings.value = data.items
  } catch (err) { detailError.value = getErrorDetail(err, '获取录音列表失败') }
  finally { loadingDetail.value = false }
}

function enterSentenceDetail(s: Sentence) { pushView('sentence-detail'); loadSentenceDetail(s) }

async function toggleLike(item: RankingItem) {
  if (!isLoggedIn.value) return
  const wasLiked = item.liked_by_me
  // 乐观更新
  item.liked_by_me = !wasLiked
  item.like_count += wasLiked ? -1 : 1
  try {
    await $fetch(`/api/recordings/${item.recording_id}/like`, {
      method: wasLiked ? 'DELETE' : 'POST',
      headers: authHeaders.value,
    })
  } catch {
    // 回滚
    item.liked_by_me = wasLiked
    item.like_count += wasLiked ? 1 : -1
  }
}
</script>

<template>
  <div class="flex h-full flex-col px-4 pb-4 w-full">
    <!-- ════════ 入口页 ════════ -->
    <template v-if="currentView === 'entry'">
      <section class="flex items-center gap-3 py-2 shrink-0">
        <NuxtLink to="/" class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100">
          <Icon name="lucide:arrow-left" class="h-4 w-4" />
        </NuxtLink>
        <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
          <Icon :name="item.icon" class="h-3.5 w-3.5" />
        </span>
        <h1 class="text-lg font-bold text-slate-900">{{ item.label }}</h1>
      </section>

      <div class="flex flex-1 min-h-0 flex-col items-center justify-center gap-4">
        <!-- 随机挑战 -->
        <button type="button" class="group flex w-full max-w-sm items-center gap-4 rounded-2xl border-2 border-amber-200 bg-amber-50 p-6 transition hover:border-amber-400 hover:bg-amber-100 hover:shadow-md" @click="enterRandom">
          <span class="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm transition group-hover:bg-amber-600">
            <Icon name="lucide:shuffle" class="h-7 w-7" />
          </span>
          <div class="text-left">
            <p class="text-lg font-bold text-amber-800">随机挑战</p>
            <p class="text-sm text-amber-600">随机 5 句，录一句评一句</p>
          </div>
          <Icon name="lucide:chevron-right" class="ml-auto h-5 w-5 text-amber-400 transition group-hover:translate-x-0.5" />
        </button>

        <!-- 句子广场 -->
        <button type="button" class="group flex w-full max-w-sm items-center gap-4 rounded-2xl border-2 border-sky-200 bg-sky-50 p-6 transition hover:border-sky-400 hover:bg-sky-100 hover:shadow-md" @click="enterSentences">
          <span class="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-sky-500 text-white shadow-sm transition group-hover:bg-sky-600">
            <Icon name="lucide:library" class="h-7 w-7" />
          </span>
          <div class="text-left">
            <p class="text-lg font-bold text-sky-800">句子广场</p>
            <p class="text-sm text-sky-600">浏览全部句子，听别人怎么念</p>
          </div>
          <Icon name="lucide:chevron-right" class="ml-auto h-5 w-5 text-sky-400 transition group-hover:translate-x-0.5" />
        </button>
      </div>
    </template>

    <!-- ════════ 随机挑战 ════════ -->
    <template v-if="currentView === 'random'">
      <section class="flex items-center gap-3 py-2 shrink-0">
        <button type="button" class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100" @click="popView">
          <Icon name="lucide:arrow-left" class="h-4 w-4" />
        </button>
        <h1 class="text-lg font-bold text-slate-900">
          <Icon name="lucide:shuffle" class="mr-1.5 inline h-4.5 w-4.5 text-amber-500" />
          随机挑战
        </h1>
        <span v-if="randomSentences.length > 0 && !allDone" class="ml-auto text-sm text-slate-500">
          {{ scoredCount }}/{{ randomSentences.length }}
        </span>
      </section>

      <!-- 进度条 -->
      <div v-if="randomSentences.length > 0 && !allDone" class="mb-2 shrink-0">
        <div class="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div class="h-full rounded-full bg-amber-500 transition-all duration-500" :style="{ width: `${progressPct}%` }"></div>
        </div>
      </div>

      <!-- 未登录提示 -->
      <div v-if="!isLoggedIn" class="mb-2 shrink-0 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-sm text-amber-700">
        <NuxtLink to="/login?redirect=/challenge" class="font-semibold underline">登录</NuxtLink> 后才能提交评分
      </div>

      <!-- 主体 -->
      <div class="flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div class="flex-1 min-h-0 overflow-y-auto p-5">
          <!-- 加载中 -->
          <div v-if="loadingRandom" class="flex flex-col items-center justify-center py-12">
            <Icon name="lucide:loader-circle" class="h-8 w-8 animate-spin text-amber-500" />
            <p class="mt-3 text-sm text-slate-500">正在加载…</p>
          </div>

          <!-- 错误 -->
          <div v-else-if="randomError" class="py-8 text-center text-sm text-rose-500">{{ randomError }}</div>

          <!-- 空 -->
          <div v-else-if="randomSentences.length === 0" class="flex flex-col items-center justify-center py-12 text-slate-400">
            <Icon name="lucide:shuffle" class="h-10 w-10" />
            <p class="mt-3 text-sm">点击下方按钮开始挑战</p>
          </div>

          <!-- 总结页 -->
          <div v-else-if="allDone" class="flex flex-col items-center gap-5 py-4">
            <div class="text-center">
              <p class="text-sm text-slate-500">本次挑战</p>
              <p class="mt-1 text-4xl font-black" :class="scoreText(avgScore)">{{ totalScore }}</p>
              <p class="text-xs text-slate-400">共 {{ randomSentences.length }} 句</p>
            </div>
            <div class="flex items-center gap-3 rounded-xl border bg-white px-5 py-3 shadow-sm">
              <div class="flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-white" :class="scoreBadge(avgScore)">
                <Icon v-if="avgScore >= 90" name="lucide:trophy" class="h-5 w-5" />
                <template v-else>{{ avgScore }}</template>
              </div>
              <div><p class="font-bold text-slate-900">平均分</p><p class="text-xs text-slate-500">{{ scoreLabel(avgScore) }}</p></div>
            </div>
            <div class="w-full space-y-1.5">
              <div v-for="(s, idx) in randomSentences" :key="s.id" class="flex items-center gap-2.5 rounded-lg px-3 py-2" :class="scoreColor(getState(s.id).score ?? 0)">
                <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/60 text-[10px] font-bold">{{ idx + 1 }}</span>
                <p class="min-w-0 flex-1 truncate text-sm font-medium">{{ s.text }}</p>
                <span class="text-xs font-bold">{{ getState(s.id).score }}</span>
              </div>
            </div>
            <div class="flex gap-3 pt-1">
              <button type="button" class="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600" @click="loadRandom">
                <Icon name="lucide:refresh-cw" class="h-3.5 w-3.5" />再来一轮
              </button>
              <button type="button" class="flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100" @click="popView">
                <Icon name="lucide:arrow-left" class="h-3.5 w-3.5" />返回
              </button>
            </div>
          </div>

          <!-- 单句卡片 -->
          <div v-else-if="currentSentence" class="mx-auto max-w-lg">
            <div class="rounded-2xl border bg-white shadow-sm overflow-hidden" :class="getState(currentSentence.id).phase === 'scored' ? scoreColor(getState(currentSentence.id).score!) : 'border-slate-200'">
              <!-- 句子头 -->
              <div class="border-b border-slate-100 px-5 py-4">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-600">{{ currentIndex + 1 }}</span>
                      <p class="text-lg font-bold text-slate-900">{{ currentSentence.text }}</p>
                    </div>
                    <p class="mt-1 pl-8 text-sm text-slate-500"><span class="font-medium text-amber-600">方言：</span>{{ currentSentence.dialect_text }}</p>
                  </div>
                  <div class="flex h-12 w-12 shrink-0 items-center justify-center">
                    <div v-show="getState(currentSentence.id).score != null" class="flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-white shadow" :class="scoreBadge(getState(currentSentence.id).score ?? 0)">
                      {{ getState(currentSentence.id).score }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- 操作区 -->
              <div class="px-5 py-4 space-y-3">
                <!-- 未评分 -->
                <template v-if="getState(currentSentence.id).phase !== 'scored'">
                  <div class="flex flex-wrap items-center gap-2">
                    <button type="button" :disabled="!isSupported || (isRecording && activeId !== currentSentence.id)" class="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:opacity-40" :class="isRecording && activeId === currentSentence.id ? 'bg-rose-500 hover:bg-rose-600' : 'bg-amber-500 hover:bg-amber-600'" @click="toggleRecording(currentSentence.id)">
                      <Icon :name="isRecording && activeId === currentSentence.id ? 'lucide:square' : 'lucide:mic'" class="h-3.5 w-3.5" />
                      {{ isRecording && activeId === currentSentence.id ? `停止 ${isRecordingLabel}` : getState(currentSentence.id).phase === 'recorded' ? '重录' : '录音' }}
                    </button>
                    <button v-show="(getState(currentSentence.id).phase === 'recorded' || getState(currentSentence.id).phase === 'submitting') && getState(currentSentence.id).blob" type="button" :disabled="getState(currentSentence.id).phase === 'submitting' || !isLoggedIn" class="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50" @click="submitScore(currentSentence.id)">
                      <Icon :name="getState(currentSentence.id).phase === 'submitting' ? 'lucide:loader-circle' : 'lucide:send'" class="h-3.5 w-3.5" :class="{ 'animate-spin': getState(currentSentence.id).phase === 'submitting' }" />
                      {{ getState(currentSentence.id).phase === 'submitting' ? '评分中…' : '提交评分' }}
                    </button>
                  </div>
                  <!-- 错误 -->
                  <div class="min-h-0">
                    <p v-show="recorderError && activeId === currentSentence.id" class="text-xs text-rose-500">{{ recorderError }}</p>
                    <p v-show="getState(currentSentence.id).error" class="text-xs text-rose-500">{{ getState(currentSentence.id).error }}</p>
                  </div>
                  <!-- 试听 -->
                  <div v-if="getState(currentSentence.id).phase === 'recorded' && getState(currentSentence.id).blob && activeId === currentSentence.id && previewUrl" class="rounded-xl bg-slate-50 p-3">
                    <p class="mb-1 text-xs font-medium text-slate-500"><Icon name="lucide:file-audio" class="mr-1 inline h-3 w-3" />试听</p>
                    <audio :src="previewUrl" controls preload="metadata" class="h-8 w-full"></audio>
                  </div>
                </template>

                <!-- 已评分 -->
                <template v-if="getState(currentSentence.id).phase === 'scored' && getState(currentSentence.id).score != null">
                  <div class="flex flex-col items-center py-3">
                    <div class="flex h-16 w-16 items-center justify-center rounded-full text-2xl font-black text-white shadow-lg" :class="scoreBadge(getState(currentSentence.id).score!)">{{ getState(currentSentence.id).score }}</div>
                    <p class="mt-2 font-bold" :class="scoreText(getState(currentSentence.id).score!)">{{ scoreLabel(getState(currentSentence.id).score!) }}</p>
                  </div>
                  <div class="rounded-xl border p-3 text-sm" :class="scoreColor(getState(currentSentence.id).score!)">
                    <p><span class="font-medium">识别：</span>{{ getState(currentSentence.id).transcript || '—' }}</p>
                    <p><span class="font-medium">参考：</span>{{ getState(currentSentence.id).reference || currentSentence.text }}</p>
                  </div>
                  <!-- 试听 -->
                  <div v-if="getState(currentSentence.id).blob && activeId === currentSentence.id && previewUrl" class="rounded-xl bg-slate-50 p-3">
                    <p class="mb-1 text-xs font-medium text-slate-500"><Icon name="lucide:file-audio" class="mr-1 inline h-3 w-3" />试听</p>
                    <audio :src="previewUrl" controls preload="metadata" class="h-8 w-full"></audio>
                  </div>
                  <div class="flex gap-2 pt-1">
                    <button v-if="!isLastSentence" type="button" class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600" @click="goNext">
                      下一句 <Icon name="lucide:arrow-right" class="h-3.5 w-3.5" />
                    </button>
                    <button v-else type="button" class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600" @click="currentIndex++">
                      查看总结 <Icon name="lucide:flag" class="h-3.5 w-3.5" />
                    </button>
                    <button type="button" class="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100" @click="resetSentence(currentSentence.id)">
                      <Icon name="lucide:refresh-cw" class="h-3.5 w-3.5" />重录
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ════════ 句子广场 ════════ -->
    <template v-if="currentView === 'sentences'">
      <section class="flex items-center gap-3 py-2 shrink-0">
        <button type="button" class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100" @click="popView">
          <Icon name="lucide:arrow-left" class="h-4 w-4" />
        </button>
        <h1 class="text-lg font-bold text-slate-900">
          <Icon name="lucide:library" class="mr-1.5 inline h-4.5 w-4.5 text-sky-500" />
          句子广场
        </h1>
      </section>

      <div class="flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div class="flex-1 min-h-0 overflow-y-auto p-4">
          <!-- 加载中 -->
          <div v-if="loadingAll" class="flex flex-col items-center justify-center py-12">
            <Icon name="lucide:loader-circle" class="h-8 w-8 animate-spin text-sky-500" />
          </div>

          <!-- 错误 -->
          <div v-else-if="allError" class="py-8 text-center text-sm text-rose-500">{{ allError }}</div>

          <!-- 句子列表 -->
          <div v-else class="space-y-2">
            <button
              v-for="s in allSentences" :key="s.id" type="button"
              class="group flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-sky-300 hover:bg-sky-50 hover:shadow-sm"
              @click="enterSentenceDetail(s)"
            >
              <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-500">
                <Icon name="lucide:message-circle" class="h-4 w-4" />
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-slate-800 truncate">{{ s.text }}</p>
                <p class="text-xs text-amber-600 truncate">{{ s.dialect_text }}</p>
              </div>
              <Icon name="lucide:chevron-right" class="h-4 w-4 shrink-0 text-slate-300 transition group-hover:text-sky-500" />
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- ════════ 句子详情 ════════ -->
    <template v-if="currentView === 'sentence-detail' && detailSentence">
      <section class="flex items-center gap-3 py-2 shrink-0">
        <button type="button" class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100" @click="popView">
          <Icon name="lucide:arrow-left" class="h-4 w-4" />
        </button>
        <h1 class="text-lg font-bold text-slate-900">
          <Icon name="lucide:book-open" class="mr-1.5 inline h-4.5 w-4.5 text-sky-500" />
          句子详情
        </h1>
      </section>

      <div class="flex flex-1 min-h-0 flex-col gap-3">
        <!-- 句子展示 + 录音区 -->
        <div class="shrink-0 rounded-2xl border border-sky-200 bg-sky-50 p-4">
          <p class="text-base font-bold text-slate-900">{{ detailSentence.text }}</p>
          <p class="mt-1 text-sm text-amber-600">{{ detailSentence.dialect_text }}</p>

          <!-- 录音 -->
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" :disabled="!isSupported || (isRecording && activeId !== detailSentence.id)" class="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:opacity-40" :class="isRecording && activeId === detailSentence.id ? 'bg-rose-500 hover:bg-rose-600' : 'bg-sky-500 hover:bg-sky-600'" @click="toggleRecording(detailSentence.id)">
              <Icon :name="isRecording && activeId === detailSentence.id ? 'lucide:square' : 'lucide:mic'" class="h-3.5 w-3.5" />
              {{ isRecording && activeId === detailSentence.id ? `停止 ${isRecordingLabel}` : getState(detailSentence.id).phase === 'recorded' ? '重录' : '录音' }}
            </button>
            <button v-show="(getState(detailSentence.id).phase === 'recorded' || getState(detailSentence.id).phase === 'submitting') && getState(detailSentence.id).blob" type="button" :disabled="getState(detailSentence.id).phase === 'submitting' || !isLoggedIn" class="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50" @click="submitScore(detailSentence.id)">
              <Icon :name="getState(detailSentence.id).phase === 'submitting' ? 'lucide:loader-circle' : 'lucide:send'" class="h-3.5 w-3.5" :class="{ 'animate-spin': getState(detailSentence.id).phase === 'submitting' }" />
              {{ getState(detailSentence.id).phase === 'submitting' ? '评分中…' : '提交评分' }}
            </button>
          </div>

          <!-- 试听 -->
          <div v-if="getState(detailSentence.id).phase === 'recorded' && getState(detailSentence.id).blob && activeId === detailSentence.id && previewUrl" class="mt-2 rounded-lg bg-white/60 p-2">
            <audio :src="previewUrl" controls preload="metadata" class="h-8 w-full"></audio>
          </div>

          <!-- 评分结果 -->
          <div v-if="getState(detailSentence.id).phase === 'scored' && getState(detailSentence.id).score != null" class="mt-3 flex items-center gap-3 rounded-xl border p-3" :class="scoreColor(getState(detailSentence.id).score!)">
            <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-lg font-bold text-white" :class="scoreBadge(getState(detailSentence.id).score!)">
              <Icon v-if="getState(detailSentence.id).score! >= 90" name="lucide:star" class="h-5 w-5" />
              <template v-else>{{ getState(detailSentence.id).score }}</template>
            </div>
            <div class="min-w-0 flex-1 text-sm">
              <p class="font-bold" :class="scoreText(getState(detailSentence.id).score!)">{{ scoreLabel(getState(detailSentence.id).score!) }}</p>
              <p class="text-slate-600 truncate">识别：{{ getState(detailSentence.id).transcript || '—' }}</p>
            </div>
          </div>

          <!-- 错误 -->
          <div v-show="(recorderError && activeId === detailSentence.id) || getState(detailSentence.id).error" class="mt-2">
            <p class="text-xs text-rose-500">{{ recorderError && activeId === detailSentence.id ? recorderError : getState(detailSentence.id).error }}</p>
          </div>
        </div>

        <!-- 排行榜 -->
        <div class="flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div class="shrink-0 px-4 pt-3 pb-2">
            <h2 class="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <Icon name="lucide:trending-up" class="h-4 w-4 text-sky-500" />
              录音排行
              <span v-if="detailRankings.length > 0" class="ml-auto text-xs font-normal text-slate-400">{{ detailRankings.length }} 条</span>
            </h2>
          </div>
          <div class="flex-1 min-h-0 overflow-y-auto px-4 pb-3">
            <!-- 加载中 -->
            <div v-if="loadingDetail" class="flex justify-center py-8">
              <Icon name="lucide:loader-circle" class="h-6 w-6 animate-spin text-sky-400" />
            </div>
            <!-- 空 -->
            <div v-else-if="detailRankings.length === 0 && !detailError" class="flex flex-col items-center py-8 text-slate-400">
              <Icon name="lucide:mic" class="h-8 w-8" />
              <p class="mt-2 text-sm">暂无录音，来录第一句吧</p>
            </div>
            <!-- 错误 -->
            <div v-else-if="detailError" class="py-8 text-center text-sm text-rose-500">{{ detailError }}</div>
            <!-- 列表 -->
            <div v-else class="space-y-2">
              <div v-for="(r, idx) in detailRankings" :key="r.recording_id" class="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                <!-- 排名 -->
                <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold" :class="idx === 0 ? 'bg-amber-400 text-white' : idx === 1 ? 'bg-slate-300 text-white' : idx === 2 ? 'bg-orange-400 text-white' : 'bg-slate-100 text-slate-500'">
                  {{ idx + 1 }}
                </div>
                <!-- 昵称 + 播放 -->
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-medium text-slate-700 truncate">{{ r.nickname }}</p>
                  <audio v-if="r.audio_url" :src="r.audio_url" controls preload="none" class="mt-1 h-7 w-full"></audio>
                </div>
                <!-- 点赞 -->
                <button type="button" :disabled="!isLoggedIn" class="flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-xs transition" :class="r.liked_by_me ? 'bg-rose-50 text-rose-600' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'" @click="toggleLike(r)">
                  <Icon :name="r.liked_by_me ? 'lucide:heart' : 'lucide:heart'" class="h-3.5 w-3.5" :class="{ 'fill-rose-500': r.liked_by_me }" />
                  {{ r.like_count }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
