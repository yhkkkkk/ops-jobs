<template>
  <a-modal
    v-model:visible="visible"
    title="选择执行目标"
    width="1400px"
    :mask-closable="false"
    @ok="handleConfirm"
    @cancel="handleCancel"
    class="host-selector-modal"
  >
    <div class="host-selector">
      <!-- 左侧：Tab内容区域 -->
      <div class="selector-main">
        <!-- Tab切换：静态选择 / 动态选择 / 主机解析 -->
        <a-tabs v-model:active-key="selectionMode" class="selection-mode-tabs">
          <a-tab-pane key="static" title="静态选择">
            <div class="static-selection-container">
              <!-- 左侧：主机分组树 -->
              <div class="groups-panel">
                <div class="panel-header">
                  <h4>主机分组</h4>
                  <span class="group-count">{{ groups.length }}个分组</span>
                </div>
                <div class="search-container">
                  <a-input-search
                    v-model="groupSearchText"
                    placeholder="搜索分组名称"
                    size="small"
                    allow-clear
                    @search="handleGroupSearch"
                    @update:value="handleGroupSearch"
                  />
                </div>
                <div class="groups-tree-container">
                  <a-tree
                    :data="treeData"
                    :expanded-keys="expandedKeys"
                    :selected-keys="selectedGroupIds"
                    :auto-expand-parent="true"
                    :show-line="true"
                    :block-node="true"
                    size="small"
                    class="groups-tree"
                    @expand="handleTreeExpand"
                    @click="handleTreeClick"
                  >
                    <template #title="slotProps">
                      <div
                        class="tree-node-content"
                        :class="{ 'node-selected': selectedGroupIds.includes(parseInt(slotProps.key)) }"
                        @click.stop="handleNodeTitleClick(slotProps)"
                      >
                        <div class="node-info">
                          <div class="node-name">{{ slotProps.title || '未知分组' }}</div>
                          <div v-if="slotProps.description" class="node-description">{{ slotProps.description }}</div>
                        </div>
                        <div class="node-stats">
                          <div class="stat-item">
                            <span class="stat-number">{{ slotProps.online_count || 0 }}</span>
                            <span class="stat-label">在线</span>
                          </div>
                          <div class="stat-item">
                            <span class="stat-number">{{ slotProps.host_count || 0 }}</span>
                            <span class="stat-label">总数</span>
                          </div>
                        </div>
                      </div>
                    </template>
                  </a-tree>
                </div>
              </div>

              <!-- 中间：主机列表 -->
              <div class="hosts-panel">
                <div class="panel-header">
                  <div class="panel-header-left">
                    <h4>主机列表</h4>
                    <span class="host-count">{{ filteredHosts.length }} 台主机</span>
                  </div>
                </div>
                <div class="search-container">
                  <a-textarea
                    v-model="displayHostSearchText"
                    placeholder="支持多IP搜索：IPv4 / IPv6 / 主机名称 / OS 名称，可直接粘贴多行IP"
                    size="small"
                    allow-clear
                    @input="handleHostSearchInput"
                    @clear="handleHostSearchClear"
                    @press-enter="handleHostSearch"
                    :auto-size="{ minRows: 1, maxRows: 4 }"
                    style="width: 100%"
                    @paste.capture="handleHostSearchPaste"
                  />
                </div>
                <div class="action-buttons">
                  <a-button size="small" @click="selectAllHosts">
                    <template #icon><icon-check-square /></template>
                    全选
                  </a-button>
                  <a-button size="small" @click="selectOnlineHosts">
                    <template #icon><icon-wifi /></template>
                    仅在线
                  </a-button>
                  <a-button size="small" @click="selectAgentOnlineHosts">
                    <template #icon><icon-cloud /></template>
                    仅agent在线
                  </a-button>
                  <a-button size="small" @click="clearHostSelection">
                    <template #icon><icon-close-circle /></template>
                    清空
                  </a-button>
                </div>
                <a-table
                  :data="filteredHosts"
                  :pagination="hostPaginationConfig"
                  v-model:selectedKeys="selectedHostIds"
                  :row-selection="{ type: 'checkbox' }"
                  @selection-change="handleSelectionChange"
                  @row-click="handleHostsTableRowClick"
                  @page-change="handleHostPageChange"
                  @page-size-change="handleHostPageSizeChange"
                  row-key="id"
                  size="small"
                  class="hosts-table"
                >
                  <template #columns>
                    <a-table-column title="主机名称" data-index="name" width="160">
                      <template #cell="{ record }">
                        <div class="host-name-cell">
                          <div class="host-name">{{ record.name }}</div>
                          <div class="host-ip">{{ getHostDisplayIp(record) }}</div>
                        </div>
                      </template>
                    </a-table-column>
                    <a-table-column title="Agent状态" data-index="agent_info" width="100">
                      <template #cell="{ record }">
                        <div v-if="record.agent_info" class="agent-status-cell">
                          <a-tag
                            size="small"
                            :color="getAgentStatusColor(record.agent_info.status)"
                            class="agent-status-tag"
                          >
                            <template #icon>
                              <div class="agent-status-dot" :class="`agent-status-${record.agent_info.status}`"></div>
                            </template>
                            {{ record.agent_info.status_display }}
                          </a-tag>
                        </div>
                        <span v-else class="text-gray-400">未安装</span>
                      </template>
                    </a-table-column>
                    <a-table-column title="OS 名称" data-index="os_type" width="100">
                      <template #cell="{ record }">
                        <a-tag size="small" :color="record.os_type === 'linux' ? 'green' : 'blue'">
                          {{ record.os_type || 'Unknown' }}
                        </a-tag>
                      </template>
                    </a-table-column>
                    <a-table-column title="主机状态" data-index="status" width="100">
                      <template #cell="{ record }">
                        <a-tag
                          size="small"
                          :color="getHostStatusColor(record.status)"
                          class="status-tag"
                        >
                          <template #icon>
                            <div class="status-dot" :class="`status-${record.status}`"></div>
                          </template>
                          {{ getHostStatusText(record.status) }}
                        </a-tag>
                      </template>
                    </a-table-column>
                    <a-table-column title="所属分组" data-index="groups_info" :width="180">
                      <template #cell="{ record }">
                        <div v-if="record.groups_info && record.groups_info.length > 0" class="groups-display">
                          <a-tag
                            v-for="group in record.groups_info.slice(0, 2)"
                            :key="group.id"
                            size="small"
                            color="arcoblue"
                            class="group-tag"
                          >
                            {{ group.name }}
                          </a-tag>
                          <a-tag v-if="record.groups_info.length > 2" size="small" color="gray">
                            +{{ record.groups_info.length - 2 }}
                          </a-tag>
                        </div>
                        <span v-else class="text-gray-400">无分组</span>
                      </template>
                    </a-table-column>
                  </template>
                </a-table>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="dynamic" title="动态选择">
            <!-- 动态选择：只选择分组，执行时动态获取分组内的所有主机 -->
            <div class="dynamic-selection-container">
              <div class="panel-header">
                <h4>动态选择分组</h4>
                <span class="group-count">{{ dynamicSelectedGroupIds.length }} 个分组</span>
              </div>

              <div class="dynamic-selection-help">
                <a-alert type="info" :closable="false">
                  <template #title>动态选择说明</template>
                  <template #default>
                    <div>• 动态选择分组后，执行时会自动获取分组内的所有主机</div>
                    <div>• 分组内主机数量变化时，会自动包含新增的主机</div>
                    <div>• 适合需要动态包含分组内所有主机的场景</div>
                  </template>
                </a-alert>
              </div>

              <!-- 分组搜索 -->
              <div class="search-container">
                <a-input-search
                  v-model="dynamicGroupSearchText"
                  placeholder="搜索分组名称"
                  size="small"
                  allow-clear
                  @search="handleDynamicGroupSearch"
                  @update:value="handleDynamicGroupSearch"
                />
              </div>

              <!-- 分组树（只显示分组，不显示主机） -->
              <div class="groups-tree-container dynamic-groups-tree">
                <a-tree
                  :data="dynamicTreeData"
                  :expanded-keys="expandedKeys"
                  :selected-keys="dynamicSelectedGroupIds"
                  :auto-expand-parent="true"
                  :show-line="true"
                  :block-node="true"
                  size="small"
                  class="groups-tree"
                  @expand="handleTreeExpand"
                  @click="handleTreeClick"
                >
                  <template #title="slotProps">
                    <div
                      class="tree-node-content"
                      :class="{ 'node-selected': dynamicSelectedGroupIds.includes(parseInt(slotProps.key)) }"
                      @click.stop="handleDynamicNodeTitleClick(slotProps)"
                    >
                      <div class="node-info">
                        <div class="node-name">{{ slotProps.title || '未知分组' }}</div>
                        <div v-if="slotProps.description" class="node-description">{{ slotProps.description }}</div>
                      </div>
                      <div class="node-stats">
                        <div class="stat-item">
                          <span class="stat-number">{{ slotProps.online_count || 0 }}</span>
                          <span class="stat-label">在线</span>
                        </div>
                        <div class="stat-item">
                          <span class="stat-number">{{ slotProps.host_count || 0 }}</span>
                          <span class="stat-label">总数</span>
                        </div>
                      </div>
                    </div>
                  </template>
                </a-tree>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="resolve" title="主机解析">
            <!-- 主机解析：通过输入IP/主机名列表解析并选择主机 -->
            <div class="resolve-panel">
              <div class="panel-header">
                <h4>主机解析</h4>
              </div>

              <div class="resolve-help">
                <a-alert type="info" :closable="false">
                  <template #title>主机解析说明</template>
                  <template #default>
                    <div>• 支持多种输入格式：IP 地址、主机名、多行文本</div>
                    <div>• 解析成功后会自动添加到目标主机列表</div>
                    <div>• 可以与静态选择、动态选择同时使用</div>
                  </template>
                </a-alert>
              </div>

              <div class="resolve-input-container">
                <a-textarea
                  v-model="resolveInputText"
                  placeholder="请输入IP地址或主机名，每行一个，支持逗号分隔&#10;示例：&#10;192.168.1.1&#10;192.168.1.2&#10;web-01.example.com"
                  size="large"
                  allow-clear
                  :auto-size="{ minRows: 6, maxRows: 10 }"
                  style="width: 100%; font-family: 'Courier New', monospace;"
                />
              </div>

              <div class="resolve-actions">
                <a-space>
                  <a-button type="primary" :loading="parsingHosts" @click="handleParseHosts">
                    <template #icon><icon-search /></template>
                    解析主机
                  </a-button>
                  <a-button @click="resolveInputText = ''">
                    <template #icon><icon-delete /></template>
                    清空
                  </a-button>
                </a-space>
              </div>

              <!-- 解析结果 -->
              <div v-if="resolvedHosts.length > 0" class="resolved-results">
                <div class="resolved-header">
                  <div class="resolved-title">
                    <icon-check-circle style="color: #52c41a; font-size: 16px; margin-right: 4px;" />
                    <span>解析成功：{{ resolvedHosts.length }} 台主机</span>
                  </div>
                  <div class="resolved-actions">
                    <a-button size="small" type="text" @click="clearResolvedHosts">
                      <template #icon><icon-delete /></template>
                      清空结果
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- 解析结果表格（只读展示） -->
              <div v-if="resolvedHosts.length > 0" class="resolved-hosts-table">
                <a-table
                  :data="resolvedHosts"
                  :pagination="{ pageSize: 10, showSizeChanger: true, showQuickJumper: true }"
                  v-model:selected-keys="resolvedSelectedHostIds"
                  :row-selection="{ type: 'checkbox' }"
                  row-key="id"
                  size="small"
                >
                  <template #columns>
                    <a-table-column title="主机名称" data-index="name" width="160">
                      <template #cell="{ record }">
                        <div class="host-name-cell">
                          <div class="host-name">{{ record.name }}</div>
                          <div class="host-ip">{{ getHostDisplayIp(record) }}</div>
                        </div>
                      </template>
                    </a-table-column>
                    <a-table-column title="状态" data-index="status" width="100">
                      <template #cell="{ record }">
                        <a-tag
                          size="small"
                          :color="getHostStatusColor(record.status)"
                        >
                          {{ getHostStatusText(record.status) }}
                        </a-tag>
                      </template>
                    </a-table-column>
                    <a-table-column title="来源" data-index="source" width="120">
                      <template #cell="{ record }">
                        <a-tag :color="record.source === 'matched' ? 'green' : 'orange'" size="small">
                          {{ record.source === 'matched' ? '已匹配' : '未匹配' }}
                        </a-tag>
                      </template>
                    </a-table-column>
                  </template>
                </a-table>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
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
          <a-button size="small" type="outline" @click="copySelectedIps" :disabled="!hasAnySelection">复制IP</a-button>
          <a-button size="small" type="text" status="danger" @click="clearAllSelection" :disabled="!hasAnySelection">清空</a-button>
        </div>
        <div class="preview-list scrollable">
          <!-- 动态选择分组预览 -->
          <div v-if="dynamicSelectedGroupIds.length > 0" class="preview-section preview-dynamic">
            <div class="preview-section-header">
              <icon-folder class="preview-section-icon" />
              <span>动态分组 ({{ dynamicSelectedGroupIds.length }})</span>
              <a-button size="mini" type="text" @click="clearDynamicGroups" status="danger">清空</a-button>
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
                <a-button size="mini" type="text" @click="removeDynamicGroup(groupId)" status="danger">
                  <template #icon><icon-close /></template>
                </a-button>
              </div>
            </div>
          </div>

          <!-- 解析结果预览 -->
          <div v-if="resolvedMatchedHosts.length > 0" class="preview-section preview-resolved">
            <div class="preview-section-header">
              <icon-search class="preview-section-icon" />
              <span>解析主机 ({{ resolvedMatchedHosts.length }})</span>
              <a-button size="mini" type="text" @click="clearResolvedHosts" status="danger">清空</a-button>
            </div>
            <div class="preview-chips">
              <div
                v-for="host in resolvedMatchedHosts"
                :key="host.id"
                class="preview-ip"
              >
                <span class="preview-ip-text">{{ getHostDisplayIp(host) }}</span>
                <span class="preview-ip-actions">
                  <a-button size="mini" type="text" @click.stop="copySingleIp(host)">复制</a-button>
                  <a-button size="mini" type="text" status="danger" @click.stop="removeResolvedHost(host.id)">删除</a-button>
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
              <icon-computer class="preview-section-icon" />
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
                  <a-button size="mini" type="text" @click.stop="copySingleIp(host)">复制</a-button>
                  <a-button size="mini" type="text" status="danger" @click.stop="removeSingleHost(host.id)">删除</a-button>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, h, type PropType } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { Host, HostGroup } from '@/types'
