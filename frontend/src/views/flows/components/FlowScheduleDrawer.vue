<template>
  <a-drawer :visible="visible" :width="drawerWidth" placement="right" :footer="false" class="flow-schedule-drawer" @update:visible="emit('update:visible', $event)">
    <template #title>定时调度</template>
    <section class="schedule-workbench">
      <header class="schedule-workbench__head">
        <div><strong>{{ template?.name || '-' }}</strong><span>按 Cron 自动启动完整流水线，固定输入来自当前模板的全局变量。</span></div>
        <a-button v-if="!readonly && !editing" type="primary" size="small" @click="startCreate"><template #icon><icon-plus /></template>新建调度</a-button>
      </header>
      <a-spin :loading="loading" class="schedule-workbench__body">
        <a-form v-if="editing" :model="form" layout="vertical" class="schedule-form">
          <div class="schedule-form__command"><a-button size="small" @click="closeEditor"><template #icon><icon-left /></template>返回列表</a-button><a-space><a-button size="small" @click="closeEditor">取消</a-button><a-button type="primary" size="small" :loading="saving" @click="saveSchedule">保存调度</a-button></a-space></div>
          <a-form-item label="调度名称" required><a-input v-model="form.name" :disabled="readonly" :max-length="200" placeholder="例如：每日发布前检查" /></a-form-item>
          <div class="schedule-form__row">
            <a-form-item label="Cron 表达式" required><a-input v-model="form.cron_expression" :disabled="readonly" placeholder="0 2 * * *" /><span class="schedule-field-note">五段格式：分 时 日 月 周</span></a-form-item>
            <a-form-item label="时区"><a-select v-model="form.timezone" :disabled="readonly"><a-option value="Asia/Shanghai">Asia/Shanghai</a-option><a-option value="UTC">UTC</a-option><a-option value="America/New_York">America/New_York</a-option><a-option value="Europe/London">Europe/London</a-option></a-select></a-form-item>
          </div>
          <a-form-item label="状态"><a-switch v-model="form.is_active" :disabled="readonly" checked-text="启用" unchecked-text="停用" /></a-form-item>
          <section class="schedule-inputs">
            <div class="schedule-section-title"><strong>预置全局变量</strong><span>定时触发始终执行完整拓扑，不包含临时节点范围或节点参数覆盖。</span></div>
            <a-empty v-if="variableDefinitions.length === 0" description="当前模板没有全局变量" />
            <div v-else class="schedule-variable-list">
              <div v-for="variable in variableDefinitions" :key="variable.key" class="schedule-variable-row">
                <div class="schedule-variable-row__label"><strong>{{ variable.name }}</strong><span>{{ flowVariableReference(variable.key) }}{{ variable.required ? ' / 必填' : '' }}</span></div>
                <span v-if="variable.type === 'secret'" class="schedule-variable-row__secret">密文变量使用模板默认值</span>
                <a-select v-else-if="variable.widget === 'host_list'" v-model="form.variableValues[variable.key]" multiple allow-search :disabled="readonly" :loading="hostsLoading" placeholder="选择目标主机">
                  <a-option v-for="host in hostOptions" :key="host.id" :value="host.id">{{ hostLabel(host) }}</a-option>
                </a-select>
                <a-textarea v-else-if="variable.widget === 'textarea'" v-model="form.variableValues[variable.key]" :disabled="readonly" :placeholder="variable.placeholder || variable.description || variable.key" :auto-size="{ minRows: 2, maxRows: 4 }" />
                <a-input v-else v-model="form.variableValues[variable.key]" :disabled="readonly" :placeholder="variable.placeholder || variable.description || variable.key" />
              </div>
            </div>
          </section>
        </a-form>
        <template v-else>
          <a-empty v-if="schedules.length === 0" description="当前模板没有定时调度" />
          <a-table v-else row-key="id" class="schedule-table" :columns="scheduleColumns" :data="schedules" :pagination="false" :scroll="{ x: 560 }">
            <template #rule="{ record }"><div class="schedule-rule-cell"><strong>{{ record.name }}</strong><span>{{ record.cron_expression }} / {{ record.timezone }}</span><small>最近启动：{{ recentRunText(record) }}</small></div></template>
            <template #inputs="{ record }"><span>{{ formatInputSummary(record.inputs) }}</span></template>
            <template #status="{ record }"><a-tag :color="record.is_active ? 'green' : 'gray'">{{ record.is_active ? '启用' : '停用' }}</a-tag></template>
            <template #actions="{ record }"><a-space v-if="!readonly" :size="2"><a-tooltip content="编辑"><a-button type="text" size="mini" aria-label="编辑调度" @click="startEdit(record)"><template #icon><icon-edit /></template></a-button></a-tooltip><a-tooltip :content="record.is_active ? '停用' : '启用'"><a-button type="text" size="mini" :aria-label="record.is_active ? '停用调度' : '启用调度'" @click="toggleSchedule(record)"><template #icon><icon-pause v-if="record.is_active" /><icon-play-arrow v-else /></template></a-button></a-tooltip><a-tooltip content="删除"><a-button type="text" status="danger" size="mini" aria-label="删除调度" @click="confirmDelete(record)"><template #icon><icon-delete /></template></a-button></a-tooltip></a-space><span v-else class="schedule-readonly">只读</span></template>
          </a-table>
        </template>
      </a-spin>
    </section>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { flowApi, hostApi } from '@/api/ops'
