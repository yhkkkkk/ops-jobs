<template>
  <a-modal
    v-model:visible="visible"
    title="选择执行目标"
    width="1200px"
    :mask-closable="false"
    @ok="handleConfirm"
    @cancel="handleCancel"
    class="host-selector-modal"
  >
    <div class="host-selector">
      <!-- Tab切换：静态选择 / 动态选择 / 主机解析 -->
      <a-tabs v-model:active-key="selectionMode" class="selection-mode-tabs">
        <a-tab-pane key="static" title="静态选择">
          <!-- 静态选择内容：左右分栏 -->
      <div class="selector-content">
        <!-- 左侧：主机分组树 -->
        <div class="groups-panel">
          <div class="panel-header">
            <h4>主机分组</h4>
            <span class="group-count">{{ groups.length }}个分组</span>
          </div>
          
          <!-- 分组搜索 -->
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

          <!-- 分组树 -->
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

        <!-- 右侧：主机列表 -->
        <div class="hosts-panel">
          <div class="panel-header">
            <h4>主机列表</h4>
            <span class="host-count">{{ filteredHosts.length }} 台主机</span>
          </div>
          
          <!-- 主机搜索 -->
          <div class="search-container">
            <a-textarea
              v-model="displayHostSearchText"
              placeholder="支持多IP搜索：IPv4 / IPv6 / 主机名称 / OS 名称，可直接粘贴多行IP"
              size="small"
              allow-clear
              @input="handleHostSearchInput"
              @paste="handleHostSearchPaste"
              @press-enter="handleHostSearch"
              :auto-size="{ minRows: 1, maxRows: 4 }"
              style="width: 100%"
            />
          </div>

          <!-- 操作按钮 -->
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
            :pagination="{ pageSize: 15, showSizeChanger: true, showQuickJumper: true }"
            v-model:selectedKeys="selectedHostIds"
            :row-selection="{ type: 'checkbox' }"
            @row-click="handleHostsTableRowClick"
            row-key="id"
            size="small"
            class="hosts-table"
          >
            <template #columns>
              <a-table-column title="主机名称" data-index="name" width="160">
                <template #cell="{ record }">
                  <div class="host-name-cell">
                    <div class="host-name">{{ record.name }}</div>
                    <div class="host-ip">{{ record.ip_address }}:{{ record.port }}</div>
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
          <div class="dynamic-selection-panel">
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
            <div class="groups-tree-container">
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
                        <span class="stat-number">{{ slotProps.agent_online_count || 0 }}</span>
                        <span class="stat-label">Agent</span>
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
            
            <!-- 已选分组的详情 -->
            <div v-if="dynamicSelectedGroupIds.length > 0" class="selected-groups-detail">
              <div class="detail-header">
                <h4>已选分组详情</h4>
              </div>
              <div class="detail-content">
                <div 
                  v-for="groupId in dynamicSelectedGroupIds" 
                  :key="`detail-${groupId}`"
                  class="group-detail-card"
                >
                  <div class="group-detail-header">
                    <span class="group-name">{{ getGroupName(groupId) }}</span>
                    <a-button 
                      type="text" 
                      size="tiny" 
                      status="danger"
                      @click="removeDynamicGroup(groupId)"
                    >
                      <template #icon><icon-close /></template>
                    </a-button>
                  </div>
                  <div class="group-stats-row">
                    <div class="stat-badge">
                      <span class="stat-value">{{ getGroupHostCount(groupId) }}</span>
                      <span class="stat-label">主机</span>
                    </div>
                    <div class="stat-badge">
                      <span class="stat-value" style="color: #52c41a">{{ getGroupOnlineCount(groupId) }}</span>
                      <span class="stat-label">在线</span>
                    </div>
                    <div class="stat-badge">
                      <span class="stat-value" style="color: #1890ff">{{ getGroupAgentOnlineCount(groupId) }}</span>
                      <span class="stat-label">Agent在线</span>
                    </div>
                    <div class="stat-badge">
                      <span class="stat-value" style="color: #ff4d4f">{{ getGroupOfflineCount(groupId) }}</span>
                      <span class="stat-label">离线</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>
        
        <a-tab-pane key="resolve" title="主机解析">
          <!-- 主机解析：通过输入IP/主机名列表解析并选择主机 -->
          <div class="resolve-panel">
            <!-- 解析输入区域 -->
            <div class="resolve-input-section">
              <div class="section-header">
                <h4>输入IP或主机名</h4>
                <a-space>
                  <a-button type="primary" @click="handleParseHosts" :loading="parsingHosts" size="small">
                    <template #icon><icon-search /></template>
                    解析并加载
                  </a-button>
                  <a-button @click="clearResolveInput" size="small">清空</a-button>
                </a-space>
              </div>
              
              <a-textarea
                v-model="resolveInputText"
                placeholder="支持多种格式：&#10;• 每行一个IP或主机名&#10;• 逗号分隔：192.168.1.1, 192.168.1.2&#10;• 空格分隔：192.168.1.1 192.168.1.2&#10;• 混合格式均可识别"
                :auto-size="{ minRows: 4, maxRows: 8 }"
                allow-clear
                style="width: 100%; font-family: 'Courier New', monospace;"
              />
              
              <!-- 解析统计 -->
              <div v-if="resolvedHosts.length > 0" class="resolve-stats">
                <a-tag color="blue">共 {{ resolvedInputCount }} 个输入</a-tag>
                <a-tag color="green">有效 {{ validResolvedCount }} 个</a-tag>
                <a-tag v-if="invalidResolvedCount > 0" color="red">未找到 {{ invalidResolvedCount }} 个</a-tag>
                <a-tag v-if="validSelectedHostCount > 0" color="purple">
                  已选 {{ validSelectedHostCount }} 台
                </a-tag>
              </div>
            </div>

            <!-- 解析结果表格 -->
            <div v-if="resolvedHosts.length > 0" class="resolve-result-section">
              <div class="section-header">
                <h4>解析结果 - 选择要加载的主机</h4>
                <a-space>
                  <a-button size="small" @click="selectAllResolvedHosts">
                    <template #icon><icon-check-square /></template>
                    全选
                  </a-button>
                  <a-button size="small" @click="selectNoneResolvedHosts">取消全选</a-button>
                  <a-button size="small" @click="selectValidResolvedHosts">仅选有效</a-button>
                </a-space>
              </div>
              
              <a-table
                :data="resolvedHosts"
                :pagination="{ pageSize: 10, showSizeChanger: true, showQuickJumper: true }"
                v-model:selectedKeys="resolvedSelectedHostIds"
                :row-selection="{ type: 'checkbox' }"
                row-key="key"
                size="small"
                class="resolved-hosts-table"
              >
                <template #columns>
                  <a-table-column title="输入值" data-index="input" width="140">
                    <template #cell="{ record }">
                      <code>{{ record.input }}</code>
                    </template>
                  </a-table-column>
                  <a-table-column title="匹配主机" data-index="host" width="180">
                    <template #cell="{ record }">
                      <template v-if="record.host">
                        <div class="host-name-cell">
                          <div class="host-name">{{ record.host.name }}</div>
                          <div class="host-ip">{{ record.host.ip_address }}:{{ record.host.port }}</div>
                        </div>
                      </template>
                      <span v-else class="text-gray-400">-</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="状态" data-index="status" width="80">
                    <template #cell="{ record }">
                      <a-tag v-if="record.status === 'valid'" size="small" color="green">
                        <template #icon><icon-check-circle /></template>
                        有效
                      </a-tag>
                      <a-tag v-else-if="record.status === 'invalid'" size="small" color="red">
                        <template #icon><icon-close-circle /></template>
                        无效
                      </a-tag>
                      <a-tag v-else size="small" color="orange">
                        <template #icon><icon-exclamation-circle /></template>
                        未找到
                      </a-tag>
                    </template>
                  </a-table-column>
                  <a-table-column title="Agent" data-index="agent" width="90">
                    <template #cell="{ record }">
                      <template v-if="record.host && record.host.agent_info">
                        <a-tag 
                          size="small" 
                          :color="getAgentStatusColor(record.host.agent_info.status)"
                        >
                          {{ record.host.agent_info.status_display }}
                        </a-tag>
                      </template>
                      <span v-else class="text-gray-400">-</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="OS" data-index="os" width="70">
                    <template #cell="{ record }">
                      <template v-if="record.host">
                        <a-tag size="small" :color="record.host.os_type === 'linux' ? 'green' : 'blue'">
                          {{ record.host.os_type || '?' }}
                        </a-tag>
                      </template>
                      <span v-else>-</span>
                    </template>
                  </a-table-column>
                  <a-table-column title="是否已加载" data-index="loaded" width="100">
                    <template #cell="{ record }">
                      <template v-if="record.host">
                        <a-tag 
                          size="small" 
                          :color="selectedHostIds.includes(record.host.id) ? 'green' : 'gray'"
                        >
                          <template #icon>
                            <icon-check-circle v-if="selectedHostIds.includes(record.host.id)" />
                            <icon-close-circle v-else />
                          </template>
                          {{ selectedHostIds.includes(record.host.id) ? '已加载' : '未加载' }}
                        </a-tag>
                      </template>
                      <span v-else>-</span>
                    </template>
                  </a-table-column>
                </template>
              </a-table>
              
              <!-- 加载按钮 -->
              <div v-if="validSelectedHostCount > 0" class="resolve-confirm-bar">
                <div class="confirm-info">
                  已选择 <a-tag color="blue">{{ validSelectedHostCount }}</a-tag> 台有效主机
                </div>
                <a-button type="primary" @click="confirmAndLoadResolvedHosts">
                  <template #icon><icon-check /></template>
                  加载到目标列表
                </a-button>
              </div>
            </div>

            <!-- 使用说明 -->
            <div v-if="resolvedHosts.length === 0" class="resolve-help">
              <a-alert type="info" :closable="false">
                <template #title>主机解析说明</template>
                <template #default>
                  <div>• 输入IP或主机名列表，系统会自动解析并匹配数据库中的主机</div>
                  <div>• 支持多种输入格式，每行一个、逗号分隔、空格分隔均可</div>
                  <div>• 解析后可以查看每个输入的匹配结果和Agent状态</div>
                  <div>• 选择主机后点击「加载到目标列表」即可将主机添加到目标列表</div>
                </template>
              </a-alert>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>

      <!-- 选择统计 -->
      <div class="selection-summary">
        <div class="summary-info">
          <template v-if="selectionMode === 'static'">
            <div class="summary-item">
              <span>已选分组:</span>
              <span class="summary-count">{{ selectedGroupIds.length }}</span>
            </div>
            <div class="summary-item" v-if="totalGroupHosts > 0">
              <span>分组主机:</span>
              <span class="summary-count">{{ totalGroupHosts }}</span>
            </div>
            <div class="summary-item">
              <span>已选主机:</span>
              <span class="summary-count">{{ selectedHostIds.length }}</span>
            </div>
          </template>
          <template v-else-if="selectionMode === 'dynamic'">
            <div class="summary-item">
              <span>已选分组:</span>
              <span class="summary-count">{{ dynamicSelectedGroupIds.length }}</span>
            </div>
            <div class="summary-item">
              <span>分组主机总数:</span>
              <span class="summary-count">{{ totalDynamicGroupHosts }}</span>
            </div>
            <div class="summary-item">
              <span>Agent在线:</span>
              <span class="summary-count" style="color: #52c41a">{{ totalDynamicAgentOnline }}</span>
            </div>
          </template>
          <template v-else-if="selectionMode === 'resolve'">
            <div class="summary-item">
              <span>已解析:</span>
              <span class="summary-count">{{ resolvedInputCount }}</span>
            </div>
            <div class="summary-item">
              <span>有效:</span>
              <span class="summary-count" style="color: #52c41a">{{ validSelectedHostCount }}</span>
            </div>
          </template>
        </div>
        <div class="summary-total">
          <a-tag color="red" size="small">
            总计: {{ totalSelectedCount }} 个目标
          </a-tag>
        </div>
      </div>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          type="primary"
          @click="handleConfirm"
          :disabled="(selectionMode === 'static' && selectedGroupIds.length === 0 && selectedHostIds.length === 0) || (selectionMode === 'dynamic' && dynamicSelectedGroupIds.length === 0) || (selectionMode === 'resolve' && validSelectedHostCount === 0)"
        >
          确定 ({{ selectionMode === 'resolve' ? validSelectedHostCount : totalSelectedCount }})
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconSearch,
  IconCheckSquare,
  IconWifi,
  IconCloud,
  IconCloseCircle,
  IconCheckCircle,
  IconExclamationCircle,
  IconCheck,
  IconClose
} from '@arco-design/web-vue/es/icon'

