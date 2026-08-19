<script setup lang="ts">
import { navItems, type NavItem } from '~/composables/useNav'

const route = useRoute()

function isActive(item: NavItem): boolean {
  if (item.to === '/') return route.path === '/'
  return route.path.startsWith(item.to)
}
</script>

<template>
  <div class="flex min-h-screen flex-col bg-slate-50 text-slate-900">
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
      </nav>
    </header>

    <main class="flex-1">
      <slot />
    </main>

    <footer class="border-t border-slate-200 py-4 text-center text-xs text-slate-400">
      泰州方言通 · 让泰州话讲下去
    </footer>
  </div>
</template>
