<template>
  <div 
    class="hosts-page"
    v-page-permissions="{ 
      resourceType: 'host', 
      permissions: ['view', 'add', 'change', 'delete', 'execute'],
      resourceIds: hosts.map(h => h.id)
    }"
  >
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>主机管理</h2>
          <p class="header-desc">管理主机资源和分组信息</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button @click="refreshAll">
              <template #icon>
                <icon-refresh />
              </template>
              刷新
            </a-button>
            <a-button 
              v-permission="{ resourceType: 'host', permission: 'add' }"
              @click="handleCreateGroup"
            >
              <template #icon>
                <icon-folder-add />
              </template>
              新增分组
            </a-button>
            <a-button 
              v-permission="{ resourceType: 'host', permission: 'add' }"
              type="primary" 
              @click="handleCreate"
            >
              <template #icon>
                <icon-plus />
              </template>
              新增主机
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <div class="hosts-content">
      <!-- 左侧分组面板 -->
      <div class="groups-panel" :style="{ width: sidebarWidth + 'px' }">
        <a-card title="主机分组" size="small">
          <template #extra>
            <a-button type="text" size="small" @click="refreshGroups">
              <template #icon>
                <icon-refresh />
              </template>
            </a-button>
          </template>

          <div class="group-list">
            <!-- 全部主机 -->
            <div
              class="group-item"
              :class="{ active: selectedGroupId === null }"
              @click="selectGroup(null)"
            >
              <div class="group-info">
                <icon-desktop class="group-icon" />
                <span class="group-name">全部主机</span>
              </div>
              <span class="group-count">{{ totalHostCount }}</span>
            </div>

            <!-- 树形分组列表 -->
            <HostGroupTree
              :groups="hostGroupTree"
              :selected-group-id="selectedGroupId"
              :expanded-groups="expandedGroups"
              @select-group="selectGroup"
              @toggle-expand="toggleGroupExpand"
              @edit-group="handleEditGroup"
              @delete-group="handleDeleteGroup"
              @add-subgroup="handleAddSubgroup"
              @test-connection="handleTestGroupConnection"
            />
          </div>
        </a-card>
      </div>

      <!-- 可拖拽的分隔条 -->
      <div
        class="resize-handle"
        @mousedown="startResize"
        :class="{ 'resizing': isResizing }"
        title="拖拽调整分组面板宽度"
      >
        <div class="resize-line"></div>
        <div class="resize-dots">
          <div class="dot"></div>
          <div class="dot"></div>
          <div class="dot"></div>
        </div>
      </div>

      <!-- 右侧主机列表 -->
      <div class="hosts-main">
        <!-- 搜索筛选 -->
        <a-card class="mb-4">
          <!-- 基础搜索栏 -->
          <div class="search-container">
            <div class="search-form">
              <a-form :model="searchForm" layout="inline" class="mb-3">
                <!-- 第一行：主机名称和IP地址 -->
                <div class="search-row">
                  <a-form-item label="主机名称">
                    <a-input
                      v-model="searchForm.name"
                      placeholder="请输入主机名称"
                      allow-clear
                      @press-enter="handleSearch"
                      style="width: 200px"
                    />
                  </a-form-item>
                  <a-form-item label="IP地址">
                    <a-textarea
                      v-model="displayIpAddress"
                      placeholder="支持多IP搜索，可直接粘贴多行IP地址"
                      allow-clear
                      @press-enter="handleSearch"
                      @paste="handleIpPaste"
                      @input="handleIpInput"
                      :auto-size="{ minRows: 1, maxRows: 6 }"
                      style="width: 320px"
                    />
                  </a-form-item>
                </div>
                <!-- 第二行：操作系统和状态 -->
                <div class="search-row">
                  <a-form-item label="操作系统">
                    <a-select
                      v-model="searchForm.os_type"
                      placeholder="请选择操作系统"
                      allow-clear
                      @change="handleSearch"
                      @clear="handleSearch"
                      style="width: 140px"
                    >
                      <a-option value="linux">Linux</a-option>
                      <a-option value="windows">Windows</a-option>
                      <a-option value="aix">AIX</a-option>
                      <a-option value="solaris">Solaris</a-option>
                    </a-select>
                  </a-form-item>
                  <a-form-item label="状态">
                    <a-select
                      v-model="searchForm.status"
                      placeholder="请选择状态"
                      allow-clear
                      @change="handleSearch"
                      @clear="handleSearch"
                      style="width: 120px"
                    >
                      <a-option value="online">在线</a-option>
                      <a-option value="offline">离线</a-option>
                      <a-option value="unknown">未知</a-option>
                    </a-select>
                  </a-form-item>
                </div>
              </a-form>
            </div>
            <div class="search-actions">
              <a-space>
                <a-button type="primary" @click="handleSearch">
                  <template #icon>
                    <icon-search />
                  </template>
                  搜索
                </a-button>
                <a-button @click="handleReset">
                  <template #icon>
                    <icon-refresh />
                  </template>
                  重置
                </a-button>
                <a-button type="text" @click="toggleAdvancedFilter">
                  <template #icon>
                    <icon-filter />
                  </template>
                  高级筛选
                  <icon-down v-if="!showAdvancedFilter" />
                  <icon-up v-else />
                </a-button>
              </a-space>
            </div>
          </div>

          <!-- 高级筛选栏 -->
          <div v-if="showAdvancedFilter" class="advanced-filter">
            <a-divider orientation="left">高级筛选</a-divider>
            <a-form :model="advancedForm" layout="inline">
              <a-form-item label="云厂商">
                <a-select
                  v-model="advancedForm.cloud_provider"
                  placeholder="请选择云厂商"
                  allow-clear
                  @change="handleSearch"
                  @clear="handleSearch"
                  style="width: 140px"
                >
                  <a-option value="aliyun">阿里云</a-option>
                  <a-option value="tencent">腾讯云</a-option>
                  <a-option value="aws">AWS</a-option>
                  <a-option value="azure">Azure</a-option>
                  <a-option value="huawei">华为云</a-option>
                  <a-option value="baidu">百度云</a-option>
                  <a-option value="ucloud">UCloud</a-option>
                  <a-option value="qiniu">七牛云</a-option>
                  <a-option value="idc">自建机房</a-option>
                  <a-option value="other">其他</a-option>
                </a-select>
              </a-form-item>
              <a-form-item label="内网IP">
                <a-textarea
                  v-model="displayInternalIp"
                  placeholder="支持多IP，可直接粘贴多行IP地址"
                  allow-clear
                  @press-enter="handleSearch"
                  @paste="handleInternalIpPaste"
                  @input="handleInternalIpInput"
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  style="width: 220px"
                />
              </a-form-item>
              <a-form-item label="外网IP">
                <a-textarea
                  v-model="displayPublicIp"
                  placeholder="支持多IP，可直接粘贴多行IP地址"
                  allow-clear
                  @press-enter="handleSearch"
                  @paste="handlePublicIpPaste"
                  @input="handlePublicIpInput"
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  style="width: 220px"
                />
              </a-form-item>
              <a-form-item label="操作系统版本">
                <a-input
                  v-model="advancedForm.os_version"
                  placeholder="请输入系统版本"
                  allow-clear
                  @press-enter="handleSearch"
                  style="width: 160px"
                />
              </a-form-item>
              <a-form-item label="认证方式">
                <a-select
                  v-model="advancedForm.auth_method"
                  placeholder="请选择认证方式"
                  allow-clear
                  @change="handleSearch"
                  @clear="handleSearch"
                  style="width: 140px"
                >
                  <a-option value="password">密码认证</a-option>
                  <a-option value="key">密钥认证</a-option>
                  <a-option value="key_password">密钥+密码</a-option>
                </a-select>
              </a-form-item>
              <a-form-item label="地域">
                <a-input
                  v-model="advancedForm.region"
                  placeholder="请输入地域"
                  allow-clear
                  @press-enter="handleSearch"
                  style="width: 140px"
                />
              </a-form-item>
              <a-form-item label="可用区">
                <a-input
                  v-model="advancedForm.zone"
                  placeholder="请输入可用区"
                  allow-clear
                  @press-enter="handleSearch"
                  style="width: 140px"
                />
              </a-form-item>
            </a-form>
          </div>

          <!-- 高级筛选下方的操作按钮 -->
          <div class="advanced-actions" v-if="showAdvancedFilter">
            <div class="advanced-actions-right">
              <a-space>
                <a-button
                  v-permission="{ resourceType: 'host', permission: 'execute' }"
                  @click="handleBatchTest"
                  :disabled="selectedRowKeys.length === 0"
                  :loading="batchTesting"
                >
                  <template #icon>
                    <icon-wifi />
                  </template>
                  批量测试连接 ({{ selectedRowKeys.length }})
                </a-button>
                <a-dropdown @select="handleCloudSync">
                  <a-button
                    v-permission="{ resourceType: 'host', permission: 'add' }"
                    :loading="cloudSyncing"
                  >
                    <template #icon>
                      <icon-cloud />
                    </template>
                    云同步
                    <icon-down />
                  </a-button>
                  <template #content>
                    <a-doption value="aliyun">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      阿里云
                    </a-doption>
                    <a-doption value="tencent">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      腾讯云
                    </a-doption>
                    <a-doption value="aws">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      AWS
                    </a-doption>
                  </template>
                </a-dropdown>
              </a-space>
            </div>
          </div>

          <!-- 基础状态下的操作按钮（右对齐） -->
          <div class="basic-actions" v-if="!showAdvancedFilter">
            <div class="basic-actions-right">
              <a-space>
                <a-button
                  v-permission="{ resourceType: 'host', permission: 'execute' }"
                  @click="handleBatchTest"
                  :disabled="selectedRowKeys.length === 0"
                  :loading="batchTesting"
                >
                  <template #icon>
                    <icon-wifi />
                  </template>
                  批量测试连接 ({{ selectedRowKeys.length }})
                </a-button>
                <a-dropdown @select="handleCloudSync">
                  <a-button
                    v-permission="{ resourceType: 'host', permission: 'add' }"
                    :loading="cloudSyncing"
                  >
                    <template #icon>
                      <icon-cloud />
                    </template>
                    云同步
                    <icon-down />
                  </a-button>
                  <template #content>
                    <a-doption value="aliyun">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      阿里云
                    </a-doption>
                    <a-doption value="tencent">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      腾讯云
                    </a-doption>
                    <a-doption value="aws">
                      <template #icon>
                        <icon-cloud />
                      </template>
                      AWS
                    </a-doption>
                  </template>
                </a-dropdown>
              </a-space>
            </div>
          </div>
        </a-card>

        <a-card>
          <!-- 批量操作区域 -->
          <div class="batch-actions">
            <a-alert
              v-if="selectedRowKeys.length > 0"
              type="info"
              :message="`已选择 ${selectedRowKeys.length} 个主机`"
              show-icon
              closable
              @close="clearSelection"
            >
              <template #action>
                <a-space>
                  <a-dropdown>
                    <a-button 
                      v-permission="{ resourceType: 'host', permission: 'change' }"
                      type="primary" 
                      size="small"
                    >
                      <template #icon>
                        <icon-swap />
                      </template>
                      移动到分组
                      <icon-down />
                    </a-button>
                    <template #content>
                      <a-doption
                        v-for="group in hostGroups"
                        :key="group.id"
                        @click="handleBatchMoveToGroup(group.id)"
                      >
                        {{ group.name }}
                      </a-doption>
                      <a-doption @click="handleBatchMoveToGroup(null)">
                        移出所有分组
                      </a-doption>
                    </template>
                  </a-dropdown>
                  <a-button 
                    v-permission="{ resourceType: 'host', permission: 'execute' }"
                    size="small" 
                    @click="handleBatchTest"
                  >
                    <template #icon>
                      <icon-wifi />
                    </template>
                    批量测试
                  </a-button>
                  <a-popconfirm
                    content="确定要删除选中的主机吗？"
                    @ok="handleBatchDelete"
                  >
                    <a-button 
                      v-permission="{ resourceType: 'host', permission: 'delete' }"
                      size="small" 
                      status="danger"
                    >
                      <template #icon>
                        <icon-delete />
                      </template>
                      批量删除
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </a-alert>
            
            <!-- 页面选择操作 -->
            <div v-if="hosts.length > 0" class="page-selection-actions">
              <a-space>
                <a-button 
                  v-if="!isAllCurrentPageSelected"
                  size="small" 
                  @click="selectAllCurrentPage"
                >
                  <template #icon>
                    <icon-check-square />
                  </template>
                  全选当前页 ({{ hosts.length }})
                </a-button>
                <a-button 
                  v-if="selectedRowKeys.length > 0"
                  size="small" 
                  @click="clearSelection"
                >
                  <template #icon>
                    <icon-close-circle />
                  </template>
                  清空选择
                </a-button>
              </a-space>
            </div>
          </div>

          <a-table
            :columns="columns"
            :data="hosts"
            :loading="loading"
            :pagination="pagination"
            v-model:selectedKeys="selectedRowKeys" :row-selection="{ type: 'checkbox' }"
            row-key="id"
            @page-change="handlePageChange"
            @page-size-change="handlePageSizeChange"
          >
        <template #os_type="{ record }">
          <a-tag :class="`os-${record.os_type}`" size="small">
            {{ getOSText(record.os_type) }}
          </a-tag>
        </template>

        <template #status="{ record }">
          <a-tag :color="record.status === 'online' ? 'green' : 'red'">
            {{ record.status === 'online' ? '在线' : '离线' }}
          </a-tag>
        </template>

        <template #groups="{ record }">
          <div v-if="record.groups_info && record.groups_info.length > 0">
            <a-tag
              v-for="group in record.groups_info"
              :key="group.id"
              color="blue"
              size="small"
              class="mr-1 mb-1"
            >
              {{ group.name }}
            </a-tag>
          </div>
          <span v-else class="text-gray-400">未分组</span>
        </template>

        <template #cloud_provider="{ record }">
          <a-tag v-if="record.cloud_provider_display" color="green" size="small">
            {{ record.cloud_provider_display }}
          </a-tag>
          <span v-else class="text-gray-400">--</span>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              v-permission="{ resourceType: 'host', permission: 'execute', resourceId: record.id }"
              type="text"
              size="small"
              @click="handleTest(record)"
              :loading="record.testing"
            >
              <template #icon>
                <icon-wifi />
              </template>
              测试连接
            </a-button>
            <a-button
              v-permission="{ resourceType: 'host', permission: 'view', resourceId: record.id }"
              type="text"
              size="small"
              @click="handleView(record)"
            >
              <template #icon>
                <icon-eye />
              </template>
              查看
            </a-button>
            <a-dropdown>
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  v-permission="{ resourceType: 'host', permission: 'change', resourceId: record.id }"
                  @click="handleEdit(record)"
                >
                  <template #icon>
                    <icon-edit />
                  </template>
                  编辑
                </a-doption>
                <a-divider style="margin: 4px 0;" />
                <a-doption
                  v-permission="{ resourceType: 'host', permission: 'delete', resourceId: record.id }"
                  @click="handleDelete(record)"
                  class="danger"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  删除
                </a-doption>
              </template>
            </a-dropdown>
          </a-space>
        </template>
      </a-table>
        </a-card>
      </div>
    </div>

    <!-- 主机表单弹窗 -->
    <HostForm
      ref="hostFormRef"
      v-model:visible="formVisible"
      :host="currentHost"
      @success="handleFormSuccess"
    />

    <!-- 分组表单 -->
    <HostGroupForm
      v-model:visible="groupFormVisible"
      :group="currentGroup"
      :parent-group="parentGroupForAdd"
      @success="handleGroupFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { hostApi, hostGroupApi } from '@/api/ops'