import {
  IconSearch,
  IconCheckSquare,
  IconWifi,
  IconCloud,
  IconCloseCircle,
  IconCheckCircle,
  IconExclamationCircle,
  IconCheck,
  IconClose,
  IconFolder,
  IconComputer,
  IconDelete
} from '@arco-design/web-vue/es/icon'

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
const expandedKeys = ref<number[]>([])

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

  ;(props.hosts || []).forEach((host: Host) => {
    if (selectedIds.has(host.id)) {
      nextMap[host.id] = host
    }
  })

  selectedHostMap.value = nextMap
}

watch([internalSelectedHostIds, () => props.hosts], syncSelectedHostMap, { immediate: true, deep: true })

// 主机解析相关
const resolveInputText = ref('') // 主机解析输入
const resolvedHosts = ref<any[]>([]) // 解析结果列表
const resolvedSelectedHostIds = ref<number[]>([]) // 解析结果中选择的主机ID
const parsingHosts = ref(false) // 解析加载状态

// 主机分页配置
const hostPaginationConfig = computed(() => {
  if (!props.enableHostPagination) {
    return { pageSize: 10, showSizeChanger: true, showQuickJumper: true }
  }
  const pageSize = 10
  return {
    current: props.hostPagination.current || 1,
    pageSize,
    total: props.hostPagination.total || 0,
    pageSizeOptions: ['10'],
    showSizeChanger: false,
    showQuickJumper: true
  }
})

