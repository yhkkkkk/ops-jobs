<template>
  <div class="host-detail">
    <div class="page-header">
      <a-breadcrumb>
        <a-breadcrumb-item @click="goBack">主机管理</a-breadcrumb-item>
        <a-breadcrumb-item>主机详情</a-breadcrumb-item>
      </a-breadcrumb>

      <div class="header-actions">
        <a-space>
          <a-button @click="goBack">
            <template #icon>
              <icon-arrow-left />
            </template>
            返回
          </a-button>
          <a-button
            @click="handleEdit"
            v-permission="{ resourceType: 'host', permission: 'change', resourceId: hostDetail?.id }"
          >
            <template #icon>
              <icon-edit />
            </template>
            编辑
          </a-button>
          <a-button
            @click="handleCollectInfo"
            :loading="collecting"
            v-permission="{ resourceType: 'host', permission: 'execute', resourceId: hostDetail?.id }"
          >
            <template #icon>
              <icon-refresh />
            </template>
            收集系统信息
          </a-button>
          <a-button
            type="primary"
            @click="handleTest"
            :loading="testing"
            v-permission="{ resourceType: 'host', permission: 'execute', resourceId: hostDetail?.id }"
          >
            <template #icon>
              <icon-wifi />
            </template>
            测试连接
          </a-button>
        </a-space>
      </div>
    </div>

    <div v-if="hostDetail" class="host-detail-content">
      <!-- 基本信息 -->
      <div class="info-section">
        <h3 class="section-title">基本信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">主机名称：</span>
            <span class="value">{{ hostDetail.name }}</span>
          </div>
          <div class="info-item">
            <span class="label">IP地址：</span>
            <span class="value">{{ hostDetail.ip_address }}</span>
          </div>
          <div class="info-item">
            <span class="label">端口：</span>
            <span class="value">{{ hostDetail.port }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统：</span>
            <span class="value">
              <a-tag :color="getOSColor(hostDetail.os_type)">
                {{ hostDetail.os_type_display }}
              </a-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="label">服务器账号：</span>
            <span class="value">
              <div v-if="hostDetail.account_info">
                <a-tag color="blue" size="small">
                  {{ hostDetail.account_info.name }}
                </a-tag>
                <div class="text-gray-500" style="font-size: 12px; margin-top: 4px;">
                  {{ hostDetail.account_info.username }}
                </div>
              </div>
              <span v-else class="text-gray-500">未配置</span>
            </span>
          </div>
          <div class="info-item">
            <span class="label">状态：</span>
            <span class="value">
              <a-tag :color="getStatusColor(hostDetail.status)">
                {{ getStatusText(hostDetail.status) }}
              </a-tag>
            </span>
          </div>
          <div class="info-item">
            <span class="label">所属分组：</span>
            <span class="value">
              <div v-if="hostDetail.groups_info && hostDetail.groups_info.length > 0">
                <a-tag
                  v-for="group in hostDetail.groups_info"
                  :key="group.id"
                  color="blue"
                  class="mr-1 mb-1"
                >
                  {{ group.name }}
                </a-tag>
              </div>
              <span v-else class="text-gray-500">未分组</span>
            </span>
          </div>
          <div class="info-item">
            <span class="label">描述：</span>
            <span class="value">{{ hostDetail.description || '暂无描述' }}</span>
          </div>
        </div>
      </div>

      <!-- 系统配置信息 -->
      <div class="info-section">
        <h3 class="section-title">系统配置信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">主机名称：</span>
            <span class="value">{{ hostDetail.hostname || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统类型：</span>
            <span class="value">{{ hostDetail.os_type_display || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统版本：</span>
            <span class="value">{{ hostDetail.os_version || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">CPU逻辑核心数：</span>
            <span class="value">{{ hostDetail.cpu_cores ? `${hostDetail.cpu_cores}` : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">CPU型号：</span>
            <span class="value">{{ hostDetail.cpu_model || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统位数：</span>
            <span class="value">{{ hostDetail.os_arch || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">磁盘容量(GB)：</span>
            <span class="value">{{ hostDetail.disk_gb ? `${hostDetail.disk_gb}` : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">内存容量(MB)：</span>
            <span class="value">{{ hostDetail.memory_gb ? `${hostDetail.memory_gb * 1024}` : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">CPU架构：</span>
            <span class="value">{{ hostDetail.cpu_arch || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">操作系统内核：</span>
            <span class="value">{{ hostDetail.kernel_version || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 云厂商信息 -->
      <div class="info-section">
        <h3 class="section-title">云厂商信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">云厂商：</span>
            <span class="value">
              <a-tag v-if="hostDetail.cloud_provider" color="green">
                {{ hostDetail.cloud_provider_display }}
              </a-tag>
              <span v-else>--</span>
            </span>
          </div>
          <div class="info-item">
            <span class="label">实例ID：</span>
            <span class="value">{{ hostDetail.instance_id || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">地域：</span>
            <span class="value">{{ hostDetail.region || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">可用区：</span>
            <span class="value">{{ hostDetail.zone || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">实例类型：</span>
            <span class="value">{{ hostDetail.instance_type || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">网络类型：</span>
            <span class="value">{{ hostDetail.network_type || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 业务信息 -->
      <div class="info-section">
        <h3 class="section-title">业务信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">环境类型：</span>
            <span class="value">
              <a-tag v-if="hostDetail.environment" :color="getEnvironmentColor(hostDetail.environment)">
                {{ hostDetail.environment_display }}
              </a-tag>
              <span v-else>--</span>
            </span>
          </div>
          <div class="info-item">
            <span class="label">业务系统：</span>
            <span class="value">{{ hostDetail.business_system || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">服务角色：</span>
            <span class="value">{{ hostDetail.service_role || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">负责人：</span>
            <span class="value">{{ hostDetail.owner || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">所属部门：</span>
            <span class="value">{{ hostDetail.department || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">备注：</span>
            <span class="value">{{ hostDetail.remarks || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 网络信息 -->
      <div class="info-section">
        <h3 class="section-title">网络信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">外网IP：</span>
            <span class="value">{{ hostDetail.public_ip || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">内网IP：</span>
            <span class="value">{{ hostDetail.internal_ip || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">内网MAC地址：</span>
            <span class="value">{{ hostDetail.internal_mac || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">外网MAC地址：</span>
            <span class="value">{{ hostDetail.external_mac || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">网关：</span>
            <span class="value">{{ hostDetail.gateway || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">DNS服务器：</span>
            <span class="value">
              <div v-if="hostDetail.dns_servers">
                <a-tag
                  v-for="dns in getDnsServers(hostDetail.dns_servers)"
                  :key="dns"
                  color="green"
                  class="mr-1 mb-1"
                >
                  {{ dns }}
                </a-tag>
              </div>
              <span v-else>--</span>
            </span>
          </div>
        </div>
      </div>

      <!-- 时间信息 -->
      <div class="info-section">
        <h3 class="section-title">时间信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">最后检查：</span>
            <span class="value">{{ hostDetail.last_check_time ? formatTime(hostDetail.last_check_time) : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">创建时间：</span>
            <span class="value">{{ hostDetail.created_at ? formatTime(hostDetail.created_at) : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">更新时间：</span>
            <span class="value">{{ hostDetail.updated_at ? formatTime(hostDetail.updated_at) : '--' }}</span>
          </div>
          <div class="info-item">
            <span class="label">系统启动时间：</span>
            <span class="value">{{ hostDetail.boot_time ? formatTime(hostDetail.boot_time) : '--' }}</span>
          </div>
        </div>
      </div>
    </div>
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <!-- 主机表单弹窗 -->
    <host-form
      v-model:visible="formVisible"
      :host="hostDetail"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import { hostApi } from '@/api/ops'
import type { Host } from '@/types'
import HostForm from './components/HostForm.vue'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const testing = ref(false)
const collecting = ref(false)
const formVisible = ref(false)
const hostDetail = ref<Host | null>(null)



// 获取主机详情
const fetchHostDetail = async () => {
  loading.value = true
  try {
    const hostId = parseInt(route.params.id as string)
    hostDetail.value = await hostApi.getHost(hostId)
  } catch (error) {
    console.error('获取主机详情失败:', error)
    Message.error('获取主机详情失败')
  } finally {
    loading.value = false
  }
}



// 事件处理
const goBack = () => {
  router.push('/hosts')
}

const handleEdit = () => {
  formVisible.value = true
}

const handleTest = async () => {
  if (!hostDetail.value) return

  testing.value = true
  try {
    await hostApi.testConnection(hostDetail.value.id)
    // 测试成功后重新获取主机详情，确保数据同步
    await fetchHostDetail()
    Message.success(`主机 ${hostDetail.value.name} 连接测试成功`)
  } catch (error) {
    // 测试失败后也重新获取主机详情，确保状态同步
    await fetchHostDetail()
    // 错误消息已由HTTP拦截器处理，这里不再重复显示
    console.error('连接测试失败:', error)
  } finally {
    testing.value = false
  }
}

const handleCollectInfo = async () => {
  if (!hostDetail.value) return

  collecting.value = true
  try {
    // 调用系统信息收集API
    await hostApi.collectSystemInfo(hostDetail.value.id)
    Message.success('系统信息收集成功')
    // 重新获取主机详情以显示最新信息
    await fetchHostDetail()
  } catch (error) {
    console.error('系统信息收集失败:', error)
    Message.error('系统信息收集失败')
  } finally {
    collecting.value = false
  }
}

const handleFormSuccess = () => {
  fetchHostDetail()
  formVisible.value = false
}

// 工具函数
const getStatusColor = (status: string) => {
  const colors = {
    online: 'green',
    offline: 'red',
    unknown: 'gray',
  }
  return colors[status] || 'gray'
}

const getStatusText = (status: string) => {
  const texts = {
    online: '在线',
    offline: '离线',
    unknown: '未知',
  }
  return texts[status] || '未知'
}



const formatTime = (timestamp: string) => {
  return dayjs(timestamp).format('YYYY-MM-DD HH:mm:ss')
}



const getOSColor = (osType: string) => {
  const colors = {
    linux: 'blue',
    windows: 'cyan',
    aix: 'purple',
    solaris: 'orange',
  }
  return colors[osType] || 'gray'
}

const getEnvironmentColor = (environment: string) => {
  const colors = {
    dev: 'green',
    test: 'orange',
    staging: 'purple',
    prod: 'red',
  }
  return colors[environment] || 'gray'
}

const getDnsServers = (dnsString: string) => {
  if (!dnsString) return []
  // DNS服务器可能以逗号、分号或空格分隔
  return dnsString.split(/[,;\s]+/).filter(dns => dns.trim())
}

// 生命周期
onMounted(() => {
  fetchHostDetail()
})
</script>

<style scoped>
.host-detail-content {
  padding: 20px;
  background: #fff;
}

.info-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 20px;
  padding-left: 10px;
  border-left: 4px solid #1890ff;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px 40px;
  padding: 0 20px;
}

.info-item {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding: 8px 0;
}

.label {
  color: #666;
  font-size: 14px;
  min-width: 120px;
  flex-shrink: 0;
}

.value {
  color: #333;
  font-size: 14px;
  flex: 1;
}

.value .text-gray-500 {
  color: #999;
}

/* 原有样式 */
.host-detail {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  flex-shrink: 0;
}

.mb-4 {
  margin-bottom: 16px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

:deep(.arco-breadcrumb-item) {
  cursor: pointer;
}

.mr-1 {
  margin-right: 4px;
}

.mb-1 {
  margin-bottom: 4px;
}

.text-gray-500 {
  color: #6b7280;
}
</style>
