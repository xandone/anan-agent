<script setup>
import { message } from 'ant-design-vue'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'
import { token } from '@/composables/auth'

const md = new MarkdownIt({ linkify: true, breaks: true })
const renderMd = (t) => DOMPurify.sanitize(md.render(t || ''))

const categories = ref([])
const selectedSlug = ref()
const conversations = ref([])
const conversationId = ref(null)
const input = ref('')
const sending = ref(false)
let abortCtrl = null // SSE 请求的中断控制器

function stopSending() {
  abortCtrl?.abort()
}
const messages = ref([]) // { role, text, meta?, streaming? }
const scrollBox = ref(null)

// 删除确认
const deleteTarget = ref(null)
const deleting = ref(false)

const current = computed(() =>
  categories.value.find((c) => c.slug === selectedSlug.value),
)
const catName = (slug) => categories.value.find((c) => c.slug === slug)?.name || slug

async function scrollToBottom() {
  await nextTick()
  scrollBox.value?.scrollTo({ top: scrollBox.value.scrollHeight, behavior: 'smooth' })
}

// ---------- 历史会话 ----------

async function loadConversations() {
  conversations.value = await api.get('/conversations')
}

async function openConversation(id) {
  const res = await api.get(`/conversations/${id}`)
  conversationId.value = res.id
  selectedSlug.value = res.category_slug
  messages.value = res.messages.map((m) => ({
    role: m.role === 'user' ? 'user' : 'agent',
    text: m.content,
    meta: m.role === 'assistant' ? buildMeta(m) : null,
  }))
  scrollToBottom()
}

function askDelete(c, e) {
  e.stopPropagation()
  deleteTarget.value = c
}

async function confirmDelete() {
  deleting.value = true
  try {
    await api.delete(`/conversations/${deleteTarget.value.id}`)
    message.success('会话已删除')
    if (conversationId.value === deleteTarget.value.id) newChat()
    deleteTarget.value = null
    loadConversations()
  } catch (e) {
    message.error(e.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

function newChat(slug) {
  if (slug) selectedSlug.value = slug
  conversationId.value = null
  messages.value = []
}

// ---------- SSE 流式发送 ----------

function buildMeta(m) {
  const parts = []
  if (m.duration_ms != null) parts.push(`${(m.duration_ms / 1000).toFixed(2)}s`)
  const tokens = m.usage?.total_tokens ?? ((m.prompt_tokens ?? 0) + (m.completion_tokens ?? 0))
  if (tokens) parts.push(`${tokens} tokens`)
  if (m.context_count != null) {
    parts.push(m.context_count > 0 ? `检索 ${m.context_count} 条语料` : '语料库暂无此类内容')
  }
  return parts.join(' · ')
}

async function send() {
  const question = input.value.trim()
  if (!question || !selectedSlug.value || sending.value) return
  input.value = ''
  await nextTick()
  autoResize() // 清空后收回输入框高度
  messages.value.push({ role: 'user', text: question })
  streamAnswer(question)
}

async function streamAnswer(question) {
  sending.value = true
  abortCtrl = new AbortController()

  // 注意：必须用 reactive 包装，直接改普通对象不会触发 Vue 更新
  const agentMsg = reactive({ role: 'agent', text: '', reasoning: '', meta: null, streaming: true })
  messages.value.push(agentMsg)
  scrollToBottom()

  const t0 = performance.now()
  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token.value}`,
      },
      body: JSON.stringify({
        category_slug: selectedSlug.value,
        question,
        conversation_id: conversationId.value,
      }),
      signal: abortCtrl.signal,
    })
    if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let stats = {}

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const events = buf.split('\n\n')
      buf = events.pop() // 最后半段留到下次
      for (const block of events) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        const data = JSON.parse(line.slice(5))
        if (data.type === 'meta') {
          stats.context_count = data.context_count
          if (!conversationId.value) conversationId.value = data.conversation_id
        } else if (data.type === 'delta') {
          agentMsg.text += data.text
          scrollToBottom()
        } else if (data.type === 'reasoning') {
          agentMsg.reasoning += data.text
          scrollToBottom()
        } else if (data.type === 'done') {
          stats.duration_ms = data.duration_ms
          stats.usage = data.usage
        } else if (data.type === 'error') {
          throw new Error(data.message)
        }
      }
    }

    // 端点不回传 usage 时用本地计时兜底
    if (stats.duration_ms == null) stats.duration_ms = Math.round(performance.now() - t0)
    agentMsg.meta = buildMeta(stats)
  } catch (e) {
    if (e.name === 'AbortError') {
      // 用户主动停止：保留已生成部分，并通知后端落库（服务端不一定能感知断连）
      if (!agentMsg.text) agentMsg.text = '（已停止生成）'
      agentMsg.meta = buildMeta({ duration_ms: Math.round(performance.now() - t0) }) + ' · 已停止'
      if (conversationId.value && agentMsg.text.trim() && agentMsg.text !== '（已停止生成）') {
        api.post('/chat/save', {
          conversation_id: conversationId.value,
          content: agentMsg.text,
          duration_ms: Math.round(performance.now() - t0),
        }).catch(() => {}) // 落库失败不影响界面
      }
    } else {
      agentMsg.text = agentMsg.text || `出错了：${e.message || e}`
    }
  } finally {
    agentMsg.streaming = false
    sending.value = false
    abortCtrl = null
    scrollToBottom()
    loadConversations()
  }
}

// ---------- 输入框自适应高度 ----------

const composerInput = ref(null)
const COMPOSER_MAX_HEIGHT = 160

function autoResize() {
  const el = composerInput.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, COMPOSER_MAX_HEIGHT)}px`
}

const fmtTime = (iso) => {
  const d = new Date(iso)
  const sameDay = d.toDateString() === new Date().toDateString()
  return sameDay ? d.toTimeString().slice(0, 5) : `${d.getMonth() + 1}/${d.getDate()}`
}

// ---------- 复制 ----------

const copiedIdx = ref(-1)
let copyTimer = null

async function copyText(text, idx) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 剪贴板 API 不可用时的降级（如非安全上下文）
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
  copiedIdx.value = idx
  clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedIdx.value = -1 }, 1500)
}

