<template>
  <div class="file-sources-panel">
    <div class="panel-actions" style="display:flex; gap:8px; align-items:center;">
      <a-upload
        :file-list="uploadList"
        :auto-upload="false"
        multiple
        :show-upload-button="true"
        :show-file-list="false"
        @change="onFileChange"
        @remove="onFileRemove"
      >
        <template #upload-button>
          <a-button type="dashed">
            <template #icon><icon-plus /></template>
            添加本地文件
          </a-button>
        </template>
      </a-upload>
      <a-button type="dashed" @click="serverInlineVisible = !serverInlineVisible">添加服务器文件</a-button>
    </div>

    <div v-if="artifacts && artifacts.length > 0" class="artifact-list" style="margin-top:12px; border:1px dashed var(--color-border-2); padding:12px; border-radius:4px; width:calc(100% + 480px); margin-right:-240px; box-sizing:border-box; background:transparent;">
      <div v-for="(a, idx) in artifacts" :key="a.uid || a.storage_path || idx" class="artifact-item" style="display:flex; align-items:center; justify-content:space-between; padding:8px; border:1px solid var(--color-border-2); border-radius:4px; margin-bottom:8px;">
        <div style="display:flex; gap:12px; align-items:center; min-width:0; flex:1">
          <a-tag :color="a.type === 'server' ? 'orange' : (a.storage_path ? 'cyan' : 'gray')">
            {{ a.type === 'server' ? '服务器' : (a.storage_path ? '制品' : '临时') }}
          </a-tag>
          <div style="min-width:0; flex:1">
            <div v-if="a.type === 'server'">
              <div style="display:flex; gap:12px; align-items:center; width:100%">
                <div style="flex:2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:500;">
                  {{ a.server || (a.server_id ? lookupHostName(a.server_id) : '-') }}
                </div>
                <div style="flex:4; color:#86909c; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                  {{ a.source_path || '-' }}
                </div>
                <div style="flex:2; color:#86909c;">
                  {{ lookupAccountName(a.account) || '-' }}
                </div>
                <div style="flex:3; color:#86909c;">
                  {{ a.remote_path || '-' }}
                </div>
              </div>
            </div>
            <div v-else>
              <div style="font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{{ a.name || a.filename || a.storage_path }}</div>
              <div style="font-size:12px; color:#86909c;">
                <span v-if="a.size">{{ formatSize(a.size) }}</span>
                <span v-if="a.checksum"> · sha256: {{ a.checksum.substr(0,12) }}...</span>
              </div>
            </div>
          </div>
        </div>
        <div>
          <a-space>
            <a-button type="text" size="small" status="danger" @click="removeArtifact(a)">移除</a-button>
          </a-space>
        </div>
      </div>
    </div>
      <div v-if="serverInlineVisible" style="margin-top:12px; border:1px dashed var(--color-border-2); padding:12px; border-radius:4px; width:calc(100% + 480px); margin-right:-240px; box-sizing:border-box; background:transparent;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <div style="font-weight:600">服务器来源列表</div>
        <a-button type="dashed" size="small" @click="addServerRow">+ 添加一行</a-button>
      </div>
      <div v-for="(row, idx) in serverRows" :key="row._uid" style="display:flex; gap:8px; margin-bottom:8px; align-items:center;">
        <a-button style="flex:4; justify-content:flex-start" type="outline" @click="openHostSelector(idx)">
          <template v-if="row.server">{{ row.server }}</template>
          <template v-else>选择源服务器</template>
        </a-button>
        <a-input v-model="row.path" placeholder="源文件路径" style="flex:10" />
        <a-select v-model="row.account" placeholder="账号" style="flex:4" :options="accounts.map(a => ({ label: a.name, value: a.id }))" />
        <a-input v-model="row.remote_path" placeholder="目标远程路径（可选）" style="flex:8" />
        <a-button type="text" status="danger" size="small" @click="removeServerRow(idx)">移除</a-button>
      </div>
      <div style="text-align:right">
        <a-button type="primary" size="small" @click="addServerEntries">确认添加</a-button>
      </div>
      <!-- HostSelector 用于选择源服务器 -->
      <HostSelector
        v-model:visible="showHostSelector"
        :hosts="hosts"
        :groups="hostGroups"
        :selected-hosts="selectedHostIdsForSelector"
        @confirm="handleHostSelectorConfirm"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import request from '@/utils/request'
import { hostApi, hostGroupApi } from '@/api/ops'
import { accountApi } from '@/api/account'
import HostSelector from '@/components/HostSelector.vue'