// Props
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  hosts: {
    type: Array,
    default: () => []
  },
  groups: {
    type: Array,
    default: () => []
  },
  selectedHosts: {
    type: Array,
    default: () => []
  },
  selectedGroups: {
    type: Array,
    default: () => []
  }
})

// Emits
const emit = defineEmits(['update:visible', 'confirm'])

// 选择模式：static（静态选择）或 dynamic（动态选择）或 resolve（主机解析）
const selectionMode = ref('static')

// 响应式数据
const selectedHostIds = ref([...props.selectedHosts])
const selectedGroupIds = ref([...props.selectedGroups])
const dynamicSelectedGroupIds = ref([]) // 动态选择的分组ID列表
const dynamicGroupSearchText = ref('') // 动态选择的分组搜索文本

// 搜索相关
const groupSearchText = ref('')
const hostSearchText = ref('')
const displayHostSearchText = ref('')

// 主机解析相关
const resolveInputText = ref('') // 主机解析输入
const resolvedHosts = ref([]) // 解析结果列表
const resolvedSelectedHostIds = ref([]) // 解析结果中选择的主机ID
const parsingHosts = ref(false) // 解析加载状态


// 格式化IP地址显示 - 多行显示策略
const formatIpDisplay = (ipString) => {
  if (!ipString) return ''

  const ipList = ipString
    .split(/[,，\s\n\r]+/)
    .map(ip => ip.trim())
    .filter(ip => ip.length > 0)

  if (ipList.length <= 1) {
    return ipString
  }

  // 多IP时，每行显示3个IP，用空格分隔
  const result = []
  for (let i = 0; i < ipList.length; i += 3) {
    const lineIps = ipList.slice(i, i + 3)
    result.push(lineIps.join(' '))
  }

  return result.join('\n')
}