// ---------- 重新生成 ----------

function regenerate(idx) {
  if (sending.value) return
  // 找到这条回答对应的用户提问
  let qIdx = idx - 1
  while (qIdx >= 0 && messages.value[qIdx].role !== 'user') qIdx--
  if (qIdx < 0) return
  const question = messages.value[qIdx].text
  messages.value.splice(idx, 1) // 移除旧回答，重新流式生成
  streamAnswer(question)
}

// 智能体列表标识色
const hues = ['#25f4ee', '#fe2c55', '#b18cff', '#ffb020', '#3ddc84', '#ff7a45']
const hueOf = (i) => hues[i % hues.length]

onMounted(async () => {
  categories.value = await api.get('/categories')
  const first = categories.value.find((c) => c.enabled)
  if (first) selectedSlug.value = first.slug
  loadConversations()
})
</script>

<template>
  <div class="chat-page rise">
    <!-- 左：历史会话 -->
    <aside class="history panel">
      <button class="new-chat" @click="newChat()">+ 新对话</button>
      <div class="panel-scroll">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="history-item"
          :class="{ active: c.id === conversationId }"
          @click="openConversation(c.id)"
        >
          <div class="history-title">{{ c.title }}</div>
          <div class="history-sub">
            <span class="history-cat">{{ catName(c.category_slug) }}</span>
            <span class="num">{{ fmtTime(c.updated_at) }}</span>
            <button class="history-del" title="删除会话" @click="askDelete(c, $event)">×</button>
          </div>
        </div>
        <p v-if="!conversations.length" class="panel-empty">还没有历史对话</p>
      </div>
    </aside>

    <!-- 中：聊天主界面 -->
    <section class="chat-main">
      <div ref="scrollBox" class="chat-scroll">
        <div v-if="!messages.length" class="welcome">
          <div class="welcome-sigil">✦</div>
          <p class="welcome-title">{{ current?.name || '智能体' }}</p>
          <p class="welcome-desc">{{ current?.description }}</p>
        </div>

        <transition-group name="msg">
          <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
            <div class="msg-col">
              <div class="bubble">
                <!-- 流式等待首字时，气泡内直接显示三点律动，不再单独渲染第二个气泡 -->
                <div v-if="m.streaming && !m.text && !m.reasoning" class="typing"><span /><span /><span /></div>
                <!-- 思考过程：可折叠，默认在生成中展开、完成后收起 -->
                <details v-if="m.reasoning" class="reasoning" :open="m.streaming && !m.text">
                  <summary>思考过程</summary>
                  <div class="reasoning-text">{{ m.reasoning }}</div>
                </details>
                <!-- 用户消息纯文本，智能体消息渲染 Markdown -->
                <template v-if="m.text">
                  <div v-if="m.role === 'agent'" class="text md" v-html="renderMd(m.text)" />
                  <div v-else class="text">{{ m.text }}</div>
                </template>
                <span v-if="m.streaming && (m.text || m.reasoning)" class="cursor" />
                <div v-if="m.meta" class="meta">{{ m.meta }}</div>
              </div>
              <!-- 操作栏：固定在气泡下方 -->
              <div v-if="m.text && !m.streaming" class="actions">
                <button class="action-btn" :class="{ copied: copiedIdx === i }"
                  @click="copyText(m.text, i)">
                  {{ copiedIdx === i ? '✓ 已复制' : '⧉ 复制' }}
                </button>
                <button v-if="m.role === 'agent'" class="action-btn"
                  :disabled="sending" @click="regenerate(i)">
                  ↻ 重新生成
                </button>
              </div>
            </div>
          </div>
        </transition-group>
      </div>

      <div class="composer">
        <textarea
          ref="composerInput"
          v-model="input"
          class="composer-input"
          rows="1"
          :placeholder="`问点什么，${current?.name || ''}在听…（Enter 发送，Shift+Enter 换行）`"
          :disabled="sending || !selectedSlug"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
        />
        <button
          class="composer-send"
          :class="{ stopping: sending }"
          :disabled="!sending && !input.trim()"
          :title="sending ? '停止生成' : '发送'"
          :aria-label="sending ? '停止生成' : '发送'"
          @click="sending ? stopSending() : send()"
        >
          {{ sending ? '■' : '↑' }}
        </button>
      </div>
    </section>

    <!-- 右：智能体列表 -->
    <aside class="agents panel">
      <p class="panel-label">选择智能体</p>
      <div class="panel-scroll">
        <button
          v-for="(c, i) in categories.filter((x) => x.enabled)"
          :key="c.slug"
          class="agent-item"
          :class="{ active: c.slug === selectedSlug }"
          :style="{ '--hue': hueOf(i) }"
          @click="newChat(c.slug)"
        >
          <span class="agent-dot">{{ c.name.charAt(0) }}</span>
          <span class="agent-info">
            <span class="agent-name">{{ c.name }}</span>
            <span class="agent-desc">{{ c.description || '这个人格还没有定义' }}</span>
          </span>
        </button>
        <p v-if="!categories.length" class="panel-empty">还没有智能体</p>
      </div>
    </aside>

    <!-- 删除二次确认 -->
    <a-modal
      :open="!!deleteTarget"
      title="删除会话"
      :confirm-loading="deleting"
      ok-text="删除"
      :ok-button-props="{ danger: true }"
      cancel-text="再想想"
      @ok="confirmDelete"
      @cancel="deleteTarget = null"
    >
      <p>确定删除会话「{{ deleteTarget?.title }}」吗？对话记录会一并清除，无法恢复。</p>
    </a-modal>
  </div>
