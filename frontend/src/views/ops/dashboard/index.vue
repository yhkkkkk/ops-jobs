<template>
  <div class="ops-dashboard-page">
    <div class="page-header">
      <div class="header-left">
        <h2>运维台 Dashboard</h2>
        <p class="header-desc">运维关注的实时 KPI 与告警概览</p>
      </div>
      <div class="header-right">
        <a-button @click="fetchOverview" type="primary">刷新</a-button>
      </div>
    </div>

    <a-row :gutter="16" class="mb-4">
  <a-col :span="6" v-for="card in cards" :key="card.key">
        <a-card class="stat-card stat-card-lg" :hoverable="true" @click="onCardClick(card.key)" style="cursor:pointer">
          <div class="stat-card-inner">
            <div class="stat-left">
              <component :is="card.icon" class="stat-icon" />
            </div>
            <div class="stat-right">
              <div class="stat-title">{{ card.title }}</div>
              <div class="stat-value">{{ card.value }}</div>
              <div v-if="card.hint" class="stat-hint">{{ card.hint }}</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-card>
      <div style="display:flex; gap: 24px; align-items:center">
        <div style="flex:1">
          <h3>Agent 在线/离线分布</h3>
          <echart-pie :data="pieData" height="320px" />
        </div>
        <div style="flex:1">
          <h3>24h 任务失败率</h3>
          <div style="font-size: 28px; color:#f53f3f; margin-top: 12px">{{ overview.fail_rate_24h }}%</div>
          <div style="margin-top:8px;color:#86909c">过去24小时失败率</div>
          <div style="margin-top:8px;color:#86909c;font-size:12px">最后更新时间：{{ formatDateTime(overview.last_updated) }}</div>
          <div style="margin-top:12px">
            <div>任务延时 P50: <strong>{{ overview.task_p50_ms }} ms</strong></div>
            <div>任务延时 P95: <strong>{{ overview.task_p95_ms }} ms</strong></div>
            <div>任务延时 P99: <strong>{{ overview.task_p99_ms }} ms</strong></div>
            <div style="margin-top:8px;color:#f53f3f">心跳告警: <strong>{{ overview.heartbeat_alerts }}</strong></div>
            <div style="margin-top:12px">
              <h4>失败主机 TOP</h4>
              <table style="width:100%; border-collapse: collapse; margin-top:8px">
                <thead>
                  <tr style="text-align:left; color:#86909c; font-size:12px">
                    <th>主机名</th><th>失败次数</th><th>最后失败时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="host in overview.top_failure_hosts" :key="host.host_name" style="border-top:1px solid #f0f0f0; height:32px">
                    <td>{{ host.host_name }}</td>
                    <td>{{ host.fail_count }}</td>
                    <td>{{ host.last_failed_at ? new Date(host.last_failed_at).toLocaleString() : '-' }}</td>
                  </tr>
                  <tr v-if="!overview.top_failure_hosts || overview.top_failure_hosts.length===0">
                    <td colspan="3" style="color:#b0b7c3; text-align:center">暂无失败主机</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </a-card>
    <a-card style="margin-top: 16px">
      <div style="display:flex; justify-content:space-between; align-items:center">
        <h3>任务延时趋势（P50 / P95）</h3>
        <div style="display:flex; gap:8px; align-items:center">
          <a-select v-model="timeRange" style="width:200px" @change="onTimeRangeChange">
            <a-option v-for="opt in timeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</a-option>
          </a-select>
          <a-date-picker v-if="timeRange==='custom'" v-model="startDate" format="YYYY-MM-DD" placeholder="开始日期" />
          <a-date-picker v-if="timeRange==='custom'" v-model="endDate" format="YYYY-MM-DD" placeholder="结束日期" />
          <a-button type="primary" @click="applyLatencyRange">应用</a-button>
        </div>
      </div>
      <EchartLine v-if="latencySeries.length > 0" :series="latencySeries" :xAxis="latencyXAxis" height="320px" />
      <div v-else style="text-align:center; padding:40px; color:#86909c">暂无数据</div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
