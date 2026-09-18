<script setup>
import { message } from 'ant-design-vue'
import { onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'

const categories = ref([])
const modalOpen = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ name: '', slug: '', description: '', system_prompt: '', enabled: true })

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
}

async function save() {
  saving.value = true
  try {
    if (editing.value) await api.put(`/categories/${editing.value.id}`, form)
    else await api.post('/categories', form)
    message.success(editing.value ? '已保存修改' : '已创建智能体')
    modalOpen.value = false
    load()
  } catch (e) {
    message.error(e.detail || '保存失败')
  } finally {
    saving.value = false
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
      <a-form layout="vertical" style="margin-top: 16px">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="名称" required>
              <a-input v-model:value="form.name" placeholder="如：诗歌类" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="slug（对话路由用）" required>
              <a-input v-model:value="form.slug" :disabled="!!editing" placeholder="如：poem" />
            </a-form-item>
          </a-col>
        </a-row>
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