</template>

<style lang="scss" scoped>
// 三栏：历史 | 对话 | 智能体，左右两栏贴边
.chat-page {
  display: flex;
  gap: 20px;
  width: 100%;
  height: calc(100vh - 96px);
  min-height: 480px;
}

.panel {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}

.panel-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}

.panel-label {
  margin: 0;
  padding: 16px 16px 10px;
  font-family: var(--font-display);
  font-size: 12px;
  letter-spacing: 0.06em;
  color: var(--text-2);
}

.panel-empty {
  text-align: center;
  color: var(--text-3);
  font-size: 12.5px;
  padding: 24px 0;
}

// ---------- 左栏：历史会话 ----------
.new-chat {
  margin: 12px;
  padding: 10px;
  border: 1.5px dashed var(--line-strong);
  border-radius: 8px;
  background: transparent;
  color: var(--text-2);
  font-size: 13.5px;
  cursor: pointer;
  transition: all 0.25s;

  &:hover {
    border-color: var(--neon);
    color: var(--neon);
  }
}

.history-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(127, 127, 127, 0.08);
    .history-del { opacity: 1; }
  }

  &.active {
    background: var(--neon-dim);
    .history-title { color: var(--neon); }
  }
}

.history-title {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--text-3);
}

.history-cat {
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(127, 127, 127, 0.12);
}

