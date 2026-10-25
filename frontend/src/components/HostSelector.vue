<template>
  <n-modal
    v-model:show="visible"
    preset="dialog"
    :show-icon="false"
    title="选择执行目标"
    :style="{ width: '1400px' }"
    :mask-closable="false"
    positive-text="确定"
    negative-text="取消"
    class="host-selector-modal"
    @positive-click="handleConfirm"
    @negative-click="handleCancel"
  >
    <div class="host-selector">
      <!-- 左侧：Tab内容区域 -->
      <div class="selector-main">
        <!-- Tab切换：静态选择 / 动态选择 / 主机解析 -->
        <n-tabs v-model:value="selectionMode" type="line" class="selection-mode-tabs">
          <n-tab-pane name="static" tab="静态选择">
            <div class="static-selection-container">
              <!-- 左侧：主机分组树 -->
              <div class="groups-panel">
                <div class="panel-header">
                  <h4>主机分组</h4>
                  <span class="group-count">{{ groups.length }}个分组</span>
                </div>
                <div class="search-container">
                  <n-input
                    :value="groupSearchText"
                    placeholder="搜索分组名称"
                    size="small"
                    clearable
                    @update:value="handleGroupSearchInput"
                  />
                </div>
                <div class="groups-tree-container">
                  <n-tree
                    :data="treeData"
                    label-field="title"
                    key-field="key"
                    :expanded-keys="expandedKeys"
                    :selected-keys="activeGroupKeys"
                    :block-node="true"
                    :selectable="true"
                    size="small"
                    class="groups-tree"
                    :render-label="renderStaticTreeLabel"
                    @update:expanded-keys="handleTreeExpand"
                    @update:selected-keys="handleStaticGroupFocus"
                  />
                </div>
              </div>

              <!-- 中间：主机列表 -->
              <div class="hosts-panel">
                <div class="panel-header">
                  <div class="panel-header-left">
                    <h4>主机列表</h4>
                    <span class="host-count">
                      {{ filteredHosts.length }} 台主机
                      <template v-if="focusedGroupId != null">
                        · {{ getGroupName(focusedGroupId) }}
                      </template>
                      <template v-if="selectedHostIds.length > 0">
                        · 已选 {{ selectedHostIds.length }}
                      </template>
                    </span>
                  </div>
                  <n-button v-if="focusedGroupId != null" size="tiny" text @click="clearGroupFocus">
                    查看全部
                  </n-button>
                </div>
                <div class="search-container">
                  <n-input
                    :value="displayHostSearchText"
                    type="textarea"
                    placeholder="支持多IP搜索：IPv4 / IPv6 / 主机名称 / OS 名称，可直接粘贴多行IP"
                    size="small"
                    clearable
                    :autosize="{ minRows: 1, maxRows: 4 }"
                    style="width: 100%"
                    @update:value="handleHostSearchInput"
                    @clear="handleHostSearchClear"
                    @keydown.enter="handleHostSearch"
                    @paste.capture="handleHostSearchPaste"
                  />
                </div>
                <div class="action-buttons">
                  <n-button size="small" @click="selectAllHosts">
                    <template #icon><CheckSquare :size="14" /></template>
                    全选
                  </n-button>
                  <n-button size="small" @click="selectOnlineHosts">
                    <template #icon><Wifi :size="14" /></template>
                    仅在线
                  </n-button>
                  <n-button size="small" @click="selectAgentOnlineHosts">
                    <template #icon><Cloud :size="14" /></template>
                    仅agent在线
                  </n-button>
                  <n-button size="small" @click="clearHostSelection">
                    <template #icon><CircleX :size="14" /></template>
                    清空
                  </n-button>
                </div>
                <n-data-table
                  :data="filteredHosts"
                  :pagination="hostTablePagination"
                  :checked-row-keys="selectedHostIds"
                  :row-key="(row: any) => row.id"
                  :columns="hostTableColumns"
                  :row-props="hostRowProps"
                  size="small"
                  class="hosts-table"
                  @update:checked-row-keys="handleSelectionChange"
                />
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="dynamic" tab="动态选择">
            <!-- 动态选择：只选择分组，执行时动态获取分组内的所有主机 -->
            <div class="dynamic-selection-container">
              <div class="panel-header">
                <h4>动态选择分组</h4>
                <span class="group-count">{{ dynamicSelectedGroupIds.length }} 个分组</span>
              </div>

              <div class="dynamic-selection-help">
                <n-alert type="info" title="动态选择说明">
                  <div>• 动态选择分组后，执行时会自动获取分组内的所有主机</div>
                  <div>• 分组内主机数量变化时，会自动包含新增的主机</div>
                  <div>• 适合需要动态包含分组内所有主机的场景</div>
                </n-alert>
              </div>

              <!-- 分组搜索 -->
              <div class="search-container">
                <n-input
                  :value="dynamicGroupSearchText"
                  placeholder="搜索分组名称"
                  size="small"
                  clearable
                  @update:value="handleDynamicGroupSearchInput"
                />
              </div>

              <!-- 分组树（只显示分组，不显示主机） -->
              <div class="groups-tree-container dynamic-groups-tree">
                <n-tree
                  :data="dynamicTreeData"
                  label-field="title"
                  :expanded-keys="expandedKeys"
                  :selected-keys="dynamicSelectedGroupIds"
                  :block-node="true"
                  size="small"
                  class="groups-tree"
                  :render-label="renderDynamicTreeLabel"
                  @update:expanded-keys="handleTreeExpand"
                />
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="resolve" tab="主机解析">
            <!-- 主机解析：通过输入IP/主机名列表解析并选择主机 -->
            <div class="resolve-panel">
              <div class="panel-header">
                <h4>主机解析</h4>
              </div>

              <div class="resolve-help">
                <n-alert type="info" title="主机解析说明">
                  <div>• 支持多种输入格式：IP 地址、主机名、多行文本</div>
                  <div>• 解析成功后会自动添加到目标主机列表</div>
                  <div>• 可以与静态选择、动态选择同时使用</div>
                </n-alert>
              </div>

              <div class="resolve-input-container">
                <n-input
                  :value="resolveInputText"
                  type="textarea"
                  placeholder="请输入IP地址或主机名，每行一个，支持逗号分隔&#10;示例：&#10;192.168.1.1&#10;192.168.1.2&#10;web-01.example.com"
                  size="large"
                  clearable
                  :autosize="{ minRows: 6, maxRows: 10 }"
                  style="width: 100%; font-family: 'Courier New', monospace;"
                  @update:value="(v: string) => resolveInputText = v"
                />
              </div>

              <div class="resolve-actions">
                <n-space :size="8">
                  <n-button type="primary" :loading="parsingHosts" @click="handleParseHosts">
                    <template #icon><Search :size="14" /></template>
                    解析主机
                  </n-button>
                  <n-button @click="resolveInputText = ''">
                    <template #icon><Trash2 :size="14" /></template>
                    清空
                  </n-button>
                </n-space>
              </div>

              <!-- 解析结果 -->
              <div v-if="resolvedHosts.length > 0" class="resolved-results">
                <div class="resolved-header">
                  <div class="resolved-title">
                    <CircleCheck :size="16" style="color: #16a34a; margin-right: 4px;" />
                    <span>解析成功：{{ resolvedHosts.length }} 台主机</span>
                  </div>
                  <div class="resolved-actions">
                    <n-button size="small" text @click="clearResolvedHosts">
                      <template #icon><Trash2 :size="14" /></template>
                      清空结果
                    </n-button>
                  </div>
                </div>
              </div>

              <!-- 解析结果表格（只读展示） -->
              <div v-if="resolvedHosts.length > 0" class="resolved-hosts-table">
                <n-data-table
                  :data="resolvedHosts"
                  :pagination="resolvedTablePagination"
                  :checked-row-keys="resolvedSelectedHostIds"
                  :row-key="(row: any) => row.id"
                  :columns="resolvedTableColumns"
                  size="small"
                  @update:checked-row-keys="(keys: any[]) => resolvedSelectedHostIds = keys"
                />
              </div>
            </div>
          </n-tab-pane>
        </n-tabs>
      </div>

      <!-- 右侧：结果预览（始终可见） -->
      <div class="preview-panel">
        <div class="preview-header">
          <div class="preview-title">结果预览</div>
          <div class="preview-count">
            静态 {{ totalStaticHosts }} 台
            <template v-if="dynamicSelectedGroupIds.length > 0">
              | 动态 {{ dynamicSelectedGroupIds.length }} 分组
            </template>
            <template v-if="resolvedHosts.filter(h => h.source === 'matched').length > 0">
              | 解析 {{ resolvedHosts.filter(h => h.source === 'matched').length }} 台
            </template>
          </div>
        </div>
        <div class="preview-actions">
          <n-button size="small" secondary @click="copySelectedIps" :disabled="!hasAnySelection">复制IP</n-button>
          <n-button size="small" text type="error" @click="clearAllSelection" :disabled="!hasAnySelection">清空</n-button>
        </div>
        <div class="preview-list scrollable">
          <!-- 动态选择分组预览 -->
          <div v-if="dynamicSelectedGroupIds.length > 0" class="preview-section preview-dynamic">
            <div class="preview-section-header">
              <Folder class="preview-section-icon" :size="14" />
              <span>动态分组 ({{ dynamicSelectedGroupIds.length }})</span>
              <n-button size="tiny" text type="error" @click="clearDynamicGroups">清空</n-button>
            </div>
            <div class="preview-groups">
              <div
                v-for="groupId in dynamicSelectedGroupIds"
                :key="`preview-group-${groupId}`"
                class="preview-group-item"
              >
                <div class="previewgroup-info">
                  <span class="preview-group-name">{{ getGroupName(groupId) }}</span>
                  <span class="preview-group-count">{{ getGroupHostCount(groupId) }} 台</span>
                </div>
                <n-button size="tiny" text type="error" @click="removeDynamicGroup(groupId)">
                  <template #icon><X :size="12" /></template>
                </n-button>
              </div>
            </div>
          </div>

          <!-- 解析结果预览 -->
          <div v-if="resolvedMatchedHosts.length > 0" class="preview-section preview-resolved">
            <div class="preview-section-header">
              <Search class="preview-section-icon" :size="14" />
              <span>解析主机 ({{ resolvedMatchedHosts.length }})</span>
              <n-button size="tiny" text type="error" @click="clearResolvedHosts">清空</n-button>
            </div>
            <div class="preview-chips">
              <div
                v-for="host in resolvedMatchedHosts"
                :key="host.id"
                class="preview-ip"
              >
                <span class="preview-ip-text">{{ getHostDisplayIp(host) }}</span>
                <span class="preview-ip-actions">
                  <n-button size="tiny" text @click.stop="copySingleIp(host)">复制</n-button>
                  <n-button size="tiny" text type="error" @click.stop="removeResolvedHost(host.id)">删除</n-button>
                </span>
              </div>
            </div>
          </div>

          <!-- 静态选择主机预览 -->
          <div v-if="!hasAnySelection" class="preview-empty">
            暂无数据，请从左侧选择主机或分组
          </div>
          <div v-else-if="selectedHostIds.length > 0" class="preview-section preview-static">
            <div class="preview-section-header">
              <Monitor class="preview-section-icon" :size="14" />
              <span>静态主机 ({{ selectedHostIds.length }})</span>
            </div>
            <div class="preview-chips">
              <div
                v-for="host in selectedHostObjects"
                :key="host.id"
                class="preview-ip"
              >
                <span class="preview-ip-text">{{ getHostDisplayIp(host) }}</span>
                <span class="preview-ip-actions">
                  <n-button size="tiny" text @click.stop="copySingleIp(host)">复制</n-button>
                  <n-button size="tiny" text type="error" @click.stop="removeSingleHost(host.id)">删除</n-button>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, h, type Ref, type PropType } from 'vue'
