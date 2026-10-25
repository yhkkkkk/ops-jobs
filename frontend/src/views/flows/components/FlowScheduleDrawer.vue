<template>
  <n-drawer :show="visible" :width="drawerWidth" placement="right" class="flow-schedule-drawer" @update:show="emit('update:visible', $event)"><n-drawer-content>
    <template #header>流水线定时调度</template>
    <section class="schedule-workbench">
      <header class="schedule-workbench__head">
        <div><strong>{{ template?.name || '-' }}</strong><span>按 Cron 自动启动完整流水线，固定输入来自当前模板的全局变量。</span></div>
        <n-button v-if="!readonly && !editing" type="primary" size="small" @click="startCreate"><template #icon><Plus  /></template>新建调度</n-button>
      </header>
      <n-spin :show="loading" class="schedule-workbench__body">
        <n-form v-if="editing" :model="form" label-placement="top" class="schedule-form">
          <div class="schedule-form__command"><n-button size="small" @click="closeEditor"><template #icon><ChevronLeft  /></template>返回列表</n-button><n-space><n-button size="small" @click="closeEditor">取消</n-button><n-button type="primary" size="small" :loading="saving" @click="saveSchedule">保存调度</n-button></n-space></div>
          <n-form-item label="调度名称" required><n-input v-model:value="form.name" :disabled="readonly" :maxlength="200" placeholder="例如：每日发布前检查" /></n-form-item>
          <div class="schedule-form__row">
            <n-form-item label="Cron 表达式" required><n-input v-model:value="form.cron_expression" :disabled="readonly" placeholder="0 2 * * *" /><span class="schedule-field-note">五段格式：分 时 日 月 周</span></n-form-item>
            <n-form-item label="时区"><n-select v-model:value="form.timezone" :disabled="readonly" :options="selectOptions1" /></n-form-item>
          </div>
          <div class="schedule-form__row schedule-form__row--policy">
            <n-form-item label="重叠触发策略"><n-select v-model:value="form.overlap_policy" :disabled="readonly" :options="selectOptions2" /><span class="schedule-field-note">已有任务未结束时的处理方式</span></n-form-item>
            <n-form-item label="错过触发策略"><n-select v-model:value="form.misfire_policy" :disabled="readonly" :options="selectOptions3" /><span class="schedule-field-note">调度恢复后如何处理错过的时间点</span></n-form-item>
            <n-form-item label="宽限秒数"><n-input-number v-model:value="form.misfire_grace_seconds" :disabled="readonly" :min="1" :max="3600" :precision="0" /><span class="schedule-field-note">超过宽限不再补跑</span></n-form-item>
          </div>
          <n-form-item label="状态">
            <n-space align="center">
              <n-switch v-model:value="form.is_active" :disabled="readonly" />
              <span class="schedule-field-note">{{ form.is_active ? '启用' : '停用' }}</span>
            </n-space>
          </n-form-item>
          <section class="schedule-inputs">
            <div class="schedule-section-title"><strong>预置全局变量</strong><span>定时触发始终执行完整拓扑，固定输入来自流水线全局变量。</span></div>
            <n-empty v-if="variableDefinitions.length === 0" description="当前模板没有全局变量" />
            <div v-else class="schedule-variable-list">
              <div v-for="variable in variableDefinitions" :key="variable.key" class="schedule-variable-row">
                <div class="schedule-variable-row__label"><strong>{{ variable.name }}</strong><span>{{ flowVariableReference(variable.key) }}{{ variable.required ? ' / 必填' : '' }}</span></div>
                <div v-if="variable.type === 'secret'" class="schedule-secret-input">
                  <n-input type="password" show-password-on="click" v-model:value="form.variableValues[variable.key]" :disabled="readonly" :placeholder="secretPlaceholder(variable)" />
                  <span v-if="secretConfigured[variable.key]">已配置；留空保持当前值</span>
                </div>
                <FlowIpSelectorField
                  v-else-if="variable.widget === 'host_list' || variable.type === 'host_list'"
                  v-model="form.variableValues[variable.key]"
                  :disabled="readonly"
                  :placeholder="variable.placeholder || '每行一个 IP 或主机名'"
                />
                <n-input type="textarea" v-else-if="variable.widget === 'textarea'" v-model:value="form.variableValues[variable.key]" :disabled="readonly" :placeholder="variable.placeholder || variable.description || variable.key" :autosize="{ minRows: 2, maxRows: 4 }" />
                <n-input v-else v-model:value="form.variableValues[variable.key]" :disabled="readonly" :placeholder="variable.placeholder || variable.description || variable.key" />
              </div>
            </div>
          </section>
        </n-form>
        <template v-else>
          <n-empty v-if="schedules.length === 0" description="当前模板没有流水线定时调度" />
          <n-data-table
            v-else
            :row-key="(row: any) => row.id"
            class="schedule-table"
            :columns="scheduleColumns"
            :data="schedules"
            :pagination="false"
            :scroll-x="560"
          />
        </template>
      </n-spin>
    </section>
  </n-drawer-content></n-drawer>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { flowApi } from '@/api/ops'
