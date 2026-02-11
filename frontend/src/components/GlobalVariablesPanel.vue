<template>
  <div class="global-vars">
    <div class="global-vars-title">{{ title }}</div>
    <div v-if="items.length === 0" class="global-vars-empty">
      <a-empty :description="emptyText" :image-style="{ height: '40px' }" />
    </div>
    <div v-else class="global-vars-list">
      <div
        v-for="item in items"
        :key="item.key"
        class="global-var-row"
        @click="openDrawer(item)"
      >
        <div class="global-var-key">{{ item.key }}</div>
        <div class="global-var-value">
          <span v-if="item.preview" class="value-preview">{{ item.preview }}</span>
          <a-button type="text" size="mini" @click.stop="openDrawer(item)">查看</a-button>
        </div>
      </div>
    </div>

    <a-drawer
      v-model:visible="drawerVisible"
      :width="820"
      :footer="false"
      unmount-on-close
    >
      <template #title>
        <div class="drawer-title">
          <span>{{ drawerItem?.key || '' }}</span>
          <span v-if="drawerItem?.description" class="drawer-title-desc">{{ drawerItem?.description }}</span>
        </div>
      </template>

      <div v-if="drawerItem" class="drawer-body">
        <template v-if="drawerItem.kind === 'host_ids' || drawerItem.kind === 'host_objects'">
          <a-table
            :columns="hostColumns"
            :data="hostRows"
            :pagination="false"
            :loading="hostLoading"
            size="small"
            row-key="id"
          >
            <template #agent_status="{ record }">
              <a-tag v-if="record.agent_status === 'online'" color="green">在线</a-tag>
              <a-tag v-else-if="record.agent_status === 'offline'" color="red">离线</a-tag>
              <a-tag v-else-if="record.agent_status === 'pending'" color="orange">待连接</a-tag>
              <a-tag v-else-if="record.agent_status === 'disabled'" color="gray">禁用</a-tag>
              <a-tag v-else color="gray">未知</a-tag>
            </template>
            <template #status="{ record }">
              <a-tag v-if="record.status === 'online'" color="green">在线</a-tag>
              <a-tag v-else-if="record.status === 'offline'" color="red">离线</a-tag>
              <a-tag v-else color="gray">未知</a-tag>
            </template>
          </a-table>
          <div v-if="drawerItem.kind === 'host_ids'" class="table-pagination">
            <a-pagination
              :current="hostPagination.page"
              :page-size="hostPagination.pageSize"
              :total="hostPagination.total"
              size="small"
              show-total
              @change="handleHostPageChange"
            />
          </div>
        </template>

        <template v-else-if="drawerItem.kind === 'ip_list'">
          <a-table
            :columns="ipColumns"
            :data="ipRows"
            :pagination="false"
            size="small"
            row-key="ip"
          />
          <div class="table-pagination">
            <a-pagination
              :current="ipPagination.page"
              :page-size="ipPagination.pageSize"
              :total="ipPagination.total"
              size="small"
              show-total
              @change="handleIpPageChange"
            />
          </div>
        </template>

        <template v-else>
          <pre class="value-block">{{ drawerItem.displayValue }}</pre>
        </template>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { hostApi } from '@/api/ops'

const props = defineProps({
  title: {
    type: String,
    default: '全局变量'
  },
  emptyText: {
    type: String,
    default: '暂无全局变量'
  },
  variables: {
    type: Object,
    default: () => ({})
  }
})

type VariableItem = {
  key: string
  type: string
  description: string
  kind: 'host_ids' | 'host_objects' | 'ip_list' | 'list' | 'text' | 'secret'
  preview: string
  displayValue: string
  ids?: number[]
  ips?: string[]
  hosts?: any[]
}

const drawerVisible = ref(false)
const drawerItem = ref<VariableItem | null>(null)

const hostLoading = ref(false)
const hostRows = ref<any[]>([])
const hostPagination = reactive({ page: 1, pageSize: 10, total: 0 })
const hostCache = reactive<Record<number, any>>({})

const ipPagination = reactive({ page: 1, pageSize: 10, total: 0 })

const hostColumns = [
  { title: '主机名', dataIndex: 'name' },
  { title: 'IP', dataIndex: 'ip_address' },
  { title: 'Agent状态', dataIndex: 'agent_status', slotName: 'agent_status' },
  { title: '状态', dataIndex: 'status', slotName: 'status' }
]

const ipColumns = [
  { title: 'IP', dataIndex: 'ip' }
]

const items = computed(() => {
  const raw = props.variables || {}
  return Object.entries(raw).map(([key, value]) => normalizeVariable(key, value))
})

const ipRows = computed(() => {
  if (!drawerItem.value || drawerItem.value.kind !== 'ip_list') return []
  const ips = drawerItem.value.ips || []
  ipPagination.total = ips.length
  const start = (ipPagination.page - 1) * ipPagination.pageSize
  const end = start + ipPagination.pageSize
  return ips.slice(start, end).map(ip => ({ ip }))
})

const openDrawer = (item: VariableItem) => {
  drawerItem.value = item
  drawerVisible.value = true
  if (item.kind === 'host_ids') {
    hostPagination.page = 1
    fetchHosts()
  }
  if (item.kind === 'ip_list') {
    ipPagination.page = 1
  }
  if (item.kind === 'host_objects') {
    hostRows.value = item.hosts || []
    hostPagination.total = hostRows.value.length
  }
}