const handleSelectionChange = (keys: any[]) => {
  selectedHostIds.value = Array.isArray(keys) ? keys : []
}

// 处理主机分页变化
const handleHostPageChange = (page: number, pageSize?: number) => {
  emit('hostPageChange', page, pageSize ?? hostPaginationConfig.value.pageSize)
}

// 处理主机每页数量变化
const handleHostPageSizeChange = (pageSize: number) => {
  emit('hostPageSizeChange', pageSize)
}

// 计算属性
const treeData = computed(() => {
  return (props.groups || [])
    .filter((group: HostGroup) => {
      if (!groupSearchText.value) return true
      return group.name?.toLowerCase().includes(groupSearchText.value.toLowerCase())
    })
    .map((group: HostGroup) => {
      const children = (props.hosts || [])
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
          icon: () => h(IconComputer),
          parentId: group.id,
          ...host
        }))
      return {
        key: group.id,
        title: group.name,
        description: group.description,
        children,
        icon: () => h(IconFolder),
        online_count: group.online_count || 0,
        host_count: group.host_count || (children?.length || 0),
        isGroup: true
      }
    })
})

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
  return filterHosts((props.hosts as Host[]) || [])
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
      icon: () => h(IconFolder),
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
const getAgentStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    online: 'green',
    offline: 'red',
    unknown: 'orange'
  }
  return colors[status] || 'gray'
}