import { NAlert, NButton, NDataTable, NInput, NModal, NSpace, NTabPane, NTabs, NTag, NTree, useMessage, type DataTableColumns } from 'naive-ui'
import type { Host, HostGroup } from '@/types'
import {
  CheckSquare,
  CircleCheck,
  CircleX,
  Cloud,
  Folder,
  Monitor,
  Search,
  Trash2,
  Wifi,
  X
} from 'lucide-vue-next'

const message = useMessage()

// Props
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  hosts: {
    type: Array as PropType<Host[]>,
    default: () => []
  },
  groups: {
    type: Array as PropType<HostGroup[]>,
    default: () => []
  },
  selectedHosts: {
    type: Array as PropType<Host[]>,
    default: () => []
  },
  selectedGroups: {
    type: Array as PropType<HostGroup[]>,
    default: () => []
  },
  // 主机分页配置
  hostPagination: {
    type: Object,
    default: () => ({
      current: 1,
      pageSize: 10,
      total: 0,
      pageSizeOptions: ['10', '20', '50', '100', '200']
    })
  },
  // 是否启用主机分页
  enableHostPagination: {
    type: Boolean,
    default: false
  },
  // 可选：获取全部主机（用于跨页全选/仅在线等操作）
  fetchAllHosts: {
    type: Function as PropType<() => Promise<Host[]>>,
    default: undefined
  }
})

