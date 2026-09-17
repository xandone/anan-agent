import { ref } from 'vue'

export const token = ref(localStorage.getItem('anan-token') || '')
export const currentUser = ref(
  JSON.parse(localStorage.getItem('anan-user') || 'null'),
)

export function setAuth(t, user) {
  token.value = t
  currentUser.value = user
  localStorage.setItem('anan-token', t)
  localStorage.setItem('anan-user', JSON.stringify(user))
}

export function clearAuth() {
  token.value = ''
  currentUser.value = null
  localStorage.removeItem('anan-token')
  localStorage.removeItem('anan-user')
}

export function logout() {
  clearAuth()
  window.location.href = '/login'
}
