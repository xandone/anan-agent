<script setup>
import { message } from 'ant-design-vue'
import { nextTick, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'

const categories = ref([])
const modalOpen = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ name: '', slug: '', description: '', system_prompt: '', enabled: true })

const formRef = ref()
const rules = {
  name: [{ required: true, whitespace: true, message: '请填写名称', trigger: 'blur' }],
  slug: [
    { required: true, whitespace: true, message: '请填写 slug', trigger: 'blur' },
    { pattern: /^[a-z0-9][a-z0-9_-]*$/, message: 'slug 只能是小写字母、数字、- 和 _，且以字母或数字开头', trigger: 'blur' },
  ],
}

// 后端 422 的 detail 是数组，统一提取成可读文本
function errText(e, fallback) {
  const d = e?.detail
  if (Array.isArray(d)) return d.map((x) => x.msg).filter(Boolean).join('；') || fallback
  return d || fallback
}

// 每个人格卡片的标识色：10 色按色环均匀分布，互不撞色
const hues = [
  '#25f4ee', // 青
  '#fe2c55', // 品红
  '#c77dff', // 紫
  '#ffd84a', // 明黄
  '#3ddc84', // 翠绿
  '#3fb8ff', // 天蓝
  '#ff6ec7', // 樱花粉
  '#a8e04a', // 青柠
  '#ff9e4a', // 橙
  '#7c8cff', // 靛蓝
]
const hueOf = (i) => hues[i % hues.length]

async function load() {
  categories.value = await api.get('/categories')
}

