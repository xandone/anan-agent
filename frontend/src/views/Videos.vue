<script setup>
import { message } from 'ant-design-vue'
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'

const videos = ref([])
const total = ref(0)
const loading = ref(false)
const filters = reactive({ status: undefined, category_id: undefined, page: 1, size: 20 })
const categories = ref([])

// 流水线传送带：五阶段 + 失败（OCR 是手动兜底，不在自动流程里）
const stages = [
  { key: 'pending', label: '待下载' },
  { key: 'downloaded', label: '已下载' },
  { key: 'asr_done', label: '已转写' },
  { key: 'classified', label: '已分类' },
  { key: 'indexed', label: '已入库' },
]
const stageCounts = ref({})
const failedCount = ref(0)
const ocrLoading = ref(new Set())
const batchLoading = ref(false)

// 表格体滚动高度：卡片内剩余空间减去表头与分页（页面整体不滚动）
const tableBox = ref(null)
const tableY = ref(300)
let resizeObs

function measureTable() {
  const box = tableBox.value
  if (!box) return
  const thead = box.querySelector('.ant-table-thead')
  const pag = box.querySelector('.ant-pagination')
  const extra = (thead?.offsetHeight ?? 55) + (pag?.offsetHeight ?? 32) + 28
  tableY.value = Math.max(box.clientHeight - extra, 160)
}

const statusColor = {
  pending: '', downloaded: 'processing',
  asr_done: 'processing', classified: 'success', indexed: 'success', failed: 'error',
}

async function load() {
  loading.value = true
  try {
    const params = { ...filters }
    Object.keys(params).forEach((k) => params[k] === undefined && delete params[k])
    const res = await api.get('/videos', { params })
    videos.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function loadStageCounts() {
  const results = await Promise.all(
    [...stages.map((s) => s.key), 'failed'].map((s) =>
      api.get('/videos', { params: { status: s, size: 1 } }).then((r) => [s, r.total]),
    ),
  )
  stageCounts.value = Object.fromEntries(results.filter(([s]) => s !== 'failed'))
  failedCount.value = results.find(([s]) => s === 'failed')?.[1] ?? 0
}

function filterByStage(key) {
  filters.status = filters.status === key ? undefined : key
  filters.page = 1
  load()
}

// 分页/每页条数变化：条数变化时回到第 1 页，避免页码越界出现空页
function onPageChange(p) {
  if (p.pageSize !== filters.size) {
    filters.size = p.pageSize
    filters.page = 1
  } else {
    filters.page = p.current
  }
  load()
}

const isAsrFailure = (r) => r.status === 'failed' && (r.error || '').startsWith('step_asr')

function openVideo(record) {
  window.open(record.file_url, '_blank')
}

async function runOcr(record) {
  ocrLoading.value.add(record.id)
  try {
    await api.post(`/videos/${record.id}/ocr`)
    message.success(`已提交 OCR：${record.title || record.aweme_id}，完成后自动继续分类`)
    setTimeout(() => { load(); loadStageCounts() }, 5000)
  } catch (e) {
    message.error(e.detail || 'OCR 提交失败')
    ocrLoading.value.delete(record.id)
  }
}

async function runOcrBatch() {
  batchLoading.value = true
  try {
    const res = await api.post('/videos/ocr-batch', { only_failed: true })
    if (res.queued === 0) message.info('没有 ASR 失败的待处理视频')
    else {
      message.success(`已批量提交 ${res.queued} 条 OCR 任务`)
      setTimeout(() => { load(); loadStageCounts() }, 5000)
    }
  } catch (e) {
    message.error(e.detail || '批量 OCR 提交失败')
  } finally {
    batchLoading.value = false
  }
}

onMounted(async () => {
  categories.value = await api.get('/categories')
  load()
  loadStageCounts()
  nextTick(measureTable)
  resizeObs = new ResizeObserver(() => nextTick(measureTable))
  if (tableBox.value) resizeObs.observe(tableBox.value)
})

onBeforeUnmount(() => resizeObs?.disconnect())

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70 },
  { title: '标题', dataIndex: 'title', ellipsis: true },
  { title: '作者', dataIndex: 'author_name', width: 120 },
  { title: '点赞', dataIndex: 'digg_count', width: 110 },
  { title: '状态', dataIndex: 'status', width: 110 },
  { title: '类别', dataIndex: 'category_id', width: 120 },
  { title: '置信度', dataIndex: 'confidence', width: 90 },
  { title: '操作', key: 'action', width: 170 },
]
</script>