// 解析IP地址输入
const parseIpInput = (input) => {
  if (!input) return ''

  // 将多行内容转换为空格分隔的单行，供搜索使用
  return input
    .split(/[\n\r]+/)
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .join(' ')
}

// 处理主机搜索粘贴事件
const handleHostSearchPaste = (event) => {
  event.preventDefault()
  const pastedText = event.clipboardData?.getData('text') || ''

  if (pastedText) {
    const formattedText = formatIpDisplay(pastedText)
    displayHostSearchText.value = formattedText
    hostSearchText.value = parseIpInput(formattedText)
  }
}

// 处理主机搜索输入事件
const handleHostSearchInput = (value) => {
  displayHostSearchText.value = value
  hostSearchText.value = parseIpInput(value)
}

// 树状结构相关
const expandedKeys = ref([])

// 初始化展开的节点
const initializeExpandedKeys = () => {
  // 确保数据有效
  if (!Array.isArray(props.groups) || props.groups.length === 0) {
    console.log('HostSelector - 分组数据无效或为空，无法初始化展开状态')
    expandedKeys.value = []
    return
  }
  
  // 默认展开所有分组
  expandedKeys.value = props.groups
    .filter(group => group && group.id)
    .map(group => group.id)
  
  console.log('HostSelector - 初始化展开的节点:', expandedKeys.value)
}

// 监听props变化，同步本地状态
watch(() => props.selectedHosts, (newHosts) => {
  if (Array.isArray(newHosts)) {
    selectedHostIds.value = [...newHosts]
  } else {
    console.warn('HostSelector - selectedHosts 不是有效数组:', newHosts)
    selectedHostIds.value = []
  }
}, { immediate: true })

watch(() => props.selectedGroups, (newGroups) => {
  if (Array.isArray(newGroups)) {
    selectedGroupIds.value = newGroups.map(id => parseInt(id)).filter(id => !isNaN(id))
    // 初始化展开状态
    initializeExpandedKeys()
  } else {
    console.warn('HostSelector - selectedGroups 不是有效数组:', newGroups)
    selectedGroupIds.value = []
  }
}, { immediate: true })

// 监听分组数据变化，初始化展开状态
watch(() => props.groups, (newGroups) => {
  console.log('HostSelector - 分组数据变化:', newGroups)
  if (Array.isArray(newGroups) && newGroups.length > 0) {
    initializeExpandedKeys()
  } else {
    console.log('HostSelector - 分组数据无效或为空')
    expandedKeys.value = []
  }
}, { immediate: true })

// 监听选择模式变化，同步分组选择状态
watch(() => selectionMode.value, (newMode) => {
  if (newMode === 'dynamic') {
    // 切换到动态选择时，将静态选择的分组同步到动态选择
    dynamicSelectedGroupIds.value = [...selectedGroupIds.value]
  } else if (newMode === 'static') {
    // 切换到静态选择时，将动态选择的分组同步到静态选择
    selectedGroupIds.value = [...dynamicSelectedGroupIds.value]
  }
})

// 监听主机选择变化，自动更新分组选择状态
watch(selectedHostIds, (newHostIds, oldHostIds) => {
  // 确保数据有效
  if (!Array.isArray(newHostIds) || !Array.isArray(props.groups) || !Array.isArray(props.hosts)) {
    return
  }
  
  // 检查哪些分组的主机选择状态发生了变化
  props.groups.forEach(group => {
    if (!group || !group.id) return
    
    // 通过主机数据中的分组信息来查找属于该分组的主机
    const groupHostIds = props.hosts
      .filter(host => host && host.groups_info && Array.isArray(host.groups_info) && 
                      host.groups_info.some(g => g && g.id === group.id))
      .map(host => host.id)
    
    if (groupHostIds.length > 0) {
      const selectedGroupHosts = newHostIds.filter(id => id && groupHostIds.includes(id))
      const wasSelected = selectedGroupIds.value.includes(group.id)
      const shouldBeSelected = selectedGroupHosts.length > 0
      
      if (wasSelected && !shouldBeSelected) {
        // 如果分组之前被选中，但现在没有主机被选中，则取消选择分组
        const index = selectedGroupIds.value.indexOf(group.id)
        if (index > -1) {
          selectedGroupIds.value.splice(index, 1)
        }
      } else if (!wasSelected && shouldBeSelected) {
        // 如果分组之前没被选中，但现在有主机被选中，则选择分组
        if (!selectedGroupIds.value.includes(group.id)) {
          selectedGroupIds.value.push(group.id)
        }
      }
    }
  })
}, { deep: true })