import type { Host, HostGroup } from '@/types'
import { useAuthStore } from '@/stores/auth'
import HostForm from './components/HostForm.vue'
import HostGroupTree from './components/HostGroupTree.vue'
import HostGroupForm from './components/HostGroupForm.vue'

const router = useRouter()
const loading = ref(false)
const hosts = ref<Host[]>([])
const formVisible = ref(false)
const currentHost = ref<Host | null>(null)

// 分组表单相关
const groupFormVisible = ref(false)
const currentGroup = ref<HostGroup | null>(null)
const parentGroupForAdd = ref<HostGroup | null>(null)

// 组件引用
const hostFormRef = ref()

// 分组相关
const hostGroups = ref<HostGroup[]>([])
const hostGroupTree = ref<HostGroup[]>([])
const selectedGroupId = ref<number | null>(null)
const totalHostCount = ref(0)
const expandedGroups = ref<number[]>([])

// 批量操作相关
const selectedRowKeys = ref<number[]>([])
const batchTesting = ref(false)
const cloudSyncing = ref(false)

// 搜索表单
const searchForm = reactive({
  name: '',
  ip_address: '',
  os_type: '',
  status: '',
})

// IP地址显示格式化
const displayIpAddress = ref('')
const displayInternalIp = ref('')
const displayPublicIp = ref('')



