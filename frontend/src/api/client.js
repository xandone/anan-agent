import axios from 'axios'
import { clearAuth, token } from '@/composables/auth'

export const api = axios.create({ baseURL: '/api', timeout: 30000 })

api.interceptors.request.use((cfg) => {
  if (token.value) cfg.headers.Authorization = `Bearer ${token.value}`
  return cfg
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      clearAuth()
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err.response?.data || err)
  },
)