import type { FlowSchedule, FlowTemplate } from '@/types'
import { buildScheduledInputs, flowVariableReference, normalizeFlowVariables } from '../flowUtils'
import FlowIpSelectorField from './FlowIpSelectorField.vue'
import { NButton, NDataTable, NDrawer, NDrawerContent, NEmpty, NForm, NFormItem, NInput, NInputNumber, NSelect, NSpace, NSpin, NSwitch, NTag, NTooltip, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { ChevronLeft, CirclePause, Pencil, Play, Plus, Trash2 } from 'lucide-vue-next'

const message = useMessage()
const dialog = useDialog()
const props = withDefaults(defineProps<{ visible: boolean; template: FlowTemplate | null; readonly?: boolean }>(), { readonly: false })
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()
const drawerWidth = computed(() => window.innerWidth < 760 ? '100vw' : '640px')
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const schedules = ref<FlowSchedule[]>([])
const scheduleHistories = ref<Record<number, any[]>>({})
const secretConfigured = ref<Record<string, boolean>>({})
const form = reactive({ id: null as number | null, name: '', cron_expression: '0 2 * * *', timezone: 'Asia/Shanghai', overlap_policy: 'skip' as 'skip' | 'allow', misfire_policy: 'skip' as 'skip' | 'coalesce', misfire_grace_seconds: 60, is_active: true, variableValues: {} as Record<string, any> })
const variableDefinitions = computed(() => normalizeFlowVariables(props.template?.variables || {}))
const scheduleColumns: DataTableColumns<any> = [
  {
    title: '调度规则',
    key: 'rule',
    minWidth: 250,
    render: (row) =>
      h('div', { class: 'schedule-rule-cell' }, [
        h('strong', row.name),
        h('span', `${row.cron_expression} / ${row.timezone}`),
        h('small', `最近启动：${recentRunText(row)}`),
      ]),
  },
  { title: '预置变量', key: 'inputs', width: 100, render: (row) => formatInputSummary(row.inputs) },
  {
    title: '状态',
    key: 'status',
    width: 82,
    render: (row) => h(NTag, { type: (row.is_active ? 'success' : 'default') as any }, { default: () => (row.is_active ? '启用' : '停用') }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 112,
    render: (row) => {
      if (readonly) return h('span', { class: 'schedule-readonly' }, '只读')
      return h(NSpace, { size: 2, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NTooltip, {}, {
            trigger: () => h(NButton, { text: true, size: 'tiny', 'aria-label': '编辑调度', onClick: () => startEdit(row) }, {
              icon: () => h(Pencil, { size: 13 }),
            }),
            default: () => '编辑',
          }),
          h(NTooltip, {}, {
            trigger: () => h(NButton, {
              text: true, size: 'tiny',
              'aria-label': row.is_active ? '停用调度' : '启用调度',
              onClick: () => toggleSchedule(row),
            }, {
              icon: () => h(row.is_active ? CirclePause : Play, { size: 13 }),
            }),
            default: () => (row.is_active ? '停用' : '启用'),
          }),
          h(NTooltip, {}, {
            trigger: () => h(NButton, { type: 'error', size: 'tiny', 'aria-label': '删除调度', onClick: () => confirmDelete(row) }, {
              icon: () => h(Trash2, { size: 13 }),
            }),
            default: () => '删除',
          }),
        ],
      })
    },
  },
]
const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const formatInputSummary = (inputs: Record<string, any> = {}) => Object.keys(inputs || {}).length ? `已配置 ${Object.keys(inputs).length} 个变量` : '模板默认值'

