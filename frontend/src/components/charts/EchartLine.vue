<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  series: Array<{ name: string; data: Array<number>; }>;
  xAxis: Array<string>;
  height?: string;
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const height = props.height || '320px'

const render = () => {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 10 },
    xAxis: { type: 'category', data: props.xAxis },
    yAxis: { type: 'value' },
    series: (props.series || []).map(s => ({ name: s.name, type: 'line', data: s.data, smooth: true }))
  }
  chart.setOption(option)
}

onMounted(() => {
  render()
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  try { chart?.dispose() } catch {}
})

watch(() => props.series, () => render(), { deep: true })
</script>

<style scoped>
</style>