.history-del {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;

  &:hover { color: var(--hot); }
}

// ---------- 右栏：智能体列表 ----------
.agent-item {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  text-align: left;
  transition: background 0.2s, border-color 0.2s;

  &:hover {
    background: rgba(127, 127, 127, 0.08);
  }

  &.active {
    background: var(--neon-dim);
    border-color: color-mix(in srgb, var(--neon) 30%, transparent);

    .agent-name { color: var(--neon); }
  }
}

.agent-dot {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  color: var(--hue);
  background: color-mix(in srgb, var(--hue) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--hue) 30%, transparent);
  transition: transform 0.25s var(--ease-out);

  .agent-item:hover & { transform: scale(1.08) rotate(-3deg); }
}

.agent-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.agent-name {
  font-size: 13.5px;
  font-weight: 500;
}

.agent-desc {
  font-size: 11.5px;
  color: var(--text-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

// ---------- 中栏：聊天主界面 ----------
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px 16px;

  // 中间栏拉宽后，消息内容保持可读宽度并居中
  > * {
    max-width: 760px;
    margin-left: auto;
    margin-right: auto;
  }

  .msg {
    max-width: 760px;
    margin-left: auto;
    margin-right: auto;

    &.user {
      justify-content: flex-end;
    }
  }
}

// 空状态
.welcome {
  text-align: center;
  padding: 64px 24px;
  color: var(--text-2);

  .welcome-sigil { font-size: 28px; color: var(--neon); margin-bottom: 12px; }
  .welcome-title {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 6px;
  }
  .welcome-desc { margin: 0 auto; max-width: 46ch; font-size: 13px; }
}

// 消息
.msg {
  display: flex;
  margin-bottom: 14px;
  &.user { justify-content: flex-end; }
}

.msg-col {
  max-width: 78%;
  display: flex;
  flex-direction: column;

  .msg.user & { align-items: flex-end; }
  .msg.agent & { align-items: flex-start; }
}

.bubble {
  max-width: 100%;
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;

  .user & {
    background: var(--neon-dim);
    border: 1px solid color-mix(in srgb, var(--neon) 30%, transparent);
    border-bottom-right-radius: 4px;
  }

  .agent & {
    background: var(--panel);
    border: 1px solid var(--line);
    border-bottom-left-radius: 4px;
  }

  .text { white-space: pre-wrap; }

  .meta {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed var(--line);
    font-size: 11.5px;
    color: var(--text-3);
    font-family: var(--font-display);
  }
}

// 操作栏：固定在气泡下方
.actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.action-btn {
  padding: 3px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.2s, background 0.2s, transform 0.15s var(--ease-out);

  &:hover:not(:disabled) {
    color: var(--neon);
    background: var(--neon-dim);
  }
  &:active:not(:disabled) { transform: scale(0.94); }
  &:disabled { opacity: 0.4; cursor: not-allowed; }

  &.copied { color: var(--neon); }
}

// 思考过程：弱化的折叠块
.reasoning {
  margin-bottom: 10px;
  padding: 8px 12px;
  border-left: 2px solid var(--line-strong);
  border-radius: 0 8px 8px 0;
  background: rgba(127, 127, 127, 0.06);
  font-size: 12.5px;
  color: var(--text-2);

  summary {
    cursor: pointer;
    color: var(--text-3);
    font-size: 12px;
    user-select: none;
    list-style: none;

    &::before {
      content: '▸ ';
    }
  }

  &[open] summary::before {
    content: '▾ ';
  }

  .reasoning-text {
    margin-top: 6px;
    white-space: pre-wrap;
    line-height: 1.6;
    max-height: 240px;
    overflow-y: auto;
  }
}

// Markdown 渲染排版
.md {
  white-space: normal;

  :deep(p) { margin: 0 0 0.6em; &:last-child { margin-bottom: 0; } }
  :deep(h1), :deep(h2), :deep(h3) {
    font-family: var(--font-display);
    margin: 0.8em 0 0.4em;
    line-height: 1.4;
  }
  :deep(h1) { font-size: 17px; }
  :deep(h2) { font-size: 16px; }
  :deep(h3) { font-size: 15px; }
  :deep(ul), :deep(ol) { margin: 0.4em 0; padding-left: 1.4em; }
  :deep(li) { margin: 0.2em 0; }
  :deep(strong) { color: var(--neon); font-weight: 600; }
  :deep(blockquote) {
    margin: 0.6em 0;
    padding: 4px 12px;
    border-left: 3px solid var(--neon);
    color: var(--text-2);
  }
  :deep(code) {
    font-family: var(--font-display);
    font-size: 12.5px;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--neon-dim);
  }
  :deep(pre) {
    padding: 12px;
    border-radius: 8px;
    background: var(--ink-deep);
    overflow-x: auto;
    code { background: none; padding: 0; }
  }
  :deep(a) { color: var(--neon); }
  :deep(hr) { border: none; border-top: 1px solid var(--line); margin: 0.8em 0; }
}

