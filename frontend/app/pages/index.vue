<script setup lang="ts">
const features = [
  {
    title: '转写',
    description: '方言语音 → 普通话文本',
    icon: 'lucide:mic',
    to: '/transcribe',
  },
  {
    title: '实时翻译',
    description: '方言 ↔ 普通话录音互译',
    icon: 'lucide:languages',
    to: '/translate',
  },
]
</script>

<template>
  <div class="mx-auto max-w-6xl px-4 py-10">
    <!-- 首屏 Hero：主入口 = 挑战赛 -->
    <section class="pb-10 text-center">
      <h1 class="text-3xl font-bold text-slate-900 sm:text-4xl">
        泰州方言通
      </h1>
      <p class="mx-auto mt-3 max-w-xl text-slate-500">
        刷句子 · 录音 · 评分 · 排行榜，游戏化地守护泰州话。
      </p>
    </section>

    <!-- 主入口：挑战赛（大卡片） -->
    <section class="mx-auto mb-6 max-w-2xl">
      <FeatureCard
        featured
        title="挑战赛"
        description="刷句子练发音，录音评分冲榜"
        icon="lucide:flame"
        to="/challenge"
      />
    </section>

    <!-- 次入口：转写 / 实时翻译（并列小卡片） -->
    <section class="mx-auto grid max-w-2xl gap-4 sm:grid-cols-2">
      <FeatureCard
        v-for="f in features"
        :key="f.to"
        :title="f.title"
        :description="f.description"
        :icon="f.icon"
        :to="f.to"
      />
    </section>
  </div>
</template>