// 计算属性
const visible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 树状结构数据
const treeData = computed(() => {
  console.log('HostSelector - treeData 计算开始')
  console.log('HostSelector - props.groups:', props.groups)
  console.log('HostSelector - props.hosts:', props.hosts)
  console.log('HostSelector - groupSearchText.value:', groupSearchText.value)
  
  // 确保 props.groups 是有效的数组
  if (!Array.isArray(props.groups) || props.groups.length === 0) {
    console.log('HostSelector - 分组数据无效或为空，返回空数组')
    return []
  }
  
  // 先过滤掉无效的分组对象
  const validGroups = props.groups.filter(group => {
    if (!group || typeof group !== 'object') {
      console.warn('HostSelector - 发现无效的分组对象:', group)
      return false
    }
    if (!group.id) {
      console.warn('HostSelector - 分组缺少ID:', group)
      return false
    }
    return true
  })
  
  console.log('HostSelector - 有效分组数量:', validGroups.length)
  
  // 应用搜索过滤
  const filteredGroups = groupSearchText.value 
    ? validGroups.filter(group => 
        (group.name && group.name.toLowerCase().includes(groupSearchText.value.toLowerCase())) ||
        (group.description && group.description.toLowerCase().includes(groupSearchText.value.toLowerCase()))
      )
    : validGroups

  console.log('HostSelector - 搜索过滤后分组数量:', filteredGroups.length)

  // 构建树状结构
  const buildTree = (groups, parentId = null) => {
    const tree = []
    
    groups.forEach(group => {
      // 检查是否是当前层级的节点
      if (group.parent === parentId) {
        // 计算该分组内的agent在线主机数量
        const agentOnlineCount = props.hosts
          .filter(host => 
            host && host.groups_info && Array.isArray(host.groups_info) && 
            host.groups_info.some(g => g && g.id === group.id) &&
            host.agent_info && host.agent_info.status === 'online'
          ).length
        
        const node = {
          key: group.id,
          title: group.name || `分组${group.id}`,
          description: group.description || '',
          online_count: group.online_count || 0,
          agent_online_count: agentOnlineCount,
          host_count: group.host_count || 0,
          children: buildTree(groups, group.id) // 递归构建子节点
        }
        tree.push(node)
      }
    })
    
    return tree
  }

  const result = buildTree(filteredGroups)
  
  console.log('HostSelector - treeData result:', result)
  return result
})

const filteredHosts = computed(() => {
  // 确保 props.hosts 是有效的数组
  if (!Array.isArray(props.hosts) || props.hosts.length === 0) {
    console.log('HostSelector - 主机数据无效或为空，返回空数组')
    return []
  }

  if (!hostSearchText.value) return props.hosts

  // 处理多关键词搜索 - 支持逗号、空格、换行符分隔
  const searchTerms = hostSearchText.value
    .split(/[,，\s\n\r]+/)  // 支持中英文逗号、空格、换行符分隔
    .map(term => term.trim().toLowerCase())
    .filter(term => term.length > 0)

  if (searchTerms.length === 0) return props.hosts

  return props.hosts.filter(host => {
    if (!host) return false

    // 对每个搜索词，检查是否在主机的任何字段中匹配
    return searchTerms.every(term => {
      return (
        (host.name && host.name.toLowerCase().includes(term)) ||
        (host.ip_address && host.ip_address.toLowerCase().includes(term)) ||
        (host.public_ip && host.public_ip.toLowerCase().includes(term)) ||
        (host.internal_ip && host.internal_ip.toLowerCase().includes(term)) ||
        (host.hostname && host.hostname.toLowerCase().includes(term)) ||
        (host.os_type && host.os_type.toLowerCase().includes(term))
      )
    })
  })
})

// 监听hostSearchText变化，同步到显示
watch(() => hostSearchText.value, (newValue) => {
  if (newValue !== parseIpInput(displayHostSearchText.value)) {
    displayHostSearchText.value = formatIpDisplay(newValue)
  }
})

const totalGroupHosts = computed(() => {
  // 确保数据有效
  if (!Array.isArray(props.hosts) || !Array.isArray(selectedGroupIds.value)) {
    return 0
  }
  
  return selectedGroupIds.value.reduce((total, groupId) => {
    // 通过主机数据中的分组信息来计算
    const groupHostCount = props.hosts.filter(host => 
      host && host.groups_info && Array.isArray(host.groups_info) && 
      host.groups_info.some(g => g && g.id === groupId)
    ).length
    return total + groupHostCount
  }, 0)
})

// 动态选择的分组主机统计
const totalDynamicGroupHosts = computed(() => {
  if (!Array.isArray(props.hosts) || !Array.isArray(dynamicSelectedGroupIds.value)) {
    return 0
  }
  
  const hostIds = new Set()
  dynamicSelectedGroupIds.value.forEach(groupId => {
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        hostIds.add(host.id)
      }
    })
  })
  return hostIds.size
})

const totalDynamicAgentOnline = computed(() => {
  if (!Array.isArray(props.hosts) || !Array.isArray(dynamicSelectedGroupIds.value)) {
    return 0
  }
  
  const hostIds = new Set()
  dynamicSelectedGroupIds.value.forEach(groupId => {
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        hostIds.add(host.id)
      }
    })
  })
  
  return props.hosts.filter(host => 
    hostIds.has(host.id) && 
    host.agent_info && 
    host.agent_info.status === 'online'
  ).length
})

