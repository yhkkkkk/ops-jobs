<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  data: Array<{ name: string; value: number }>;
  height?: string;
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
const height = props.height || '260px'

const render = () => {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'item' },
    legend: { orient: 'horizontal', left: 'center' },
    series: [
      {
        name: 'Agents',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: '16', fontWeight: 'bold' } },
        labelLine: { show: false },
        data: props.data || []
      }
    ]
  }
  chart.setOption(option)
}

onMounted(() => {
  render()
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  try {
    chart?.dispose()
  } catch (e) {}
})

watch(() => props.data, () => {
  render()
}, { deep: true })
</script>

<style scoped>
:root { --chart-bg: transparent; }
</style>


