<script setup>
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import { themeMode } from '@/composables/theme'

const data = ref(null)
const loading = ref(false)

// 图表色板（亮暗主题下都可读）
const PALETTE = ['#25f4ee', '#fe2c55', '#b18cff', '#ffd166', '#7ae582',
  '#5aa9ff', '#ff8a5c', '#f472b6', '#4ade80', '#a3e635']

const STAGES = [
  { key: 'pending', label: '待下载', color: '#8a8a94' },
  { key: 'downloaded', label: '已下载', color: '#5aa9ff' },
  { key: 'asr_done', label: '已转写', color: '#b18cff' },
  { key: 'classified', label: '已分类', color: '#ffd166' },
  { key: 'indexed', label: '已入库', color: '#25f4ee' },
  { key: 'failed', label: '失败', color: '#fe2c55' },
]

const SOURCES = [
  { key: 'hot', label: '热榜' },
  { key: 'account', label: '达人' },
  { key: 'like', label: '点赞' },
  { key: 'search', label: '搜索' },
  { key: 'manual', label: '手动' },
]

const fmt = (n) => (n ?? 0).toLocaleString()

async function load() {
  loading.value = true
  try {
    data.value = await api.get('/dashboard/summary')
  } catch (e) {
    message.error(e.detail || '看板数据加载失败')
  } finally {
    loading.value = false
  }
}

// ---- 统计卡片 ----
const statCards = computed(() => {
  if (!data.value) return []
  const d = data.value
  return [
    { label: '视频总数', value: d.video_total, color: '#5aa9ff' },
    { label: '已入库', value: d.status_counts.indexed ?? 0, color: '#25f4ee' },
    { label: '评论总数', value: d.comment_total, color: '#fe2c55' },
    { label: '语料总数', value: d.corpus_total, color: '#b18cff' },
    { label: '启用智能体', value: d.category_stats.filter((c) => c.enabled).length, color: '#ffd166' },
  ]
})

// ---- ECharts ----
const stageEl = ref(null)
const donutEl = ref(null)
const sourceEl = ref(null)
const trendEl = ref(null)
let charts = []