// Emits
const emit = defineEmits(['update:visible', 'confirm', 'hostPageChange', 'hostPageSizeChange'])

// 响应式数据
const visible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 搜索和选择
const groupSearchText = ref('')
const displayHostSearchText = ref('')
const hostSearchText = ref('')
const expandedKeys = ref<Array<string | number>>([])
/** 左侧当前聚焦的分组（过滤中间主机列表）；与「勾选整组」selectedGroupIds 分离 */
const focusedGroupId = ref<number | null>(null)
const activeGroupKeys = computed(() => (focusedGroupId.value != null ? [focusedGroupId.value] : []))
/** 全量主机目录：树/按组过滤用；避免分页列表缺 groups_info 成员 */
const catalogHosts = ref<Host[]>([])

const hostCatalog = computed<Host[]>(() => {
  if (catalogHosts.value.length > 0) return catalogHosts.value
  return (props.hosts as Host[]) || []
})

const ensureHostCatalog = async () => {
  if (!props.visible) return
  if (!props.fetchAllHosts) {
    catalogHosts.value = (props.hosts as Host[]) || []
    return
  }
  try {
    const all = await props.fetchAllHosts()
    if (Array.isArray(all) && all.length > 0) {
      catalogHosts.value = all
    } else {
      catalogHosts.value = (props.hosts as Host[]) || []
    }
  } catch {
    catalogHosts.value = (props.hosts as Host[]) || []
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) void ensureHostCatalog()
  },
  { immediate: true },
)

// 内部选择状态 - 用于静态选择
const internalSelectedHostIds = ref<number[]>([])
const selectedGroupIds = ref<number[]>([])
const selectedHostMap = ref<Record<number, Host>>({})

// 动态选择状态
const dynamicSelectedGroupIds = ref<number[]>([])
const dynamicGroupSearchText = ref('')
const selectionMode = ref('static')  // 'static' | 'dynamic' | 'resolve'

// 同步外部selectedHosts到内部状态
watch(() => props.selectedHosts, (newVal) => {
  if (Array.isArray(newVal)) {
    const normalizedIds = newVal.map((h: any) => {
      if (typeof h === 'object') return h.id
      return h
    }).filter((id: any) => typeof id === 'number')
    internalSelectedHostIds.value = normalizedIds

    const nextMap: Record<number, Host> = { ...selectedHostMap.value }
    newVal.forEach((h: any) => {
      if (h && typeof h === 'object' && typeof h.id === 'number') {
        nextMap[h.id] = h
      }
    })
    Object.keys(nextMap).forEach((id) => {
      const numId = Number(id)
      if (!normalizedIds.includes(numId)) {
        delete nextMap[numId]
      }
    })
    selectedHostMap.value = nextMap
  }
}, { immediate: true, deep: true })

// 同步外部selectedGroups到内部状态
watch(() => props.selectedGroups, (newVal) => {
  if (Array.isArray(newVal)) {
    dynamicSelectedGroupIds.value = newVal.map((g: any) => {
      if (typeof g === 'object') return g.id
      return g
    }).filter((id: any) => typeof id === 'number')
  }
}, { immediate: true, deep: true })

const syncSelectedHostMap = () => {
  const selectedIds = new Set(internalSelectedHostIds.value)
  const nextMap: Record<number, Host> = {}

  Object.entries(selectedHostMap.value).forEach(([id, host]) => {
    const numId = Number(id)
    if (selectedIds.has(numId)) {
      nextMap[numId] = host
    }
  })

  hostCatalog.value.forEach((host: Host) => {
    if (selectedIds.has(host.id)) {
      nextMap[host.id] = host
    }
  })
  ;(props.hosts || []).forEach((host: Host) => {
    if (selectedIds.has(host.id)) {
      nextMap[host.id] = host
    }
  })

  selectedHostMap.value = nextMap
}

watch([internalSelectedHostIds, hostCatalog, () => props.hosts], syncSelectedHostMap, { immediate: true, deep: true })

// 主机解析相关
const resolveInputText = ref('') // 主机解析输入
const resolvedHosts = ref<any[]>([]) // 解析结果列表
const resolvedSelectedHostIds = ref<number[]>([]) // 解析结果中选择的主机ID
const parsingHosts = ref(false) // 解析加载状态

// 主机分页配置（Naive UI n-data-table 分页对象）
const hostTablePagination = computed<any>(() => {
  // 按组过滤时用本地分页（数据来自全量目录）
  if (!props.enableHostPagination || focusedGroupId.value != null) {
    return {
      pageSize: 10,
      showSizePicker: true,
      pageSizes: [10, 20, 50, 100],
      showQuickJumper: true
    }
  }
  const pageSize = 10
  return {
    page: props.hostPagination.current || 1,
    pageSize,
    itemCount: props.hostPagination.total || 0,
    showSizePicker: false,
    showQuickJumper: true,
    onChange: (page: number) => handleHostPageChange(page, pageSize)
  }
})

// 解析结果表格分页（本地分页）
const resolvedTablePagination = {
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  showQuickJumper: true
}

const handleSelectionChange = (keys: any[]) => {
  selectedHostIds.value = Array.isArray(keys) ? keys : []
}

// 处理主机分页变化
const handleHostPageChange = (page: number, pageSize?: number) => {
  emit('hostPageChange', page, pageSize ?? 10)
}

// 处理主机每页数量变化
const handleHostPageSizeChange = (pageSize: number) => {
  emit('hostPageSizeChange', pageSize)
}

// 渲染主机名称单元格
const renderHostNameCell = (row: any) =>
  h('div', { class: 'host-name-cell' }, [
    h('div', { class: 'host-name' }, row.name),
    h('div', { class: 'host-ip' }, getHostDisplayIp(row))
  ])

