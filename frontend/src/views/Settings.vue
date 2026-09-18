<script setup>
import { message } from 'ant-design-vue'
import { onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'

const config = ref({})
const form = reactive({})
const saving = ref(false)

async function load() {
  config.value = await api.get('/config')
  Object.keys(form).forEach((k) => delete form[k]) // 编辑表单留空，只提交改过的字段
}

async function save() {
  saving.value = true
  try {
    const updates = {}
    Object.keys(form).forEach((k) => form[k] && (updates[k] = form[k]))
    if (!Object.keys(updates).length) return message.info('没有修改')
    await api.put('/config', updates)
    message.success('配置已保存并重载')
    load()
  } catch (e) {
    message.error(e.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)

const groups = [
  {
    title: '模型',
    fields: [
      { key: 'llm_api_url', label: 'LLM API 地址' },
      { key: 'llm_model', label: 'LLM 模型' },
      { key: 'llm_api_key', label: 'LLM API Key' },
      { key: 'embedding_api_url', label: 'Embedding API 地址' },
      { key: 'embedding_model', label: 'Embedding 模型' },
    ],
  },
  {
    title: '外部服务',
    fields: [
      { key: 'ocr_api_url', label: 'OCR 服务地址' },
      { key: 'douyin_api_url', label: 'TikTokDownloader 地址' },
    ],
  },
]
</script>

<template>
  <div>
    <header class="page-head rise">
      <h1>配置</h1>
      <p>改动立即生效，不用重启。留空的字段保持原值。</p>
    </header>

    <div class="settings-body rise rise-1">
      <section v-for="g in groups" :key="g.title" class="group">
        <h3>{{ g.title }}</h3>
        <div v-for="f in g.fields" :key="f.key" class="field">
          <label>{{ f.label }}</label>
          <input
            v-model="form[f.key]"
            class="field-input"
            :placeholder="`请填写${f.label}`"
            :type="f.key.includes('key') ? 'password' : 'text'"
            :name="`cfg-${f.key}`"
            :autocomplete="f.key.includes('key') ? 'new-password' : 'off'"
          />
          <p class="field-current">当前：{{ config[f.key] || '未配置' }}</p>
        </div>
      </section>

      <a-button type="primary" size="large" :loading="saving" @click="save">
        保存并重载
      </a-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page-head {
  margin-bottom: 28px;
  h1 { font-size: 26px; margin: 0 0 6px; }
  p { margin: 0; color: var(--text-2); }
}

.settings-body {
  max-width: 640px;
}

.group {
  margin-bottom: 28px;

  h3 {
    font-size: 13px;
    color: var(--text-2);
    letter-spacing: 0.06em;
    margin: 0 0 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--line);
  }
}

.field {
  margin-bottom: 14px;

  label {
    display: block;
    font-size: 13px;
    color: var(--text-2);
    margin-bottom: 6px;
  }
}

.field-current {
  margin: 5px 0 0;
  font-size: 11.5px;
  color: var(--text-3);
  font-family: var(--font-display);
  word-break: break-all;
}

.field-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--text);
  font-size: 13.5px;
  font-family: var(--font-display);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;

  &::placeholder {
    color: var(--text-3);
  }

  &:focus {
    border-color: rgba(37, 244, 238, 0.5);
    box-shadow: 0 0 0 3px rgba(37, 244, 238, 0.08);
  }
}
</style>
