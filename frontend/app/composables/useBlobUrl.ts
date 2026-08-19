/**
 * useBlobUrl —— 为音频/视频 Blob 维护一个可播放的临时 object URL。
 *
 * 供 #13 挑战赛、#15 转写等「录音/上传 → 回放」页面复用：
 * 只需传入一个响应式 Blob 源（ref / getter），即可拿到随其变化的 `url`。
 *
 * 内存安全：
 * - 源 Blob 变化时，自动 `URL.revokeObjectURL` 释放旧地址再建新地址；
 * - 组件/作用域销毁时，自动释放当前地址，避免内存泄漏。
 *
 * 约定：调用方不直接持有 handlem，播放地址一律通过返回的 `url` 使用。
 */
import { shallowRef, watch, onScopeDispose, type MaybeRefOrGetter, toValue } from 'vue'

export function useBlobUrl(source: MaybeRefOrGetter<Blob | null>) {
  /** 当前可播放地址；源为空时为 null */
  const url = shallowRef<string | null>(null)

  function revokeCurrent() {
    if (url.value !== null) {
      URL.revokeObjectURL(url.value)
      url.value = null
    }
  }

  // 源变化（新 Blob 或清空）时：先释放旧地址，再按需生成新地址
  watch(
    () => toValue(source),
    (blob) => {
      revokeCurrent()
      if (blob) {
        url.value = URL.createObjectURL(blob)
      }
    },
    { immediate: true },
  )

  // 作用域销毁时兜底释放，防止泄漏
  onScopeDispose(revokeCurrent)

  return { url }
}