const totalSelectedCount = computed(() => {
  if (selectionMode.value === 'dynamic') {
    // 动态选择：返回分组内主机总数
    return totalDynamicGroupHosts.value
  }
  
  if (selectionMode.value === 'resolve') {
    // 主机解析：返回有效选中主机数量
    return validSelectedHostCount.value
  }
  
  // 静态选择：计算去重后的实际选择数量
  if (!Array.isArray(props.hosts) || !Array.isArray(selectedGroupIds.value) || !Array.isArray(selectedHostIds.value)) {
    return 0
  }
  
  // 计算去重后的实际选择数量
  const groupHostIds = new Set()
  selectedGroupIds.value.forEach(groupId => {
    // 通过主机数据中的分组信息来查找
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        groupHostIds.add(host.id)
      }
    })
  })
  
  // 分组数量 + 去重后的单独主机数量
  const deduplicatedHostCount = selectedHostIds.value.filter(hostId => !groupHostIds.has(hostId)).length
  return selectedGroupIds.value.length + deduplicatedHostCount
})

// 动态选择的分组树数据（过滤搜索）
const dynamicTreeData = computed(() => {
  // 复用静态选择的treeData逻辑，但应用动态搜索过滤
  const baseTreeData = treeData.value
  
  if (!dynamicGroupSearchText.value) {
    return baseTreeData
  }
  
  // 应用搜索过滤
  const filterTree = (nodes) => {
    return nodes.filter(node => {
      const matchesSearch = node.title.toLowerCase().includes(dynamicGroupSearchText.value.toLowerCase()) ||
                          (node.description && node.description.toLowerCase().includes(dynamicGroupSearchText.value.toLowerCase()))
      
      // 递归过滤子节点
      if (node.children && node.children.length > 0) {
        node.children = filterTree(node.children)
      }
      
      // 如果节点匹配或子节点有匹配的，保留该节点
      return matchesSearch || (node.children && node.children.length > 0)
    })
  }
  
  return filterTree(baseTreeData)
})

// 主机解析相关的计算属性
const resolvedInputCount = computed(() => resolvedHosts.value.length)

const validResolvedCount = computed(() => {
  return resolvedHosts.value.filter(h => h.status === 'valid').length
})

const invalidResolvedCount = computed(() => {
  return resolvedHosts.value.filter(h => h.status === 'not_found').length
})

// 有效选中主机数量（只统计有对应有效主机的选中项）
const validSelectedHostCount = computed(() => {
  return resolvedSelectedHostIds.value.filter(key => {
    const host = resolvedHosts.value.find(h => h.key === key)
    return host && host.host
  }).length
})

// 获取分组名称
const getGroupName = (groupId) => {
  const group = props.groups.find(g => g && g.id === groupId)
  return group?.name || `分组 ${groupId}`
}

// 获取分组内主机数量
const getGroupHostCount = (groupId) => {
  return props.hosts.filter(host => 
    host && host.groups_info && Array.isArray(host.groups_info) && 
    host.groups_info.some(g => g && g.id === groupId)
  ).length
}

// 获取分组内在线主机数量
const getGroupOnlineCount = (groupId) => {
  return props.hosts.filter(host => 
    host && host.groups_info && Array.isArray(host.groups_info) && 
    host.groups_info.some(g => g && g.id === groupId) &&
    host.status === 'online'
  ).length
}

// 获取分组内Agent在线主机数量
const getGroupAgentOnlineCount = (groupId) => {
  return props.hosts.filter(host => 
    host && host.groups_info && Array.isArray(host.groups_info) && 
    host.groups_info.some(g => g && g.id === groupId) &&
    host.agent_info && host.agent_info.status === 'online'
  ).length
}

// 获取分组内离线主机数量
const getGroupOfflineCount = (groupId) => {
  return props.hosts.filter(host => 
    host && host.groups_info && Array.isArray(host.groups_info) && 
    host.groups_info.some(g => g && g.id === groupId) &&
    host.status === 'offline'
  ).length
}

// 移除动态选择的分组
const removeDynamicGroup = (groupId) => {
  const index = dynamicSelectedGroupIds.value.indexOf(groupId)
  if (index > -1) {
    dynamicSelectedGroupIds.value.splice(index, 1)
  }
}

// 树状结构事件处理
const handleTreeExpand = (expandedKeysList, node) => {
  // 处理树的展开/收起
  expandedKeys.value = expandedKeysList
}

const handleTreeClick = (e, node) => {
  // 处理树组件的点击事件
  console.log('Tree component clicked:', e, node)
}

const handleNodeTitleClick = (nodeData) => {
  // 处理节点标题的点击事件
  console.log('Node title clicked:', nodeData)
  
  // 获取节点对应的分组ID
  const groupId = parseInt(nodeData.key)
  if (!groupId || isNaN(groupId)) {
    console.warn('HostSelector - handleNodeTitleClick: 无效的分组ID:', nodeData.key)
    return
  }
  
  console.log('HostSelector - 准备切换分组选择状态:', groupId)
  
  // 调用现有的分组选择切换函数
  toggleGroupSelection(groupId)
  
  console.log('HostSelector - 分组选择状态已更新:', selectedGroupIds.value)
}

// 分组选择相关（保留原有函数以兼容）
const toggleGroupSelection = (groupId) => {
  if (!groupId || !Array.isArray(props.groups) || !Array.isArray(props.hosts)) {
    console.warn('HostSelector - toggleGroupSelection: 参数无效')
    return
  }
  
  const group = props.groups.find(g => g && g.id === groupId)
  if (!group) {
    console.warn('HostSelector - toggleGroupSelection: 未找到分组:', groupId)
    return
  }
  
  const index = selectedGroupIds.value.indexOf(groupId)
  if (index > -1) {
    // 取消选择分组
    selectedGroupIds.value.splice(index, 1)
    
    // 取消选择属于该分组的主机
    // 通过主机数据中的分组信息来查找
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        const hostIndex = selectedHostIds.value.indexOf(host.id)
        if (hostIndex > -1) {
          selectedHostIds.value.splice(hostIndex, 1)
        }
      }
    })
  } else {
    // 选择分组
    selectedGroupIds.value.push(groupId)
    
    // 自动选择属于该分组的主机
    // 通过主机数据中的分组信息来查找
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        if (!selectedHostIds.value.includes(host.id)) {
          selectedHostIds.value.push(host.id)
        }
      }
    })
  }
}