defineProps({
  artifacts: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:artifacts'])

const uploadList = ref<any[]>([])
const serverRows = ref<any[]>([{ _uid: Date.now().toString(), server: '', server_id: null, path: '', account: '', remote_path: '' }])
const artifacts = ref<any[]>([])

const hosts = ref<any[]>([])
const hostGroups = ref<any[]>([])
const accounts = ref<any[]>([])
const serverInlineVisible = ref(false)
const showHostSelector = ref(false)
const hostSelectorRowIdx = ref<number | null>(null)
const selectedHostIdsForSelector = ref<number[]>([])

onMounted(async () => {
  // load recent hosts and accounts for dropdowns (limited)
  try {
    const h = await hostApi.getHosts({ page_size: 100 })
    hosts.value = h.results || []
  } catch (e) {
    hosts.value = []
  }
  try {
    const a = await accountApi.getAccounts({ page_size: 200 })
    accounts.value = a.results || []
  } catch (e) {
    accounts.value = []
  }
  // load host groups for HostSelector
  try {
    const g = await hostGroupApi.getGroups({ page_size: 200 })
    hostGroups.value = g.results || []
  } catch (e) {
    hostGroups.value = []
  }
})

const onFileChange = async (files: any[]) => {
  uploadList.value = files
  for (const f of files) {
    const exists = artifacts.value.find(a => a.uid === f.uid || a.name === f.name)
    if (exists) continue
    artifacts.value.push({ uid: f.uid, name: f.name, uploading: true })
    try {
      const formData = new FormData()
      formData.append('file', f.file || f)
      const resp = await request.post('/agents/artifacts/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const data = resp.data || resp
      const meta = {
        uid: f.uid,
        name: f.name,
        storage_path: data.content?.storage_path || data.storage_path || data.content?.storage_path,
        download_url: data.content?.download_url || data.download_url || data.content?.download_url,
        checksum: data.content?.checksum || data.checksum || data.content?.checksum,
        size: data.content?.size || data.size || (f.file && f.file.size) || 0,
      }
      const idx = artifacts.value.findIndex(x => x.uid === f.uid || x.name === f.name)
      if (idx > -1) artifacts.value[idx] = meta
      else artifacts.value.push(meta)
      emit('update:artifacts', artifacts.value)
    } catch (e) {
      console.error('artifact upload failed', e)
      Message.error(`文件 ${f.name} 上传失败`)
      artifacts.value = artifacts.value.filter(x => x.uid !== f.uid && x.name !== f.name)
      emit('update:artifacts', artifacts.value)
    }
  }
}

const onFileRemove = (fileItem: any) => {
  uploadList.value = uploadList.value.filter(f => f.uid !== fileItem.uid)
  artifacts.value = artifacts.value.filter(a => a.uid !== fileItem.uid && a.name !== fileItem.name)
  emit('update:artifacts', artifacts.value)
}

const addServerRow = () => {
  serverRows.value.push({ _uid: Date.now().toString() + Math.random().toString(36).slice(2), server: '', path: '', account: '', remote_path: '' })
}

const removeServerRow = (idx: number) => {
  serverRows.value.splice(idx, 1)
}

const addServerEntries = () => {
  for (const r of serverRows.value) {
    if (!r.server && !r.path) continue
    artifacts.value.push({
      type: 'server',
      server: r.server,
      server_id: r.server_id || null,
      storage_path: undefined,
      download_url: r.path && r.path.startsWith('http') ? r.path : undefined,
      source_path: r.path,
      account: r.account,
      filename: r.path ? r.path.split('/').pop() : undefined,
      checksum: undefined,
      size: undefined,
      remote_path: r.remote_path || ''
    })
  }
  serverRows.value = [{ _uid: Date.now().toString(), server: '', path: '', account: '', remote_path: '' }]
  emit('update:artifacts', artifacts.value)
}

const removeArtifact = (a: any) => {
  artifacts.value = artifacts.value.filter(x => x !== a)
  emit('update:artifacts', artifacts.value)
}

const openDownload = (url: string) => {
  if (!url) return
  window.open(url, '_blank')
}

// HostSelector helpers
const openHostSelector = (rowIdx: number) => {
  hostSelectorRowIdx.value = rowIdx
  // pre-select if possible by server_id
  const existingId = serverRows.value[rowIdx]?.server_id
  if (existingId) {
    selectedHostIdsForSelector.value = [existingId]
  } else {
    selectedHostIdsForSelector.value = []
  }
  showHostSelector.value = true
}

const handleHostSelectorConfirm = (selection: any) => {
  if (selection && Array.isArray(selection.selectedHosts) && selection.selectedHosts.length > 0) {
    const hostId = selection.selectedHosts[0]
    const host = hosts.value.find(h => h.id === hostId)
    if (host && hostSelectorRowIdx.value !== null) {
      const idx = hostSelectorRowIdx.value
      serverRows.value[idx].server_id = host.id
      serverRows.value[idx].server = host.name || host.ip_address || String(host.id)
    }
  }
  showHostSelector.value = false
  hostSelectorRowIdx.value = null
}

const formatSize = (bytes?: number) => {
  if (!bytes && bytes !== 0) return '-'
  const kb = 1024
  if (bytes < kb) return bytes + ' B'
  const mb = kb * kb
  if (bytes < mb) return (bytes / kb).toFixed(2) + ' KB'
  return (bytes / mb).toFixed(2) + ' MB'
}

const lookupHostName = (id: number) => {
  const h = hosts.value.find(x => x.id === id)
  return h ? (h.name || h.ip_address) : ''
}

const lookupAccountName = (id: any) => {
  if (!id) return ''
  const a = accounts.value.find(x => String(x.id) === String(id))
  return a ? a.name : ''
}
</script>

<style scoped>
.artifact-item { }
</style>