// 主机列表表格列（Naive UI：必须带 selection 列才有多选框）
const hostTableColumns: DataTableColumns<any> = [
  { type: 'selection', multiple: true },
  { title: '主机名称', key: 'name', width: 160, render: (row) => renderHostNameCell(row) },
  {
    title: 'Agent状态',
    key: 'agent_info',
    width: 100,
    render: (row) => row.agent_info
      ? h('div', { class: 'agent-status-cell' }, [
          h(NTag, { size: 'small', type: getAgentStatusColor(row.agent_info.status), class: 'agent-status-tag' }, {
            icon: () => h('div', { class: `agent-status-dot agent-status-${row.agent_info.status}` }),
            default: () => row.agent_info.status_display
          })
        ])
      : h('span', { class: 'text-gray-400' }, '未安装')
  },
  {
    title: 'OS 名称',
    key: 'os_type',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: row.os_type === 'linux' ? 'success' : 'info' }, { default: () => row.os_type || 'Unknown' })
  },
  {
    title: '主机状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: getHostStatusColor(row.status), class: 'status-tag' }, {
      icon: () => h('div', { class: `status-dot status-${row.status}` }),
      default: () => getHostStatusText(row.status)
    })
  },
  {
    title: '所属分组',
    key: 'groups_info',
    width: 180,
    render: (row) => {
      if (!row.groups_info || row.groups_info.length === 0) {
        return h('span', { class: 'text-gray-400' }, '无分组')
      }
      const tags = row.groups_info.slice(0, 2).map((g: any) =>
        h(NTag, { size: 'small', type: 'primary', class: 'group-tag' }, { default: () => g.name })
      )
      if (row.groups_info.length > 2) {
        tags.push(h(NTag, { size: 'small' }, { default: () => `+${row.groups_info.length - 2}` }))
      }
      return h('div', { class: 'groups-display' }, tags)
    }
  }
]

// 解析结果表格列
const resolvedTableColumns: DataTableColumns<any> = [
  { type: 'selection', multiple: true },
  { title: '主机名称', key: 'name', width: 160, render: (row) => renderHostNameCell(row) },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: getHostStatusColor(row.status) }, { default: () => getHostStatusText(row.status) })
  },
  {
    title: '来源',
    key: 'source',
    width: 120,
    render: (row) => h(NTag, { size: 'small', type: row.source === 'matched' ? 'success' : 'warning' }, { default: () => (row.source === 'matched' ? '已匹配' : '未匹配') })
  }
]

// 行点击切换勾选（蓝鲸式：点行也能选）
const hostRowProps = (row: any) => ({
  style: 'cursor: pointer',
  onClick: (e: MouseEvent) => {
    const target = e.target as HTMLElement | null
    if (target?.closest('.n-checkbox, .n-checkbox-box, button, a')) return
    handleHostsTableRowClick(row)
  },
})

const getSelectedCountInGroup = (groupId: number) => {
  return hostCatalog.value.filter((host: Host) =>
    internalSelectedHostIds.value.includes(host.id)
    && host.groups_info?.some((g) => g.id === groupId)
  ).length
}

// 分组树节点：分组显示已选数；主机叶子显示勾选态
const makeTreeLabelRenderer = (selectedIds: Ref<number[]>, onTitleClick: (option: any) => void) =>
  ({ option }: { option: any }) => {
    const isHost = Boolean(option.isHost) || String(option.key).startsWith('host-')
    if (isHost) {
      const hostId = Number(option.hostId ?? String(option.key).replace(/^host-/, ''))
      const checked = internalSelectedHostIds.value.includes(hostId)
      return h('div', {
        class: ['tree-node-content', 'tree-host-node', { 'node-selected': checked }],
        onClick: (e: MouseEvent) => {
          e.stopPropagation()
          toggleHostSelection(hostId, option as Host)
        },
      }, [
        h('span', { class: ['tree-host-check', { checked }] }, checked ? '✓' : ''),
        h('div', { class: 'node-info' }, [
          h('div', { class: 'node-name' }, option.title || option.name || `主机${hostId}`),
          h('div', { class: 'node-description' }, getHostDisplayIp(option)),
        ]),
      ])
    }

    const groupId = Number(option.key)
    const selectedInGroup = getSelectedCountInGroup(groupId)
    const total = option.host_count || 0
    return h('div', {
      class: ['tree-node-content', {
        'node-selected': selectedIds.value.includes(groupId),
        'node-has-selection': selectedInGroup > 0,
      }],
      onClick: (e: MouseEvent) => {
        e.stopPropagation()
        onTitleClick(option)
      },
    }, [
      h('div', { class: 'node-info' }, [
        h('div', { class: 'node-name' }, option.title || '未知分组'),
        ...(option.description ? [h('div', { class: 'node-description' }, option.description)] : []),
      ]),
      h('div', { class: 'node-stats' }, [
        selectedInGroup > 0
          ? h('div', { class: 'stat-item stat-selected' }, [
              h('span', { class: 'stat-number' }, String(selectedInGroup)),
              h('span', { class: 'stat-label' }, '已选'),
            ])
          : null,
        h('div', { class: 'stat-item' }, [
          h('span', { class: 'stat-number' }, String(option.online_count || 0)),
          h('span', { class: 'stat-label' }, '在线'),
        ]),
        h('div', { class: 'stat-item' }, [
          h('span', { class: 'stat-number' }, String(total)),
          h('span', { class: 'stat-label' }, '总数'),
        ]),
      ].filter(Boolean)),
    ])
  }

// 计算属性
const treeData = computed(() => {
  return (props.groups || [])
    .filter((group: HostGroup) => {
      if (!groupSearchText.value) return true
      return group.name?.toLowerCase().includes(groupSearchText.value.toLowerCase())
    })
    .map((group: HostGroup) => {
      const children = hostCatalog.value
        .filter((host: Host) => {
          if (!groupSearchText.value) return true
          const groupMatch = group.name?.toLowerCase().includes(groupSearchText.value.toLowerCase())
          if (groupMatch) return true
          return host.name?.toLowerCase().includes(groupSearchText.value.toLowerCase()) ||
                 host.ip_address?.includes(groupSearchText.value)
        })
        .filter((host: Host) => {
          if (selectionMode.value === 'dynamic') return false
          return host.groups_info?.some((g) => g.id === group.id)
        })
        .map((host: Host) => ({
          key: `host-${host.id}`,
          title: host.name,
          isLeaf: true,
          isHost: true,
          hostId: host.id,
          prefix: () => h(Monitor),
          parentId: group.id,
          ...host,
        }))
      const selectedInGroup = children.filter((child: any) =>
        internalSelectedHostIds.value.includes(child.hostId)
      ).length
      return {
        key: group.id,
        title: group.name,
        description: group.description,
        // 有已选主机时默认展开，蓝鲸式：分组下能直接看到所选主机
        children,
        prefix: () => h(Folder),
        online_count: group.online_count || 0,
        host_count: group.host_count || (children?.length || 0),
        selected_count: selectedInGroup,
        isGroup: true,
      }
    })
})

