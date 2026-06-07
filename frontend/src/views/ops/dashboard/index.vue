<template>
  <div class="ops-dashboard-page app-page">
    <div class="app-page-header">
      <div>
        <p class="app-page-eyebrow">OPS CONTROL PLANE</p>
        <h1 class="app-page-title">运维台 Dashboard</h1>
        <p class="app-page-desc">
          关注 Agent 连通性、任务失败率、延时分位和失败主机，优先服务值班排障与容量判断。
        </p>
      </div>
      <a-space>
        <span class="last-updated">最后更新：{{ formatDateTime(overview.last_updated) || '-' }}</span>
        <a-button type="primary" :loading="loading" @click="fetchOverview">刷新</a-button>
      </a-space>
    </div>

    <div class="app-metric-grid">
      <button
        v-for="card in cards"
        :key="card.key"
        class="app-card app-metric-card metric-button"
        type="button"
        @click="onCardClick(card.key)"
      >
        <div class="app-metric-top">
          <div>
            <p class="app-metric-label">{{ card.title }}</p>
            <div class="app-metric-value">{{ card.value }}</div>
          </div>
          <span class="app-metric-icon" :class="card.tone">
            <component :is="card.icon" />
          </span>
        </div>
        <p class="app-metric-note">{{ card.hint }}</p>
      </button>
    </div>

    <div class="ops-grid">
      <a-card class="ops-panel" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>Agent 在线分布</h3>
            <p>用于快速识别待激活、离线和禁用节点。</p>
          </div>
          <span class="app-status-pill" :class="agentHealthClass">
            {{ agentHealthText }}
          </span>
        </div>
        <echart-pie :data="pieData" height="320px" />
      </a-card>

      <a-card class="ops-panel" :bordered="false">
        <div class="app-section-title">
          <div>
            <h3>24h 任务质量</h3>
            <p>失败率、延时和心跳告警合并为值班摘要。</p>
          </div>
        </div>

        <div class="quality-hero">
          <div>
            <div class="quality-label">失败率</div>
            <div class="quality-value" :class="failRateTone">{{ overview.fail_rate_24h }}%</div>
          </div>
          <span class="app-status-pill" :class="failRateClass">{{ failRateText }}</span>
        </div>

        <div class="latency-stack">
          <div class="latency-row">
            <span>P50</span>
            <strong>{{ overview.task_p50_ms }} ms</strong>
          </div>
          <div class="latency-row">
            <span>P95</span>
            <strong>{{ overview.task_p95_ms }} ms</strong>
          </div>
          <div class="latency-row">
            <span>P99</span>
            <strong>{{ overview.task_p99_ms }} ms</strong>
          </div>
          <div class="latency-row warning">
            <span>心跳告警</span>
            <strong>{{ overview.heartbeat_alerts }}</strong>
          </div>
        </div>
      </a-card>
    </div>

    <a-card class="ops-panel" :bordered="false">
      <div class="app-section-title trend-title">
        <div>
          <h3>任务延时趋势</h3>
          <p>P50 / P95 分位延时趋势，辅助判断执行链路是否出现退化。</p>
        </div>
        <div class="trend-controls">
          <a-select v-model="timeRange" class="range-select" @change="onTimeRangeChange">
            <a-option v-for="opt in timeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </a-option>
          </a-select>
          <a-date-picker v-if="timeRange === 'custom'" v-model="startDate" format="YYYY-MM-DD" placeholder="开始日期" />
          <a-date-picker v-if="timeRange === 'custom'" v-model="endDate" format="YYYY-MM-DD" placeholder="结束日期" />
          <a-button type="primary" @click="applyLatencyRange">应用</a-button>
        </div>
      </div>
      <EchartLine v-if="latencySeries.length > 0" :series="latencySeries" :xAxis="latencyXAxis" height="320px" />
      <div v-else class="app-empty">暂无延时趋势数据</div>
    </a-card>

    <a-card class="ops-panel" :bordered="false">
      <div class="app-section-title">
        <div>
          <h3>失败主机 TOP</h3>
          <p>按失败次数排序，优先排查最近失败节点。</p>
        </div>
      </div>
      <div class="failure-table-wrap">
        <table class="failure-table">
          <thead>
            <tr>
              <th>主机名</th>
              <th>失败次数</th>
              <th>最后失败时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="host in overview.top_failure_hosts" :key="host.host_name">
              <td>{{ host.host_name }}</td>
              <td>
                <span class="failure-count">{{ host.fail_count }}</span>
              </td>
              <td>{{ host.last_failed_at ? formatDateTime(host.last_failed_at) : '-' }}</td>
            </tr>
            <tr v-if="!overview.top_failure_hosts || overview.top_failure_hosts.length === 0">
              <td colspan="3" class="empty-cell">暂无失败主机</td>
            </tr>
          </tbody>
        </table>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import { Message } from '@arco-design/web-vue'