const recentRunText = (schedule: FlowSchedule) => {
  const run = scheduleHistories.value[schedule.id]?.[0]
  if (!run) return '暂无'
  return run.flow_run_id ? `${run.status} / 已关联任务` : run.status
}
const loadSchedules = async () => {
  if (!props.template?.id) return
  loading.value = true
  try {
    schedules.value = normalizeList<FlowSchedule>(await flowApi.getSchedules({ template: props.template.id }))
    scheduleHistories.value = Object.fromEntries(await Promise.all(schedules.value.map(async schedule => [schedule.id, await flowApi.getScheduleRuns(schedule.id)])))
  }
  catch (error) { console.error('加载流水线定时调度失败:', error); message.error('加载流水线定时调度失败') }
  finally { loading.value = false }
}
const resetForm = (schedule?: FlowSchedule) => {
  form.id = schedule?.id || null; form.name = schedule?.name || ''; form.cron_expression = schedule?.cron_expression || '0 2 * * *'; form.timezone = schedule?.timezone || 'Asia/Shanghai'; form.overlap_policy = schedule?.overlap_policy || 'skip'; form.misfire_policy = schedule?.misfire_policy || 'skip'; form.misfire_grace_seconds = schedule?.misfire_grace_seconds || 60; form.is_active = schedule?.is_active ?? true
  const values = { ...(schedule?.inputs || {}) }; secretConfigured.value = {}
  variableDefinitions.value.filter(variable => variable.type === 'secret').forEach(variable => {
    secretConfigured.value[variable.key] = Object.prototype.hasOwnProperty.call(values, variable.key)
    delete values[variable.key]
  })
  variableDefinitions.value.filter(variable => variable.type === 'host_list').forEach(variable => {
    const value = values[variable.key]
    if (Array.isArray(value)) values[variable.key] = value.some(item => typeof item === 'number') ? '' : value.join('\n')
  })
  form.variableValues = values
}
const startCreate = async () => { resetForm(); editing.value = true }
const startEdit = async (schedule: FlowSchedule) => { resetForm(schedule); editing.value = true }
const closeEditor = () => { editing.value = false; resetForm() }
const secretPlaceholder = (variable: any) => secretConfigured.value[variable.key] || variable.has_default ? '已配置；输入新值可替换' : (variable.placeholder || '输入密文值')
const schedulePayload = () => {
  const inputs = buildScheduledInputs(variableDefinitions.value, form.variableValues)
  variableDefinitions.value.filter(variable => variable.type === 'secret').forEach(variable => {
    const value = form.variableValues[variable.key]
    if (value) inputs[variable.key] = value
    else delete inputs[variable.key]
  })
  return { name: form.name.trim(), template: props.template!.id!, cron_expression: form.cron_expression.trim(), timezone: form.timezone, overlap_policy: form.overlap_policy, misfire_policy: form.misfire_policy, misfire_grace_seconds: form.misfire_grace_seconds, is_active: form.is_active, inputs }
}
const saveSchedule = async () => {
  if (!props.template?.id || !form.name.trim() || !form.cron_expression.trim()) { message.warning('请填写调度名称和 Cron 表达式'); return }
  saving.value = true
  try { if (form.id) await flowApi.updateSchedule(form.id, schedulePayload()); else await flowApi.createSchedule(schedulePayload()); message.success('流水线定时调度已保存'); editing.value = false; await loadSchedules() }
  catch (error) { console.error('保存流水线定时调度失败:', error); message.error('保存失败，请检查 Cron 表达式和变量输入') }
  finally { saving.value = false }
}
const toggleSchedule = async (schedule: FlowSchedule) => {
  try { await flowApi.updateSchedule(schedule.id, { name: schedule.name, template: schedule.template, cron_expression: schedule.cron_expression, timezone: schedule.timezone, overlap_policy: schedule.overlap_policy, misfire_policy: schedule.misfire_policy, misfire_grace_seconds: schedule.misfire_grace_seconds, inputs: schedule.inputs || {}, is_active: !schedule.is_active }); await loadSchedules() }
  catch (error) { console.error('更新流水线定时调度状态失败:', error); message.error('更新调度状态失败') }
}
const confirmDelete = (schedule: FlowSchedule) => dialog.warning({ title: '删除流水线定时调度', content: `确认删除“${schedule.name}”？`, onPositiveClick: async () => { await flowApi.deleteSchedule(schedule.id); message.success('流水线定时调度已删除'); await loadSchedules() } })
watch(() => [props.visible, props.template?.id], ([visible]) => { if (!visible) return; editing.value = false; resetForm(); loadSchedules() })

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: 'Asia/Shanghai', value: 'Asia/Shanghai' }, { label: 'UTC', value: 'UTC' }, { label: 'America/New_York', value: 'America/New_York' }, { label: 'Europe/London', value: 'Europe/London' }]
const selectOptions2 = [{ label: '跳过本次', value: 'skip' }, { label: '允许并发', value: 'allow' }]
const selectOptions3 = [{ label: '跳过', value: 'skip' }, { label: '合并为一次补跑', value: 'coalesce' }]
</script>

