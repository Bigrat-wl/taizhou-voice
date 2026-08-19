<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description: string
    icon: string
    to: string
    /**
     * featured = 主入口大卡片；否则为普通小卡片
     */
    featured?: boolean
  }>(),
  { featured: false },
)
</script>

<template>
  <NuxtLink
    :to="to"
    class="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"
    :class="featured ? 'flex-col items-start gap-4 p-8' : ''"
  >
    <span
      class="flex shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white"
      :class="featured ? 'h-14 w-14' : 'h-12 w-12'"
    >
      <Icon :name="icon" class="h-6 w-6" />
    </span>

    <div>
      <h3 class="font-semibold text-slate-900" :class="featured ? 'text-2xl' : ''">
        {{ title }}
      </h3>
      <p class="mt-1 text-sm text-slate-500">{{ description }}</p>
    </div>

    <Icon
      v-if="featured"
      name="lucide:arrow-right"
      class="mt-2 h-5 w-5 text-indigo-500 transition group-hover:translate-x-1"
    />
  </NuxtLink>
</template>