const dark = computed(() => themeMode.value === 'dark')
const axisColor = computed(() => (dark.value ? '#8a8a94' : '#5a5a64'))
const splitColor = computed(() => (dark.value ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'))

function categorySegments() {
  return (data.value?.category_stats ?? [])
    .filter((c) => c.video_count > 0)
    .map((c, i) => ({ ...c, color: PALETTE[i % PALETTE.length] }))
}

// 自定义图例颜色与饼图数据顺序一致
const donutSegments = computed(categorySegments)
const donutTotal = computed(() =>
  (data.value?.category_stats ?? []).reduce((s, c) => s + c.video_count, 0))
const donutColor = (name) =>
  donutSegments.value.find((s) => s.name === name)?.color ?? 'var(--text-3)'

function buildOptions() {
  const d = data.value
  const axis = {
    axisLine: { lineStyle: { color: splitColor.value } },
    axisLabel: { color: axisColor.value },
    splitLine: { lineStyle: { color: splitColor.value } },
  }
  const tooltip = { backgroundColor: dark.value ? '#1c1c24' : '#fff', borderWidth: 0,
    textStyle: { color: dark.value ? '#e8e8ec' : '#1a1a20' } }

  return [
    [stageEl, {
      tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: 'value', ...axis },
      yAxis: {
        type: 'category', inverse: true, ...axis,
        data: STAGES.map((s) => s.label),
      },
      series: [{
        type: 'bar', barWidth: 16,
        data: STAGES.map((s) => ({
          value: d.status_counts[s.key] ?? 0,
          itemStyle: { color: s.color, borderRadius: [0, 8, 8, 0] },
        })),
        label: { show: true, position: 'right', color: axisColor.value },
      }],
    }],
    [donutEl, {
      tooltip: { ...tooltip, trigger: 'item', formatter: '{b}：{c} 个视频（{d}%）' },
      title: {
        text: fmt(donutTotal.value), subtext: '已分类视频',
        left: 'center', top: '38%',
        textStyle: { color: dark.value ? '#e8e8ec' : '#1a1a20', fontSize: 24, fontWeight: 700 },
        subtextStyle: { color: axisColor.value, fontSize: 11 },
      },
      series: [{
        type: 'pie', radius: ['58%', '80%'], center: ['50%', '50%'],
        avoidLabelOverlap: true, label: { show: false },
        itemStyle: { borderColor: dark.value ? '#16161c' : '#fff', borderWidth: 2 },
        data: donutSegments.value.length
          ? donutSegments.value.map((c) => ({
              name: c.name, value: c.video_count, itemStyle: { color: c.color } }))
          : [{ name: '暂无数据', value: 1, silent: true,
               itemStyle: { color: splitColor.value }, tooltip: { show: false } }],
      }],
    }],
    [sourceEl, {
      tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: 'value', ...axis },
      yAxis: { type: 'category', inverse: true, ...axis, data: SOURCES.map((s) => s.label) },
      series: [{
        type: 'bar', barWidth: 14,
        data: SOURCES.map((s, i) => ({
          value: d.source_counts[s.key] ?? 0,
          itemStyle: { color: PALETTE[i % PALETTE.length], borderRadius: [0, 7, 7, 0] },
        })),
        label: { show: true, position: 'right', color: axisColor.value },
      }],
    }],
    [trendEl, {
      tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (ps) => `${ps[0].name}：${ps[0].value} 条` },
      grid: { left: 8, right: 8, top: 16, bottom: 8, containLabel: true },
      xAxis: { type: 'category', ...axis, data: d.daily_counts.map((x) => x.date) },
      yAxis: { type: 'value', minInterval: 1, ...axis },
      series: [{
        type: 'bar', barWidth: '55%',
        data: d.daily_counts.map((x) => x.count),
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: dark.value ? '#25f4ee' : '#0d9488' },
            { offset: 1, color: dark.value ? 'rgba(37,244,238,0.25)' : 'rgba(13,148,136,0.25)' },
          ]),
        },
      }],
    }],
  ]
}

function renderCharts() {
  if (!data.value) return
  charts.forEach((c) => c.dispose())
  charts = []
  for (const [elRef, option] of buildOptions()) {
    if (!elRef.value) continue
    const chart = echarts.init(elRef.value, dark.value ? 'dark' : null)
    chart.setOption({ backgroundColor: 'transparent', ...option })
    charts.push(chart)
  }
}

function onResize() {
  charts.forEach((c) => c.resize())
}

watch([data, themeMode], () => nextTick(renderCharts))

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  charts.forEach((c) => c.dispose())
  charts = []
})
</script>

