<template>
  <div class="packages-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>Agent 安装包管理</h2>
          <p class="header-desc">管理 Agent 安装包版本、上传和下载</p>
        </div>
        <div class="header-right">
          <n-space>
            <n-button type="primary" @click="handleCreatePackage">
              <template #icon>
                <Plus />
              </template>
              上传安装包
            </n-button>
            <n-button @click="fetchPackages">
              <template #icon>
                <RefreshCw />
              </template>
              刷新
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <!-- 搜索栏 -->
    <n-card class="mb-4">
      <div class="form-grid-row">
        <div class="form-grid-col" style="grid-column: span 3">
          <n-select
            v-model:value="searchForm.version"
            placeholder="版本号"
            clearable
            filterable
           
            @search="handleVersionSearch"
            @update:value="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="(versionOptions || []).map((version: any) => ({ label: String(version), value: String(version) }))" />
        </div>
        <div class="form-grid-col" style="grid-column: span 2">
                    <n-select
            v-model:value="searchForm.os_type"
            placeholder="操作系统"
            clearable
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="selectOptions1" />
        </div>
        <div class="form-grid-col" style="grid-column: span 3">
                    <n-select
            v-model:value="searchForm.arch"
            placeholder="架构"
            clearable
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="selectOptions2" />
        </div>
        <div class="form-grid-col" style="grid-column: span 3">
                    <n-select
            v-model:value="searchForm.package_type"
            placeholder="包类型"
            clearable
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="selectOptions3" />
        </div>
        <div class="form-grid-col" style="grid-column: span 4">
                    <n-select
            v-model:value="searchForm.storage_type"
            placeholder="存储方式"
            clearable
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 100%" :options="selectOptions4" />
        </div>
        <div class="form-grid-col" style="grid-column: span 3">
          <n-select
            :value="(searchForm.is_active as any)"
            placeholder="状态"
            clearable
            :options="[{ label: '启用', value: true }, { label: '禁用', value: false }] as any"
            style="width: 100%"
            @update:value="(v: any) => { searchForm.is_active = v; handleSearch() }"
          />
        </div>
        <div class="form-grid-col" style="grid-column: span 6">
          <div class="search-actions">
            <n-space>
              <n-button type="primary" @click="handleSearch">
                <template #icon>
                  <Search />
                </template>
                搜索
              </n-button>
              <n-button @click="handleReset">
                <template #icon>
                  <RefreshCw />
                </template>
                重置
              </n-button>
            </n-space>
          </div>
        </div>
      </div>
    </n-card>

    <!-- 安装包列表 -->
    <div class="table-container">
      <n-data-table
        :columns="columns"
        :data="packages"
        :loading="loading"
        :pagination="tablePagination"
        remote
        :scroll-x="1200"
      />
    </div>

    <!-- 创建/编辑对话框 -->
    <n-modal preset="card" :style="{ width: '600px' }"
      v-model:show="packageModalVisible"
      :title="isEdit ? '编辑安装包' : '上传安装包'"
     
      @cancel="handleModalCancel"
      :confirm-loading="submitLoading"
    >
      <n-form
        ref="packageFormRef"
        :model="packageForm"
        :rules="packageFormRules"
        layout="vertical"
      >
        <n-form-item label="包类型" path="package_type" required>
          <n-radio-group v-model:value="packageForm.package_type" :disabled="isEdit">
            <n-radio value="agent">Agent</n-radio>
            <n-radio value="agent-server">Agent-Server</n-radio>
          </n-radio-group>
        </n-form-item>

        <n-form-item label="版本号" path="version" required>
          <n-input
            v-model:value="packageForm.version"
            placeholder="例如: 1.0.0, v1.0.0"
            :max-length="50"
          />
        </n-form-item>

        <n-form-item label="操作系统" path="os_type" required v-if="!isEdit">
                    <n-select
            v-model:value="packageForm.os_type"
            placeholder="请选择操作系统" :options="selectOptions5" />
        </n-form-item>

        <n-form-item label="操作系统" v-if="isEdit">
          <n-input :model-value="getOsTypeDisplay(currentPackage?.os_type)" readonly>
            <template #prefix>
              <Lock :size="14" />
            </template>
          </n-input>
          <template #footer>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <Info  />
              <span>更新时无法修改操作系统，如需更改请重新上传安装包</span>
            </div>
          </template>
        </n-form-item>

        <n-form-item label="架构" path="arch" required v-if="!isEdit">
                    <n-select
            v-model:value="packageForm.arch"
            placeholder="请选择架构" :options="selectOptions6" />
        </n-form-item>

        <n-form-item label="架构" v-if="isEdit">
          <n-input :model-value="getArchDisplay(currentPackage?.arch)" readonly>
            <template #prefix>
              <Lock :size="14" />
            </template>
          </n-input>
          <template #footer>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <Info  />
              <span>更新时无法修改架构，如需更改请重新上传安装包</span>
            </div>
          </template>
        </n-form-item>

        <n-form-item label="存储方式" path="storage_type" v-if="!isEdit">
          <n-radio-group v-model:value="packageForm.storage_type">
            <n-radio value="oss">阿里云OSS</n-radio>
            <n-radio value="s3">AWS S3</n-radio>
            <n-radio value="cos">腾讯云COS</n-radio>
            <n-radio value="minio">MinIO</n-radio>
            <n-radio value="rustfs">RustFS</n-radio>
          </n-radio-group>
          <template #footer>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <Info  />
              <span>选择文件存储方式，对象存储需要在系统配置中设置相关参数</span>
            </div>
          </template>
        </n-form-item>

        <!-- 编辑时的存储方式显示 -->
        <n-form-item label="存储方式" v-if="isEdit">
          <n-input :model-value="getStorageTypeDisplay(currentPackage?.storage_type)" readonly>
            <template #prefix>
              <Lock :size="14" />
            </template>
          </n-input>
          <template #footer>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <Info  />
              <span>更新时无法修改存储方式，如需更改存储方式请重新上传安装包</span>
            </div>
          </template>
        </n-form-item>

        <n-form-item label="安装包文件" path="file" :required="!isEdit">
          <n-upload
            :file-list="fileList"
            :default-upload="false"
            :limit="1"
            accept=".tar.gz,.zip,.tgz,.exe"
            :show-file-list="false"
            @update:file-list="handleFileListUpdate"
            @remove="handleFileRemove"
            class="package-upload"
          >
            <n-button secondary>
              <template #icon>
                <Upload />
              </template>
              选择文件
            </n-button>
          </n-upload>
          <!-- 自定义文件列表，包含删除按钮 -->
          <div v-if="fileList.length > 0" class="custom-package-file-list">
            <div
              v-for="(fileItem, index) in fileList"
              :key="fileItem.uid || index"
              class="custom-package-file-item"
            >
              <div class="package-file-info">
                <FileText class="package-file-icon" />
                <div class="package-file-details">
                  <div class="package-file-name">{{ fileItem.name || (fileItem.originFile as File)?.name || '未知文件' }}</div>
                  <div class="package-file-size">{{ formatFileSize((fileItem.file as File)?.size || (fileItem.originFile as File)?.size || 0) }}</div>
                </div>
              </div>
              <div class="package-file-actions">
                <n-button
                  text
                  size="small"
                  @click="handleFileRemove"
                  class="package-remove-btn"
                >
                  <template #icon>
                    <X />
                  </template>
                </n-button>
              </div>
            </div>
          </div>
          <div v-else-if="isEdit && currentPackage?.file_name" class="current-file-info">
            <FileText class="package-file-icon" />
            <span>当前文件: {{ currentPackage.file_name }}</span>
            <span class="file-size-text">({{ formatFileSize(currentPackage.file_size || 0) }})</span>
          </div>
        </n-form-item>

        <n-form-item label="描述" path="description">
          <n-input type="textarea"
            v-model:value="packageForm.description"
            placeholder="请输入描述信息"
            :max-length="500"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </n-form-item>

        <n-form-item label="状态">
          <n-space>
            <n-checkbox v-model:checked="packageForm.is_active">启用</n-checkbox>
            <n-checkbox v-model:checked="packageForm.is_default">设为默认版本</n-checkbox>
          </n-space>
        </n-form-item>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button @click="handleModalCancel">取消</n-button>
          <n-button type="primary" @click="handleSubmitPackage" :loading="submitLoading">
            {{ isEdit ? '保存' : '上传' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 删除确认对话框 -->
    <n-modal preset="card"
      v-model:show="deleteModalVisible"
      title="确认删除"
      @ok="handleConfirmDelete"
      @cancel="deleteModalVisible = false"
    >
      <div>
        <p>确定要删除安装包 <strong>{{ currentPackage?.version }} - {{ currentPackage?.os_type_display }} - {{ currentPackage?.arch_display }}</strong> 吗？</p>
        <p style="color: #f53f3f; margin-top: 8px;">此操作不可恢复，请谨慎操作！</p>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { packageApi, type AgentPackage } from '@/api/agents'
import { useFilterQuerySync, parseBooleanQuery } from '@/composables/useFilterQuerySync'
import type { UploadFileInfo } from 'naive-ui'
import { formatFileSize, formatDateTime } from '@/utils/date'
import { useRoute } from 'vue-router'
import { NButton, NCard, NCheckbox, NDataTable, NForm, NFormItem, NInput, NModal, NRadio, NRadioGroup, NSelect, NSpace, NTag, NUpload, type DataTableColumns, type FormRules, useMessage } from 'naive-ui'
import { FileText, Info, Lock, Plus, RefreshCw, Search, Upload } from 'lucide-vue-next'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const message = useMessage()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const packages = ref<AgentPackage[]>([])
const versionOptions = ref<string[]>([])
const availableVersions = ref<string[]>([])

const searchForm = reactive({
  version: '',
  os_type: '',
  arch: '',
  package_type: '',
  storage_type: '',
  is_active: undefined as boolean | undefined,
})

// 对话框相关
const packageModalVisible = ref(false)
const deleteModalVisible = ref(false)
const submitLoading = ref(false)
const packageFormRef = ref()
const isEdit = ref(false)
const currentPackage = ref<AgentPackage | null>(null)
const fileList = ref<UploadFileInfo[]>([])

// 表单数据
const packageForm = reactive({
  package_type: 'agent' as 'agent' | 'agent-server',
  version: '',
  os_type: '' as 'linux' | 'windows' | 'darwin' | '',
  arch: '' as 'amd64' | 'arm64' | '386' | '',
  file: null as File | null,
  storage_type: 'oss' as 'oss' | 's3' | 'cos' | 'minio' | 'rustfs',
  description: '',
  is_active: true,
  is_default: false,
})

// 表单验证规则
const packageFormRules: FormRules = {
  package_type: [
    { required: true, message: '请选择包类型' },
  ],
  version: [
    { required: true, message: '请输入版本号' },
  ],
  os_type: [
    { required: true, message: '请选择操作系统' },
  ],
  arch: [
    { required: true, message: '请选择架构' },
  ],
  file: [
    {
      validator: (_rule: unknown, value: any) => {
        if (!isEdit.value && !value) {
          return new Error('请上传文件')
        }
        return true
      },
    },
  ],
}

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  fields: [
    { key: 'version' },
    { key: 'os_type' },
    { key: 'arch' },
    { key: 'package_type' },
    { key: 'storage_type' },
    { key: 'is_active', fromQuery: parseBooleanQuery }
  ]
})

