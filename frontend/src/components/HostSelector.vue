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
      <!-- 主要内容区域：左右分栏 -->
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
              <a-table-column title="IPv6" data-index="ipv6" width="100">
                <template #cell="{ record }">
                  <span class="text-gray-400">--</span>
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

      <!-- 选择统计 -->
      <div class="selection-summary">
        <div class="summary-info">
          <div class="summary-item">
            <span>已选择分组:</span>
            <span class="summary-count">{{ selectedGroupIds.length }}</span>
          </div>
          <div class="summary-item" v-if="totalGroupHosts > 0">
            <span>分组内主机:</span>
            <span class="summary-count">{{ totalGroupHosts }}</span>
          </div>
          <div class="summary-item">
            <span>已选择主机:</span>
            <span class="summary-count">{{ selectedHostIds.length }}</span>
          </div>
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
          :disabled="selectedGroupIds.length === 0 && selectedHostIds.length === 0"
        >
          确定 ({{ totalSelectedCount }})
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { 
  IconSearch, 
  IconCheckSquare, 
  IconWifi, 
  IconCloseCircle 
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

// 响应式数据
const selectedHostIds = ref([...props.selectedHosts])
const selectedGroupIds = ref([...props.selectedGroups])

// 搜索相关
const groupSearchText = ref('')
const hostSearchText = ref('')
const displayHostSearchText = ref('')


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
        const node = {
          key: group.id,
          title: group.name || `分组${group.id}`,
          description: group.description || '',
          online_count: group.online_count || 0,
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

const totalSelectedCount = computed(() => {
  // 确保数据有效
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

const clearHostSelection = () => {
  selectedHostIds.value = []
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

// 确认选择
const handleConfirm = () => {
  emit('confirm', {
    selectedHosts: selectedHostIds.value,
    selectedGroups: selectedGroupIds.value
  })
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
</style>
