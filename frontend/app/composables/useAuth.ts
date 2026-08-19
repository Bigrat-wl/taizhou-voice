export interface AuthUser {
  id: number
  email: string
  nickname: string
}

export interface AuthResponse {
  token: string
  user: AuthUser
}

const TOKEN_KEY = 'token'
const USER_KEY = 'auth-user'

/**
 * 认证状态 + 登录/注册/登出。
 *
 * - token 持久化到 localStorage（key: `token`），应用内通过 useState 共享（SSR 安全）。
 * - user 同步持久化（key: `auth-user`），刷新后昵称等字段不丢失。
 * - 登录/注册成功后自动写入 token 并返回，由页面负责跳转。
 */
export function useAuth() {
  const token = useState<string | null>('auth-token', () => {
    if (import.meta.client) return localStorage.getItem(TOKEN_KEY)
    return null
  })
  const user = useState<AuthUser | null>('auth-user', () => {
    if (import.meta.client) {
      const raw = localStorage.getItem(USER_KEY)
      if (raw) {
        try { return JSON.parse(raw) as AuthUser } catch { /* ignore */ }
      }
    }
    return null
  })

  const isLoggedIn = computed(() => !!token.value)
  const nickname = computed(() => user.value?.nickname || '')

  function persist(): void {
    if (import.meta.client) {
      if (token.value) {
        localStorage.setItem(TOKEN_KEY, token.value)
        localStorage.setItem(USER_KEY, JSON.stringify(user.value))
      } else {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
      }
    }
  }

  async function applyAuth(respPromise: Promise<AuthResponse>): Promise<AuthResponse> {
    const data = await respPromise
    token.value = data.token
    user.value = data.user
    persist()
    return data
  }

  async function login(email: string, password: string): Promise<AuthResponse> {
    return applyAuth(
      $fetch<AuthResponse>('/api/auth/login', {
        method: 'POST',
        body: { email, password },
      }),
    )
  }

  async function register(
    email: string,
    password: string,
    nickname: string,
  ): Promise<AuthResponse> {
    return applyAuth(
      $fetch<AuthResponse>('/api/auth/register', {
        method: 'POST',
        body: { email, password, nickname },
      }),
    )
  }

  function logout(): void {
    token.value = null
    user.value = null
    persist()
  }

  return { token, user, nickname, isLoggedIn, login, register, logout }
}
