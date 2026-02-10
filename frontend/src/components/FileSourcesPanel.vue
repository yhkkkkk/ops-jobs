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
      <a-button type="dashed" @click="serverInlineVisible = !serverInlineVisible">
        <template #icon><icon-plus /></template>
        添加服务器文件
      </a-button>
    </div>

    <div v-if="localArtifacts && localArtifacts.length > 0" class="artifact-list artifact-list-panel">
      <div v-for="(a, idx) in localArtifacts" :key="a.uid || a.storage_path || idx" class="artifact-item" style="display:flex; align-items:center; justify-content:space-between; padding:8px; border:1px solid var(--color-border-2); border-radius:4px; margin-bottom:8px;">
        <div style="display:flex; gap:12px; align-items:center; min-width:0; flex:1">
          <a-tag :color="a.type === 'server' ? 'orange' : (a.storage_path ? 'cyan' : 'gray')">
            {{ a.type === 'server' ? '服务器' : (a.storage_path ? '制品' : '临时') }}
          </a-tag>
          <div style="min-width:0; flex:1">
            <div v-if="a.type === 'server'">
              <div class="server-row">
                <div class="server-name-status">
                  <span class="agent-dot" :style="{ background: getAgentStatusColor(a.server_id) }" />
                  <div class="server-name">
                    {{ a.server || (a.server_id ? lookupHostName(a.server_id) : '-') }}
                  </div>
                  <div class="agent-text">
                    {{ getAgentStatusText(a.server_id) }}
                  </div>
                </div>
                <div class="col-source-path">
                  {{ a.source_path || '-' }}
                </div>
                <div class="col-account">
                  {{ lookupAccountName(a.account_id || a.account) || '-' }}
                </div>
                <div class="col-remote">
                  {{ a.remote_path || '-' }}
                </div>
              </div>
            </div>
            <div v-else>
              <div v-if="a.uploading" style="display:flex; align-items:center; gap:8px;">
                <a-progress :percent="(a.progress || 0) / 100" size="small" style="flex:1" />
                <div style="width:48px; text-align:right; font-size:12px; color:#86909c;">{{ a.progress || 0 }}%</div>
              </div>
              <div v-else>
                <div style="font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{{ a.name || a.filename || a.storage_path }}</div>
                <div class="col-muted">
                  <span v-if="a.size">{{ formatSize(a.size) }}</span>
                  <span v-if="a.checksum"> · sha256: {{ a.checksum.substr(0,12) }}...</span>
                </div>
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
      <div v-if="serverInlineVisible" class="server-inline-panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <div style="font-weight:600">服务器来源列表</div>
        <a-button type="dashed" size="small" @click="addServerRow">+ 添加一行</a-button>
      </div>
      <div v-for="(row, idx) in serverRows" :key="row._uid" class="server-row">
        <div class="server-row-line">
          <a-button class="server-btn" type="outline" @click="openHostSelector(idx)">
            <template v-if="row.server">{{ row.server }}</template>
            <template v-else>选择源服务器</template>
          </a-button>
          <a-input v-model="row.path" placeholder="源文件路径" class="path-input" />
        </div>
        <div class="server-row-line">
          <a-select v-model="row.account_id" placeholder="账号" class="account-select" :options="accounts.map(a => ({ label: a.name, value: a.id }))" />
          <a-input v-model="row.remote_path" placeholder="目标远程路径（可选）" class="remote-input" />
          <a-button type="text" status="danger" size="small" @click="removeServerRow(idx)">移除</a-button>
        </div>
      </div>
      <div style="text-align:right">
        <a-button type="primary" size="small" @click="addServerEntries">确认添加</a-button>
      </div>
      <!-- HostSelector 用于选择源服务器 -->
      <HostSelector
        v-model:visible="showHostSelector"
        :hosts="hosts"
        :groups="hostGroups"
        :selected-hosts="selectedHostIdsForSelector as any"
        @confirm="handleHostSelectorConfirm"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import request from '@/utils/request'
import { hostApi, hostGroupApi } from '@/api/ops'
import { accountApi } from '@/api/account'
import HostSelector from '@/components/HostSelector.vue'

