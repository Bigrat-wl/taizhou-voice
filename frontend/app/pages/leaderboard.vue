<script setup lang="ts">
import { ref, shallowRef, computed, onMounted } from 'vue'
import { navItems } from '~/composables/useNav'

const item = navItems.find((n) => n.to === '/leaderboard')!

// ── 认证 ──
const { token, isLoggedIn } = useAuth()
const authHeaders = computed(() =>
  token.value ? { Authorization: `Bearer ${token.value}` } : {},
)

// ── Tab 切换 ──
type Tab = 'correct' | 'likes'
const activeTab = shallowRef<Tab>('correct')

// ━━━ 正确数榜 ━━━
interface CorrectRankItem {
  rank: number
  nickname: string
  correct_count: number
  total_score: number
  best_score: number
}

const correctList = ref<CorrectRankItem[]>([])
const loadingCorrect = shallowRef(false)
const correctError = shallowRef('')

async function fetchCorrect() {
  loadingCorrect.value = true
  correctError.value = ''
  try {
    const data = await $fetch<CorrectRankItem[]>('/api/leaderboard/correct', {
      query: { limit: 20 },
    })
    correctList.value = data
  } catch (err) {
    correctError.value = getErrorDetail(err, '获取正确数榜失败')
  } finally {
    loadingCorrect.value = false
  }
}

// ━━━ 点赞数榜（某句子） ━━━
interface SentenceInfo { id: number; text: string; dialect_text: string }
interface RecordingItem {
  recording_id: number
  nickname: string
  audio_url: string
  like_count: number
  liked_by_me: boolean
}
interface SentenceRecordings {
  sentence: SentenceInfo
  items: RecordingItem[]
}

// 句子列表（供选择）
interface Sentence { id: number; text: string; dialect_text: string }
const sentences = ref<Sentence[]>([])
const loadingSentences = shallowRef(false)

// 当前选中句子
const selectedSentenceId = shallowRef<number | null>(null)

// 录音列表
const recordings = ref<SentenceRecordings | null>(null)
const loadingRecordings = shallowRef(false)
const recordingsError = shallowRef('')

// 当前正在播放的录音 id
const playingId = shallowRef<number | null>(null)

async function fetchSentences() {
  loadingSentences.value = true
  try {
    const data = await $fetch<{ sentences: Sentence[] }>('/api/sentences', {
      query: { n: 50 },
    })
    sentences.value = data.sentences
    if (sentences.value.length > 0 && selectedSentenceId.value === null) {
      selectedSentenceId.value = sentences.value[0].id
    }
  } catch {
    // 句子列表获取失败不阻塞主流程
  } finally {
    loadingSentences.value = false
  }
}

async function fetchRecordings(sentenceId: number) {
  loadingRecordings.value = true
  recordingsError.value = ''
  recordings.value = null
  try {
    const data = await $fetch<SentenceRecordings>(
      `/api/sentences/${sentenceId}/recordings`,
      { headers: authHeaders.value },
    )
    recordings.value = data
  } catch (err) {
    recordingsError.value = getErrorDetail(err, '获取录音列表失败')
  } finally {
    loadingRecordings.value = false
  }
}

// 选中句子变化时重新加载
function selectSentence(id: number) {
  selectedSentenceId.value = id
  playingId.value = null
  fetchRecordings(id)
}

// ━━━ 点赞/取消点赞 ━━━
const likingId = shallowRef<number | null>(null)

async function toggleLike(recording: RecordingItem) {
  if (!isLoggedIn.value) return
  if (likingId.value === recording.recording_id) return
  likingId.value = recording.recording_id

  try {
    const method = recording.liked_by_me ? 'DELETE' : 'POST'
    const data = await $fetch<{ like_count: number; liked_by_me: boolean }>(
      `/api/recordings/${recording.recording_id}/like`,
      { method, headers: authHeaders.value },
    )
    recording.like_count = data.like_count
    recording.liked_by_me = data.liked_by_me
  } catch {
    // 静默失败，不弹错误
  } finally {
    likingId.value = null
  }
}

// ━━━ 音频播放 ━━━
const audioEl = shallowRef<HTMLAudioElement | null>(null)

