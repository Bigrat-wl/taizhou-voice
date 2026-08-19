// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: ['@nuxtjs/tailwindcss', '@nuxt/icon'],

  // 开发期后端代理：/api 与 /data（静态音频）→ FastAPI（:8000）；部署期靠后端 CORS
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://localhost:8000/api',
        changeOrigin: true
      },
      '/data': {
        target: 'http://localhost:8000/data',
        changeOrigin: true
      }
    }
  },

  icon: {
    clientBundle: {
      icons: [
        'lucide:home',
        'lucide:flame',
        'lucide:trophy',
        'lucide:mic',
        'lucide:volume-2',
        'lucide:arrow-left-right',
        'lucide:arrow-right',
        'lucide:file-audio',
        'lucide:file-text',
        'lucide:log-in',
        'lucide:log-out',
        'lucide:loader-circle',
        'lucide:lock',
        'lucide:mail',
        'lucide:square',
        'lucide:upload',
        'lucide:user',
        'lucide:user-plus',
        'lucide:check',
        'lucide:skip-forward',
        'lucide:refresh-cw',
        'lucide:send',
        'lucide:circle-check',
        'lucide:list-music',
      ]
    }
  }
})