// 主机选择相关
const selectAllHosts = () => {
  selectedHostIds.value = filteredHosts.value.map(host => host.id)
}

const selectOnlineHosts = () => {
  selectedHostIds.value = filteredHosts.value
    .filter(host => host.status === 'online')
    .map(host => host.id)
}

const selectAgentOnlineHosts = () => {
  selectedHostIds.value = filteredHosts.value
    .filter(host => host.agent_info && host.agent_info.status === 'online')
    .map(host => host.id)
}

const clearHostSelection = () => {
  selectedHostIds.value = []
}

// 点击主机表格行时切换选择状态（忽略复选框本身的点击）
const handleHostsTableRowClick = (record, index, event) => {
  // 如果点击目标是在复选框或复选框内部，忽略此处理（以免和复选框原生行为冲突）
  const target = event?.target
  if (target && (target.closest('.arco-checkbox') || target.closest('input[type="checkbox"]'))) {
    return
  }

  const hostId = record?.id
  if (!hostId) return

  const idx = selectedHostIds.value.indexOf(hostId)
  if (idx > -1) {
    selectedHostIds.value.splice(idx, 1)
  } else {
    selectedHostIds.value.push(hostId)
  }
}

// 搜索处理
const handleGroupSearch = (value) => {
  groupSearchText.value = value
}

const handleHostSearch = (value) => {
  hostSearchText.value = value
}

const selectOnline = () => {
  // 仅选择在线的主机
  selectedHostIds.value = filteredHosts.value
    .filter(h => h.status === 'online')
    .map(h => h.id)
}

// 获取去重后的主机数量
const getDeduplicatedHostCount = () => {
  if (!Array.isArray(selectedGroupIds.value) || !Array.isArray(props.hosts)) {
    return 0
  }
  
  const groupHostIds = new Set()
  selectedGroupIds.value.forEach(groupId => {
    if (!groupId) return
    
    // 通过主机数据中的分组信息来查找
    props.hosts.forEach(host => {
      if (host && host.groups_info && Array.isArray(host.groups_info) && 
          host.groups_info.some(g => g && g.id === groupId)) {
        groupHostIds.add(host.id)
      }
    })
  })
  
  return selectedHostIds.value.filter(hostId => !groupHostIds.has(hostId)).length
}

// 动态选择的分组搜索处理
const handleDynamicGroupSearch = (value) => {
  dynamicGroupSearchText.value = value
}

// 动态选择的分组节点点击处理
const handleDynamicNodeTitleClick = (nodeData) => {
  const groupId = parseInt(nodeData.key)
  if (!groupId || isNaN(groupId)) {
    console.warn('HostSelector - handleDynamicNodeTitleClick: 无效的分组ID:', nodeData.key)
    return
  }
  
  // 切换分组选择状态
  const index = dynamicSelectedGroupIds.value.indexOf(groupId)
  if (index > -1) {
    // 取消选择
    dynamicSelectedGroupIds.value.splice(index, 1)
  } else {
    // 选择分组
    dynamicSelectedGroupIds.value.push(groupId)
  }
}

// 主机解析相关方法
const handleParseHosts = async () => {
  if (!resolveInputText.value.trim()) {
    return
  }

  parsingHosts.value = true
  
  try {
    // 解析输入文本，支持多种分隔符
    const inputs = resolveInputText.value
      .split(/[,，\s\n\r]+/)
      .map(ip => ip.trim())
      .filter(ip => ip.length > 0)
    
    // 去重
    const uniqueInputs = [...new Set(inputs)]
    
    // 解析每个输入
    const results = []
    for (const input of uniqueInputs) {
      // 在主机列表中查找匹配的主机
      const matchedHost = props.hosts.find(host => {
        if (!host) return false
        return (
          host.ip_address?.toLowerCase() === input.toLowerCase() ||
          host.public_ip?.toLowerCase() === input.toLowerCase() ||
          host.internal_ip?.toLowerCase() === input.toLowerCase() ||
          host.name?.toLowerCase() === input.toLowerCase() ||
          host.hostname?.toLowerCase() === input.toLowerCase()
        )
      })
      
      if (matchedHost) {
        results.push({
          key: input,
          input: input,
          host: matchedHost,
          status: 'valid'
        })
      } else {
        results.push({
          key: input,
          input: input,
          host: null,
          status: 'not_found'
        })
      }
    }
    
    resolvedHosts.value = results
    // 默认全选有效主机
    resolvedSelectedHostIds.value = results
      .filter(h => h.status === 'valid')
      .map(h => h.key)
      
  } catch (error) {
    console.error('解析主机失败:', error)
  } finally {
    parsingHosts.value = false
  }
}

const clearResolveInput = () => {
  resolveInputText.value = ''
  resolvedHosts.value = []
  resolvedSelectedHostIds.value = []
}

const selectAllResolvedHosts = () => {
  resolvedSelectedHostIds.value = resolvedHosts.value.map(h => h.key)
}

const selectNoneResolvedHosts = () => {
  resolvedSelectedHostIds.value = []
}

const selectValidResolvedHosts = () => {
  resolvedSelectedHostIds.value = resolvedHosts.value
    .filter(h => h.status === 'valid')
    .map(h => h.key)
}

const confirmAndLoadResolvedHosts = () => {
  // 将解析结果中选中的有效主机添加到静态选择列表
  const hostsToAdd = resolvedHosts.value
    .filter(h => resolvedSelectedHostIds.value.includes(h.key) && h.host)
    
  hostsToAdd.forEach(h => {
    if (!selectedHostIds.value.includes(h.host.id)) {
      selectedHostIds.value.push(h.host.id)
    }
  })
  
  // 切换到静态选择模式
  selectionMode.value = 'static'
  
  // 清理解析结果
  clearResolveInput()
  
  // 显示成功提示
  if (hostsToAdd.length > 0) {
    Message.success(`已加载 ${hostsToAdd.length} 台主机到目标列表`)
  }
}