function playRecording(item: RecordingItem) {
  // 点击正在播放的 → 暂停
  if (playingId.value === item.recording_id && audioEl.value) {
    audioEl.value.pause()
    playingId.value = null
    return
  }

  // 停止之前的
  if (audioEl.value) {
    audioEl.value.pause()
    audioEl.value = null
  }

  playingId.value = item.recording_id
  const audio = new Audio(item.audio_url)
  audioEl.value = audio
  audio.play().catch(() => { playingId.value = null })
  audio.onended = () => { playingId.value = null }
}

// ━━━ 分数颜色辅助 ━━━
function scoreBadgeColor(score: number): string {
  if (score >= 90) return 'bg-emerald-500'
  if (score >= 60) return 'bg-amber-500'
  return 'bg-rose-500'
}

// ━━━ 初始化 ━━━
onMounted(() => {
  fetchCorrect()
  fetchSentences()
})

// Tab 切换时懒加载
function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'correct' && correctList.value.length === 0 && !loadingCorrect.value) {
    fetchCorrect()
  }
  if (tab === 'likes' && selectedSentenceId.value && recordings.value === null && !loadingRecordings.value) {
    fetchRecordings(selectedSentenceId.value)
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <!-- 页头 -->
    <section class="mb-6 text-center">
      <span class="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-rose-100 text-rose-600">
        <Icon :name="item.icon" class="h-4 w-4" />
      </span>
      <h1 class="mt-2 text-xl font-bold text-slate-900">{{ item.label }}</h1>
    </section>

    <!-- Tab 切换 -->
    <div class="mb-6 flex rounded-xl bg-slate-100 p-1">
      <button
        type="button"
        class="flex-1 rounded-lg py-2.5 text-sm font-semibold transition"
        :class="activeTab === 'correct' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
        @click="switchTab('correct')"
      >
        <Icon name="lucide:trophy" class="mr-1.5 inline h-4 w-4" />
        正确数榜
      </button>
      <button
        type="button"
        class="flex-1 rounded-lg py-2.5 text-sm font-semibold transition"
        :class="activeTab === 'likes' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
        @click="switchTab('likes')"
      >
        <Icon name="lucide:heart" class="mr-1.5 inline h-4 w-4" />
        点赞榜
      </button>
    </div>

    <!-- ━━━ 正确数榜 Tab ━━━ -->
    <div v-show="activeTab === 'correct'">
      <!-- 加载中 -->
      <div v-if="loadingCorrect" class="py-16 text-center">
        <Icon name="lucide:loader-circle" class="mx-auto h-8 w-8 animate-spin text-indigo-500" />
        <p class="mt-3 text-sm text-slate-500">加载中…</p>
      </div>

      <!-- 错误 -->
      <p v-if="correctError" class="rounded-lg bg-rose-50 px-4 py-3 text-center text-sm text-rose-600">
        {{ correctError }}
      </p>

      <!-- 空状态 -->
      <div
        v-if="!loadingCorrect && !correctError && correctList.length === 0"
        class="rounded-2xl border border-slate-200 bg-white p-12 text-center"
      >
        <Icon name="lucide:trophy" class="mx-auto h-12 w-12 text-slate-300" />
        <p class="mt-4 text-slate-500">暂无排名数据，快来挑战吧！</p>
      </div>

      <!-- 排行列表 -->
      <div v-if="correctList.length > 0" class="flex flex-col gap-2">
        <!-- 前三名突出 -->
        <div
          v-for="(item, idx) in correctList.slice(0, 3)"
          :key="item.rank"
          class="flex items-center gap-4 rounded-2xl border bg-white px-5 py-4 shadow-sm transition hover:shadow-md"
          :class="{
            'border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50': idx === 0,
            'border-slate-300 bg-gradient-to-r from-slate-50 to-gray-50': idx === 1,
            'border-orange-300 bg-gradient-to-r from-orange-50 to-amber-50': idx === 2,
          }"
        >
          <!-- 名次徽章 -->
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-bold text-white"
            :class="{
              'bg-amber-500': idx === 0,
              'bg-slate-400': idx === 1,
              'bg-orange-500': idx === 2,
            }"
          >
            {{ item.rank }}
          </div>
          <!-- 信息 -->
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold text-slate-900">{{ item.nickname }}</p>
            <p class="text-xs text-slate-500">
              总分 {{ item.total_score }} · 最高 {{ item.best_score }}
            </p>
          </div>
          <!-- 正确数 -->
          <div class="text-right">
            <p class="text-2xl font-bold text-indigo-600">{{ item.correct_count }}</p>
            <p class="text-xs text-slate-400">句正确</p>
          </div>
        </div>

        <!-- 第 4 名起 -->
        <div
          v-for="item in correctList.slice(3)"
          :key="item.rank"
          class="flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-3 transition hover:bg-slate-50"
        >
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-500">
            {{ item.rank }}
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-slate-800">{{ item.nickname }}</p>
            <p class="text-xs text-slate-400">
              总分 {{ item.total_score }} · 最高 {{ item.best_score }}
            </p>
          </div>
          <div class="text-right">
            <p class="text-lg font-bold text-indigo-600">{{ item.correct_count }}</p>
            <p class="text-xs text-slate-400">句正确</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ━━━ 点赞榜 Tab ━━━ -->
    <div v-show="activeTab === 'likes'">
      <!-- 句子选择器 -->
      <div class="mb-6">
        <label class="mb-2 block text-sm font-medium text-slate-700">选择句子</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="s in sentences"
            :key="s.id"
            type="button"
            class="rounded-lg border px-3 py-1.5 text-xs font-medium transition"
            :class="
              selectedSentenceId === s.id
                ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            "
            @click="selectSentence(s.id)"
          >
            {{ s.text }}
          </button>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loadingRecordings" class="py-12 text-center">
        <Icon name="lucide:loader-circle" class="mx-auto h-8 w-8 animate-spin text-indigo-500" />
        <p class="mt-3 text-sm text-slate-500">加载录音…</p>
      </div>

      <!-- 错误 -->
      <p v-if="recordingsError" class="rounded-lg bg-rose-50 px-4 py-3 text-center text-sm text-rose-600">
        {{ recordingsError }}
      </p>

      <!-- 句子信息 -->
      <div
        v-if="recordings && recordings.sentence"
        class="mb-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4"
      >
        <p class="text-base font-semibold text-indigo-900">{{ recordings.sentence.text }}</p>
        <p class="mt-1 text-sm text-indigo-600">
          <span class="font-medium">方言：</span>{{ recordings.sentence.dialect_text }}
        </p>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!loadingRecordings && !recordingsError && recordings && recordings.items.length === 0"
        class="rounded-2xl border border-slate-200 bg-white p-12 text-center"
      >
        <Icon name="lucide:mic-off" class="mx-auto h-12 w-12 text-slate-300" />
        <p class="mt-4 text-slate-500">暂无录音，去挑战赛录一条吧！</p>
      </div>

      <!-- 录音列表 -->
      <div v-if="recordings && recordings.items.length > 0" class="flex flex-col gap-3">
        <div
          v-for="(rec, idx) in recordings.items"
          :key="rec.recording_id"
          class="flex items-center gap-4 rounded-2xl border bg-white px-5 py-4 shadow-sm transition hover:shadow-md"
          :class="{
            'border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50': idx === 0,
            'border-slate-300 bg-gradient-to-r from-slate-50 to-gray-50': idx === 1,
            'border-orange-300 bg-gradient-to-r from-orange-50 to-amber-50': idx === 2,
          }"
        >
          <!-- 排名 -->
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
            :class="{
              'bg-amber-500': idx === 0,
              'bg-slate-400': idx === 1,
              'bg-orange-500': idx === 2,
              'bg-slate-300': idx > 2,
            }"
          >
            {{ idx + 1 }}
          </div>

          <!-- 播放按钮 -->
          <button
            type="button"
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition"
            :class="
              playingId === rec.recording_id
                ? 'bg-indigo-600 text-white'
                : 'bg-indigo-100 text-indigo-600 hover:bg-indigo-200'
            "
            @click="playRecording(rec)"
          >
            <Icon
              :name="playingId === rec.recording_id ? 'lucide:pause' : 'lucide:play'"
              class="h-5 w-5"
            />
          </button>

          <!-- 昵称 -->
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-slate-800">{{ rec.nickname }}</p>
          </div>

          <!-- 点赞按钮 -->
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="
              rec.liked_by_me
                ? 'bg-rose-100 text-rose-600 hover:bg-rose-200'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-700'
            "
            :disabled="!isLoggedIn || likingId === rec.recording_id"
            :title="!isLoggedIn ? '请先登录' : ''"
            @click="toggleLike(rec)"
          >
            <Icon
              :name="rec.liked_by_me ? 'lucide:heart' : 'lucide:heart'"
              class="h-4 w-4"
              :class="rec.liked_by_me ? 'fill-current' : ''"
            />
            {{ rec.like_count }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