import { IconCheckCircle, IconCloseCircle, IconClockCircle, IconMinusCircle } from '@arco-design/web-vue/es/icon'
import EchartPie from '@/components/charts/EchartPie.vue'
import EchartLine from '@/components/charts/EchartLine.vue'
import { formatDateTime } from '@/utils/date'

const overview = reactive({
  agents_total: 0,
  agents_online: 0,
  agents_offline: 0,
  agents_pending: 0,
  agents_disabled: 0,
  running_tasks: 0,
  fail_rate_24h: 0,
  task_p50_ms: 0,
  task_p95_ms: 0,
  task_p99_ms: 0,
  heartbeat_alerts: 0,
  top_failure_hosts: [] as Array<{ host_name: string; fail_count: number; last_failed_at?: string | null }>,
  last_updated: null as string | null
})

const loading = ref(false)
const router = useRouter()

const fetchOverview = async () => {
  loading.value = true
  try {
    const resp: any = await dashboardApi.getOpsOverview()
    if (resp) {
      Object.assign(overview, resp)
    }
  } catch (e) {
    console.error('获取运维台概览失败', e)
    Message.error('获取运维台概览失败')
  } finally {
    loading.value = false
  }
}

const cards = computed(() => [
  {
    key: 'total',
    title: 'Agent 总数',
    value: overview.agents_total,
    icon: IconClockCircle,
    hint: `待激活 ${overview.agents_pending}，已禁用 ${overview.agents_disabled}`,
    tone: 'tone-neutral'
  },
  {
    key: 'online',
    title: '在线 Agent',
    value: overview.agents_online,
    icon: IconCheckCircle,
    hint: `在线率 ${agentOnlineRate.value}%`,
    tone: 'tone-success'
  },
  {
    key: 'offline',
    title: '离线 Agent',
    value: overview.agents_offline,
    icon: IconCloseCircle,
    hint: overview.agents_offline > 0 ? '需要确认心跳或网络状态' : '当前无离线节点',
    tone: overview.agents_offline > 0 ? 'tone-danger' : 'tone-success'
  },
  {
    key: 'p95',
    title: '任务 P95',
    value: overview.task_p95_ms,
    icon: IconMinusCircle,
    hint: '毫秒，点击查看执行记录',
    tone: 'tone-neutral'
  },
])

const agentOnlineRate = computed(() => {
  if (!overview.agents_total) return 0
  return Math.round((overview.agents_online / overview.agents_total) * 100)
})

const agentHealthClass = computed(() => {
  if (overview.agents_offline > 0 || overview.heartbeat_alerts > 0) return 'app-status-warn'
  return 'app-status-success'
})

const agentHealthText = computed(() => {
  if (overview.agents_offline > 0) return `${overview.agents_offline} 个离线`
  if (overview.heartbeat_alerts > 0) return `${overview.heartbeat_alerts} 个心跳告警`
  return '节点正常'
})

const failRateClass = computed(() => {
  if (overview.fail_rate_24h >= 5) return 'app-status-danger'
  if (overview.fail_rate_24h > 0) return 'app-status-warn'
  return 'app-status-success'
})

const failRateTone = computed(() => {
  if (overview.fail_rate_24h >= 5) return 'danger'
  if (overview.fail_rate_24h > 0) return 'warn'
  return 'success'
})

const failRateText = computed(() => {
  if (overview.fail_rate_24h >= 5) return '高风险'
  if (overview.fail_rate_24h > 0) return '需关注'
  return '稳定'
})

const pieData = computed(() => ([
  { name: '在线', value: overview.agents_online },
  { name: '离线', value: overview.agents_offline },
  { name: '待激活', value: overview.agents_pending },
  { name: '已禁用', value: overview.agents_disabled },
]))

const onCardClick = (key: string) => {
  if (key === 'total') {
    router.push('/ops/agents')
  } else if (key === 'online') {
    router.push({ path: '/ops/agents', query: { status: 'online' } })
  } else if (key === 'offline') {
    router.push({ path: '/ops/agents', query: { status: 'offline' } })
  } else if (key === 'p95') {
    router.push('/execution-records')
  }
}

const latencySeries = ref<any[]>([])
const latencyXAxis = ref<string[]>([])
const timeRange = ref<'7d' | '30d' | 'custom'>('7d')
const startDate = ref<any>(null)
const endDate = ref<any>(null)

const timeOptions = computed(() => {
  const today = dayjs()
  const fmt = (d: any) => dayjs(d).format('YYYY-MM-DD')
  return [
    { value: '7d', label: `7 天（${fmt(today.subtract(6, 'day'))} - ${fmt(today)}）` },
    { value: '30d', label: `30 天（${fmt(today.subtract(29, 'day'))} - ${fmt(today)}）` },
    { value: 'custom', label: '自定义' }
  ]
})

const buildZeroSeries = (labels: string[]) => {
  const zeros = labels.map(() => 0.0)
  latencyXAxis.value = labels
  latencySeries.value = [
    { name: 'P50 (ms)', data: zeros },
    { name: 'P95 (ms)', data: zeros }
  ]
}

