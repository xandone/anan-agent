import { createRouter, createWebHistory } from 'vue-router'
import { token } from '@/composables/auth'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/chat' },
  { path: '/dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/collect', component: () => import('@/views/Collect.vue') },
  { path: '/videos', component: () => import('@/views/Videos.vue') },
  { path: '/categories', component: () => import('@/views/Categories.vue') },
  { path: '/chat', component: () => import('@/views/Chat.vue') },
  { path: '/settings', component: () => import('@/views/Settings.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!token.value) return '/login'
  return true
})

export default router