// 确认选择
const handleConfirm = () => {
  if (selectionMode.value === 'static') {
    // 静态选择：传递主机ID和分组ID（分组会在前端展开为主机ID）
    emit('confirm', {
      selection_type: 'static',
      selectedHosts: selectedHostIds.value,
      selectedGroups: selectedGroupIds.value
    })
  } else if (selectionMode.value === 'resolve') {
    // 主机解析：传递解析选择的主机
    const resolvedHostIds = resolvedHosts.value
      .filter(h => resolvedSelectedHostIds.value.includes(h.key) && h.host)
      .map(h => h.host.id)
    emit('confirm', {
      selection_type: 'static',
      selectedHosts: resolvedHostIds,
      selectedGroups: []
    })
  } else {
    // 动态选择：只传递分组ID，后端执行时动态获取分组内的所有主机
    emit('confirm', {
      selection_type: 'dynamic',
      selectedGroups: dynamicSelectedGroupIds.value
    })
  }
  visible.value = false
}

// 取消选择
const handleCancel = () => {
  visible.value = false
}

// 工具函数
const getHostStatusColor = (status) => {
  const colors = {
    'online': 'green',
    'offline': 'red',
    'unknown': 'gray'
  }
  return colors[status] || 'gray'
}

const getHostStatusText = (status) => {
  const texts = {
    'online': '正常',
    'offline': '离线',
    'unknown': '未知'
  }
  return texts[status] || status
}

const getAgentStatusColor = (status) => {
  const colors = {
    'pending': 'orange',
    'online': 'green',
    'offline': 'red',
    'disabled': 'gray'
  }
  return colors[status] || 'gray'
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 组件挂载后的初始化
onMounted(() => {
  console.log('HostSelector - 组件已挂载')
  console.log('HostSelector - 挂载时的props.groups:', props.groups)
  console.log('HostSelector - 挂载时的props.hosts:', props.hosts)
  
  // 确保在组件挂载后初始化展开状态
  if (Array.isArray(props.groups) && props.groups.length > 0) {
    initializeExpandedKeys()
  } else {
    console.log('HostSelector - 挂载时分组数据无效或为空，跳过初始化')
  }
})
</script>

<style scoped>
/* 主机选择器样式 */
.host-selector-modal {
  .arco-modal-body {
    padding: 0;
    height: 80vh;
    max-height: 800px;
  }
}

.selector-content {
  display: flex;
  height: 100%;
  gap: 0;
}

/* 左侧分组面板 */
.groups-panel {
  width: 320px;
  border-right: 1px solid #e8e8e8;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.panel-header {
  padding: 12px 16px; /* 减少内边距 */
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.panel-header h4 {
  margin: 0;
  font-size: 15px; /* 减少字体大小 */
  font-weight: 600;
  color: #262626;
}

.group-count, .host-count {
  font-size: 11px; /* 减少字体大小 */
  color: #666;
  background-color: #f0f0f0;
  padding: 1px 6px; /* 减少内边距 */
  border-radius: 8px; /* 减少圆角 */
}

/* 搜索容器 */
.search-container {
  padding: 12px 16px; /* 减少内边距 */
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  flex-shrink: 0;
}

.search-container :deep(.arco-textarea-wrapper) {
  border-radius: 4px;
  transition: border-color 0.2s;
}

.search-container :deep(.arco-textarea-wrapper:hover) {
  border-color: #4080ff;
}

.search-container :deep(.arco-textarea-wrapper:focus-within) {
  border-color: #4080ff;
  box-shadow: 0 0 0 2px rgba(64, 128, 255, 0.1);
}

.search-container :deep(.arco-textarea) {
  font-size: 12px;
  line-height: 1.4;
  resize: vertical;
}

/* 分组树容器 */
.groups-tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 4px; /* 进一步减少内边距 */
}

/* 分组树 */
.groups-tree {
  font-size: 12px; /* 进一步减少字体大小 */
  color: #262626;
}

.groups-tree :deep(.arco-tree-node-content) {
  padding: 6px 0; /* 进一步减少内边距 */
}

.groups-tree :deep(.arco-tree-node-content-inner) {
  display: flex;
  align-items: center;
  gap: 8px; /* 进一步减少间距 */
}

.tree-node-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.node-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px; /* 进一步减少间距 */
}

.node-name {
  font-weight: 600;
  line-height: 1.1; /* 进一步减少行高 */
}

.node-description {
  font-size: 9px; /* 进一步减少字体大小 */
  color: #666;
  line-height: 1.1; /* 进一步减少行高 */
}

.node-stats {
  display: flex;
  gap: 6px; /* 进一步减少间距 */
  align-items: center;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0px; /* 进一步减少间距 */
}

.stat-number {
  font-size: 12px; /* 进一步减少字体大小 */
  font-weight: 600;
  color: #1890ff;
}

.stat-label {
  font-size: 9px; /* 进一步减少字体大小 */
  color: #666;
}

/* 右侧主机面板 */
.hosts-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  overflow: hidden;
}

/* 操作按钮 */
.action-buttons {
  padding: 12px 20px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 主机表格 */
.hosts-table {
  flex: 1;
  overflow: hidden;
}

/* 表格行高优化 */
.hosts-table :deep(.arco-table-tr) {
  height: 40px; /* 进一步减少行高 */
}

.hosts-table :deep(.arco-table-td) {
  padding: 4px 10px; /* 进一步减少单元格内边距 */
  vertical-align: middle;
}

/* 复选框列优化 */
.hosts-table :deep(.arco-table-selection) {
  width: 50px; /* 固定复选框列宽度 */
}

.hosts-table :deep(.arco-checkbox) {
  margin: 0;
  padding: 0;
}

.hosts-table :deep(.arco-checkbox-wrapper) {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* 主机名称单元格样式 */
.host-name-cell {
  display: flex;
  flex-direction: column;
  gap: 0px; /* 减少间距 */
  padding: 1px 0; /* 减少内边距 */
}

.host-name {
  font-size: 12px;
  font-weight: 500;
  color: #262626;
  line-height: 1.1; /* 减少行高 */
}

.host-ip {
  font-size: 10px;
  color: #666;
  line-height: 1.1; /* 减少行高 */
}

/* 状态标签样式优化 */
.status-tag {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 20px; /* 减少高度 */
  padding: 0 6px;
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.status-dot.status-online {
  background-color: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
}

.status-dot.status-offline {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2);
}

.status-dot.status-unknown {
  background-color: #d9d9d9;
  box-shadow: 0 0 0 2px rgba(217, 217, 217, 0.2);
}

/* Agent状态标签样式 */
.agent-status-cell {
  display: flex;
  align-items: center;
}

.agent-status-tag {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 20px;
  padding: 0 6px;
}

.agent-status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.agent-status-dot.agent-status-pending {
  background-color: #ff9800;
  box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.2);
}

.agent-status-dot.agent-status-online {
  background-color: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
}

.agent-status-dot.agent-status-offline {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2);
}