// 有已选主机的分组自动展开，便于在树里看到所选主机
watch(
  [internalSelectedHostIds, hostCatalog, () => props.groups],
  () => {
    const needExpand = (props.groups || [])
      .filter((group: HostGroup) => getSelectedCountInGroup(group.id) > 0)
      .map((group: HostGroup) => group.id)
    if (needExpand.length === 0) return
    const set = new Set(expandedKeys.value)
    needExpand.forEach((id) => set.add(id))
    expandedKeys.value = Array.from(set)
  },
  { deep: true },
)

const filterHosts = (list: Host[]) => {
  if (!hostSearchText.value) return list

  // 解析搜索关键词，支持竖线、逗号、空格分隔的多IP搜索
  const searchTerms = hostSearchText.value
    .split(/[|,]/)  // 按竖线或逗号分割
    .map(term => term.trim())
    .filter(term => term.length > 0)

  if (searchTerms.length === 0) return list

  return list.filter((host: Host) => {
    const hostIp = host.ip_address || ''
    const hostName = host.name?.toLowerCase() || ''

    // 只要匹配任何一个搜索词即可
    return searchTerms.some(term => {
      const termLower = term.toLowerCase()
      return hostName.includes(termLower) || hostIp.includes(term)
    })
  })
}

const filteredHosts = computed<Host[]>(() => {
  // 聚焦分组时用全量目录，避免分页页里看不到该组主机
  let list = focusedGroupId.value != null ? hostCatalog.value : ((props.hosts as Host[]) || [])
  if (focusedGroupId.value != null) {
    const gid = focusedGroupId.value
    list = list.filter((host: Host) => host.groups_info?.some((g) => g.id === gid))
  }
  return filterHosts(list)
})

// 使用内部状态的选择主机ID
const selectedHostIds = computed({
  get: () => internalSelectedHostIds.value,
  set: (value: any) => {
    internalSelectedHostIds.value = Array.isArray(value)
      ? value.map((id: any) => Number(id)).filter((id: number) => !Number.isNaN(id))
      : []
  }
})

// 选择的主机对象列表
const selectedHostObjects = computed<{ id: number; ip_address?: string; name?: string }[]>(() => {
  return internalSelectedHostIds.value.map((id) => {
    return selectedHostMap.value[id]
  }).filter((h: Host | undefined): h is Host => !!h)
})

const dynamicTreeData = computed(() => {
  return (props.groups || [])
    .filter((group: HostGroup) => {
      if (!dynamicGroupSearchText.value) return true
      return group.name?.toLowerCase().includes(dynamicGroupSearchText.value.toLowerCase())
    })
    .map((group: HostGroup) => ({
      key: group.id,
      title: group.name,
      description: group.description,
      prefix: () => h(Folder),
      online_count: group.online_count || 0,
      host_count: group.host_count || 0,
      isGroup: true
    }))
})

// 解析结果中已匹配的主机
const resolvedMatchedHosts = computed(() => {
  return resolvedHosts.value.filter((h: any) => h.source === 'matched')
})

// 总静态主机数（包括表格选择的和解析匹配的）
const totalStaticHosts = computed(() => {
  const tableCount = selectedHostIds.value.length
  const resolvedCount = resolvedMatchedHosts.value.length
  return tableCount + resolvedCount
})

// 是否有任何选择
const hasAnySelection = computed(() => {
  return selectedHostIds.value.length > 0 ||
         dynamicSelectedGroupIds.value.length > 0 ||
         resolvedMatchedHosts.value.length > 0
})

// 获取分组名称
const getGroupName = (groupId: number) => {
  const group = (props.groups || []).find((g: HostGroup) => g.id === groupId)
  return group?.name || `分组${groupId}`
}

// 获取分组内主机数量
const getGroupHostCount = (groupId: number) => {
  const group = (props.groups || []).find((g: HostGroup) => g.id === groupId)
  return group?.host_count || 0
}

// 获取分组在线数量
const getGroupOnlineCount = (groupId: number) => {
  const group = (props.groups || []).find((g: HostGroup) => g.id === groupId)
  return group?.online_count || 0
}

// 获取分组Agent在线数量
const getGroupAgentOnlineCount = (groupId: number) => {
  const hosts = (props.hosts || []).filter((h: Host) =>
    h.groups_info?.some((g) => g.id === groupId)
  )
  return hosts.filter((h: Host) => h.agent_info?.status === 'online').length
}

// 获取分组离线数量
const getGroupOfflineCount = (groupId: number) => {
  const hosts = (props.hosts || []).filter((h: Host) =>
    h.groups_info?.some((g) => g.id === groupId)
  )
  return hosts.filter((h: any) => h.status === 'offline').length
}

const formatHostIp = (ip?: string, port?: number) => {
  if (!ip) return ''

  if (typeof port === 'number' && ip.endsWith(`:${port}`)) {
    return ip.slice(0, -(`:${port}`).length)
  }

  if (ip.startsWith('[')) {
    const closeIndex = ip.indexOf(']')
    if (closeIndex > 0) {
      return ip.slice(1, closeIndex)
    }
  }

  const colonCount = (ip.match(/:/g) || []).length
  if (colonCount === 1) {
    const [hostPart, maybePort] = ip.split(':')
    if (/^\d+$/.test(maybePort || '')) {
      return hostPart
    }
  }

  return ip
}

const getHostDisplayIp = (host: any) => {
  return formatHostIp(host?.ip_address, host?.port)
}

// 获取Agent状态颜色
const getAgentStatusColor = (status: string): 'success' | 'error' | 'warning' | 'default' => {
  const colors: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    online: 'success',
    offline: 'error',
    unknown: 'warning'
  }
  return colors[status] || 'default'
}

// 获取主机状态颜色
const getHostStatusColor = (status: string): 'success' | 'error' | 'warning' | 'default' => {
  const colors: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    online: 'success',
    offline: 'error',
    maintenance: 'warning',
    unknown: 'default'
  }
  return colors[status] || 'default'
}

