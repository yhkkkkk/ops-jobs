<template>
  <div class="cron-builder">
    <cron-core v-model="value" v-slot="{ fields, period, error }">
      <div class="cron-section">
        <div class="cron-row">
          <span class="cron-label">执行频率</span>
          <a-select
            :model-value="period.attrs.modelValue"
            @change="period.events['update:model-value']"
            size="small"
          >
            <a-option
              v-for="item in period.items"
              :key="item.id"
              :value="item.id"
            >
              {{ getPeriodText(item) }}
            </a-option>
          </a-select>
        </div>
      </div>

      <div class="cron-section">
        <div
          v-for="field in fields"
          :key="field.id"
          class="cron-row"
        >
          <span class="cron-label">{{ getFieldLabel(field.id) }}</span>
          <a-select
            multiple
            allow-search
            allow-clear
            :model-value="field.attrs.modelValue"
            @change="field.events['update:model-value']"
            :placeholder="translateText(field.selectedStr) || '请选择'"
            size="small"
          >
            <a-option
              v-for="item in field.items"
              :key="item.value"
              :value="item.value"
            >
              {{ getFieldItemText(field.id, item) }}
            </a-option>
          </a-select>
        </div>
      </div>

      <div class="cron-section cron-presets">
        <div class="cron-row cron-row-presets">
          <span class="cron-label">常用</span>
          <div class="cron-presets-list">
            <a-button
              v-for="preset in presets"
              :key="preset.value"
              size="mini"
              @click="applyPreset(preset.value)"
            >
              {{ preset.label }}
            </a-button>
          </div>
        </div>
      </div>

      <div class="cron-expression">
        <div class="cron-expression-label">Cron表达式</div>
        <a-input :model-value="value" readonly />
      </div>

      <div v-if="error" class="cron-error">
        <icon-exclamation-circle />
        {{ error }}
      </div>
    </cron-core>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconExclamationCircle } from '@arco-design/web-vue/es/icon'

interface Props {
  modelValue: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '* * * * *'
})

const emit = defineEmits<Emits>()

const value = computed({
  get: () => props.modelValue,
  set: (val: string) => emit('update:modelValue', val)
})

const presets = [
  { label: '每5分钟', value: '*/5 * * * *' },
  { label: '每10分钟', value: '*/10 * * * *' },
  { label: '每30分钟', value: '*/30 * * * *' },
  { label: '每2小时', value: '0 */2 * * *' },
  { label: '每天2点', value: '0 2 * * *' },
  { label: '每周一9点', value: '0 9 * * 1' },
  { label: '每月1号0点', value: '0 0 1 * *' }
]

const applyPreset = (expression: string) => {
  value.value = expression
}

const getFieldLabel = (id: string) => {
  const map: Record<string, string> = {
    minute: '分钟',
    hour: '小时',
    day: '日',
    month: '月',
    dayOfWeek: '周'
  }
  return map[id] || id
}

const periodTextMap: Record<string, string> = {
  minute: '每分钟',
  hour: '每小时',
  day: '每天',
  week: '每周',
  month: '每月',
  year: '每年'
}

const monthNameMap: Record<string, string> = {
  january: '1月',
  february: '2月',
  march: '3月',
  april: '4月',
  may: '5月',
  june: '6月',
  july: '7月',
  august: '8月',
  september: '9月',
  october: '10月',
  november: '11月',
  december: '12月'
}

const weekdayValueMap: Record<string, string> = {
  '0': '周日',
  '1': '周一',
  '2': '周二',
  '3': '周三',
  '4': '周四',
  '5': '周五',
  '6': '周六',
  '7': '周日',
  SUN: '周日',
  MON: '周一',
  TUE: '周二',
  WED: '周三',
  THU: '周四',
  FRI: '周五',
  SAT: '周六'
}

const translateText = (text?: string) => {
  if (!text) return ''
  const trimmed = String(text).trim()
  const lower = trimmed.toLowerCase()
  const directMap: Record<string, string> = {
    'every minute': '每分钟',
    'every hour': '每小时',
    'every day': '每天',
    'every day of the week': '每周的每一天',
    'every week': '每周',
    'every month': '每月',
    'every year': '每年',
    'every weekday': '每个工作日',
    'weekday': '工作日',
    'last day': '最后一天'
  }
  if (directMap[lower]) return directMap[lower]
  if (lower.startsWith('every ')) {
    const rest = lower.slice(6)
    const tokenMap: Record<string, string> = {
      minute: '分钟',
      hour: '小时',
      day: '天',
      week: '周',
      month: '月',
      year: '年',
      weekday: '个工作日'
    }
    if (tokenMap[rest]) {
      return `每${tokenMap[rest]}`
    }
  }
  return trimmed
}

const getPeriodText = (item: any) => {
  return periodTextMap[item.id] || translateText(item.text) || item.id
}

const getFieldItemText = (fieldId: string, item: any) => {
  const value = String(item.value ?? '')
  if (fieldId === 'month') {
    if (/^\d+$/.test(value)) return `${value}月`
    if (item.text) {
      const key = String(item.text).toLowerCase()
      if (monthNameMap[key]) return monthNameMap[key]
    }
  }
  if (fieldId === 'dayOfWeek') {
    if (weekdayValueMap[value]) return weekdayValueMap[value]
    if (item.text && weekdayValueMap[item.text]) return weekdayValueMap[item.text]
  }
  return translateText(item.text) || value
}
</script>

<style scoped>
.cron-builder {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cron-section {
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: #fff;
}

.cron-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.cron-row:last-child {
  margin-bottom: 0;
}

.cron-row-presets {
  align-items: flex-start;
}

.cron-label {
  font-size: 12px;
  color: #4e5969;
}

.cron-presets-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cron-expression {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cron-expression-label {
  font-size: 12px;
  color: #4e5969;
}

.cron-error {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #f53f3f;
  font-size: 12px;
}
</style>
