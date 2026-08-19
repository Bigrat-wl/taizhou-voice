/**
 * 统一提取错误文案。
 *
 * 优先读取 FastAPI 标准错误体 `err.data.detail`；
 * 其次尝试 `err.message`；
 * 兜底返回 `fallback`。
 */
export function getErrorDetail(err: unknown, fallback = '操作失败，请稍后再试'): string {
  if (err && typeof err === 'object' && 'data' in err) {
    const data = (err as { data?: { detail?: string } }).data
    if (data?.detail) return data.detail
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}