// 表格列定义
const columns: DataTableColumns<any> = [
  { title: '类型', key: 'package_type_display', width: 130, render: (row) => row.package_type_display },
  { title: '版本号', key: 'version', width: 100, render: (row) => row.version },
  { title: '操作系统', key: 'os_type_display', width: 100, render: (row) => row.os_type_display },
  { title: '架构', key: 'arch_display', width: 150, render: (row) => row.arch_display },
  {
    title: '存储方式',
    key: 'storage_type',
    width: 120,
    render: (row) => h(NTag, { type: getStorageTypeColor(row.storage_type) as any }, { default: () => getStorageTypeDisplay(row.storage_type) }),
  },
  { title: '文件名', key: 'file_name', width: 140, ellipsis: { tooltip: true }, render: (row) => row.file_name },
  { title: '文件大小', key: 'file_size', width: 120, render: (row) => formatFileSize(row.file_size) },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => h(NTag, { type: row.is_active ? 'success' : 'error' }, { default: () => (row.is_active ? '启用' : '禁用') }),
  },
  {
    title: '默认版本',
    key: 'is_default',
    width: 100,
    render: (row) => (row.is_default ? h(NTag, { type: 'info' }, { default: () => '默认' }) : h('span', '-')),
  },
  { title: '创建人', key: 'created_by_name', width: 100, render: (row) => row.created_by_name },
  { title: '创建时间', key: 'created_at', width: 180, render: (row) => formatDateTime(row.created_at) },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render: (row) =>
      h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NButton, { text: true, size: 'small', onClick: () => handleEdit(row) }, { default: () => '编辑' }),
          h(NButton, { text: true, size: 'small', onClick: () => handleDownload(row) }, { default: () => '下载' }),
          h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' }),
        ],
      }),
  },
]

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))