import type { FlowSchedule, FlowTemplate } from '@/types'
import { buildScheduledInputs, flowVariableReference, normalizeFlowVariables } from '../flowUtils'

const props = withDefaults(defineProps<{ visible: boolean; template: FlowTemplate | null; readonly?: boolean }>(), { readonly: false })
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()
const drawerWidth = computed(() => window.innerWidth < 760 ? '100vw' : '640px')
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const hostsLoading = ref(false)
const schedules = ref<FlowSchedule[]>([])
const hostOptions = ref<any[]>([])
const scheduleHistories = ref<Record<number, any[]>>({})
const opaqueSecretInputs = ref<Record<string, any>>({})
const form = reactive({ id: null as number | null, name: '', cron_expression: '0 2 * * *', timezone: 'Asia/Shanghai', is_active: true, variableValues: {} as Record<string, any> })
const variableDefinitions = computed(() => normalizeFlowVariables(props.template?.variables || {}))
const scheduleColumns = [{ title: '调度规则', key: 'rule', slotName: 'rule', minWidth: 250 }, { title: '预置变量', key: 'inputs', slotName: 'inputs', width: 100 }, { title: '状态', key: 'status', slotName: 'status', width: 82 }, { title: '操作', key: 'actions', slotName: 'actions', width: 112, fixed: 'right' }]
const normalizeList = <T,>(value: any): T[] => Array.isArray(value) ? value : value?.results || value?.data || []
const hostLabel = (host: any) => [host.name, host.internal_ip || host.public_ip].filter(Boolean).join(' / ')
const formatInputSummary = (inputs: Record<string, any> = {}) => Object.keys(inputs || {}).length ? `已配置 ${Object.keys(inputs).length} 个变量` : '模板默认值'

