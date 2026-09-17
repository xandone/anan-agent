<script setup>
import { message } from 'ant-design-vue'
import { reactive, ref } from 'vue'
import { api } from '@/api/client'

const loadingKey = ref('')
const hotForm = reactive({ board: '热榜', limit: 50 })
const accountForm = reactive({ sec_uid: '', count: 50, min_digg: 0 })
const manualForm = reactive({ aweme_id: '' })

async function submit(key, path, form, label) {
  loadingKey.value = key
  try {
    const res = await api.post(`/collect/${path}`, form)
    message.success(`${label}：登记 ${res.registered ?? 1} 个视频，流水线已启动`)
  } catch (e) {
    message.error(`${label}失败：${e.detail || e.message || e}`)
  } finally {
    loadingKey.value = ''
  }
}

const boards = ['热榜', '娱乐榜', '社会榜', '挑战榜']
</script>

<template>
  <div>
    <header class="page-head rise">
      <h1>采集任务</h1>
      <p>三种方式把抖音内容送进流水线：蹭热点、盯达人、或者精确到一条视频。</p>
    </header>

    <a-row :gutter="[20, 20]">
      <a-col :xs="24" :md="8">
        <div class="collect-card lift rise rise-1">
          <div class="card-glow" style="--glow: var(--hot)" />
          <h3><span class="mark" style="color: var(--hot)">♨</span> 热榜采集</h3>
          <p class="desc">追热点。从抖音官方榜单批量抓取当下最火的视频。</p>
          <a-form layout="vertical">
            <a-form-item label="榜单">
              <a-select v-model:value="hotForm.board"
                :options="boards.map((v) => ({ value: v }))" />
            </a-form-item>
            <a-form-item label="数量">
              <a-input-number v-model:value="hotForm.limit" :min="1" :max="200" style="width: 100%" />
            </a-form-item>
            <a-button type="primary" block :loading="loadingKey === 'hot'"
              @click="submit('hot', 'hot', hotForm, '热榜采集')">
              开始采集
            </a-button>
          </a-form>
        </div>
      </a-col>

      <a-col :xs="24" :md="8">
        <div class="collect-card lift rise rise-2">
          <div class="card-glow" style="--glow: var(--neon)" />
          <h3><span class="mark" style="color: var(--neon)">◎</span> 达人采集</h3>
          <p class="desc">盯人。批量抓取某个账号的作品，可按点赞数过滤掉冷内容。</p>
          <a-form layout="vertical">
            <a-form-item label="达人 sec_uid">
              <a-input v-model:value="accountForm.sec_uid" placeholder="主页链接中的 sec_uid" />
            </a-form-item>
            <a-form-item label="作品数量">
              <a-input-number v-model:value="accountForm.count" :min="1" :max="500" style="width: 100%" />
            </a-form-item>
            <a-form-item label="最低点赞数过滤">
              <a-input-number v-model:value="accountForm.min_digg" :min="0" style="width: 100%" />
            </a-form-item>
            <a-button type="primary" block :loading="loadingKey === 'account'"
              @click="submit('account', 'account', accountForm, '达人采集')">
              开始采集
            </a-button>
          </a-form>
        </div>
      </a-col>

      <a-col :xs="24" :md="8">
        <div class="collect-card lift rise rise-3">
          <div class="card-glow" style="--glow: #b18cff" />
          <h3><span class="mark" style="color: #b18cff">✦</span> 单个视频</h3>
          <p class="desc">精确投喂。适合先拿一条视频验证整条流水线。</p>
          <a-form layout="vertical">
            <a-form-item label="作品 ID (aweme_id)">
              <a-input v-model:value="manualForm.aweme_id" placeholder="视频链接中的作品 ID" />
            </a-form-item>
            <a-button type="primary" block :loading="loadingKey === 'manual'"
              @click="submit('manual', 'manual', manualForm, '添加')">
              下载并处理
            </a-button>
          </a-form>
          <p class="hint">推荐第一步从这里开始，跑通后再开批量。</p>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<style lang="scss" scoped>
.page-head {
  margin-bottom: 28px;

  h1 {
    font-size: 26px;
    margin: 0 0 6px;
  }
  p {
    margin: 0;
    color: var(--text-2);
    max-width: 60ch;
  }
}

.collect-card {
  position: relative;
  height: 100%;
  padding: 24px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;

  h3 {
    margin: 0 0 8px;
    font-size: 16px;
    .mark { margin-right: 6px; }
  }

  .desc {
    margin: 0 0 20px;
    font-size: 13px;
    color: var(--text-2);
  }

  .hint {
    margin: 16px 0 0;
    font-size: 12px;
    color: var(--text-3);
  }
}

// 卡片顶部的一缕色光，悬停时增强
.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--glow);
  opacity: 0.4;
  transition: opacity 0.3s, box-shadow 0.3s;

  .collect-card:hover & {
    opacity: 1;
    box-shadow: 0 0 16px var(--glow);
  }
}
</style>