// 获取安装包列表
const fetchPackages = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
  if (searchForm.version) {
    params.version = searchForm.version
  }
  if (searchForm.package_type) {
    params.package_type = searchForm.package_type
  }
  if (searchForm.os_type) {
    params.os_type = searchForm.os_type
  }
    if (searchForm.arch) {
      params.arch = searchForm.arch
    }
    if (searchForm.storage_type) {
      params.storage_type = searchForm.storage_type
    }
    if (searchForm.is_active !== undefined) {
      params.is_active = searchForm.is_active
    }

    const response = await packageApi.getPackages(params)
    packages.value = response.results
    pagination.total = response.total
    buildAvailableVersions()
  } catch (error: any) {
    message.error(error.message || '获取安装包列表失败')
  } finally {
    loading.value = false
  }
}

const buildAvailableVersions = () => {
  const set = new Set<string>()
  packages.value.forEach((pkg) => {
    if (pkg.version) {
      set.add(pkg.version)
    }
  })
  const list = Array.from(set)
  list.sort((a, b) => b.localeCompare(a))
  availableVersions.value = list
  versionOptions.value = [...list]
}

const filterVersions = (searchValue: string) => {
  if (!searchValue.trim()) {
    return [...availableVersions.value]
  }
  const searchTerm = searchValue.toLowerCase().trim()
  return availableVersions.value.filter(version =>
    version.toLowerCase().includes(searchTerm)
  )
}

