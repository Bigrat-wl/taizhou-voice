<script setup lang="ts">
import { navItems } from '~/composables/useNav'

const item = navItems.find((n) => n.to === '/convert')!
</script>

<template>
  <section class="mx-auto flex max-w-4xl flex-col items-center gap-4 px-4 py-20 text-center">
    <span class="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
      <Icon :name="item.icon" class="h-8 w-8" />
    </span>
    <h1 class="text-2xl font-bold text-slate-900">{{ item.label }}</h1>
    <p class="max-w-md text-slate-500">
      音频互转 · 功能开发中（方言 ↔ 普通话音频）。
    </p>
  </section>
</template>