// 格式化IP地址显示 - 多行显示策略
const formatIpDisplay = (ipString: string) => {
  if (!ipString) return ''

  const ipList = ipString
    .split(/[,，\s\n\r]+/)
    .map(ip => ip.trim())
    .filter(ip => ip.length > 0)

  if (ipList.length <= 1) {
    return ipString
  }

  // 多IP时，每行显示3-4个IP，用空格分隔
  const result = []
  for (let i = 0; i < ipList.length; i += 4) {
    const lineIps = ipList.slice(i, i + 4)
    result.push(lineIps.join(' '))
  }

  return result.join('\n')
}

// 解析IP地址输入
const parseIpInput = (input: string) => {
  if (!input) return ''

  // 将多行内容转换为空格分隔的单行，供后端搜索使用
  return input
    .split(/[\n\r]+/)
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .join(' ')
}

// 处理IP粘贴事件
const handleIpPaste = (event: ClipboardEvent) => {
  event.preventDefault()
  const pastedText = event.clipboardData?.getData('text') || ''

  if (pastedText) {
    const formattedText = formatIpDisplay(pastedText)
    displayIpAddress.value = formattedText
    searchForm.ip_address = parseIpInput(formattedText)
  }
}

// 处理IP输入事件
const handleIpInput = (value: string) => {
  displayIpAddress.value = value
  searchForm.ip_address = parseIpInput(value)
}

