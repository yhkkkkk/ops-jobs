<template>
  <div class="variable-editor">
    <div class="section-header">
      <div class="title">自定义变量</div>
      <n-button type="primary" size="small" @click="addVariable">新增变量</n-button>
    </div>

    <n-empty v-if="variablesList.length === 0" description="暂无变量，点击新增">
      <n-button type="primary" size="small" @click="addVariable">
        <template #icon><Plus  /></template>
        新增变量
      </n-button>
    </n-empty>

    <div v-else class="vars-list">
      <div
        v-for="(item, idx) in variablesList"
        :key="item.id"
        class="var-row"
      >
        <div class="form-grid-row" :gutter="12" align="center">
          <div class="form-grid-col" style="grid-column: span 5">
            <n-input
              v-model:value="item.name"
              placeholder="名称"
              clearable
              @blur="emitChange"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 7">
            <n-input
              v-if="item.type !== 'host_list'"
              v-model:value="item.value"
              :type="item.type === 'secret' && !item.show ? 'password' : 'text'"
              :placeholder="item.type === 'secret' ? '密文值' : '值'"
              clearable
              @update:value="emitChange"
            />
            <div v-else class="host-var-compact">
              <span class="host-var-count">{{ item.hostList?.length || 0 }} 台主机</span>
              <n-button secondary size="small" @click="openHostSelector(item)">选择主机</n-button>
            </div>
          </div>
          <div class="form-grid-col" style="grid-column: span 3">
            <n-select v-model:value="item.type" @update:value="emitChange" placeholder="类型" :options="selectOptions1" />
          </div>
          <div class="form-grid-col" style="grid-column: span 3">
            <n-checkbox v-model:checked="item.required" @update:checked="emitChange" class="no-wrap">必填</n-checkbox>
          </div>
          <div class="form-grid-col" style="grid-column: span 4">
            <n-checkbox-group
              v-model:value="item.injectInto"
              :options="injectOptions"
              @update:value="emitChange"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 2">
            <n-space :size="4">
              <n-button
                v-if="item.type === 'secret'"
                text
                size="small"
                @click="item.show = !item.show"
              >
                <template #icon>
                  <Eye v-if="item.show" />
                  <EyeOff v-else />
                </template>
              </n-button>
              <n-button type="error" size="small" @click="remove(idx)">
                <template #icon><Trash2 /></template>
              </n-button>
            </n-space>
          </div>
        </div>
        <div v-if="item.type === 'host_list' && item.hostList?.length" class="host-var-actions-row">
          <n-button text size="tiny" @click="copyHostIps(item)">复制IP</n-button>
          <n-button text size="tiny" @click="fillAllHosts(item)">填充全部主机</n-button>
          <n-button text size="tiny" @click="clearHostList(item)">清空</n-button>
        </div>
        <div class="form-grid-row" style="margin-top: 6px">
          <div class="form-grid-col" style="grid-column: span 16">
            <n-input
              v-model:value="item.description"
              placeholder="描述（可选）"
              clearable
              @update:value="emitChange"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="system-vars">
      <div class="section-header">
        <div class="title">系统变量（只读）</div>
      </div>
      <template v-if="displaySystemVars.length">
        <div class="sys-list">
          <div v-for="item in displaySystemVars" :key="item.name" class="sys-row">
            <span class="sys-name">{{ item.name }}</span>
            <span class="sys-desc">{{ item.description }}</span>
          </div>
        </div>
      </template>
      <n-empty v-else description="暂无系统变量" />
    </div>

    <!-- 主机选择器弹窗（用于 host_list 变量） -->
    <HostSelector
      v-model:visible="hostSelectorVisible"
      :hosts="hosts"
      :groups="hostGroups"
      :selected-hosts="(currentHostVar?.hostList || []) as any"
      :selected-groups="[]"
      :host-pagination="hostPagination"
      :enable-host-pagination="false"
      show-preview
      show-copy
      @confirm="handleHostSelectConfirm"
      @host-page-change="handleHostPageChange"
      @host-page-size-change="handleHostPageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, onMounted } from 'vue'
import HostSelector from '@/components/HostSelector.vue'
import { hostApi, hostGroupApi } from '@/api/ops'
import { NButton, NCheckbox, NCheckboxGroup, NEmpty, NInput, NSelect, useMessage } from 'naive-ui'
import { Eye, EyeOff, Plus, Trash2 } from 'lucide-vue-next'

interface VariableItem {
  id: string
  name: string
  value: any
  hostList?: (string | number)[]
  type: 'text' | 'secret' | 'host_list'
  required: boolean
  description?: string
  injectInto: string[]
  show?: boolean
}

interface SystemVar {
  name: string
  description?: string
}

