<script setup>
import { theme } from 'ant-design-vue'
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import { currentUser, logout } from '@/composables/auth'
import { themeMode, toggleTheme } from '@/composables/theme'

const route = useRoute()
const isLoginPage = computed(() => route.path === '/login')

const themeConfig = computed(() => {
  const dark = themeMode.value === 'dark'
  return {
    algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: dark ? '#25f4ee' : '#0d9488',
      colorError: dark ? '#fe2c55' : '#e62a50',
      colorBgBase: dark ? '#0e0e12' : '#f4f5f7',
      colorBgContainer: dark ? '#16161c' : '#ffffff',
      colorBgElevated: dark ? '#1c1c24' : '#ffffff',
      colorBorder: dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
      colorBorderSecondary: dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
      colorText: dark ? '#e8e8ec' : '#1a1a20',
      colorTextSecondary: dark ? '#8a8a94' : '#5a5a64',
      colorTextLightSolid: dark ? '#0a0a0d' : '#ffffff', // 主色按钮上的文字
      borderRadius: 10,
      fontFamily: `'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif`,
    },
  }
})

const navItems = [
  { path: '/dashboard', label: '数据看板', icon: '◔' },
  { path: '/collect', label: '采集任务', icon: '⬇' },
  { path: '/videos', label: '视频库', icon: '▤' },
  { path: '/categories', label: '智能体', icon: '◈' },
  { path: '/chat', label: '对话', icon: '✦' },
  { path: '/settings', label: '配置', icon: '⚙' },
]

const activeIndex = computed(() =>
  Math.max(0, navItems.findIndex((i) => route.path.startsWith(i.path))),
)
</script>

<template>
  <a-config-provider :theme="themeConfig">
    <!-- 登录页：无框架 -->
    <RouterView v-if="isLoginPage" />

    <div v-else class="shell">
      <aside class="rail">
        <router-link to="/" class="logo" data-text="anan-agent">anan-agent</router-link>
        <p class="tagline">内容智能体工作台</p>

        <nav class="nav" :style="{ '--active': activeIndex }">
          <span class="nav-indicator" aria-hidden="true" />
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: route.path.startsWith(item.path) }"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            {{ item.label }}
          </router-link>
        </nav>

        <div class="rail-foot">
          <span class="user-chip" :title="currentUser?.username">
            <span class="user-avatar">{{ (currentUser?.display_name || '?').charAt(0) }}</span>
            {{ currentUser?.display_name }}
          </span>
          <button class="logout-btn" title="退出登录" @click="logout">退出</button>
        </div>
      </aside>

      <main class="stage">
        <RouterView v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </RouterView>
      </main>

      <!-- 白天/黑夜切换：点击处圆形扩散 -->
      <button
        class="theme-toggle"
        :title="themeMode === 'dark' ? '切换到白天' : '切换到黑夜'"
        :aria-label="themeMode === 'dark' ? '切换到白天主题' : '切换到黑夜主题'"
        @click="toggleTheme"
      >
        {{ themeMode === 'dark' ? '☾' : '☀' }}
      </button>
    </div>
  </a-config-provider>
</template>

<style lang="scss" scoped>
.shell {
  display: flex;
  min-height: 100vh;
}

// ---------- 侧边导航轨 ----------
.rail {
  width: 216px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 28px 16px 20px;
  border-right: 1px solid var(--line);
  background: var(--ink-deep);
  position: sticky;
  top: 0;
  height: 100vh;
}

// Logo：霓虹色差重影，呼应抖音图标的青/红错位
.logo {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  text-decoration: none;
  position: relative;
  display: inline-block;
  text-shadow:
    1.5px 0 0 rgba(254, 44, 85, 0.55),
    -1.5px 0 0 rgba(37, 244, 238, 0.55);
  transition: text-shadow 0.3s var(--ease-out);

  &:hover {
    text-shadow:
      3px 0 0 rgba(254, 44, 85, 0.8),
      -3px 0 0 rgba(37, 244, 238, 0.8);
  }
}

.tagline {
  margin: 6px 0 32px;
  font-size: 12px;
  color: var(--text-3);
}

// 导航：滑动指示条
.nav {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: calc(var(--active) * 44px);
  width: 3px;
  height: 36px;
  margin-top: 2px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--neon), var(--hot));
  transition: top 0.35s var(--ease-out);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 44px;
  padding: 0 14px 0 18px;
  border-radius: 8px;
  color: var(--text-2);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s, background 0.2s;

  .nav-icon {
    font-size: 13px;
    opacity: 0.8;
    width: 18px;
    text-align: center;
  }

  &:hover {
    color: var(--text);
    background: var(--neon-dim);
  }

  &.active {
    color: var(--neon);
    background: var(--neon-dim);
    font-weight: 500;
  }
}

.rail-foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text-3);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-2);
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.user-avatar {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--on-neon);
  background: linear-gradient(135deg, var(--neon), var(--hot));
}

.logout-btn {
  margin-left: auto;
  flex-shrink: 0;
  padding: 3px 10px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    color: var(--hot);
    border-color: var(--hot);
  }
}

// ---------- 内容区 ----------
.stage {
  flex: 1;
  min-width: 0;
  padding: 32px 36px;
}

// 页面切换：淡出 + 轻微上浮
.page-enter-active {
  transition: opacity 0.25s var(--ease-out), transform 0.25s var(--ease-out);
}
.page-leave-active {
  transition: opacity 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.page-leave-to {
  opacity: 0;
}

// ---------- 主题切换按钮 ----------
.theme-toggle {
  position: fixed;
  top: 18px;
  right: 24px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
  background: var(--panel);
  color: var(--text-2);
  font-size: 17px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: border-color 0.25s, color 0.25s, box-shadow 0.25s, transform 0.15s var(--ease-out);

  &:hover {
    color: var(--neon);
    border-color: var(--neon);
    box-shadow: 0 0 16px var(--neon-dim);
  }

  &:active {
    transform: scale(0.9);
  }
}

@media (max-width: 768px) {  .rail {
    width: 64px;
    padding: 20px 8px;

    .tagline,
    .rail-foot,
    .nav-item:not(.active) .nav-icon + * {
      display: none;
    }
    .logo {
      font-size: 14px;
      writing-mode: vertical-lr;
    }
    .nav-item {
      justify-content: center;
      padding: 0;
      font-size: 0;
    }
    .nav-icon {
      font-size: 16px;
    }
  }
  .stage {
    padding: 20px 16px;
  }
}
</style>