// 获取主机状态文本
const getHostStatusText = (status: string) => {
  const texts: Record<string, string> = {
    online: '在线',
    offline: '离线',
    maintenance: '维护中',
    unknown: '未知'
  }
  return texts[status] || status
}

// 方法
const handleTreeExpand = (keys: Array<string | number>) => {
  expandedKeys.value = keys
}

const handleStaticGroupFocus = (keys: Array<string | number>) => {
  // selected-keys 可能点到 host；只接受分组 id
  const groupKey = keys.find((k) => !String(k).startsWith('host-'))
  if (groupKey == null) return
  const gid = Number(groupKey)
  if (Number.isNaN(gid)) return
  focusedGroupId.value = focusedGroupId.value === gid ? null : gid
}

const clearGroupFocus = () => {
  focusedGroupId.value = null
}

/** 点击分组名：聚焦过滤 + 勾选/取消整组主机（蓝鲸：点拓扑选机器） */
const handleNodeTitleClick = (nodeData: any) => {
  if (nodeData.isHost) return
  const key = parseInt(String(nodeData.key), 10)
  if (Number.isNaN(key)) return

  focusedGroupId.value = key
  if (!expandedKeys.value.includes(key)) {
    expandedKeys.value = [...expandedKeys.value, key]
  }

  const index = selectedGroupIds.value.indexOf(key)
  if (index === -1) {
    selectedGroupIds.value.push(key)
    const groupHosts = hostCatalog.value.filter((h: Host) =>
      h.groups_info?.some((g) => g.id === key)
    )
    upsertSelectedHosts(groupHosts)
  } else {
    selectedGroupIds.value.splice(index, 1)
    const stillSelectedGroups = selectedGroupIds.value
    const groupHosts = hostCatalog.value.filter((h: Host) =>
      h.groups_info?.some((g) => g.id === key)
    )
    groupHosts.forEach((host: Host) => {
      const belongsToOtherGroup = host.groups_info?.some((g) =>
        stillSelectedGroups.includes(g.id)
      )
      if (!belongsToOtherGroup) {
        const idx = internalSelectedHostIds.value.indexOf(host.id)
        if (idx > -1) {
          internalSelectedHostIds.value.splice(idx, 1)
        }
      }
    })
  }
}

const toggleHostSelection = (hostId: number, host?: Host) => {
  const idx = internalSelectedHostIds.value.indexOf(hostId)
  if (idx > -1) {
    internalSelectedHostIds.value.splice(idx, 1)
    return
  }
  internalSelectedHostIds.value.push(hostId)
  if (host && typeof host === 'object') {
    selectedHostMap.value = { ...selectedHostMap.value, [hostId]: host as Host }
  }
}

const handleHostsTableRowClick = (record: any) => {
  if (!record?.id) return
  toggleHostSelection(record.id, record)
}

const handleGroupSearchInput = (value?: string) => {
  groupSearchText.value = String(value ?? '')
}

const handleGroupSearch = () => {
  // 搜索逻辑在computed中处理
}

const handleHostSearchInput = (value?: string) => {
  // 搜索逻辑在 computed 中处理，这里同步受控输入值到 hostSearchText
  if (value !== undefined) {
    displayHostSearchText.value = value
  }
  hostSearchText.value = String(value ?? displayHostSearchText.value).trim()
}

const handleHostSearchClear = () => {
  // 清空搜索时同步更新 hostSearchText
  hostSearchText.value = ''
}

const handleHostSearch = () => {
  hostSearchText.value = displayHostSearchText.value.trim()
}

const handleHostSearchPaste = (event: ClipboardEvent) => {
  const text = event.clipboardData?.getData('text')
  if (text) {
    // 处理多行IP粘贴，转换为竖线分隔格式
    const processedText = text
      .split(/[,，\s\n\r]+/)  // 按逗号、空格、换行符分割
      .map(ip => ip.trim())
      .filter(ip => ip.length > 0)
      .join(' | ')  // 用竖线连接

    // 阻止默认粘贴行为，手动设置处理后的文本
    event.preventDefault()

    // 获取当前光标位置
    const target = event.target as HTMLTextAreaElement
    const start = target.selectionStart
    const end = target.selectionEnd
    const originalValue = displayHostSearchText.value

    // 在光标位置插入处理后的文本
    const newValue = originalValue.substring(0, start) + processedText + originalValue.substring(end)

    // 更新显示和搜索文本
    displayHostSearchText.value = newValue
    hostSearchText.value = newValue
  }
}

const handleDynamicNodeTitleClick = (nodeData: any) => {
  const key = parseInt(nodeData.key)
  const index = dynamicSelectedGroupIds.value.indexOf(key)
  if (index === -1) {
    dynamicSelectedGroupIds.value.push(key)
  } else {
    dynamicSelectedGroupIds.value.splice(index, 1)
  }
}

const renderStaticTreeLabel = makeTreeLabelRenderer(selectedGroupIds, handleNodeTitleClick)
const renderDynamicTreeLabel = makeTreeLabelRenderer(dynamicSelectedGroupIds, handleDynamicNodeTitleClick)

const handleDynamicGroupSearchInput = (value?: string) => {
  dynamicGroupSearchText.value = String(value ?? '')
}

const handleDynamicGroupSearch = () => {
  // 搜索逻辑在computed中处理
}

const resolveActionHosts = async () => {
  if (props.fetchAllHosts) {
    const allHosts = await props.fetchAllHosts()
    if (Array.isArray(allHosts) && allHosts.length > 0) {
      return filterHosts(allHosts)
    }
  }
  return filteredHosts.value
}

const upsertSelectedHosts = (hostsToSelect: Host[]) => {
  const selectedSet = new Set(internalSelectedHostIds.value)
  const nextMap: Record<number, Host> = { ...selectedHostMap.value }

  hostsToSelect.forEach((host: Host) => {
    if (!selectedSet.has(host.id)) {
      internalSelectedHostIds.value.push(host.id)
      selectedSet.add(host.id)
    }
    nextMap[host.id] = host
  })

  selectedHostMap.value = nextMap
}

// 全选
const selectAllHosts = async () => {
  const allHosts = await resolveActionHosts()
  upsertSelectedHosts(allHosts)
}

// 仅选择在线主机
const selectOnlineHosts = async () => {
  const hostList = await resolveActionHosts()
  const onlineHosts = hostList.filter((h: any) => h.status === 'online')
  upsertSelectedHosts(onlineHosts)
}

