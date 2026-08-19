<script setup lang="ts">
import { navItems } from '~/composables/useNav'

const item = navItems.find((n) => n.to === '/transcribe')!
</script>

<template>
  <section class="mx-auto flex max-w-4xl flex-col items-center gap-4 px-4 py-20 text-center">
    <span class="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
      <Icon :name="item.icon" class="h-8 w-8" />
    </span>
    <h1 class="text-2xl font-bold text-slate-900">{{ item.label }}</h1>
    <p class="max-w-md text-slate-500">
      转写 · 功能开发中（方言语音 → 普通话文本）。
    </p>
  </section>
</template>
