import { nextTick, ref, watch } from 'vue'

const STORAGE_KEY = 'anan-theme'

function initial() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) return saved
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export const themeMode = ref(initial())

function apply(mode) {
  document.documentElement.dataset.theme = mode
}

apply(themeMode.value)

watch(themeMode, (mode) => {
  localStorage.setItem(STORAGE_KEY, mode)
  apply(mode)
})

/**
 * 以点击位置为圆心，新主题圆形扩散覆盖全屏。
 * 依赖 View Transitions API（Chrome/Edge 111+），不支持时静默降级为直接切换。
 */
export function toggleTheme(event) {
  const next = themeMode.value === 'dark' ? 'light' : 'dark'

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (!document.startViewTransition || reduced) {
    themeMode.value = next
    return
  }

  const x = event?.clientX ?? window.innerWidth - 44
  const y = event?.clientY ?? 38
  // 半径取到最远角的距离，保证圆能覆盖全屏
  const radius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y),
  )

  const transition = document.startViewTransition(async () => {
    document.documentElement.classList.add('theme-animating') // 暂停逐元素颜色过渡
    themeMode.value = next
    await nextTick() // 等 Vue/AntDV 把新主题渲染进 DOM 再截取新快照
  })

  transition.finished.finally(() => {
    document.documentElement.classList.remove('theme-animating')
  })

  transition.ready.then(() => {
    document.documentElement.animate(
      {
        clipPath: [
          `circle(0px at ${x}px ${y}px)`,
          `circle(${radius}px at ${x}px ${y}px)`,
        ],
      },
      {
        duration: 550,
        easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
        pseudoElement: '::view-transition-new(root)',
      },
    )
  })
}

export const isDark = () => themeMode.value === 'dark'
