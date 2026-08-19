# 泰州方言通 前端

基于 Nuxt 4 + Vue 3 的 Web 前端，包含挑战赛、转写、TTS、音频互转四个功能。

## 技术栈

- Nuxt 4 + Vue 3 + TypeScript
- Tailwind CSS（`@nuxtjs/tailwindcss`）
- 图标 `@nuxt/icon`（Lucide）

## 开发

```bash
pnpm install
pnpm dev          # http://localhost:3000
```

## 构建

```bash
pnpm build        # 产出 .output/
```

## 后端代理

开发期 `/api` 请求经 devServer proxy 转发到后端 FastAPI（`http://localhost:8000`），配置见 `nuxt.config.ts`。部署期跨域由后端 CORS 处理。