function openModal(cat) {
  editing.value = cat
  Object.assign(form, cat || { name: '', slug: '', description: '', system_prompt: '', enabled: true })
  modalOpen.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function save() {
  try {
    await formRef.value.validate()
  } catch {
    return // 校验未通过，antd 已在表单项下标红提示
  }
  form.name = form.name.trim()
  form.slug = form.slug.trim()
  saving.value = true
  try {
    if (editing.value) await api.put(`/categories/${editing.value.id}`, form)
    else await api.post('/categories', form)
    message.success(editing.value ? '已保存修改' : '已创建智能体')
    modalOpen.value = false
    load()
  } catch (e) {
    message.error(errText(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(cat) {
  try {
    await api.delete(`/categories/${cat.id}`)
    message.success(`已删除「${cat.name}」`)
    modalOpen.value = false
    load()
  } catch (e) {
    message.error(errText(e, '删除失败'))
  }
}

const generating = ref(false)

async function generate() {
  const name = form.name.trim()
  if (!name) {
    message.warning('请先填写名称')
    formRef.value?.validate(['name']).catch(() => {})
    return
  }
  generating.value = true
  try {
    const draft = await api.post('/categories/ai-draft', { name }, { timeout: 90000 })
    if (!editing.value) {
      // 编辑模式下 slug 不可改，只填描述和人格 Prompt
      if (draft.slug) form.slug = draft.slug
    }
    if (draft.description) form.description = draft.description
    if (draft.system_prompt) form.system_prompt = draft.system_prompt
    formRef.value?.clearValidate()
    message.success((draft.slug || editing.value) ? '已生成，可按需调整' : '已生成，slug 请手动填写')
  } catch (e) {
    message.error(errText(e, '生成失败，请重试'))
  } finally {
    generating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <header class="page-head rise">
      <h1>智能体</h1>
      <p>每个类别就是一个人格。语料喂得越多，它说话越像那个世界的人。</p>
    </header>

    <div class="grid">
      <div
        v-for="(c, i) in categories"
        :key="c.id"
        class="persona lift rise"
        :class="[`rise-${Math.min(i + 1, 3)}`, { off: !c.enabled }]"
        :style="{ '--hue': hueOf(i) }"
        @click="openModal(c)"
      >
        <div class="avatar">{{ c.name.charAt(0) }}</div>
        <div class="persona-body">
          <div class="persona-name">
            {{ c.name }}
            <a-tag v-if="!c.enabled" class="off-tag">已停用</a-tag>
          </div>
          <p class="persona-desc">{{ c.description || '还没有定义这个人格。' }}</p>
          <div class="persona-stats">
            <span><b class="num">{{ c.video_count }}</b> 视频</span>
            <span><b class="num">{{ c.corpus_count }}</b> 语料</span>
            <span class="actions" @click.stop>
              <a class="act" @click="openModal(c)">编辑</a>
              <a-popconfirm
                title="删除该智能体？"
                :description="`其 ${c.corpus_count} 条语料将一并删除，关联视频归为未分类。`"
                ok-text="删除"
                cancel-text="取消"
                @confirm="remove(c)"
              >
                <a class="act danger">删除</a>
              </a-popconfirm>
            </span>
            <router-link class="try" :to="{ path: '/chat', query: { agent: c.slug } }" @click.stop>对话 →</router-link>
          </div>
        </div>
      </div>

      <button class="persona add rise rise-2" @click="openModal(null)">
        <span class="plus">+</span>
        新增智能体
      </button>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? `编辑 · ${editing.name}` : '新增智能体'"
      :confirm-loading="saving"
      width="640px"
      ok-text="保存"
      cancel-text="取消"
      @ok="save"
    >
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical" style="margin-top: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" name="name" required>
              <a-input v-model:value="form.name" placeholder="如：诗歌智能体" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="slug（对话路由用）" name="slug" required>
              <a-input v-model:value="form.slug" :disabled="!!editing" placeholder="如：poem" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item class="gen-row">
          <a-button size="small" ghost type="primary" :loading="generating" @click="generate">
            ✨ AI 智能生成
          </a-button>
          <span class="gen-hint">{{ editing ? '根据名称重新生成类别定义和人格 Prompt' : '根据名称自动生成 slug、类别定义和人格 Prompt' }}</span>
        </a-form-item>
        <a-form-item label="类别定义（供 LLM 打标判断）">
          <a-textarea v-model:value="form.description" :rows="3"
            placeholder="什么样的内容算这一类？写得越清楚，分类越准。" />
        </a-form-item>
        <a-form-item label="人格 Prompt（system prompt）">
          <a-textarea v-model:value="form.system_prompt" :rows="5"
            placeholder="例：你是一个阴阳怪气风格的评论大师，说话绵里藏针……" />
        </a-form-item>
        <a-form-item>
          <a-checkbox v-model:checked="form.enabled">启用</a-checkbox>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style lang="scss" scoped>
.page-head {
  margin-bottom: 28px;
  h1 { font-size: 26px; margin: 0 0 6px; }
  p { margin: 0; color: var(--text-2); max-width: 60ch; }
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.persona {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;

  &.off {
    opacity: 0.5;
  }
}

// 人格头像：首字 + 标识色晕染
.avatar {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--hue);
  background: color-mix(in srgb, var(--hue) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--hue) 30%, transparent);
  transition: transform 0.3s var(--ease-out);

  .persona:hover & {
    transform: scale(1.06) rotate(-3deg);
  }
}

.persona-body {
  min-width: 0;
  flex: 1;
}

.persona-name {
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.off-tag {
  font-size: 11px;
}

.persona-desc {
  margin: 6px 0 12px;
  font-size: 12.5px;
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.persona-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-3);

  b {
    color: var(--text);
    margin-right: 3px;
  }

  .actions {
    display: flex;
    gap: 10px;
    opacity: 0;
    transition: opacity 0.25s;

    .act {
      color: var(--text-2);
      text-decoration: none;
      cursor: pointer;

      &:hover {
        color: var(--text);
      }

      &.danger:hover {
        color: #ff4d4f;
      }
    }
  }

  .persona:hover & .actions {
    opacity: 1;
  }

  .try {
    margin-left: auto;
    color: var(--hue);
    text-decoration: none;
    opacity: 0;
    transform: translateX(-4px);
    transition: opacity 0.25s, transform 0.25s;
  }

  .persona:hover & .try {
    opacity: 1;
    transform: translateX(0);
  }
}

.gen-row {
  margin-top: -10px;

  :deep(.ant-form-item-control-input-content) {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.gen-hint {
  font-size: 12px;
  color: var(--text-3);
}

// 新增卡片：虚线占位
.persona.add {
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  min-height: 132px;
  background: transparent;
  border: 1.5px dashed var(--line-strong);
  color: var(--text-2);
  font-size: 14px;
  transition: border-color 0.25s, color 0.25s;

  .plus {
    font-family: var(--font-display);
    font-size: 26px;
    transition: transform 0.3s var(--ease-out);
  }

  &:hover {
    border-color: var(--neon);
    color: var(--neon);

    .plus {
      transform: rotate(90deg);
    }
  }
}
</style>