const handleHostPageChange = (page: number) => {
  hostPagination.page = page
  fetchHosts()
}

const handleIpPageChange = (page: number) => {
  ipPagination.page = page
}

const fetchHosts = async () => {
  if (!drawerItem.value || drawerItem.value.kind !== 'host_ids') return
  const ids = drawerItem.value.ids || []
  hostPagination.total = ids.length
  if (ids.length === 0) {
    hostRows.value = []
    return
  }

  const start = (hostPagination.page - 1) * hostPagination.pageSize
  const end = start + hostPagination.pageSize
  const pageIds = ids.slice(start, end)

  try {
    hostLoading.value = true
    const results = await Promise.all(pageIds.map(async (id) => {
      if (hostCache[id]) {
        return hostCache[id]
      }
      try {
        const host = await hostApi.getHost(id)
        const normalized = {
          ...host,
          agent_status: host?.agent_info?.status || 'unknown'
        }
        hostCache[id] = normalized
        return normalized
      } catch (error) {
        return {
          id,
          name: `ID: ${id}`,
          ip_address: '-',
          agent_status: 'unknown',
          status: 'unknown'
        }
      }
    }))
    hostRows.value = results
  } catch (error) {
    Message.error('加载主机列表失败')
  } finally {
    hostLoading.value = false
  }
}

const normalizeVariable = (key: string, rawValue: any): VariableItem => {
  let value = rawValue
  let type = 'text'
  let description = ''

  if (rawValue && typeof rawValue === 'object' && !Array.isArray(rawValue)) {
    const hasMeta = Object.prototype.hasOwnProperty.call(rawValue, 'value')
      || Object.prototype.hasOwnProperty.call(rawValue, 'type')
      || Object.prototype.hasOwnProperty.call(rawValue, 'description')
    if (hasMeta) {
      value = rawValue.value
      type = rawValue.type || 'text'
      description = rawValue.description || ''
    }
  }

  if (type === 'secret') {
    return {
      key,
      type,
      description,
      kind: 'secret',
      preview: '',
      displayValue: '******'
    }
  }

  if (Array.isArray(value)) {
    const list = value
    if (list.length > 0 && list.every(item => typeof item === 'object' && (item.ip_address || item.name))) {
      return {
        key,
        type,
        description,
        kind: 'host_objects',
        preview: `主机列表 (${list.length})`,
        displayValue: '',
        hosts: list
      }
    }
    if (list.length > 0 && list.every(item => isNumeric(item))) {
      const ids = list.map(item => Number(item))
      return {
        key,
        type,
        description,
        kind: 'host_ids',
        preview: `主机列表 (${ids.length})`,
        displayValue: ids.join(', '),
        ids
      }
    }
    if (list.length > 0 && list.every(item => isIp(String(item)))) {
      const ips = list.map(item => String(item))
      return {
        key,
        type,
        description,
        kind: 'ip_list',
        preview: `IP列表 (${ips.length})`,
        displayValue: ips.join(', '),
        ips
      }
    }

    return {
      key,
      type,
      description,
      kind: 'list',
      preview: `列表 (${list.length})`,
      displayValue: stringifyValue(list)
    }
  }

  if (typeof value === 'string') {
    const parts = value.split(/[\s,;]+/).filter(Boolean)
    if (parts.length > 1 && parts.every(item => isNumeric(item))) {
      const ids = parts.map(item => Number(item))
      return {
        key,
        type,
        description,
        kind: 'host_ids',
        preview: `主机列表 (${ids.length})`,
        displayValue: ids.join(', '),
        ids
      }
    }
    if (parts.length > 1 && parts.every(item => isIp(item))) {
      return {
        key,
        type,
        description,
        kind: 'ip_list',
        preview: `IP列表 (${parts.length})`,
        displayValue: parts.join(', '),
        ips: parts
      }
    }
  }

  const displayValue = stringifyValue(value)
  return {
    key,
    type,
    description,
    kind: 'text',
    preview: '',
    displayValue
  }
}

const stringifyValue = (value: any) => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch (error) {
    return String(value)
  }
}

const truncate = (value: string, maxLength: number) => {
  if (!value) return '-'
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength)}...`
}

const isNumeric = (value: any) => {
  const str = String(value)
  return /^\d+$/.test(str)
}

const isIp = (value: string) => {
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(value)
}

watch(drawerVisible, (visible) => {
  if (!visible) {
    hostRows.value = []
    hostPagination.page = 1
    hostPagination.total = 0
  }
})
</script>

<style scoped>
.global-vars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.global-vars-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
}

.global-vars-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.global-var-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.global-var-row:hover {
  border-color: var(--color-primary-6);
}

.global-var-key {
  width: 160px;
  color: var(--color-text-2);
  font-weight: 500;
  font-size: 13px;
}

.global-var-value {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
}

.value-preview {
  color: var(--color-text-1);
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.drawer-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-title-desc {
  font-size: 12px;
  color: var(--color-text-3);
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.value-block {
  margin: 0;
  padding: 12px 14px;
  background: #f7f8fa;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  color: var(--color-text-1);
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
}
</style>
