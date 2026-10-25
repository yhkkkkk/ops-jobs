<template>
  <div class="flow-ip-selector-field">
    <div class="flow-ip-selector-field__summary">
      <n-input
        type="textarea"
        :value="modelValue"
        :placeholder="placeholder || '每行一个 IP 或主机名；也可点右侧选择主机'"
        :autosize="{ minRows: 2, maxRows: 5 }"
        :disabled="disabled"
        @update:value="emit('update:modelValue', $event)"
      />
      <n-button size="small" :disabled="disabled" @click="openSelector">
        选择主机
      </n-button>
    </div>
    <p class="flow-ip-selector-field__hint">{{ countLabel }}</p>

    <HostSelector
      v-model:visible="selectorVisible"
      :hosts="hosts"
      :groups="groups"
      :selected-hosts="selectedHosts"
      :selected-groups="[]"
      :host-pagination="hostPagination"
      :enable-host-pagination="true"
      :fetch-all-hosts="fetchAllHosts"
      @confirm="handleConfirm"
      @host-page-change="handleHostPageChange"
      @host-page-size-change="handleHostPageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import HostSelector from '@/components/HostSelector.vue'
import { hostApi, hostGroupApi } from '@/api/ops'
import type { Host, HostGroup } from '@/types'
import { NButton, NInput, useMessage } from 'naive-ui'

const props = withDefaults(defineProps<{
  modelValue?: string
  placeholder?: string
  disabled?: boolean
}>(), {
  modelValue: '',
  placeholder: '',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const message = useMessage()
const selectorVisible = ref(false)
const hosts = ref<Host[]>([])
const groups = ref<HostGroup[]>([])
const hostPagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  pageSizeOptions: ['10', '20', '50', '100'],
})

const identifiers = computed(() =>
  String(props.modelValue || '')
    .split(/[\s,]+/)
    .map(item => item.trim())
    .filter(Boolean),
)

const countLabel = computed(() => {
  const count = identifiers.value.length
  return count ? `已填写 ${count} 个主机标识` : '未选择主机'
})

const selectedHosts = computed(() => {
  const set = new Set(identifiers.value)
  return hosts.value.filter(host =>
    set.has(String(host.id))
    || (host.internal_ip && set.has(host.internal_ip))
    || (host.public_ip && set.has(host.public_ip))
    || (host.name && set.has(host.name)),
  )
})

const fetchAllHosts = async () => {
  const response = await hostApi.getHosts({ page_size: 2000 })
  return (response as any)?.results || (response as any)?.data || response || []
}

const loadGroups = async () => {
  try {
    const response = await hostGroupApi.getGroups()
    groups.value = ((response as any)?.results || (response as any)?.data || response || []) as HostGroup[]
  } catch {
    groups.value = []
  }
}

const loadHosts = async () => {
  try {
    const response = await hostApi.getHosts({
      page: hostPagination.value.current,
      page_size: hostPagination.value.pageSize,
    })
    hosts.value = ((response as any)?.results || []) as Host[]
    hostPagination.value.total = Number((response as any)?.count || hosts.value.length)
  } catch (error) {
    console.error(error)
    message.error('加载主机列表失败')
  }
}

const openSelector = async () => {
  if (props.disabled) return
  await Promise.all([loadGroups(), loadHosts()])
  selectorVisible.value = true
}

const handleHostPageChange = async (page: number) => {
  hostPagination.value.current = page
  await loadHosts()
}

const handleHostPageSizeChange = async (pageSize: number) => {
  hostPagination.value.pageSize = pageSize
  hostPagination.value.current = 1
  await loadHosts()
}

const handleConfirm = (payload: { hosts: Host[] }) => {
  const selected = (payload.hosts || [])
    .map(host => host.internal_ip || host.public_ip || host.name || String(host.id))
    .filter(Boolean)
  const kept = identifiers.value.filter(item => !selectedHosts.value.some(host =>
    item === String(host.id)
    || item === host.internal_ip
    || item === host.public_ip
    || item === host.name,
  ))
  emit('update:modelValue', [...kept, ...selected].join('\n'))
}

watch(selectorVisible, value => {
  if (value) loadHosts()
})
</script>

<style scoped>
.flow-ip-selector-field {
  display: grid;
  gap: 6px;
  width: 100%;
}
.flow-ip-selector-field__summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}
.flow-ip-selector-field__hint {
  margin: 0;
  color: var(--app-muted);
  font-size: 12px;
}
</style>