const defaultSystemVars: SystemVar[] = [
  { name: '{{ SYS.JOB_ID }}', description: '执行记录ID' },
  { name: '{{ SYS.TEMPLATE_ID }}', description: '作业模板ID' },
  { name: '{{ SYS.PLAN_ID }}', description: '执行方案ID' },
  { name: '{{ SYS.STEP_ID }}', description: '步骤ID' },
  { name: '{{ SYS.EXECUTOR }}', description: '执行人用户名' },
  { name: '{{ SYS.EXECUTE_AT }}', description: '执行时间(ISO)' },
  { name: '{{ SYS.TARGET_IPS }}', description: '目标主机IP列表' },
  { name: '{{ SYS.TARGET_COUNT }}', description: '目标主机数量' },
  { name: '{{ SYS.BATCH_ID }}', description: '批次ID（滚动执行）' },
]

const message = useMessage()
const props = defineProps<{
  modelValue: Record<string, any> | undefined
  systemVars?: SystemVar[]
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: Record<string, any>): void
}>()

const injectOptions = [
  { label: '脚本', value: 'script' },
  { label: '步骤参数', value: 'step_params' },
  { label: '文件', value: 'file_sources' },
]

const variablesList = reactive<VariableItem[]>([])
let internalUpdate = false
const hostSelectorVisible = ref(false)
const hosts = ref<any[]>([])
const hostGroups = ref<any[]>([])
const hostPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  pageSizeOptions: ['10']
})
const currentHostVar = ref<VariableItem | null>(null)
// 使用 Map 追踪当前编辑的变量，key 是变量的 name，value 是变量对象
const editingVarMap = new Map<string, VariableItem>()
const allHostsLoaded = ref(false)

const displaySystemVars = computed<SystemVar[]>(() => {
  if (props.systemVars && props.systemVars.length) return props.systemVars
  return defaultSystemVars
})

const syncFromModel = () => {
  if (internalUpdate) return
  
  // 保存当前正在编辑的变量的 hostList 数据
  // 使用变量名称作为 key，这样即使 ID 变化也能找到对应的数据
  const preservedHostLists = new Map<string, (string | number)[]>()
  for (const item of variablesList) {
    if (item.name?.trim() && item.type === 'host_list' && item.hostList?.length) {
      preservedHostLists.set(item.name.trim(), [...item.hostList])
    }
  }
  
  variablesList.splice(0, variablesList.length)
  const raw = props.modelValue || {}
  Object.entries(raw).forEach(([name, meta]) => {
    const v = (meta as any) || {}
    const type = (v.type as any) === 'secret'
      ? 'secret'
      : (v.type as any) === 'host_list'
        ? 'host_list'
        : 'text'
    
    // 优先使用 modelValue 中的数据，其次使用保留的数据
    let hostListVal: (string | number)[] | undefined
    if (type === 'host_list') {
      if (Array.isArray(v.value) && v.value.length > 0) {
        hostListVal = v.value
      } else if (preservedHostLists.has(name)) {
        hostListVal = preservedHostLists.get(name)
      } else {
        hostListVal = []
      }
    }
    
    const newItem: VariableItem = {
      id: `${name}-${Math.random().toString(16).slice(2, 6)}`,
      name,
      value: type === 'host_list' ? '' : (v.value ?? ''),
      hostList: hostListVal,
      type,
      required: !!v.required,
      description: v.description || '',
      injectInto: Array.isArray(v.inject_into) && v.inject_into.length ? v.inject_into : ['script', 'step_params', 'file_sources'],
      show: false,
    }
    variablesList.push(newItem)
    
    // 更新 Map 中的引用
    editingVarMap.set(name, newItem)
  })
}

watch(
  () => props.modelValue,
  () => syncFromModel(),
  { immediate: true }
)

const fetchAllHosts = async (force = false) => {
  if (allHostsLoaded.value && !force) return
  hostPagination.value.pageSize = 10
  const pageSize = 500
  const all: any[] = []
  let page = 1
  let total = 0

  while (true) {
    const resp = await hostApi.getHosts({ page, page_size: pageSize })
    const results = resp.results || []
    if (page === 1) {
      total = resp.total || 0
    }
    all.push(...results)
    if (all.length >= total || results.length === 0) {
      break
    }
    page += 1
  }

  hosts.value = all
  hostPagination.value.total = total || all.length
  allHostsLoaded.value = true
}

const ensureHostsLoaded = async (force = false) => {
  if (!allHostsLoaded.value || force) {
    await fetchAllHosts(force)
  }
  if (hostGroups.value.length === 0) {
    const resp = await hostGroupApi.getGroups({ page_size: 200 })
    hostGroups.value = resp.results || []
  }
}

const fetchHosts = async () => {
  await fetchAllHosts()
}

const handleHostPageChange = (page: number) => {
  hostPagination.value.current = page
}

const handleHostPageSizeChange = (pageSize: number) => {
  hostPagination.value.pageSize = 10
  hostPagination.value.current = 1
}