const handleVersionSearch = (value: string) => {
  versionOptions.value = filterVersions(value)
}

watch(
  () => route.query,
  () => {
    initFromQuery()
    fetchPackages()
  },
  { immediate: true }
)

// 搜索（带防抖）
const handleSearch = () => {
  // 清除之前的防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 设置新的防抖定时器（300ms）
  searchDebounceTimer = setTimeout(() => {
    pagination.current = 1
    syncToQuery()
  }, 300)
}

// 重置搜索
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchForm.version = ''
  searchForm.os_type = ''
  searchForm.arch = ''
  searchForm.package_type = ''
  searchForm.storage_type = ''
  searchForm.is_active = undefined
  pagination.current = 1
  syncToQuery()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  syncToQuery()
}

onBeforeUnmount(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
})

// 创建安装包
const handleCreatePackage = () => {
  isEdit.value = false
  currentPackage.value = null
  fileList.value = []
  resetPackageForm()
  packageModalVisible.value = true
}

// 编辑安装包
const handleEdit = (record: AgentPackage) => {
  isEdit.value = true
  currentPackage.value = record
  fileList.value = []

  packageForm.package_type = record.package_type as any
  packageForm.version = record.version
  packageForm.os_type = record.os_type
  packageForm.arch = record.arch
  packageForm.storage_type = (record.storage_type as any) || 'oss'  // 设置当前存储类型，用于显示
  packageForm.description = record.description || ''
  packageForm.is_active = record.is_active
  packageForm.is_default = record.is_default
  packageForm.file = null

  packageModalVisible.value = true
}