<template>
  <div class="videos-page">
    <!-- 流水线传送带 -->
    <div class="pipeline rise">
      <div
        v-for="(s, i) in stages"
        :key="s.key"
        class="stage-node"
        :class="{
          active: filters.status === s.key,
          working: s.key === 'downloaded' && stageCounts[s.key] > 0,
        }"
        @click="filterByStage(s.key)"
      >
        <span class="stage-dot" />
        <span class="stage-label">{{ s.label }}</span>
        <span class="stage-count num">{{ stageCounts[s.key] ?? 0 }}</span>
        <span v-if="i < stages.length - 1" class="stage-link" aria-hidden="true" />
      </div>
      <div
        v-if="failedCount > 0"
        class="stage-node failed"
        :class="{ active: filters.status === 'failed' }"
        @click="filterByStage('failed')"
      >
        <span class="stage-dot" />
        <span class="stage-label">失败</span>
        <span class="stage-count num">{{ failedCount }}</span>
      </div>
    </div>

    <a-card class="rise rise-1 table-card" :bordered="false">
      <template #title>视频库</template>
      <template #extra>
        <a-space>
          <a-button
            v-if="failedCount > 0"
            danger
            :loading="batchLoading"
            @click="runOcrBatch"
          >
            批量 OCR（{{ failedCount }} 条失败）
          </a-button>
          <a-select
            v-model:value="filters.category_id"
            placeholder="类别"
            allow-clear
            style="width: 150px"
            :options="categories.map((c) => ({ value: c.id, label: c.name }))"
            @change="load"
          />
          <a-button @click="load(); loadStageCounts()">刷新</a-button>
        </a-space>
      </template>

      <div ref="tableBox" class="table-box">
        <a-table
          :columns="columns"
          :data-source="videos"
          :loading="loading"
          row-key="id"
          :scroll="{ y: tableY }"
          :pagination="{
            current: filters.page,
            pageSize: filters.size,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            showTotal: (t) => `共 ${t} 条`,
            locale: { items_per_page: '条/页', jump_to: '前往', page: '页' },
            buildOptionText: (opt) => `${opt.value}条/页`,
          }"
          @change="(p) => onPageChange(p)"
        >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'status'">
            <a-tag :color="statusColor[record.status]">{{ record.status }}</a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'digg_count'">
            <span class="num digg">♥ {{ record.digg_count.toLocaleString() }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'category_id'">
            {{ categories.find((c) => c.id === record.category_id)?.name || '未分类' }}
          </template>
          <template v-else-if="column.dataIndex === 'confidence'">
            <span class="num">{{ record.confidence != null ? record.confidence.toFixed(2) : '—' }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space :size="6">
              <a-tooltip v-if="record.file_url" title="打开视频文件">
                <a-button size="small" @click="openVideo(record)">▶ 播放</a-button>
              </a-tooltip>
              <a-tooltip v-if="isAsrFailure(record)" title="语音转写失败，用 OCR 提取画面字幕兜底">
                <a-button
                  size="small"
                  danger
                  :loading="ocrLoading.has(record.id)"
                  @click="runOcr(record)"
                >
                  OCR 补字幕
                </a-button>
              </a-tooltip>
              <span v-if="!record.file_url && !isAsrFailure(record)" class="action-none">—</span>
            </a-space>
          </template>
        </template>
        <template #emptyText>
          <div class="empty">
            <p>还没有视频</p>
            <router-link to="/collect">去采集任务页开始下载 →</router-link>
          </div>
        </template>
        </a-table>
      </div>
    </a-card>
  </div>
</template>

<style lang="scss" scoped>
// 页面撑满视口：只有表格体滚动，传送带和卡片头固定
.videos-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px); // 减去 .stage 上下各 32px 内边距
  overflow: hidden;

  @media (max-width: 768px) {
    height: calc(100vh - 40px); // 移动端内边距 20px × 2
  }
}

.table-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;

  :deep(.ant-card-head) {
    flex-shrink: 0;
  }

  :deep(.ant-card-body) {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
}

.table-box {
  flex: 1;
  min-height: 0;

  // 打通 antd 表格内部层级，让分页器沉底（而不是紧跟在表格下面）
  :deep(.ant-table-wrapper),
  :deep(.ant-spin-nested-loading),
  :deep(.ant-spin-container) {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  :deep(.ant-table) {
    flex: 1;
    min-height: 0;
  }

  :deep(.ant-pagination) {
    margin-top: auto;
    padding-top: 16px;
    flex-wrap: wrap;
    row-gap: 8px;
  }

  // 每页条数选择器：默认宽度太窄，"100 条/页"会被裁掉
  // （下拉框宽度跟随触发器，撑开触发器即可同时解决两处）
  :deep(.ant-pagination-options-size-changer) {
    min-width: 106px;
  }

  :deep(.ant-pagination-options-quick-jumper) {
    // 防止一行放不下时被挤出可视区
    flex-shrink: 0;
    white-space: nowrap;
  }
}

// ---------- 流水线传送带 ----------
.pipeline {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  flex-shrink: 0;
  gap: 0;
  margin-bottom: 24px;
  padding: 18px 24px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow-x: auto;
}

.stage-node {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-right: 44px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  user-select: none;

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  &.active {
    background: var(--neon-dim);

    .stage-label { color: var(--neon); }
  }

  &.failed {
    .stage-dot { background: var(--hot); }
    .stage-count { color: var(--hot); }
  }
}

.stage-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--text-3);
  flex-shrink: 0;

  .working & {
    background: var(--neon);
    animation: pulse-dot 1.6s ease-in-out infinite;
  }
  .active & {
    background: var(--neon);
  }
}

.stage-label {
  font-size: 13px;
  color: var(--text-2);
  white-space: nowrap;
}

.stage-count {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

// 节点间的流动虚线
.stage-link {
  position: absolute;
  right: -40px;
  top: 50%;
  width: 36px;
  height: 1px;
  background-image: linear-gradient(90deg, var(--text-3) 40%, transparent 40%);
  background-size: 8px 1px;
  animation: flow 1.2s linear infinite;
  opacity: 0.6;
}

@keyframes flow {
  to { background-position-x: 8px; }
}

.digg {
  color: var(--hot);
  font-size: 13px;
}

.action-none {
  color: var(--text-3);
}

.empty {
  padding: 48px 0;
  color: var(--text-2);

  a { color: var(--neon); }
}
</style>
