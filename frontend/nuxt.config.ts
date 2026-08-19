// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: ['@nuxtjs/tailwindcss', '@nuxt/icon'],

  // 开发期后端代理：/api → FastAPI（:8000）；部署期靠后端 CORS
  devServer: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
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
      ]
    }
  }
})