// 处理内网IP粘贴事件
const handleInternalIpPaste = (event: ClipboardEvent) => {
  event.preventDefault()
  const pastedText = event.clipboardData?.getData('text') || ''

  if (pastedText) {
    const formattedText = formatIpDisplay(pastedText)
    displayInternalIp.value = formattedText
    advancedForm.internal_ip = parseIpInput(formattedText)

  }
}

// 处理内网IP输入事件
const handleInternalIpInput = (value: string) => {
  displayInternalIp.value = value
  advancedForm.internal_ip = parseIpInput(value)

}

// 处理外网IP粘贴事件
const handlePublicIpPaste = (event: ClipboardEvent) => {
  event.preventDefault()
  const pastedText = event.clipboardData?.getData('text') || ''

  if (pastedText) {
    const formattedText = formatIpDisplay(pastedText)
    displayPublicIp.value = formattedText
    advancedForm.public_ip = parseIpInput(formattedText)

  }
}

// 处理外网IP输入事件
const handlePublicIpInput = (value: string) => {
  displayPublicIp.value = value
  advancedForm.public_ip = parseIpInput(value)

}

// 监听表单变化，同步到显示
watch(() => searchForm.ip_address, (newValue) => {
  if (newValue !== parseIpInput(displayIpAddress.value)) {
    displayIpAddress.value = formatIpDisplay(newValue)
  }
})

watch(() => advancedForm.internal_ip, (newValue) => {
  if (newValue !== parseIpInput(displayInternalIp.value)) {
    displayInternalIp.value = formatIpDisplay(newValue)
  }
})

watch(() => advancedForm.public_ip, (newValue) => {
  if (newValue !== parseIpInput(displayPublicIp.value)) {
    displayPublicIp.value = formatIpDisplay(newValue)
  }
})

// 高级筛选表单
const advancedForm = reactive({
  cloud_provider: '',
  internal_ip: '',
  public_ip: '',
  os_version: '',
  auth_method: '',
  region: '',
  zone: '',
})