// @ts-ignore - path alias may not be resolved by editor type checker in this environment
import { dashboardApi } from '@/api/dashboard'
import { Message } from '@arco-design/web-vue'
import dayjs from 'dayjs'
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

const fetchOverview = async () => {
  loading.value = true
  try {
    const resp: any = await dashboardApi.getOpsOverview()
    if (resp) {
      Object.assign(overview, resp)
    }
  } catch (e) {
    console.error('获取运维台概览失败', e)
  } finally {
    loading.value = false
  }
}

const cards = computed(() => [
  { key: 'total', title: 'Agent 总数', value: overview.agents_total, icon: IconClockCircle, hint: '' },
  { key: 'online', title: '在线', value: overview.agents_online, icon: IconCheckCircle, hint: '' },
  { key: 'offline', title: '离线', value: overview.agents_offline, icon: IconCloseCircle, hint: '' },
  { key: 'p95', title: '任务 P95 (ms)', value: overview.task_p95_ms, icon: IconMinusCircle, hint: '' },
])

const pieData = computed(() => ([
  { name: '在线', value: overview.agents_online },
  { name: '离线', value: overview.agents_offline },
  { name: '待激活', value: overview.agents_pending },
  { name: '已禁用', value: overview.agents_disabled },
]))

import { useRouter } from 'vue-router'
const router = useRouter()

const onCardClick = (key: string) => {
  // navigate to ops agents with filter based on card key
  if (key === 'total') {
    router.push('/ops/agents')
  } else if (key === 'online') {
    router.push({ path: '/ops/agents', query: { status: 'online' } })
  } else if (key === 'offline') {
    router.push({ path: '/ops/agents', query: { status: 'offline' } })
  } else if (key === 'p95') {
    // drill down to execution records page
    router.push('/execution-records')
  }
}
// 延时趋势数据与时间选择
const latencySeries = ref<any[]>([])
const latencyXAxis = ref<string[]>([])
const timeRange = ref<'7d'|'30d'|'custom'>('7d')
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
      const p50 = resp.map((r: any) => r.p50)
      const p95 = resp.map((r: any) => r.p95)
      latencySeries.value = [
        { name: 'P50 (ms)', data: p50 },
        { name: 'P95 (ms)', data: p95 }
      ]
    } else {
      // 当接口返回空数组时，尝试构建默认时间轴（根据 params.time_range）
      const tr = params?.time_range || '7d'
      let labels: string[] = []
      if (tr === '30d') {
        for (let i = 29; i >= 0; i--) labels.push(dayjs().subtract(i, 'day').format('YYYY-MM-DD'))
      } else { // 默认 7d
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

// 页面初始化加载概览与延时趋势
onMounted(() => {
  fetchOverview()
  fetchLatencyTrend()
})
</script>

<style scoped>
.ops-dashboard-page {
  padding: 12px;
}
.page-header {
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:12px;
}
.header-left h2 { margin:0 }
.header-desc { margin:0; color:#86909c; font-size:13px }
.mb-4 { margin-bottom:16px }
.stat-card { text-align:center }
.stat-card-lg { padding: 12px 16px; min-height: 96px; display:flex; align-items:center; }
.stat-card .stat-card-inner { display:flex; gap:12px; align-items:center; width:100% }
.stat-card .stat-left { flex:0 0 48px; display:flex; align-items:center; justify-content:center }
.stat-card .stat-icon { font-size:24px; color:#1890ff }
.stat-card .stat-right { flex:1; text-align:left }
.stat-card .stat-title { color:#86909c; font-size:13px }
.stat-card .stat-value { font-size:22px; font-weight:600; margin-top:6px }
.stat-card .stat-hint { color:#b0b7c3; font-size:12px; margin-top:6px }
</style>