.agent-status-dot.agent-status-disabled {
  background-color: #d9d9d9;
  box-shadow: 0 0 0 2px rgba(217, 217, 217, 0.2);
}

/* 分组标签样式 */
.groups-display {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  align-items: center;
}

.group-tag {
  margin: 0;
  height: 18px;
  padding: 0 5px;
  font-size: 10px;
  line-height: 16px;
  border-radius: 3px;
}

/* 选择统计 */
.selection-summary {
  padding: 12px 16px; /* 减少内边距 */
  border-top: 1px solid #e8e8e8;
  background-color: #fafafa;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.summary-info {
  display: flex;
  gap: 12px; /* 减少间距 */
  align-items: center;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 4px; /* 减少间距 */
  font-size: 12px; /* 减少字体大小 */
  color: #666;
}

.summary-count {
  font-weight: 600;
  color: #1890ff;
}

.summary-total {
  font-size: 13px; /* 减少字体大小 */
  font-weight: 600;
}

/* 滚动条样式 */
.groups-tree-container::-webkit-scrollbar,
.hosts-table::-webkit-scrollbar {
  width: 6px;
}

.groups-tree-container::-webkit-scrollbar-track,
.hosts-table::-webkit-scrollbar-track {
  background-color: #f1f1f1;
  border-radius: 3px;
}

.groups-tree-container::-webkit-scrollbar-thumb,
.hosts-table::-webkit-scrollbar-thumb {
  background-color: #c1c1c1;
  border-radius: 3px;
}

.groups-tree-container::-webkit-scrollbar-thumb:hover,
.hosts-table::-webkit-scrollbar-thumb:hover {
  background-color: #a8a8a8;
}

/* 树状结构特定样式 */
.groups-tree :deep(.arco-tree-node) {
  margin-bottom: 2px;
}

.groups-tree :deep(.arco-tree-node-content) {
  border-radius: 6px;
  transition: all 0.2s ease;
  cursor: pointer;
  padding: 8px 12px;
  border: 1px solid transparent;
}

.groups-tree :deep(.arco-tree-node-content:hover) {
  background-color: #f0f9ff;
  border-color: #91d5ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
}

.groups-tree :deep(.arco-tree-node-selected .arco-tree-node-content) {
  background-color: #e6f7ff;
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.2);
}

.groups-tree :deep(.arco-tree-node-indent) {
  width: 16px;
}

.groups-tree :deep(.arco-tree-switcher) {
  width: 16px;
  height: 16px;
  margin-right: 4px;
  cursor: pointer;
  color: #666;
  transition: color 0.2s ease;
}

.groups-tree :deep(.arco-tree-switcher:hover) {
  color: #1890ff;
}

/* 树节点内容样式 */
.tree-node-content {
  animation: fadeInUp 0.3s ease-out;
  cursor: pointer;
  user-select: none;
}

.tree-node-content:hover {
  transform: translateY(-1px);
}

.tree-node-content:active {
  transform: translateY(0);
}

/* 动画效果 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 工具类 */
.text-gray-400 {
  color: #9ca3af;
}

.text-gray-500 {
  color: #6b7280;
}

.text-gray-600 {
  color: #4b5563;
}

.text-sm {
  font-size: 12px;
}

.mb-3 {
  margin-bottom: 12px;
}

/* 动态选择面板样式 */
.dynamic-selection-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.dynamic-selection-help {
  margin-bottom: 16px;
}

.dynamic-selection-help :deep(.arco-alert) {
  font-size: 12px;
}

/* 搜索和操作栏 */
.search-and-action-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}

.group-search-input {
  flex: 1;
}

/* 内联主机解析面板样式 */
.resolve-panel-inline {
  margin-bottom: 16px;
  padding: 12px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
}

.resolve-panel-inline .resolve-input-section {
  margin-bottom: 12px;
}

.resolve-panel-inline .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resolve-panel-inline .section-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}

.resolve-panel-inline .resolve-stats {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.resolve-panel-inline .resolve-result-section {
  margin-bottom: 12px;
}

.resolve-panel-inline .resolve-result-section .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resolve-panel-inline .resolve-result-section .section-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}

.resolve-panel-inline .resolved-hosts-table {
  max-height: 300px;
  overflow-y: auto;
}

.resolve-panel-inline .resolve-action-bar {
  display: flex;
  justify-content: flex-end;
  padding: 8px 0;
  border-top: 1px solid var(--color-border-2);
  margin-top: 8px;
}

.resolve-panel-inline .resolve-help {
  padding: 8px;
}

.resolve-panel-inline .resolve-help :deep(.arco-alert) {
  font-size: 12px;
}

/* 已选分组详情样式 */
.selected-groups-detail {
  margin-top: 16px;
  padding: 12px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
}

.detail-header {
  margin-bottom: 12px;
}

.detail-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-detail-card {
  padding: 12px;
  background-color: #fff;
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
}

.group-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.group-detail-header .group-name {
  font-weight: 600;
  font-size: 13px;
  color: #262626;
}

.group-stats-row {
  display: flex;
  gap: 16px;
}

.stat-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-badge .stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1890ff;
}

.stat-badge .stat-label {
  font-size: 11px;
  color: #666;
}

/* 主机解析面板样式 */
.resolve-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.resolve-input-section {
  margin-bottom: 16px;
}

.resolve-input-section .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resolve-input-section .section-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.resolve-stats {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.resolve-result-section {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.resolve-result-section .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.resolve-result-section .section-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.resolved-hosts-table {
  flex: 1;
  overflow: hidden;
}

.resolve-confirm-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background-color: var(--color-primary-light-1);
  border-radius: 4px;
  margin-top: 8px;
}

.confirm-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-1);
}

.resolve-help {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resolve-help :deep(.arco-alert) {
  max-width: 600px;
}
</style>