// 高级筛选显示状态
const showAdvancedFilter = ref(false)

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: ['10', '20', '50', '100']
})

const columns = [
  {
    title: '主机名',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: 'IP地址',
    dataIndex: 'ip_address',
    key: 'ip_address',
  },
  {
    title: '端口',
    dataIndex: 'port',
    key: 'port',
  },
  {
    title: '操作系统',
    dataIndex: 'os_type',
    key: 'os_type',
    slotName: 'os_type',
  },
  {
    title: '用户名',
    dataIndex: 'username',
    key: 'username',
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    slotName: 'status',
  },
  {
    title: '所属分组',
    dataIndex: 'groups_info',
    key: 'groups_info',
    slotName: 'groups',
  },
  {
    title: '云厂商',
    dataIndex: 'cloud_provider_display',
    key: 'cloud_provider_display',
    slotName: 'cloud_provider',
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
  },
]



// 获取主机列表
const fetchHosts = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }

    // 构建搜索参数
    const searchTerms = []
    if (searchForm.name) searchTerms.push(searchForm.name)

    // 处理多IP搜索 - 支持逗号、空格、换行符分隔
    if (searchForm.ip_address) {
      const ipList = searchForm.ip_address
        .split(/[,，\s\n\r]+/)  // 支持中英文逗号、空格、换行符分隔
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)

      if (ipList.length > 0) {
        searchTerms.push(...ipList)
      }
    }

    // 添加OS类型筛选
    if (searchForm.os_type) {
      params.os_type = searchForm.os_type
    }

    // 添加状态筛选
    if (searchForm.status) {
      params.status = searchForm.status
    }

    // 添加高级筛选参数
    if (advancedForm.cloud_provider) {
      params.cloud_provider = advancedForm.cloud_provider
    }

    // 处理内网IP多IP搜索
    if (advancedForm.internal_ip) {
      const internalIpList = advancedForm.internal_ip
        .split(/[,，\s\n\r]+/)  // 支持换行符
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)

      if (internalIpList.length > 0) {
        // 将多个IP添加到搜索词中
        searchTerms.push(...internalIpList)
      }
    }

    // 处理外网IP多IP搜索
    if (advancedForm.public_ip) {
      const publicIpList = advancedForm.public_ip
        .split(/[,，\s\n\r]+/)  // 支持换行符
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)

      if (publicIpList.length > 0) {
        // 将多个IP添加到搜索词中
        searchTerms.push(...publicIpList)
      }
    }

    // 设置搜索参数
    if (searchTerms.length > 0) {
      params.search = searchTerms.join(' ')
    }
    if (advancedForm.os_version) {
      params.os_version = advancedForm.os_version
    }
    if (advancedForm.auth_method) {
      params.auth_method = advancedForm.auth_method
    }
    if (advancedForm.region) {
      params.region = advancedForm.region
    }
    if (advancedForm.zone) {
      params.zone = advancedForm.zone
    }

    // 添加分组筛选
    if (selectedGroupId.value !== null) {
      params.group_id = selectedGroupId.value
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null || params[key] === undefined) {
        delete params[key]
      }
    })

    const response = await hostApi.getHosts(params)
    hosts.value = response.results
    pagination.total = response.total
    totalHostCount.value = response.total
  } catch (error) {
    console.error('获取主机列表失败:', error)
    Message.error('获取主机列表失败')
    hosts.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  fetchHosts()
}

// 重置搜索
const handleReset = () => {
  Object.assign(searchForm, {
    name: '',
    ip_address: '',
    os_type: '',
    status: '',
  })
  Object.assign(advancedForm, {
    cloud_provider: '',
    internal_ip: '',
    public_ip: '',
    os_version: '',
    auth_method: '',
    region: '',
    zone: '',
  })
  pagination.current = 1
  fetchHosts()
}

// 切换高级筛选
const toggleAdvancedFilter = () => {
  showAdvancedFilter.value = !showAdvancedFilter.value
}

// OS类型显示文本
const getOSText = (osType: string) => {
  const osMap = {
    'linux': 'Linux',
    'windows': 'Windows',
    'aix': 'AIX',
    'solaris': 'Solaris'
  }
  return osMap[osType as keyof typeof osMap] || osType
}

// 拖拽调整侧边栏宽度
const SIDEBAR_WIDTH_KEY = 'hosts-sidebar-width'
const sidebarWidth = ref(parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY) || '280')) // 从本地存储读取或使用默认宽度
const isResizing = ref(false)
const minSidebarWidth = 200
const maxSidebarWidth = 500

const startResize = (e: MouseEvent) => {
  isResizing.value = true
  const startX = e.clientX
  const startWidth = sidebarWidth.value

  const handleMouseMove = (e: MouseEvent) => {
    const deltaX = e.clientX - startX
    const newWidth = startWidth + deltaX

    // 限制宽度范围
    if (newWidth >= minSidebarWidth && newWidth <= maxSidebarWidth) {
      sidebarWidth.value = newWidth
    }
  }

  const handleMouseUp = () => {
    isResizing.value = false
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''

    // 保存宽度到本地存储
    localStorage.setItem(SIDEBAR_WIDTH_KEY, sidebarWidth.value.toString())
  }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchHosts()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchHosts()
}

