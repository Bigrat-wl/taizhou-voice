export interface NavItem {
  label: string
  to: string
  icon: string
}

/** 顶部导航 & 首页入口共用的功能项配置 */
export const navItems: NavItem[] = [
  { label: '首页', to: '/', icon: 'lucide:home' },
  { label: '挑战赛', to: '/challenge', icon: 'lucide:flame' },
  { label: '排行榜', to: '/leaderboard', icon: 'lucide:trophy' },
  { label: '转写', to: '/transcribe', icon: 'lucide:mic' },
  { label: 'TTS', to: '/tts', icon: 'lucide:volume-2' },
  { label: '音频互转', to: '/convert', icon: 'lucide:arrow-left-right' },
]