// 仅选择Agent在线主机
const selectAgentOnlineHosts = async () => {
  const hostList = await resolveActionHosts()
  const agentOnlineHosts = hostList.filter((h: any) => h.agent_info?.status === 'online')
  upsertSelectedHosts(agentOnlineHosts)
}

// 清空主机选择
const clearHostSelection = () => {
  internalSelectedHostIds.value = []
  selectedGroupIds.value = []
  focusedGroupId.value = null
}

// 清空所有选择
const clearAllSelection = () => {
  internalSelectedHostIds.value = []
  selectedGroupIds.value = []
  dynamicSelectedGroupIds.value = []
  resolvedHosts.value = []
}

// 移除单个主机
const removeSingleHost = (hostId: number) => {
  const index = internalSelectedHostIds.value.indexOf(hostId)
  if (index > -1) {
    internalSelectedHostIds.value.splice(index, 1)
  }
}

// 移除动态分组
const removeDynamicGroup = (groupId: number) => {
  const index = dynamicSelectedGroupIds.value.indexOf(groupId)
  if (index > -1) {
    dynamicSelectedGroupIds.value.splice(index, 1)
  }
}

// 清空动态分组
const clearDynamicGroups = () => {
  dynamicSelectedGroupIds.value = []
}

// 复制单个IP（不包含端口）
const copySingleIp = (host: any) => {
  const ip = formatHostIp(host?.ip_address, host?.port)
  if (!ip) {
    message.warning('没有可复制的IP地址')
    return
  }
  navigator.clipboard.writeText(ip)
  message.success(`已复制IP: ${ip}`)
}

// 复制所有选中的IP（不包含端口）
const copySelectedIps = () => {
  const ips: string[] = []

  // 添加表格选择的主机IP（不包含端口）
  selectedHostObjects.value.forEach((h: any) => {
    const ip = formatHostIp(h?.ip_address, h?.port)
    if (ip) {
      if (!ips.includes(ip)) {
        ips.push(ip)
      }
    }
  })

  // 添加解析匹配的主机IP（不包含端口）
  resolvedMatchedHosts.value.forEach((h: any) => {
    const ip = formatHostIp(h?.ip_address, h?.port)
    if (ip) {
      if (!ips.includes(ip)) {
        ips.push(ip)
      }
    }
  })

  if (ips.length > 0) {
    navigator.clipboard.writeText(ips.join('\n'))
    message.success(`已复制 ${ips.length} 个IP地址`)
  } else {
    message.warning('没有可复制的IP地址')
  }
}

// 解析主机
const handleParseHosts = async () => {
  if (!resolveInputText.value.trim()) {
    message.warning('请输入要解析的IP地址或主机名')
    return
  }

  parsingHosts.value = true

  try {
    // 解析输入文本
    const inputText = resolveInputText.value
    const items = inputText.split(/[\n,]/).map(item => item.trim()).filter(item => item)

    const matchedHosts: any[] = []
    const unmatchedItems: string[] = []

    // 在主机列表中查找匹配的主机
    items.forEach(item => {
      const found = (props.hosts || []).find((host: Host) => {
        // 按IP匹配
        if (host.ip_address === item) return true
        // 按名称匹配
        if (host.name?.toLowerCase() === item.toLowerCase()) return true
        // 按IP:port匹配
        if (`${host.ip_address}:${host.port}` === item) return true
        return false
      })

      if (found) {
        matchedHosts.push({
          ...found,
          source: 'matched'
        })
      } else {
        unmatchedItems.push(item)
      }
    })

    // 更新解析结果
    resolvedHosts.value = matchedHosts

    // 同时将匹配的主机添加到已选主机列表
    if (matchedHosts.length > 0) {
      // Emit event to parent to add matched hosts
      message.success(`解析成功：${matchedHosts.length} 台主机已添加到目标列表`)
    }

    if (unmatchedItems.length > 0) {
      message.warning(`未找到匹配的主机：${unmatchedItems.slice(0, 3).join(', ')}${unmatchedItems.length > 3 ? '...' : ''}`)
    }

  } catch (error) {
    console.error('解析主机失败:', error)
    message.error('解析主机失败')
  } finally {
    parsingHosts.value = false
  }
}

// 清空解析结果
const clearResolvedHosts = () => {
  resolvedHosts.value = []
  resolvedSelectedHostIds.value = []
  resolveInputText.value = ''
}

// 移除解析的主机
const removeResolvedHost = (hostId: number) => {
  const index = resolvedHosts.value.findIndex((h: any) => h.id === hostId)
  if (index > -1) {
    resolvedHosts.value.splice(index, 1)
  }
}

// 确认选择
const handleConfirm = () => {
  // 合并所有选择的主机
  const allSelectedHosts: any[] = []

  // 添加表格选择的主机
  selectedHostObjects.value.forEach((host: any) => {
    if (host) {
      allSelectedHosts.push(host)
    }
  })

  // 添加解析匹配的主机（不在表格选择中的）
  resolvedMatchedHosts.value.forEach((h: any) => {
    const exists = allSelectedHosts.find((item: any) => item.id === h.id)
    if (!exists) {
      allSelectedHosts.push(h)
    }
  })

  // 执行核心是主机集合：静态/解析结果进 hosts；groups 仅动态选择，由后端在执行时展开。
  // 前端分组勾选、过滤只是选机便利，不替代最终主机列表。
  if (allSelectedHosts.length === 0 && dynamicSelectedGroupIds.value.length === 0) {
    message.warning('请至少选择一台主机，或选择一个动态分组')
    return false
  }

  emit('confirm', {
    hosts: allSelectedHosts,
    groups: dynamicSelectedGroupIds.value
  })
  visible.value = false
}

// 取消选择
const handleCancel = () => {
  visible.value = false
}

// 处理分组树展开
const handleGroupTreeExpand = (keys: any[]) => {
  expandedKeys.value = keys
}

// 获取分组树展开的键
const getExpandedKeys = () => {
  return expandedKeys.value
}

// 生命周期
onMounted(() => {
  // 初始化
})
</script>

<style scoped>
.host-selector {
  display: flex;
  gap: 16px;
  height: 680px;
}