<template>
  <div>
    <header class="page-head rise">
      <h1>数据看板</h1>
      <p>采集、流水线、语料和智能体的整体运行情况，一屏速览。</p>
    </header>

    <template v-if="data">
      <!-- 统计卡片 -->
      <div class="stat-row rise rise-1">
        <div v-for="c in statCards" :key="c.label" class="stat-card lift">
          <div class="card-glow" :style="{ '--glow': c.color }" />
          <p class="stat-label">{{ c.label }}</p>
          <p class="stat-value num" :style="{ color: c.color }">{{ fmt(c.value) }}</p>
        </div>
      </div>

      <a-row :gutter="[20, 20]">
        <!-- 流水线状态 -->
        <a-col :xs="24" :xl="12">
          <section class="panel rise rise-2">
            <h3>流水线状态</h3>
            <div ref="stageEl" class="chart chart-md" />
          </section>
        </a-col>

        <!-- 类别分布 -->
        <a-col :xs="24" :xl="12">
          <section class="panel rise rise-2">
            <h3>类别分布（按视频数）</h3>
            <div class="donut-wrap">
              <div ref="donutEl" class="chart donut" />
              <ul class="donut-legend">
                <li v-for="c in data.category_stats" :key="c.id">
                  <span class="dot" :style="{ background: donutColor(c.name) }" />
                  <span class="legend-name">{{ c.name }}</span>
                  <span class="num">{{ c.video_count }}</span>
                  <span class="legend-sub">语料 {{ fmt(c.corpus_count) }}</span>
                </li>
              </ul>
            </div>
          </section>
        </a-col>

        <!-- 采集来源 -->
        <a-col :xs="24" :md="12" :xl="8">
          <section class="panel rise rise-3">
            <h3>采集来源</h3>
            <div ref="sourceEl" class="chart chart-md" />
          </section>
        </a-col>

        <!-- 近 14 天采集趋势 -->
        <a-col :xs="24" :md="12" :xl="8">
          <section class="panel rise rise-3">
            <h3>近 14 天采集趋势</h3>
            <div ref="trendEl" class="chart chart-md" />
          </section>
        </a-col>

        <!-- 高赞评论 Top 5 -->
        <a-col :xs="24" :xl="8">
          <section class="panel rise rise-4">
            <h3>高赞评论 Top 5</h3>
            <ul class="top-comments">
              <li v-for="(c, i) in data.top_comments" :key="i">
                <span class="rank num" :class="{ hot: i < 3 }">{{ i + 1 }}</span>
                <div class="tc-body">
                  <p class="tc-text">{{ c.text }}</p>
                  <p class="tc-meta">
                    <span class="tc-digg">♥ {{ fmt(c.digg_count) }}</span>
                    <span class="tc-video">{{ c.video_title || '未命名视频' }}</span>
                  </p>
                </div>
              </li>
              <li v-if="!data.top_comments.length" class="empty">暂无评论数据</li>
            </ul>
          </section>
        </a-col>
      </a-row>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.page-head {
  margin-bottom: 24px;

  h1 { font-size: 26px; margin: 0 0 6px; }
  p { margin: 0; color: var(--text-2); max-width: 60ch; }
}

// ---- 统计卡片 ----
.stat-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  flex: 1;
  min-width: 150px;
  padding: 18px 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;

  .stat-label {
    margin: 0 0 6px;
    font-size: 12.5px;
    color: var(--text-2);
  }
  .stat-value {
    margin: 0;
    font-size: 30px;
    font-weight: 700;
    line-height: 1.1;
  }
}

.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--glow);
  opacity: 0.4;
  transition: opacity 0.3s, box-shadow 0.3s;

  .stat-card:hover & {
    opacity: 1;
    box-shadow: 0 0 16px var(--glow);
  }
}

// ---- 通用面板 ----
.panel {
  height: 100%;
  padding: 20px 22px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);

  h3 {
    margin: 0 0 12px;
    font-size: 15px;
  }
}

.chart {
  width: 100%;
}
.chart-md {
  height: 220px;
}

// ---- 类别分布 ----
.donut-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.donut {
  width: 220px;
  height: 220px;
  flex-shrink: 0;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.donut-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1;
  min-width: 200px;
  max-height: 200px;
  overflow-y: auto;

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    font-size: 13px;
  }
  .legend-name {
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .num { margin-left: auto; font-weight: 600; }
  .legend-sub {
    font-size: 12px;
    color: var(--text-3);
    width: 72px;
    text-align: right;
  }
}

// ---- 高赞评论 ----
.top-comments {
  list-style: none;
  margin: 0;
  padding: 0;

  li {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--line);

    &:last-child { border-bottom: none; }
  }
  .rank {
    width: 22px;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-3);
    text-align: center;

    &.hot { color: var(--hot); }
  }
  .tc-body { flex: 1; min-width: 0; }
  .tc-text {
    margin: 0 0 4px;
    font-size: 13px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .tc-meta {
    margin: 0;
    display: flex;
    gap: 12px;
    font-size: 12px;
  }
  .tc-digg { color: var(--hot); flex-shrink: 0; }
  .tc-video {
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    justify-content: center;
    color: var(--text-3);
    font-size: 13px;
  }
}
</style>
