<script setup lang="ts">
const { register } = useAuth()
const route = useRoute()
const router = useRouter()

const email = ref('')
const password = ref('')
const nickname = ref('')
const error = ref('')
const loading = ref(false)

const redirect = computed(() => (typeof route.query.redirect === 'string' ? route.query.redirect : '/'))

async function onSubmit() {
  error.value = ''
  if (!nickname.value.trim()) {
    error.value = '请输入昵称'
    return
  }
  if (!email.value) {
    error.value = '请输入邮箱'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  loading.value = true
  try {
    await register(email.value, password.value, nickname.value.trim())
    router.push(redirect.value)
  } catch (e: any) {
    error.value = e?.data?.detail || e?.message || '注册失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12">
    <div class="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div class="mb-6 flex flex-col items-center text-center">
        <span class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
          <Icon name="lucide:user-plus" class="h-6 w-6" />
        </span>
        <h1 class="text-xl font-bold text-slate-900">注册</h1>
        <p class="mt-1 text-sm text-slate-500">创建账号，开始泰州话挑战</p>
      </div>

      <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
        <label class="flex flex-col gap-1.5">
          <span class="text-sm font-medium text-slate-700">昵称</span>
          <span class="flex items-center gap-2 rounded-lg border border-slate-200 px-3 focus-within:border-indigo-400">
            <Icon name="lucide:user" class="h-4 w-4 shrink-0 text-slate-400" />
            <input
              v-model="nickname"
              type="text"
              autocomplete="nickname"
              maxlength="64"
              placeholder="老泰州"
              class="w-full py-2 text-sm outline-none"
            />
          </span>
        </label>

        <label class="flex flex-col gap-1.5">
          <span class="text-sm font-medium text-slate-700">邮箱</span>
          <span class="flex items-center gap-2 rounded-lg border border-slate-200 px-3 focus-within:border-indigo-400">
            <Icon name="lucide:mail" class="h-4 w-4 shrink-0 text-slate-400" />
            <input
              v-model="email"
              type="email"
              autocomplete="email"
              placeholder="you@example.com"
              class="w-full py-2 text-sm outline-none"
            />
          </span>
        </label>

        <label class="flex flex-col gap-1.5">
          <span class="text-sm font-medium text-slate-700">密码</span>
          <span class="flex items-center gap-2 rounded-lg border border-slate-200 px-3 focus-within:border-indigo-400">
            <Icon name="lucide:lock" class="h-4 w-4 shrink-0 text-slate-400" />
            <input
              v-model="password"
              type="password"
              autocomplete="new-password"
              placeholder="至少 6 位"
              class="w-full py-2 text-sm outline-none"
            />
          </span>
        </label>

        <p v-if="error" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="loading"
          class="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60"
        >
          <Icon v-if="loading" name="lucide:loader-circle" class="h-4 w-4 animate-spin" />
          <Icon v-else name="lucide:user-plus" class="h-4 w-4" />
          {{ loading ? '注册中…' : '注册' }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-slate-500">
        已有账号？
        <NuxtLink
          :to="{ path: '/login', query: route.query }"
          class="font-medium text-indigo-600 hover:underline"
        >
          去登录
        </NuxtLink>
      </p>
    </div>
  </section>
</template>