// 新增主机
const handleCreate = () => {
  currentHost.value = null
  formVisible.value = true
}

// 编辑主机
const handleEdit = (record: Host) => {
  currentHost.value = record
  formVisible.value = true
}

// 查看主机详情
const handleView = (record: Host) => {
  console.log('查看主机详情:', record)
  router.push({
    name: 'HostDetail',
    params: { id: record.id.toString() }
  })
}

// 测试连接
const handleTest = async (record: Host) => {
  record.testing = true
  try {
    await hostApi.testConnection(record.id)
    record.status = 'online'
    Message.success(`主机 ${record.name} 连接测试成功`)
  } catch (error) {
    record.status = 'offline'
  } finally {
    record.testing = false
  }
}

// 删除模板
const handleDelete = async (record: Host) => {
  try {
    await Modal.confirm({
      title: '确认删除',
      content: `确定要删除任务"${record.name}"吗？此操作不可恢复。`,
      onOk: async () => {
        await hostApi.deleteHost(record.id)
        Message.success('主机删除成功')
        fetchHosts()
      }
    })
    
  } catch (error) {
    Message.error('主机删除失败')
    console.error('删除主机失败:', error)
  }
}

// 表单提交成功
const handleFormSuccess = () => {
  fetchHosts()
}

// 刷新主机表单中的分组数据
const refreshHostFormGroups = () => {
  if (hostFormRef.value && hostFormRef.value.refreshGroups) {
    console.log('刷新主机表单中的分组数据')
    hostFormRef.value.refreshGroups()
  }
}

// 分组表单成功处理
const handleGroupFormSuccess = () => {
  fetchGroups()
  fetchHosts()
  refreshHostFormGroups()
}

// 分组相关函数
const fetchGroups = async () => {
  try {
    // 获取树形结构数据
    const treeResponse = await hostGroupApi.getGroupTree()
    hostGroupTree.value = treeResponse || []

    // 获取平铺列表数据（用于其他功能）
    const listResponse = await hostGroupApi.getGroups()
    hostGroups.value = listResponse.results || []
  } catch (error) {
    console.error('获取分组列表失败:', error)
    hostGroups.value = []
    hostGroupTree.value = []
  }
}

const refreshGroups = () => {
  fetchGroups()
}

// 刷新所有数据（主机列表和分组）
const refreshAll = () => {
  fetchGroups()
  fetchHosts()
}

const selectGroup = (groupId: number | null) => {
  selectedGroupId.value = groupId
  selectedRowKeys.value = [] // 清空选择
  handleSearch() // 重新搜索
}

const handleCreateGroup = () => {
  currentGroup.value = null
  parentGroupForAdd.value = null
  groupFormVisible.value = true
}

const handleAddSubgroup = (parentGroup: HostGroup) => {
  currentGroup.value = null
  parentGroupForAdd.value = parentGroup
  groupFormVisible.value = true
}

const handleEditGroup = (group: HostGroup) => {
  currentGroup.value = group
  parentGroupForAdd.value = null
  groupFormVisible.value = true
}