<style scoped>
.schedule-workbench { display: grid; grid-template-rows: auto minmax(0, 1fr); height: 100%; min-width: 0; overflow: hidden; }
.schedule-workbench__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 0 0 12px; border-bottom: 1px solid var(--app-border); }
.schedule-workbench__head > div, .schedule-section-title, .schedule-rule-cell { display: grid; gap: 3px; min-width: 0; }
.schedule-workbench__head strong, .schedule-section-title strong { color: var(--app-fg); font-size: 14px; }
.schedule-workbench__head span, .schedule-section-title span, .schedule-field-note { color: var(--app-muted); font-size: 12px; line-height: 1.5; }
.schedule-workbench__body { min-height: 0; padding-top: 12px; overflow: auto; }
.schedule-form { display: grid; gap: 2px; min-width: 0; }
.schedule-form__command { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.schedule-form__row { display: grid; grid-template-columns: minmax(0, 1fr) 180px; gap: 12px; }
.schedule-form__row--policy { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.schedule-form :deep(.arco-form-item) { margin-bottom: 10px; }
.schedule-inputs { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--app-border); }
.schedule-variable-list { display: grid; gap: 10px; }
.schedule-variable-row { display: grid; grid-template-columns: minmax(160px, .45fr) minmax(0, 1fr); gap: 10px; align-items: start; }
.schedule-variable-row__label { display: grid; gap: 2px; padding-top: 5px; min-width: 0; }
.schedule-variable-row__label strong, .schedule-variable-row__label span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.schedule-variable-row__label strong { color: var(--app-fg); font-size: 13px; }
.schedule-variable-row__label span, .schedule-rule-cell small { color: var(--app-muted); font-size: 12px; }
.schedule-rule-cell span { color: var(--app-muted); font-family: var(--app-mono); font-size: 12px; }
.schedule-variable-row__secret { padding-top: 7px; color: var(--app-muted); font-size: 13px; }
.schedule-rule-cell strong { overflow: hidden; color: var(--app-fg); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.schedule-readonly { color: var(--app-muted); font-size: 12px; }
@media (max-width: 600px) { .schedule-form__row, .schedule-variable-row { grid-template-columns: 1fr; } }
</style>