const fetchLatencyTrendWithParams = async (params: any) => {
  try {
    const resp: any = await dashboardApi.getLatencyTrend(params)
    if (Array.isArray(resp) && resp.length > 0) {
      latencyXAxis.value = resp.map((r: any) => r.ts)
      latencySeries.value = [
        { name: 'P50 (ms)', data: resp.map((r: any) => r.p50) },
        { name: 'P95 (ms)', data: resp.map((r: any) => r.p95) }
      ]
    } else {
      const tr = params?.time_range || '7d'
      const labels: string[] = []
      if (tr === '30d') {
        for (let i = 29; i >= 0; i--) labels.push(dayjs().subtract(i, 'day').format('YYYY-MM-DD'))
      } else {
        for (let i = 6; i >= 0; i--) labels.push(dayjs().subtract(i, 'day').format('YYYY-MM-DD'))
      }
      buildZeroSeries(labels)
    }
  } catch (e) {
    console.error('获取延时趋势失败', e)
    latencySeries.value = []
    latencyXAxis.value = []
  }
}

const fetchLatencyTrend = async () => {
  await fetchLatencyTrendWithParams({ time_range: timeRange.value, granularity: 'day' })
}

const applyLatencyRange = () => {
  const params: any = {}
  if (timeRange.value === 'custom') {
    if (!startDate.value || !endDate.value) {
      Message.warning('请选择开始和结束日期')
      return
    }
    const fmtVal = (v: any) => {
      if (!v) return undefined
      if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return v
      if (v && typeof v.format === 'function') return v.format('YYYY-MM-DD')
      try { return dayjs(v).format('YYYY-MM-DD') } catch { return undefined }
    }
    params.time_range = 'custom'
    params.start_date = fmtVal(startDate.value)
    params.end_date = fmtVal(endDate.value)
  } else {
    params.time_range = timeRange.value
  }
  fetchLatencyTrendWithParams(params)
}

const onTimeRangeChange = () => {
  if (timeRange.value === 'custom') {
    startDate.value = dayjs().subtract(6, 'day')
    endDate.value = dayjs()
    return
  }
  applyLatencyRange()
}

onMounted(() => {
  fetchOverview()
  fetchLatencyTrend()
})
</script>

<style scoped>
.ops-dashboard-page {
  padding: 0;
}

.last-updated {
  color: var(--app-meta);
  font-family: var(--app-mono);
  font-size: 12px;
}

.metric-button {
  width: 100%;
  border: 1px solid var(--app-border);
  text-align: left;
}

.tone-success {
  color: var(--app-success);
  background: var(--app-success-soft);
}

.tone-danger {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}

.tone-neutral {
  color: var(--app-accent);
  background: var(--app-accent-soft);
}

.ops-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.8fr);
  gap: 20px;
}

.ops-panel {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

.quality-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px;
  background: var(--app-surface-soft);
  border-radius: var(--app-radius-sm);
}

.quality-label {
  color: var(--app-muted);
  font-size: 13px;
}

.quality-value {
  margin-top: 6px;
  font-family: var(--app-mono);
  font-size: 44px;
  line-height: 1;
  font-weight: 750;
  letter-spacing: -0.03em;
}

.quality-value.success {
  color: var(--app-success);
}

.quality-value.warn {
  color: var(--app-warn);
}

.quality-value.danger {
  color: var(--app-danger);
}

.latency-stack {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.latency-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  color: var(--app-muted);
  border-bottom: 1px solid var(--app-border);
  font-size: 13px;
}

.latency-row:last-child {
  border-bottom: 0;
}

.latency-row strong {
  color: var(--app-fg);
  font-family: var(--app-mono);
  font-size: 15px;
}

.latency-row.warning strong {
  color: var(--app-danger);
}

.trend-title {
  align-items: flex-start;
}

.trend-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.range-select {
  width: 220px;
}

.failure-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.failure-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.failure-table th {
  padding: 0 0 10px;
  color: var(--app-muted);
  font-weight: 600;
  text-align: left;
  border-bottom: 1px solid var(--app-border);
}

.failure-table td {
  padding: 13px 0;
  color: var(--app-fg-secondary);
  border-bottom: 1px solid var(--app-border);
}

.failure-count {
  display: inline-flex;
  min-width: 32px;
  height: 24px;
  align-items: center;
  justify-content: center;
  color: var(--app-danger);
  background: var(--app-danger-soft);
  border-radius: 999px;
  font-family: var(--app-mono);
  font-size: 12px;
  font-weight: 700;
}

.empty-cell {
  height: 120px;
  color: var(--app-meta) !important;
  text-align: center;
}

@media (max-width: 1180px) {
  .ops-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .trend-controls {
    justify-content: flex-start;
  }

  .range-select {
    width: 100%;
  }

  .last-updated {
    display: none;
  }
}
</style>