const props = defineProps({
  artifacts: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:artifacts'])

const uploadList = ref<any[]>([])
const serverRows = ref<any[]>([{ _uid: Date.now().toString(), server: '', server_id: null, path: '', account_id: '', remote_path: '' }])
const localArtifacts = ref<any[]>([])
// 记录用户已移除的文件 uid/name，防止移除后再次被自动加入显示
const removedUids = new Set<string>()

// Watch props.artifacts and sync to local state
watch(() => props.artifacts, (newVal) => {
  if (newVal && Array.isArray(newVal)) {
    // 过滤掉用户已移除但尚未过期的 artifact，避免自动重新出现
    localArtifacts.value = newVal.filter((a: any) => {
      const key = a.uid || a.name
      return !removedUids.has(key)
    })
  }
}, { immediate: true, deep: true })

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

// Upload progress smoothing helpers
const progressTargets = new Map<string, number>()
const progressTimers = new Map<string, number>()

const startProgressAnimator = (uid: string) => {
  if (progressTimers.has(uid)) return
  const timer = window.setInterval(() => {
    const idx = localArtifacts.value.findIndex(x => x.uid === uid || x.name === uid)
    if (idx === -1) {
      const t = progressTimers.get(uid)
      if (t) clearInterval(t)
      progressTimers.delete(uid)
      progressTargets.delete(uid)
      return
    }

    const target = progressTargets.get(uid) ?? (localArtifacts.value[idx].progress || 0)
    let current = Number(localArtifacts.value[idx].progress || 0)
    if (current >= target) {
      const t = progressTimers.get(uid)
      if (t) clearInterval(t)
      progressTimers.delete(uid)
      progressTargets.delete(uid)
      return
    }

    // smooth step toward target
    const step = Math.max(1, Math.ceil((target - current) / 6))
    current = Math.min(target, current + step)
    localArtifacts.value[idx].progress = current
  }, 120)

  progressTimers.set(uid, timer)
}

const stopProgressAnimator = (uid: string) => {
  const t = progressTimers.get(uid)
  if (t) {
    clearInterval(t)
    progressTimers.delete(uid)
  }
  progressTargets.delete(uid)
}

const onFileChange = async (files: any[]) => {
  uploadList.value = files
  for (const f of files) {
    const key = f.uid || f.name
    // 如果该文件之前被用户移除，但这是用户显式重新选择该文件——允许重传并移除标记
    if (removedUids.has(key)) {
      removedUids.delete(key)
    }

    const exists = localArtifacts.value.find(a => a.uid === f.uid || a.name === f.name)
    if (exists) continue
    // 加入本地制品列表并显示上传进度
    localArtifacts.value.push({ uid: f.uid, name: f.name, uploading: true, progress: 0 })
    try {
      const formData = new FormData()
      formData.append('file', f.file || f)
      const resp = await request.post('/agents/artifacts/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0, // 不设置超时时间，直到上传完成
        onUploadProgress: (e: any) => {
          const total = e.total || (f.file ? f.file.size : f.size) || 0
          const raw = total ? Math.min(100, Math.round((e.loaded / total) * 100)) : 0
          // 避免在此直接设置为 100%；由服务端响应确认上传完成后再置为 100%
          const target = raw >= 100 ? 99 : raw
          const idx = localArtifacts.value.findIndex(x => x.uid === f.uid || x.name === f.name)
          if (idx > -1) {
            // 设置平滑目标并确保动画运行
            progressTargets.set(f.uid || f.name, target)
            startProgressAnimator(f.uid || f.name)
          }
        }
      })
      const data = resp.data || resp
      const meta = {
        type: 'artifact',
        uid: f.uid,
        name: f.name,
        storage_path: data.content?.storage_path || data.storage_path || data.content?.storage_path,
        download_url: data.content?.download_url || data.download_url || data.content?.download_url,
        checksum: data.content?.checksum || data.checksum || data.content?.checksum,
        size: data.content?.size || data.size || (f.file && f.file.size) || 0,
      }
      const idx = localArtifacts.value.findIndex(x => x.uid === f.uid || x.name === f.name)
      if (idx > -1) {
        // 合并元数据并标记为已完成
        localArtifacts.value[idx] = {
          ...localArtifacts.value[idx],
          ...meta,
          uploading: false,
          progress: 100
        }
      } else {
        localArtifacts.value.push({ ...meta, uploading: false, progress: 100 })
      }
      // 上传完成：清理移除标记并停止动画
      removedUids.delete(f.uid || f.name)
      stopProgressAnimator(f.uid || f.name)
      emit('update:artifacts', localArtifacts.value)
    } catch (e) {
      console.error('artifact upload failed', e)
      Message.error(`文件 ${f.name} 上传失败`)
      localArtifacts.value = localArtifacts.value.filter(x => x.uid !== f.uid && x.name !== f.name)
      emit('update:artifacts', localArtifacts.value)
    }
  }
}

const onFileRemove = (fileItem: any) => {
  uploadList.value = uploadList.value.filter(f => f.uid !== fileItem.uid)
  // 标记为已移除，防止短时间内重复加入
  removedUids.add(fileItem.uid || fileItem.name)
  localArtifacts.value = localArtifacts.value.filter(a => a.uid !== fileItem.uid && a.name !== fileItem.name)
  emit('update:artifacts', localArtifacts.value)
}

const addServerRow = () => {
  serverRows.value.push({ _uid: Date.now().toString() + Math.random().toString(36).slice(2), server: '', path: '', account: '', remote_path: '' })
}

const removeServerRow = (idx: number) => {
  serverRows.value.splice(idx, 1)
}

const addServerEntries = () => {
  for (const r of serverRows.value) {
    if (!r.server_id || !r.path || !r.account_id) {
      Message.error('服务器来源需要选择源主机、源路径和账号')
      continue
    }
    const host = hosts.value.find(h => h.id === r.server_id)
    const serverName = r.server || host?.name || host?.ip_address || String(r.server_id)
    const sourceHost = host?.ip_address || host?.name || serverName
    localArtifacts.value.push({
      type: 'server',
      server: serverName,
      server_id: r.server_id || null,
      source_server_host: sourceHost,
      source_server_path: r.path,
      account_id: r.account_id,
      source_path: r.path,
      filename: r.path ? r.path.split('/').pop() : undefined,
      checksum: undefined,
      size: undefined,
      remote_path: r.remote_path || ''
    })
  }
  serverRows.value = [{ _uid: Date.now().toString(), server: '', server_id: null, path: '', account_id: '', remote_path: '' }]
  emit('update:artifacts', localArtifacts.value)
}

const removeArtifact = (a: any) => {
  // 标记被用户移除的 artifact
  removedUids.add(a.uid || a.name)
  localArtifacts.value = localArtifacts.value.filter(x => x !== a)
  emit('update:artifacts', localArtifacts.value)
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

const getAgentStatus = (serverId: any) => {
  if (!serverId) return 'unknown'
  const h = hosts.value.find(x => String(x.id) === String(serverId))
  return h?.agent_info?.status || (h?.agent_info?.status_display ? 'online' : 'unknown')
}

const getAgentStatusText = (serverId: any) => {
  if (!serverId) return '未知'
  const h = hosts.value.find(x => String(x.id) === String(serverId))
  if (!h) return '未知'
  return h.agent_info?.status_display || (h.agent_info?.status === 'online' ? '在线' : (h.agent_info?.status === 'offline' ? '离线' : '未知'))
}

const getAgentStatusColor = (serverId: any) => {
  const status = getAgentStatus(serverId)
  if (status === 'online') return '#52c41a'
  if (status === 'offline') return '#ff4d4f'
  return '#d9d9d9'
}
</script>

<style scoped>
.artifact-item { }
.artifact-list-panel {
  margin-top: 12px;
  border: 1px dashed var(--color-border-2);
  padding: 12px;
  border-radius: 4px;
  width: 100%;
  margin-right: 0;
  box-sizing: border-box;
  background: transparent;
}
.server-inline-panel {
  margin-top: 12px;
  border: 1px dashed var(--color-border-2);
  padding: 12px;
  border-radius: 4px;
  width: 100%;
  margin-right: 0;
  box-sizing: border-box;
  background: transparent;
}
.col-muted {
  font-size:12px;
  color:#86909c;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.server-btn {
  flex:2 1 180px;
  min-width:150px;
  justify-content:flex-start;
}
.path-input {
  flex:5 1 360px;
  min-width:260px;
}
.account-select {
  flex:1 1 140px;     /* 收缩优先 */
  min-width:120px;     /* 确保可用 */
  max-width:180px;     /* 上限，避免过长 */
}
.remote-input {
  flex:4 1 320px;
  min-width:240px;
}
.server-row {
  display:flex;
  gap:8px;     /* 两行之间的距离 */
  align-items:center;
  width:100%;
  flex-wrap:wrap;
  margin-bottom:12px;     /* 行与行之间 */
}
.server-row:last-child {
  margin-bottom:0;         /* 最后一行不多出空白 */
}
.server-row-line {
  display:flex;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;     /* 缩放/窄屏自动换行 */
}
.server-name-status { display:flex; align-items:center; gap:8px; flex:2 1 180px; min-width:150px; white-space:nowrap; overflow:hidden; }
.agent-dot { width:8px; height:8px; border-radius:50%; display:inline-block; flex:0 0 auto; }
.server-name { flex:0 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; font-weight:500; }
.agent-text { flex:0 0 auto; font-size:12px; color:#86909c; margin-left:8px; white-space:nowrap; }
.col-source-path { flex:4 1 220px; color:#86909c; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.col-account { flex:1 1 120px; color:#86909c; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.col-remote { flex:3 1 220px; color:#86909c; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
</style>