const recentRunText = (schedule: FlowSchedule) => {
  const run = scheduleHistories.value[schedule.id]?.[0]
  if (!run) return '暂无'
  return run.flow_run_id ? `${run.status} / 实例 #${run.flow_run_id}` : run.status
}
const loadSchedules = async () => {
  if (!props.template?.id) return
  loading.value = true
  try {
    schedules.value = normalizeList<FlowSchedule>(await flowApi.getSchedules({ template: props.template.id }))
    scheduleHistories.value = Object.fromEntries(await Promise.all(schedules.value.map(async schedule => [schedule.id, await flowApi.getScheduleRuns(schedule.id)])))
  }
  catch (error) { console.error('加载流水线定时调度失败:', error); Message.error('加载流水线定时调度失败') }
  finally { loading.value = false }
}
const loadHosts = async () => {
  if (hostOptions.value.length || !variableDefinitions.value.some(variable => variable.widget === 'host_list')) return
  hostsLoading.value = true
  try { const response = await hostApi.getHosts({ page: 1, page_size: 500 }); hostOptions.value = response.results || [] }
  catch (error) { console.error('加载可选主机失败:', error); Message.error('加载可选主机失败') }
  finally { hostsLoading.value = false }
}
const resetForm = (schedule?: FlowSchedule) => {
  form.id = schedule?.id || null; form.name = schedule?.name || ''; form.cron_expression = schedule?.cron_expression || '0 2 * * *'; form.timezone = schedule?.timezone || 'Asia/Shanghai'; form.is_active = schedule?.is_active ?? true
  const values = { ...(schedule?.inputs || {}) }; opaqueSecretInputs.value = {}
  variableDefinitions.value.filter(variable => variable.type === 'secret').forEach(variable => { if (Object.prototype.hasOwnProperty.call(values, variable.key)) opaqueSecretInputs.value[variable.key] = values[variable.key]; delete values[variable.key] })
  form.variableValues = values
}
const startCreate = async () => { resetForm(); editing.value = true; await loadHosts() }
const startEdit = async (schedule: FlowSchedule) => { resetForm(schedule); editing.value = true; await loadHosts() }
const closeEditor = () => { editing.value = false; resetForm() }
const schedulePayload = () => ({ name: form.name.trim(), template: props.template!.id!, cron_expression: form.cron_expression.trim(), timezone: form.timezone, is_active: form.is_active, inputs: { ...buildScheduledInputs(variableDefinitions.value, form.variableValues), ...opaqueSecretInputs.value } })
const saveSchedule = async () => {
  if (!props.template?.id || !form.name.trim() || !form.cron_expression.trim()) { Message.warning('请填写调度名称和 Cron 表达式'); return }
  saving.value = true
  try { if (form.id) await flowApi.updateSchedule(form.id, schedulePayload()); else await flowApi.createSchedule(schedulePayload()); Message.success('定时调度已保存'); editing.value = false; await loadSchedules() }
  catch (error) { console.error('保存流水线定时调度失败:', error); Message.error('保存失败，请检查 Cron 表达式和变量输入') }
  finally { saving.value = false }
}
const toggleSchedule = async (schedule: FlowSchedule) => {
  try { await flowApi.updateSchedule(schedule.id, { name: schedule.name, template: schedule.template, cron_expression: schedule.cron_expression, timezone: schedule.timezone, inputs: schedule.inputs || {}, is_active: !schedule.is_active }); await loadSchedules() }
  catch (error) { console.error('更新流水线定时调度状态失败:', error); Message.error('更新调度状态失败') }
}
const confirmDelete = (schedule: FlowSchedule) => Modal.warning({ title: '删除定时调度', content: `确认删除“${schedule.name}”？`, hideCancel: false, onOk: async () => { await flowApi.deleteSchedule(schedule.id); Message.success('定时调度已删除'); await loadSchedules() } })
watch(() => [props.visible, props.template?.id], ([visible]) => { if (!visible) return; editing.value = false; resetForm(); loadSchedules() })
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
.schedule-form :deep(.arco-form-item) { margin-bottom: 10px; }
.schedule-inputs { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--app-border); }
.schedule-variable-list { display: grid; gap: 10px; }
.schedule-variable-row { display: grid; grid-template-columns: minmax(160px, .45fr) minmax(0, 1fr); gap: 10px; align-items: start; }
.schedule-variable-row__label { display: grid; gap: 2px; padding-top: 5px; min-width: 0; }
.schedule-variable-row__label strong, .schedule-variable-row__label span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.schedule-variable-row__label strong { color: var(--app-fg); font-size: 13px; }
.schedule-variable-row__label span, .schedule-rule-cell small { color: var(--app-muted); font-size: 12px; }`r`n.schedule-rule-cell span { color: var(--app-muted); font-family: var(--app-mono); font-size: 12px; }
.schedule-variable-row__secret { padding-top: 7px; color: var(--app-muted); font-size: 13px; }
.schedule-rule-cell strong { overflow: hidden; color: var(--app-fg); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.schedule-readonly { color: var(--app-muted); font-size: 12px; }
@media (max-width: 600px) { .schedule-form__row, .schedule-variable-row { grid-template-columns: 1fr; } }
</style>