// 获取主机状态颜色
const getHostStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    online: 'green',
    offline: 'red',
    maintenance: 'orange',
    unknown: 'gray'
  }
  return colors[status] || 'gray'
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
const handleTreeExpand = (keys: any[]) => {
  expandedKeys.value = keys
}

const handleTreeClick = (key: any, event: any) => {
  // 阻止默认点击行为，防止选中分组
}

const handleNodeTitleClick = (nodeData: any) => {
  const key = parseInt(nodeData.key)
  const index = selectedGroupIds.value.indexOf(key)
  if (index === -1) {
    // 添加分组到已选分组
    selectedGroupIds.value.push(key)
    // 添加该分组下的所有主机到已选主机
    const groupHosts = (props.hosts || []).filter((h: Host) =>
      h.groups_info?.some((g) => g.id === key)
    )
    groupHosts.forEach((host: Host) => {
      if (!internalSelectedHostIds.value.includes(host.id)) {
        internalSelectedHostIds.value.push(host.id)
      }
    })
  } else {
    // 从已选分组中移除
    selectedGroupIds.value.splice(index, 1)
    // 移除该分组下的所有主机（仅当该主机不属于其他已选分组时）
    const stillSelectedGroups = selectedGroupIds.value
    const groupHosts = (props.hosts || []).filter((h: Host) =>
      h.groups_info?.some((g) => g.id === key)
    )
    groupHosts.forEach((host: Host) => {
      // 检查主机是否还属于其他已选分组
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

const handleHostsTableRowClick = (record: any) => {
  // 可以在这里实现点击行切换选中状态
}

const handleGroupSearch = () => {
  // 搜索逻辑在computed中处理
}

const handleHostSearchInput = () => {
  // 搜索逻辑在 computed 中处理，这里只需要同步到 hostSearchText
  hostSearchText.value = displayHostSearchText.value.trim()
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
    Message.warning('没有可复制的IP地址')
    return
  }
  navigator.clipboard.writeText(ip)
  Message.success(`已复制IP: ${ip}`)
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
    Message.success(`已复制 ${ips.length} 个IP地址`)
  } else {
    Message.warning('没有可复制的IP地址')
  }
}

// 解析主机
const handleParseHosts = async () => {
  if (!resolveInputText.value.trim()) {
    Message.warning('请输入要解析的IP地址或主机名')
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
      Message.success(`解析成功：${matchedHosts.length} 台主机已添加到目标列表`)
    }

    if (unmatchedItems.length > 0) {
      Message.warning(`未找到匹配的主机：${unmatchedItems.slice(0, 3).join(', ')}${unmatchedItems.length > 3 ? '...' : ''}`)
    }

  } catch (error) {
    console.error('解析主机失败:', error)
    Message.error('解析主机失败')
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

.selection-mode-tabs :deep(.arco-tabs-content) {
  height: calc(100% - 50px);
  padding-top: 12px;
}

.selection-mode-tabs :deep(.arco-tabs-content-list) {
  height: 100%;
}

.selection-mode-tabs :deep(.arco-tabs-pane) {
  height: 100%;
}

/* 静态选择容器 */
.static-selection-container {
  display: flex;
  gap: 12px;
  height: calc(100% - 20px);
}

/* 分组面板 */
.groups-panel {
  flex: 0 0 200px;
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

.hosts-table :deep(.arco-table-body) {
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

:deep(.arco-btn-text) {
  padding: 2px 4px;
}

:deep(.arco-btn-size-mini) {
  padding: 2px 4px;
}

:deep(.arco-btn-size-mini .arco-btn-icon) {
  font-size: 12px;
}
</style>
