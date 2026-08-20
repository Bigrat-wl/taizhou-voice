<script setup lang="ts">
import { navItems, type NavItem } from '~/composables/useNav'

const route = useRoute()
const router = useRouter()
const { isLoggedIn, nickname, logout } = useAuth()

/** Function pages (translate/transcribe/challenge) use fullHeight layout */
const fullHeight = computed(() => !!route.meta.fullHeight)

const dropdownOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

function isActive(item: NavItem): boolean {
  if (item.to === '/') return route.path === '/'
  return route.path.startsWith(item.to)
}

function toggleDropdown(): void {
  dropdownOpen.value = !dropdownOpen.value
}

function closeDropdown(): void {
  dropdownOpen.value = false
}

function handleLogout(): void {
  closeDropdown()
  logout()
  router.push('/')
}

function onClickOutside(event: MouseEvent): void {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <div :class="fullHeight ? 'flex h-screen flex-col overflow-hidden bg-slate-50 text-slate-900' : 'flex min-h-screen flex-col bg-slate-50 text-slate-900'">
    <header class="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <nav class="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <NuxtLink to="/" class="flex items-center gap-2 text-lg font-bold text-slate-900">
          <Icon name="lucide:volume-2" class="h-6 w-6 text-indigo-600" />
          <span>泰州方言通</span>
        </NuxtLink>

        <ul class="ml-auto flex items-center gap-1 overflow-x-auto">
          <li v-for="item in navItems" :key="item.to">
            <NuxtLink
              :to="item.to"
              class="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
              :class="isActive(item) ? 'bg-indigo-50 text-indigo-700' : ''"
            >
              <Icon :name="item.icon" class="h-4 w-4" />
              <span>{{ item.label }}</span>
            </NuxtLink>
          </li>
        </ul>

        <!-- 登录 / 用户下拉菜单 -->
        <div class="relative shrink-0 border-l border-slate-200 pl-3">
          <template v-if="isLoggedIn">
            <div ref="dropdownRef">
              <button
                type="button"
                class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
                @click="toggleDropdown"
              >
                <Icon name="lucide:user" class="h-4 w-4 text-indigo-600" />
                <span>{{ nickname || '用户' }}</span>
                <Icon
                  name="lucide:chevron-down"
                  class="h-3.5 w-3.5 text-slate-400 transition-transform"
                  :class="dropdownOpen ? 'rotate-180' : ''"
                />
              </button>
              <Transition
                enter-active-class="transition duration-100 ease-out"
                enter-from-class="scale-95 opacity-0"
                enter-to-class="scale-100 opacity-100"
                leave-active-class="transition duration-75 ease-in"
                leave-from-class="scale-100 opacity-100"
                leave-to-class="scale-95 opacity-0"
              >
                <div
                  v-if="dropdownOpen"
                  class="absolute right-0 z-50 mt-1 w-40 origin-top-right rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                >
                  <button
                    type="button"
                    class="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                    @click="handleLogout"
                  >
                    <Icon name="lucide:log-out" class="h-4 w-4" />
                    退出登录
                  </button>
                </div>
              </Transition>
            </div>
          </template>
          <NuxtLink
            v-else
            to="/login"
            class="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            <Icon name="lucide:log-in" class="h-4 w-4" />
            登录
          </NuxtLink>
        </div>
      </nav>
    </header>

    <main :class="fullHeight ? 'flex-1 min-h-0' : 'flex-1'">
      <slot />
    </main>

    <footer v-if="!fullHeight" class="border-t border-slate-200 py-4 text-center text-xs text-slate-400">
      泰州方言通 · 让泰州话讲下去
    </footer>
  </div>
</template>