.selector-main {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.selection-mode-tabs {
  height: 100%;
}

.selection-mode-tabs :deep(.n-tabs-pane-wrapper) {
  height: calc(100% - 50px);
  padding-top: 12px;
}

.selection-mode-tabs :deep(.n-tab-pane) {
  height: 100%;
  padding-left: 0;
  padding-right: 0;
  padding-bottom: 0;
}

/* 静态选择容器 */
.static-selection-container {
  display: flex;
  gap: 12px;
  height: calc(100% - 20px);
}

.tree-host-node {
  gap: 8px;
}

.tree-host-check {
  flex: 0 0 16px;
  width: 16px;
  height: 16px;
  border: 1px solid #c0c4cc;
  border-radius: 3px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1;
  color: #fff;
  background: #fff;
  margin-top: 2px;
}

.tree-host-check.checked {
  background: #2080f0;
  border-color: #2080f0;
}

.node-has-selection .node-name {
  color: #2080f0;
  font-weight: 600;
}

.stat-selected .stat-number {
  color: #2080f0;
  font-weight: 600;
}

/* 分组面板 */
.groups-panel {
  flex: 0 0 280px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
  background: #f7f8fa;
  border-radius: 6px 6px 0 0;
  flex-shrink: 0;
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.group-count {
  font-size: 12px;
  color: #86909c;
}

.search-container {
  padding: 8px 10px;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.groups-tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.groups-tree {
  background: transparent;
}

.dynamic-groups-tree {
  max-height: 500px;
}

/* 主机面板 */
.hosts-panel {
  flex: 1;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}

.panel-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.host-count {
  font-size: 12px;
  color: #86909c;
}

.action-buttons {
  padding: 8px 12px;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.hosts-table {
  flex: 1;
  overflow: hidden;
}

.hosts-table :deep(.n-data-table-wrapper) {
  max-height: 400px;
  overflow-y: auto;
}

/* 动态选择容器 */
.dynamic-selection-container {
  padding: 0 4px;
  height: calc(100% - 20px);
}

.dynamic-selection-help {
  margin-bottom: 12px;
}

/* 主机解析面板 */
.resolve-panel {
  padding: 0 4px;
  height: calc(100% - 20px);
}

.resolve-help {
  margin-bottom: 12px;
}

.resolve-input-container {
  margin-bottom: 12px;
}

.resolve-actions {
  margin-bottom: 12px;
}

.resolved-results {
  margin-bottom: 12px;
}

.resolved-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
}

.resolved-title {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #389e0d;
}

.resolved-actions {
  display: flex;
  gap: 8px;
}

.resolved-hosts-table {
  max-height: 300px;
  overflow-y: auto;
}

/* 主机名称单元格 */
.host-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.host-name {
  font-weight: 500;
  font-size: 13px;
}

.host-ip {
  font-size: 12px;
  color: #86909c;
}

/* 所属分组显示 */
.groups-display {
  display: flex;
  flex-wrap: nowrap;
  gap: 2px;
}

.group-tag {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 状态点 */
.status-dot,
.agent-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}

.status-online,
.agent-status-online {
  background: #52c41a;
}

.status-offline,
.agent-status-offline {
  background: #ff4d4f;
}

.status-maintenance {
  background: #1890ff;
}

.status-unknown,
.agent-status-unknown {
  background: #86909c;
}

/* 树节点样式 */
.tree-node-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  flex: 1;
}

.tree-node-content:hover {
  background: #f2f3f5;
}

.node-selected {
  background: #e6f7ff !important;
}

.node-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.node-name {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-description {
  font-size: 12px;
  color: #86909c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-stats {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.stat-number {
  font-size: 14px;
  font-weight: 500;
  color: #1d2129;
  line-height: 1.2;
}

.stat-label {
  font-size: 10px;
  color: #86909c;
}

/* 预览面板 */
.preview-panel {
  flex: 0 0 320px;
  border-left: 1px solid #e8e8e8;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  box-sizing: border-box;
  flex-shrink: 0;
  min-height: 0;
  align-self: stretch;
  overflow: hidden;
  height: 100%;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.preview-title {
  font-weight: 500;
  font-size: 14px;
  color: #1d2129;
}

.preview-count {
  font-size: 12px;
  color: #86909c;
  text-align: right;
  line-height: 1.4;
}

.preview-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.preview-list {
  flex: 1;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 10px;
  min-height: 0;
  overflow-y: auto;
  max-height: 600px;
}

.preview-list.scrollable {
  overflow-y: auto;
}

.preview-empty {
  color: #999;
  text-align: center;
  padding: 20px 0;
  font-size: 12px;
}

/* 预览分区样式 */
.preview-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-section-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #666;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f0f0;
}

.preview-section-icon {
  font-size: 14px;
  color: #1890ff;
}

/* 动态分组预览 */
.preview-dynamic {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  padding: 8px;
}

.preview-dynamic .preview-section-header {
  color: #389e0d;
  border-bottom-color: #d9f7be;
}

.preview-dynamic .preview-section-icon {
  color: #52c41a;
}

.preview-groups {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 300px;
  overflow-y: auto;
}

.preview-group-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #d9f7be;
}

.previewgroup-info {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}

.preview-group-name {
  font-size: 12px;
  font-weight: 500;
  color: #1d2129;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.preview-group-count {
  font-size: 11px;
  color: #86909c;
}

/* 解析结果预览 */
.preview-resolved {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 4px;
  padding: 8px;
}

.preview-resolved .preview-section-header {
  color: #d48806;
  border-bottom-color: #fff1b8;
}

.preview-resolved .preview-section-icon {
  color: #faad14;
}

/* 静态主机预览 */
.preview-static {
  background: #f6f9ff;
  border: 1px solid #adc6ff;
  border-radius: 4px;
  padding: 8px;
}

.preview-static .preview-section-header {
  color: #165DFF;
  border-bottom-color: #d6e4ff;
}

.preview-static .preview-section-icon {
  color: #165DFF;
}

.preview-chips {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 500px;
  overflow-y: auto;
}

.preview-ip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.preview-ip-text {
  font-family: 'Courier New', Consolas, monospace;
  font-size: 12px;
  color: #1d2129;
}

.preview-ip-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.preview-ip:hover .preview-ip-actions {
  opacity: 1;
}

/* 主机选择相关样式 */
.text-gray-400 {
  color: #86909c;
}

.status-tag {
  max-width: 80px;
}

.agent-status-cell {
  display: flex;
  align-items: center;
}

.agent-status-tag {
  max-width: 90px;
}

.agent-status-dot {
  margin-right: 4px;
}

.preview-ip-actions :deep(.n-button),
.preview-section-header :deep(.n-button) {
  padding: 2px 4px;
  font-size: 12px;
}
</style>