// 重置表单
const resetPackageForm = () => {
  packageForm.package_type = 'agent'
  packageForm.version = ''
  packageForm.os_type = ''
  packageForm.arch = ''
  packageForm.file = null
  packageForm.storage_type = 'oss'
  packageForm.description = ''
  packageForm.is_active = true
  packageForm.is_default = false
}

// Naive Upload: update:file-list 传数组；旧 @change 是 { file, fileList }，当数组用会 silent fail
const handleFileListUpdate = (files: UploadFileInfo[]) => {
  const list = Array.isArray(files) ? files : []
  fileList.value = list.slice(-1)
  const item = fileList.value[0]
  if (!item) {
    packageForm.file = null
    return
  }
  packageForm.file = (item.file || (item as any).originFile || null) as File | null
}

// 移除文件
const handleFileRemove = () => {
  fileList.value = []
  packageForm.file = null
}

// 提交表单
const handleSubmitPackage = async () => {
  try {
    await packageFormRef.value?.validate()
  } catch (error) {
    return
  }

  // 验证：创建时必须上传文件
  if (!isEdit.value && !packageForm.file) {
    message.error('请上传文件')
    return
  }

  submitLoading.value = true

  try {
  const formData = new FormData()
  formData.append('package_type', packageForm.package_type)
  formData.append('version', packageForm.version)
  formData.append('os_type', packageForm.os_type)
  formData.append('arch', packageForm.arch)
    if (packageForm.file) {
      formData.append('file', packageForm.file)
    }
    // 更新时不传递storage_type，保持原有存储类型
    if (!isEdit.value) {
      formData.append('storage_type', packageForm.storage_type)
    }
    if (packageForm.description) {
      formData.append('description', packageForm.description)
    }
    formData.append('is_active', String(packageForm.is_active))
    formData.append('is_default', String(packageForm.is_default))

    if (isEdit.value && currentPackage.value) {
      await packageApi.updatePackage(currentPackage.value.id, formData)
      message.success('安装包更新成功')
    } else {
      await packageApi.createPackage(formData)
      message.success('安装包上传成功')
    }

    packageModalVisible.value = false
    fetchPackages()
  } catch (error: any) {
    message.error(error.message || (isEdit.value ? '更新失败' : '上传失败'))
  } finally {
    submitLoading.value = false
  }
}

// 取消对话框
const handleModalCancel = () => {
  packageModalVisible.value = false
  resetPackageForm()
  fileList.value = []
}

// 下载安装包
const handleDownload = async (record: AgentPackage) => {
  try {
    // 如果设置了外部下载地址，直接打开
    if (record.download_url) {
      window.open(record.download_url, '_blank')
      return
    }
    
    // 否则通过api下载
    const downloadUrl = `/api/agents/packages/${record.id}/download/`
    // 创建一个隐藏的a标签来触发下载
    const link = document.createElement('a')
    link.href = downloadUrl
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error: any) {
    message.error(error.message || '下载失败')
  }
}

// 删除安装包
const handleDelete = (record: AgentPackage) => {
  currentPackage.value = record
  deleteModalVisible.value = true
}

// 确认删除
const handleConfirmDelete = async () => {
  if (!currentPackage.value) return

  try {
    await packageApi.deletePackage(currentPackage.value.id)
    message.success('删除成功')
    deleteModalVisible.value = false
    currentPackage.value = null
    fetchPackages()
  } catch (error: any) {
    message.error(error.message || '删除失败')
  }
}

const getOsTypeDisplay = (osType?: string): string => {
  const typeMap: Record<string, string> = {
    linux: 'Linux',
    windows: 'Windows',
    darwin: 'macOS',
  }
  if (!osType) return '-'
  return typeMap[osType] || osType
}

