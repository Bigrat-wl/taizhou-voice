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
  { label: '实时翻译', to: '/translate', icon: 'lucide:languages' },
]
