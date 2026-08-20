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
        'lucide:alert-circle',
        'lucide:arrow-left',
        'lucide:arrow-left-right',
        'lucide:arrow-right',
        'lucide:book-open',
        'lucide:check',
        'lucide:chevron-down',
        'lucide:chevron-right',
        'lucide:circle-check',
        'lucide:file-audio',
        'lucide:file-text',
        'lucide:flag',
        'lucide:flame',
        'lucide:flask-conical',
        'lucide:heart',
        'lucide:home',
        'lucide:languages',
        'lucide:library',
        'lucide:list',
        'lucide:list-music',
        'lucide:loader-circle',
        'lucide:lock',
        'lucide:log-in',
        'lucide:log-out',
        'lucide:mail',
        'lucide:message-circle',
        'lucide:mic',
        'lucide:mic-off',
        'lucide:music',
        'lucide:pause',
        'lucide:play',
        'lucide:refresh-cw',
        'lucide:scan-text',
        'lucide:send',
        'lucide:shuffle',
        'lucide:skip-forward',
        'lucide:square',
        'lucide:star',
        'lucide:trending-up',
        'lucide:trophy',
        'lucide:upload',
        'lucide:user',
        'lucide:user-plus',
        'lucide:volume-2',
      ]
    }
  }
})
