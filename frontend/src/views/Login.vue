<script setup>
import { message } from 'ant-design-vue'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { setAuth } from '@/composables/auth'

const router = useRouter()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')
const shaking = ref(false)
const showPassword = ref(false)

async function submit() {
  if (!form.username || !form.password) {
    errorMsg.value = '请输入用户名和密码'
    shake()
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await api.post('/auth/login', form)
    setAuth(res.token, res.user)
    message.success(`欢迎回来，${res.user.display_name}`)
    router.push('/')
  } catch (e) {
    errorMsg.value = e.detail || '登录失败，请稍后重试'
    shake()
  } finally {
    loading.value = false
  }
}

function shake() {
  shaking.value = false
  requestAnimationFrame(() => { shaking.value = true })
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" :class="{ shake: shaking }" @submit.prevent="submit">
      <div class="logo">anan-agent</div>
      <p class="tagline">内容智能体工作台</p>

      <label class="field">
        <span>用户名</span>
        <input v-model.trim="form.username" autocomplete="username" placeholder="用户名" autofocus />
      </label>
      <label class="field">
        <span>密码</span>
        <div class="password-wrap">
          <input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="密码"
          />
          <button
            type="button"
            class="toggle-pwd"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            @click="showPassword = !showPassword"
          >
            <svg v-if="showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        </div>
      </label>

      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

      <button class="submit" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登 录' }}
      </button>
    </form>
  </div>
</template>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: 360px;
  padding: 40px 36px 36px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
  animation: rise-in 0.5s var(--ease-out) both;
}

.logo {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-align: center;
  text-shadow:
    1.5px 0 0 rgba(254, 44, 85, 0.55),
    -1.5px 0 0 rgba(37, 244, 238, 0.55);
}

.tagline {
  text-align: center;
  color: var(--text-3);
  font-size: 12.5px;
  margin: 6px 0 32px;
}

.field {
  display: block;
  margin-bottom: 18px;

  span {
    display: block;
    font-size: 12.5px;
    color: var(--text-2);
    margin-bottom: 6px;
  }

  input {
    width: 100%;
    padding: 11px 14px;
    background: var(--ink);
    border: 1px solid var(--line);
    border-radius: 9px;
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;

    &:focus {
      border-color: color-mix(in srgb, var(--neon) 50%, transparent);
      box-shadow: 0 0 0 3px var(--neon-dim);
    }
    &::placeholder { color: var(--text-3); }
  }
}

.error {
  margin: -6px 0 14px;
  font-size: 12.5px;
  color: var(--hot);
}

// 密码可见性切换
.password-wrap {
  position: relative;

  input {
    padding-right: 42px;
  }

  .toggle-pwd {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    padding: 0;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--text-3);
    cursor: pointer;
    transition: color 0.2s;

    &:hover {
      color: var(--text);
    }

    svg {
      width: 17px;
      height: 17px;
    }
  }
}

.submit {
  width: 100%;
  padding: 12px;
  margin-top: 6px;
  border: none;
  border-radius: 9px;
  background: var(--neon);
  color: var(--on-neon);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: box-shadow 0.25s, transform 0.15s var(--ease-out), opacity 0.2s;

  &:hover:not(:disabled) {
    box-shadow: 0 6px 24px var(--neon-dim);
  }
  &:active:not(:disabled) {
    transform: scale(0.97);
  }
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

// 登录失败抖动
.shake {
  animation: shake-x 0.4s ease;
}

@keyframes shake-x {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-5px); }
  80% { transform: translateX(5px); }
}
</style>