const getArchDisplay = (arch?: string): string => {
  const archMap: Record<string, string> = {
    amd64: 'AMD64/x86_64',
    arm64: 'ARM64',
    386: 'i386',
  }
  if (!arch) return '-'
  return archMap[arch] || arch
}

const getStorageTypeDisplay = (storageType: string): string => {
  const typeMap: Record<string, string> = {
    oss: '阿里云OSS',
    s3: 'AWS S3',
    cos: '腾讯云COS',
    minio: 'MinIO',
    rustfs: 'RustFS',
  }
  return typeMap[storageType] || storageType
}

// 获取存储方式标签颜色
const getStorageTypeColor = (storageType: string): string => {
  const colorMap: Record<string, string> = {
    oss: 'orange',
    s3: 'purple',
    cos: 'green',
    minio: 'cyan',
    rustfs: 'magenta',
  }
  return colorMap[storageType] || 'gray'
}


// 机械转换生成的静态下拉选项
const selectOptions1 = [{ label: 'Linux', value: 'linux' }, { label: 'Windows', value: 'windows' }, { label: 'macOS', value: 'darwin' }]
const selectOptions2 = [{ label: 'AMD64', value: 'amd64' }, { label: 'ARM64', value: 'arm64' }, { label: 'i386', value: '386' }]
const selectOptions3 = [{ label: 'Agent', value: 'agent' }, { label: 'Agent-Server', value: 'agent-server' }]
const selectOptions4 = [{ label: '阿里云OSS', value: 'oss' }, { label: 'AWS S3', value: 's3' }, { label: '腾讯云COS', value: 'cos' }, { label: 'MinIO', value: 'minio' }, { label: 'RustFS', value: 'rustfs' }]
const selectOptions5 = [{ label: 'Linux', value: 'linux' }, { label: 'Windows', value: 'windows' }, { label: 'macOS', value: 'darwin' }]
const selectOptions6 = [{ label: 'AMD64/x86_64', value: 'amd64' }, { label: 'ARM64', value: 'arm64' }, { label: 'i386', value: '386' }]
</script>

<style scoped>
.packages-page {
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

.search-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: 100%;
}

.table-container {
  background: white;
  border-radius: 6px;
  overflow: auto;
  padding-bottom: 20px;
  box-sizing: border-box;
}

/* 表格样式优化 */
:deep(.arco-table) {
  .arco-table-th {
    background-color: #fff !important;
    /*font-weight: 600;*/
  }

  /* 操作列按钮间距 */
  .arco-space-item {
    margin-right: 8px;
  }
}

::deep(.arco-table-body-wrapper) {
  padding-bottom: 20px !important;
}

/* 自定义文件上传样式 */
.custom-package-file-list {
  margin-top: 12px;
}

.custom-package-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background-color: var(--app-surface-muted);
}

.package-file-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.package-file-icon {
  font-size: 16px;
  color: var(--app-muted);
  margin-right: 8px;
}

.package-file-details {
  flex: 1;
}

.package-file-name {
  font-size: 14px;
  color: var(--app-fg);
  font-weight: 500;
  margin-bottom: 2px;
}

.package-file-size {
  font-size: 12px;
  color: var(--app-muted);
}

.package-file-actions {
  display: flex;
  align-items: center;
}

.package-remove-btn {
  color: var(--app-muted);
  transition: color 0.3s;
}

.package-remove-btn:hover {
  color: var(--color-danger-6);
}

.current-file-info {
  display: flex;
  align-items: center;
  margin-top: 8px;
  padding: 8px 12px;
  background-color: var(--app-surface-muted);
  border-radius: 6px;
  color: var(--app-fg-secondary);
  font-size: 14px;
}

.current-file-info .package-file-icon {
  margin-right: 8px;
}

.file-size-text {
  margin-left: 8px;
  color: var(--app-muted);
  font-size: 12px;
}
</style>