const handleDeleteGroup = (group: HostGroup) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除分组"${group.name}"吗？删除后该分组下的主机将移动到未分组状态。`,
    okText: '确定',
    cancelText: '取消',
    onOk: async () => {
      try {
        await hostGroupApi.deleteGroup(group.id)
        Message.success('分组删除成功')
        fetchGroups()
        fetchHosts()
        refreshHostFormGroups()
      } catch (error: any) {
        console.error('删除分组失败:', error)
      }
    }
  })
}

const handleTestGroupConnection = async (group: HostGroup) => {
  try {
    // 使用正确的Message.loading API
    const loadingMessage = Message.loading({
      content: `正在测试分组"${group.name}"下的主机连接...`,
      duration: 0
    })

    // 获取分组下的所有主机
    const groupHosts = hosts.value.filter(host =>
      host.groups_info?.some(g => g.id === group.id)
    )

    if (groupHosts.length === 0) {
      loadingMessage.close()
      Message.warning(`分组"${group.name}"下没有主机`)
      return
    }

    // 批量测试连接
    const hostIds = groupHosts.map(host => host.id)
    await hostApi.batchTestConnection(hostIds)

    loadingMessage.close()
    Message.success(`分组"${group.name}"连接测试完成`)
    fetchHosts() // 刷新主机状态
  } catch (error: any) {
    console.error('分组连接测试失败:', error)
  }
}

const handleBatchTest = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要测试的主机')
    return
  }

  batchTesting.value = true
  try {
        const result = await hostApi.batchTestConnection(selectedRowKeys.value)

    // 增加健robustness check to prevent inconsistent return data structures
    if (result && result.details) {
      // 更新主机状态
      result.details.forEach(item => {
        const host = hosts.value.find(h => h.id === item.host_id)
        if (host && item.result) {
          host.status = item.result.success ? 'online' : 'offline'
        }
      })
      Message.success(`批量测试完成：${result.success ?? 0}/${result.total ?? 0} 台主机连接成功`)
    } else {
      console.error('批量测试连接返回了无效的数据结构:', result)
      Message.error('批量测试失败：返回数据格式不正确')
    }
  } catch (error) {
    console.error('批量测试连接失败:', error)
  } finally {
    batchTesting.value = false
  }
}

// 云同步处理
const handleCloudSync = async (provider: string) => {
  cloudSyncing.value = true
  try {
    const result = await hostApi.syncCloudHosts(provider)
    if (result.success) {
      Message.success(result.message)
      // 刷新主机列表
      await fetchHosts()
    } else {
      Message.error(result.message)
    }
  } catch (error) {
    console.error('云同步失败:', error)
    Message.error('云同步失败')
  } finally {
    cloudSyncing.value = false
  }
}

// 分组展开相关方法
const toggleGroupExpand = (groupId: number) => {
  const index = expandedGroups.value.indexOf(groupId)
  if (index > -1) {
    expandedGroups.value.splice(index, 1)
  } else {
    expandedGroups.value.push(groupId)
  }
}

// 这些方法已经不再需要，因为使用了新的树形组件
// const getGroupHosts = (groupId: number) => {
//   return hosts.value.filter(host =>
//     host.groups_info?.some(group => group.id === groupId)
//   )
// }

// const selectHost = (host: Host) => {
//   // 选中主机，可以高亮显示或其他操作
//   console.log('选中主机:', host)
// }

// 批量操作相关方法 - rowSelection已在模板中直接使用

// 检查当前页是否全选
const isAllCurrentPageSelected = computed(() => {
  if (hosts.value.length === 0) return false
  return hosts.value.every(host => selectedRowKeys.value.includes(host.id))
})

// 全选当前页
const selectAllCurrentPage = () => {
  const currentPageHostIds = hosts.value.map(host => host.id)
  // 合并当前选中的和当前页的，去重
  const newSelection = [...new Set([...selectedRowKeys.value, ...currentPageHostIds])]
  selectedRowKeys.value = newSelection
}





const clearSelection = () => {
  selectedRowKeys.value = []
}

const handleBatchMoveToGroup = async (groupId: number | null) => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要移动的主机')
    return
  }

  try {
    const loadingMessage = Message.loading({
      content: '正在移动主机...',
      duration: 0
    })

    // 由于响应拦截器返回的是content部分，我们需要直接使用返回的数据
    const result = await hostApi.batchMoveToGroup(selectedRowKeys.value, groupId)

    loadingMessage.close()

    // 如果没有抛出异常，说明请求成功了
    // 构建成功消息
    const targetGroupName = result.target_group_name
    const movedCount = result.moved_count || selectedRowKeys.value.length

    let successMessage = ''
    if (targetGroupName) {
      successMessage = `成功将 ${movedCount} 台主机移动到分组 '${targetGroupName}'`
    } else {
      successMessage = `成功将 ${movedCount} 台主机移出所有分组`
    }

    Message.success(successMessage)
    clearSelection()
    fetchHosts() // 刷新主机列表

  } catch (error: any) {
    console.error('批量移动失败:', error)
    Message.error(error.message || '主机移动失败')
  }
}

// 删除重复的handleBatchTest函数，使用上面已定义的版本

const handleBatchDelete = async () => {
  try {
    // 调用批量删除API
    console.log('批量删除主机:', selectedRowKeys.value)
    Message.success('批量删除成功')
    clearSelection()
    fetchHosts()
  } catch (error) {
    console.error('批量删除失败:', error)
  }
}

onMounted(async () => {
  // 等待认证状态确认后再发送请求
  await nextTick()

  // 检查认证状态
  const authStore = useAuthStore()
  if (!authStore.token) {
    console.warn('用户未登录，跳过数据获取')
    return
  }

  console.log('用户已登录，开始获取数据')
  fetchHosts()
  fetchGroups()
})
</script>

<style scoped>
.hosts-page {
  padding: 0;
}

.page-header {
  background: white;
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1d2129;
}

.header-desc {
  margin: 0;
  font-size: 14px;
  color: #86909c;
}

.mb-4 {
  margin-bottom: 16px;
}

.hosts-content {
  display: flex;
  gap: 16px;
  height: calc(100vh - 200px);
}

.groups-panel {
  width: 280px;
  flex-shrink: 0;
}

.hosts-main {
  flex: 1;
  min-width: 0;
}

.group-list {
  max-height: calc(100vh - 300px);
  overflow-y: auto;
}

.group-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.group-item:hover {
  background-color: #f5f5f5;
}

.group-item.active {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
}

.group-info {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.group-icon {
  margin-right: 8px;
  color: #666;
}

.group-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-count {
  background-color: #f0f0f0;
  color: #666;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 12px;
  min-width: 20px;
  text-align: center;
}

.group-item.active .group-count {
  background-color: #1890ff;
  color: white;
}

:deep(.arco-card-body) {
  padding: 16px;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff !important;
    font-weight: 600;
  }

  /* 固定列样式优化 - 不使用!important避免影响动态样式 */
  .arco-table-col-fixed-right .arco-table-td {
    background-color: inherit;
  }

  .arco-table-col-fixed-right .arco-table-cell {
    background-color: inherit;
  }
}

/* 新增样式 */
.expand-btn {
  padding: 0;
  margin-right: 4px;
}

.expand-icon {
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.group-hosts {
  margin-left: 20px;
  border-left: 2px solid #f0f0f0;
  padding-left: 12px;
}

.host-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  margin-bottom: 2px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.host-item:hover {
  background-color: #f8f9fa;
}

.host-info {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.host-icon {
  margin-right: 6px;
  color: #666;
  font-size: 12px;
}

.host-name {
  font-size: 12px;
  margin-right: 8px;
  font-weight: 500;
}

.host-ip {
  font-size: 11px;
  color: #999;
}

.host-status {
  font-size: 11px;
}

.batch-actions {
  margin-bottom: 16px;
}

.page-selection-actions {
  margin-top: 12px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
}

.danger {
  color: #f53f3f !important;
}

.danger:hover {
  background-color: #fef2f2 !important;
  color: #dc2626 !important;
}

/* 下拉菜单项悬停效果 */
:deep(.arco-dropdown-option:hover) {
  background-color: var(--color-fill-2) !important;
}

:deep(.arco-dropdown-option.danger:hover) {
  background-color: #fef2f2 !important;
  color: #dc2626 !important;
}

.mr-1 {
  margin-right: 4px;
}

.mb-1 {
  margin-bottom: 4px;
}

.text-gray-400 {
  color: #9ca3af;
}

/* 拖拽分隔条样式 */
.hosts-content {
  display: flex;
  height: calc(100vh - 120px);
  gap: 0;
}

.groups-panel {
  flex-shrink: 0;
  transition: width 0.1s ease;
}

.resize-handle {
  width: 4px;
  background-color: transparent;
  cursor: col-resize;
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.resize-handle:hover {
  background-color: var(--color-border-3);
}

.resize-handle.resizing {
  background-color: var(--color-primary-light-3);
}

.resize-line {
  width: 1px;
  height: 100%;
  background-color: var(--color-border-2);
  transition: background-color 0.2s;
}

.resize-handle:hover .resize-line {
  background-color: var(--color-primary);
}

.resize-handle.resizing .resize-line {
  background-color: var(--color-primary);
}

.resize-dots {
  position: absolute;
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}

.resize-handle:hover .resize-dots {
  opacity: 1;
}

.resize-handle.resizing .resize-dots {
  opacity: 1;
}

.dot {
  width: 2px;
  height: 2px;
  background-color: var(--color-text-3);
  border-radius: 50%;
}

.resize-handle:hover .dot {
  background-color: var(--color-primary);
}

.resize-handle.resizing .dot {
  background-color: var(--color-primary);
}

.hosts-main {
  flex: 1;
  min-width: 0;
}

/* OS类型标签样式 */
:deep(.os-linux) {
  background-color: var(--color-blue-light-1) !important;
  color: var(--color-blue) !important;
  border-color: var(--color-blue-light-3) !important;
}

:deep(.os-windows) {
  background-color: var(--color-cyan-light-1) !important;
  color: var(--color-cyan) !important;
  border-color: var(--color-cyan-light-3) !important;
}

:deep(.os-aix) {
  background-color: var(--color-purple-light-1) !important;
  color: var(--color-purple) !important;
  border-color: var(--color-purple-light-3) !important;
}

:deep(.os-solaris) {
  background-color: var(--color-orange-light-1) !important;
  color: var(--color-orange) !important;
  border-color: var(--color-orange-light-3) !important;
}

/* 搜索容器样式 */
.search-container {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.search-form {
  flex: 1;
}

.search-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* 多IP搜索框样式 */
.search-form :deep(.arco-textarea-wrapper) {
  border-radius: 4px;
  transition: border-color 0.2s;
}

.search-form :deep(.arco-textarea-wrapper:hover) {
  border-color: #4080ff;
}

.search-form :deep(.arco-textarea-wrapper:focus-within) {
  border-color: #4080ff;
  box-shadow: 0 0 0 2px rgba(64, 128, 255, 0.1);
}

.search-form :deep(.arco-textarea) {
  font-size: 13px;
  line-height: 1.4;
  resize: vertical;
}

/* 确保表单项布局稳定 */
.search-form .arco-form-item {
  flex-shrink: 0;
}

/* 搜索行布局 */
.search-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.search-row:last-child {
  margin-bottom: 0;
}

.search-row .arco-form-item {
  margin-bottom: 0;
  margin-right: 0;
}

/* 高级筛选样式 */
.advanced-filter {
  background: var(--color-fill-1);
  padding: 16px;
  border-radius: 6px;
  margin-top: 12px;
}

.advanced-filter :deep(.arco-divider) {
  margin: 0 0 16px 0;
}

.advanced-filter :deep(.arco-form-item) {
  margin-bottom: 12px;
}

/* 操作按钮样式 */
.advanced-actions {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-2);
}

.advanced-actions-right {
  display: flex;
  justify-content: flex-end;
}

.basic-actions {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-2);
}

.basic-actions-right {
  display: flex;
  justify-content: flex-end;
}
</style>