onMounted(() => {
  syncFromModel()
  void ensureHostsLoaded()
})

const emitChange = () => {
  // 去除空名或重复名
  const cleaned: Record<string, any> = {}
  for (const item of variablesList) {
    const name = (item.name || '').trim()
    if (!name) continue // 空行保留在 UI，但不写回 model
    if (cleaned[name]) {
      message.warning(`变量 ${name} 重复，已忽略后者`)
      continue
    }
    if (item.type === 'host_list') {
      const list = (item.hostList || []).filter(v => v !== '' && v !== null && v !== undefined)
      cleaned[name] = {
        value: list.map(v => {
          const num = Number(v)
          return Number.isFinite(num) ? num : v
        }),
        type: 'host_list',
        required: item.required,
        description: item.description,
        inject_into: ['step_params'],
      }
      continue
    }
    cleaned[name] = {
      value: item.value,
      type: item.type,
      required: item.required,
      description: item.description,
      inject_into: item.injectInto.length ? item.injectInto : ['script', 'step_params', 'file_sources'],
    }
  }
  emit('update:modelValue', cleaned)
  internalUpdate = true
  // 让父组件 v-model 更新但不重置本地未命名项
  requestAnimationFrame(() => {
    internalUpdate = false
  })
}

const addVariable = () => {
  variablesList.push({
    id: Math.random().toString(16).slice(2),
    name: '',
    value: '',
    hostList: [],
    type: 'text',
    required: false,
    description: '',
    injectInto: ['script', 'step_params', 'file_sources'],
    show: false,
  })
}

const remove = (idx: number) => {
  variablesList.splice(idx, 1)
  emitChange()
}

const clearHostList = (item: VariableItem) => {
  item.hostList = []
  emitChange()
}

const copyHostIps = async (item: VariableItem) => {
  const ids = item.hostList || []
  if (!ids.length) {
    message.info('暂无主机可复制')
    return
  }
  // 将已加载主机的 IP 拼接（不包含端口），找不到的用ID占位
  const ipList = ids.map(id => {
    const h = hosts.value.find((x: any) => x.id === id)
    if (h) {
      // 只取IP部分，不包含端口
      return h.ip_address ? h.ip_address.split(':')[0] : String(id)
    }
    return String(id)
  })
  try {
    await navigator.clipboard.writeText(ipList.join('\n'))
    message.success('已复制主机IP')
  } catch (e) {
    message.warning('复制失败，请手动选择文本')
  }
}

const openHostSelector = async (item: VariableItem) => {
  await ensureHostsLoaded(true)
  // 确保变量名称存在
  const varName = (item.name || '').trim()
  if (!varName) {
    message.warning('请先填写变量名称')
    return
  }
  // 更新 Map 中的引用
  editingVarMap.set(varName, item)
  currentHostVar.value = item
  hostSelectorVisible.value = true
}

const fillAllHosts = async (item: VariableItem) => {
  await ensureHostsLoaded(true)
  if (!hosts.value.length) {
    message.info('暂无主机可填充')
    return
  }
  item.hostList = hosts.value.map((host: any) => host.id)
  emitChange()
}

const handleHostSelectConfirm = (payload: { hosts?: any[], groups?: number[] }) => {
  if (!currentHostVar.value) {
    hostSelectorVisible.value = false
    return
  }
  
  // 检查变量名称是否存在
  const varName = (currentHostVar.value.name || '').trim()
  if (!varName) {
    message.warning('请先填写变量名称')
    return
  }
  
  // HostSelector emit 的是 { hosts, groups }，需要提取主机ID
  const hosts = payload.hosts || []
  const hostIds = hosts.map((h: any) => h.id)
  
  currentHostVar.value.hostList = hostIds as any
  
  // 同时更新 Map 中的引用，确保数据不会丢失
  editingVarMap.set(varName, currentHostVar.value)
  
  emitChange()
  hostSelectorVisible.value = false
}

// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: '文本', value: 'text' }, { label: '密文', value: 'secret' }, { label: '主机列表', value: 'host_list' }]
</script>

<style scoped>
.variable-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  font-weight: 600;
  font-size: 14px;
}
.vars-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.var-row {
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}
.actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}
.system-vars {
  margin-top: 16px;
}
.sys-name {
  font-family: 'Courier New', monospace;
  display: inline-block;
  min-width: 140px;
  color: var(--app-fg);
}
.sys-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}
.sys-row {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface-muted);
}
.sys-desc {
  color: var(--app-fg-secondary);
  font-size: 12px;
}

.host-var-compact {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.host-var-count {
  color: var(--app-muted);
  font-size: 12px;
  white-space: nowrap;
}
.host-var-actions-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 6px;
  padding-left: 2px;
}
.no-wrap {
  white-space: nowrap;
}
</style>