// 复制按钮旧样式已由 .action-btn 替代
// 流式输出光标
.cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--neon);
  animation: cursor-blink 0.8s step-end infinite;
}

@keyframes cursor-blink {
  50% { opacity: 0; }
}

// 消息入场
.msg-enter-active {
  transition: opacity 0.35s var(--ease-out), transform 0.35s var(--ease-out);
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

// 正在输入
.typing {
  display: flex;
  gap: 5px;
  padding: 16px 18px;

  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-3);
    animation: blink 1.2s ease-in-out infinite;
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes blink {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); background: var(--neon); }
}

// 输入条：与消息流同宽居中
.composer {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 760px;
  margin: 12px auto 0;
  padding: 12px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  transition: border-color 0.25s, box-shadow 0.25s;

  &:focus-within {
    border-color: color-mix(in srgb, var(--neon) 50%, transparent);
    box-shadow: 0 0 0 3px var(--neon-dim);
  }
}

.composer-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  // 上下各 7px 内边距：单行时与右侧发送按钮等高，文字视觉居中
  padding: 7px 0;
  font-family: var(--font-body);
  max-height: 160px;
  overflow-y: auto;

  &::placeholder { color: var(--text-3); }
}

.composer-send {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--neon);
  color: var(--on-neon);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: transform 0.15s var(--ease-out), box-shadow 0.25s, opacity 0.2s, background 0.25s;

  &:hover:not(:disabled) {
    box-shadow: 0 4px 20px var(--neon-dim);
  }
  &:active:not(:disabled) {
    transform: scale(0.95);
  }
  &:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  // 生成中：切换为停止按钮
  &.stopping {
    background: var(--hot);

    &:hover {
      box-shadow: 0 4px 20px var(--hot-dim);
    }
  }
}

// 窄屏降级：三栏折为上下
@media (max-width: 1024px) {
  .chat-page { flex-wrap: wrap; height: auto; }
  .chat-main { order: -1; width: 100%; height: 60vh; min-height: 400px; }
  .panel { width: calc(50% - 10px); max-height: 260px; }
}
</style>
