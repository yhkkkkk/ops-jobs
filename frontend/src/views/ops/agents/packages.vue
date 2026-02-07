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
          <a-space>
            <a-button type="primary" @click="handleCreatePackage">
              <template #icon>
                <IconPlus />
              </template>
              上传安装包
            </a-button>
            <a-button @click="fetchPackages">
              <template #icon>
                <IconRefresh />
              </template>
              刷新
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 搜索栏 -->
    <a-card class="mb-4">
      <a-form :model="searchForm" layout="inline">
        <a-form-item label="搜索">
          <a-input
            v-model="searchForm.search"
            placeholder="版本号、描述"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 250px"
          />
        </a-form-item>
        <a-form-item label="操作系统">
          <a-select
            v-model="searchForm.os_type"
            placeholder="请选择操作系统"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="linux">Linux</a-option>
            <a-option value="windows">Windows</a-option>
            <a-option value="darwin">macOS</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="架构">
          <a-select
            v-model="searchForm.arch"
            placeholder="请选择架构"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="amd64">AMD64</a-option>
            <a-option value="arm64">ARM64</a-option>
            <a-option value="386">i386</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="包类型">
          <a-select
            v-model="searchForm.package_type"
            placeholder="请选择类型"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 140px"
          >
            <a-option value="agent">Agent</a-option>
            <a-option value="agent-server">Agent-Server</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="存储方式">
          <a-select
            v-model="searchForm.storage_type"
            placeholder="请选择存储方式"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option value="oss">阿里云OSS</a-option>
            <a-option value="s3">AWS S3</a-option>
            <a-option value="cos">腾讯云COS</a-option>
            <a-option value="minio">MinIO</a-option>
            <a-option value="rustfs">RustFS</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="状态">
          <a-select
            v-model="searchForm.is_active"
            placeholder="请选择状态"
            allow-clear
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 120px"
          >
            <a-option :value="true">启用</a-option>
            <a-option :value="false">禁用</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">
            <template #icon>
              <IconSearch />
            </template>
            搜索
          </a-button>
          <a-button @click="handleReset" style="margin-left: 8px">
            <template #icon>
              <IconRefresh />
            </template>
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 安装包列表 -->
    <div class="table-container">
      <a-table
        :columns="columns"
        :data="packages"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #storage_type="{ record }">
          <a-tag :color="getStorageTypeColor(record.storage_type)">
            {{ getStorageTypeDisplay(record.storage_type) }}
          </a-tag>
        </template>

        <template #file_size="{ record }">
          {{ formatFileSize(record.file_size) }}
        </template>

        <template #status="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>

        <template #is_default="{ record }">
          <a-tag v-if="record.is_default" color="blue">默认</a-tag>
          <span v-else>-</span>
        </template>

        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="handleEdit(record)">
              编辑
            </a-button>
            <a-button type="text" size="small" @click="handleDownload(record)">
              下载
            </a-button>
            <a-button
              type="text"
              size="small"
              status="danger"
              @click="handleDelete(record)"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 创建/编辑对话框 -->
    <a-modal
      v-model:visible="packageModalVisible"
      :title="isEdit ? '编辑安装包' : '上传安装包'"
      width="600px"
      @cancel="handleModalCancel"
      :confirm-loading="submitLoading"
    >
      <a-form
        ref="packageFormRef"
        :model="packageForm"
        :rules="packageFormRules"
        layout="vertical"
      >
        <a-form-item label="包类型" field="package_type" required>
          <a-radio-group v-model="packageForm.package_type" :disabled="isEdit">
            <a-radio value="agent">Agent</a-radio>
            <a-radio value="agent-server">Agent-Server</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="版本号" field="version" required>
          <a-input
            v-model="packageForm.version"
            placeholder="例如: 1.0.0, v1.0.0"
            :max-length="50"
          />
        </a-form-item>

        <a-form-item label="操作系统" field="os_type" required>
          <a-select
            v-model="packageForm.os_type"
            placeholder="请选择操作系统"
          >
            <a-option value="linux">Linux</a-option>
            <a-option value="windows">Windows</a-option>
            <a-option value="darwin">macOS</a-option>
          </a-select>
        </a-form-item>

        <a-form-item label="架构" field="arch" required>
          <a-select
            v-model="packageForm.arch"
            placeholder="请选择架构"
          >
            <a-option value="amd64">AMD64/x86_64</a-option>
            <a-option value="arm64">ARM64</a-option>
            <a-option value="386">i386</a-option>
          </a-select>
        </a-form-item>

        <a-form-item label="存储方式" field="storage_type" v-if="!isEdit">
          <a-radio-group v-model="packageForm.storage_type">
            <a-radio value="oss">阿里云OSS</a-radio>
            <a-radio value="s3">AWS S3</a-radio>
            <a-radio value="cos">腾讯云COS</a-radio>
            <a-radio value="minio">MinIO</a-radio>
            <a-radio value="rustfs">RustFS</a-radio>
          </a-radio-group>
          <template #extra>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <icon-info-circle />
              <span>选择文件存储方式，对象存储需要在系统配置中设置相关参数</span>
            </div>
          </template>
        </a-form-item>

        <!-- 编辑时的存储方式显示 -->
        <a-form-item label="存储方式" v-if="isEdit">
          <a-input :model-value="getStorageTypeDisplay(currentPackage?.storage_type)" readonly>
            <template #prefix>
              <IconLock />
            </template>
          </a-input>
          <template #extra>
            <div style="color: #ff7d00; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;">
              <icon-info-circle />
              <span>更新时无法修改存储方式，如需更改存储方式请重新上传安装包</span>
            </div>
          </template>
        </a-form-item>

        <a-form-item label="安装包文件" field="file" :required="!isEdit">
          <a-upload
            :file-list="fileList"
            :auto-upload="false"
            :limit="1"
            accept=".tar.gz,.zip,.tgz,.exe"
            :show-file-list="false"
            @change="handleFileChange"
            @remove="handleFileRemove"
            class="package-upload"
          >
            <template #upload-button>
              <a-button type="outline">
                <template #icon>
                  <IconUpload />
                </template>
                选择文件
              </a-button>
            </template>
          </a-upload>
          <!-- 自定义文件列表，包含删除按钮 -->
          <div v-if="fileList.length > 0" class="custom-package-file-list">
            <div
              v-for="(fileItem, index) in fileList"
              :key="fileItem.uid || index"
              class="custom-package-file-item"
            >
              <div class="package-file-info">
                <IconFile class="package-file-icon" />
                <div class="package-file-details">
                  <div class="package-file-name">{{ fileItem.name || (fileItem.originFile as File)?.name || '未知文件' }}</div>
                  <div class="package-file-size">{{ formatFileSize((fileItem.file as File)?.size || (fileItem.originFile as File)?.size || 0) }}</div>
                </div>
              </div>
              <div class="package-file-actions">
                <a-button
                  type="text"
                  size="small"
                  @click="handleFileRemove"
                  class="package-remove-btn"
                >
                  <template #icon>
                    <IconClose />
                  </template>
                </a-button>
              </div>
            </div>
          </div>
          <div v-else-if="isEdit && currentPackage?.file_name" class="current-file-info">
            <IconFile class="package-file-icon" />
            <span>当前文件: {{ currentPackage.file_name }}</span>
            <span class="file-size-text">({{ formatFileSize(currentPackage.file_size || 0) }})</span>
          </div>
        </a-form-item>

        <a-form-item label="描述" field="description">
          <a-textarea
            v-model="packageForm.description"
            placeholder="请输入描述信息"
            :max-length="500"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>

        <a-form-item label="状态">
          <a-space>
            <a-checkbox v-model="packageForm.is_active">启用</a-checkbox>
            <a-checkbox v-model="packageForm.is_default">设为默认版本</a-checkbox>
          </a-space>
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button @click="handleModalCancel">取消</a-button>
          <a-button type="primary" @click="handleSubmitPackage" :loading="submitLoading">
            {{ isEdit ? '保存' : '上传' }}
          </a-button>
        </a-space>
      </template>
    </a-modal>

    <!-- 删除确认对话框 -->
    <a-modal
      v-model:visible="deleteModalVisible"
      title="确认删除"
      @ok="handleConfirmDelete"
      @cancel="deleteModalVisible = false"
    >
      <div>
        <p>确定要删除安装包 <strong>{{ currentPackage?.version }} - {{ currentPackage?.os_type_display }} - {{ currentPackage?.arch_display }}</strong> 吗？</p>
        <p style="color: #f53f3f; margin-top: 8px;">此操作不可恢复，请谨慎操作！</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconPlus,
  IconRefresh,
  IconSearch,
  IconUpload,
  IconFile,
  IconClose,
  IconLock, IconInfoCircle,
} from '@arco-design/web-vue/es/icon'
import { packageApi, type AgentPackage } from '@/api/agents'
import type { FileItem } from '@arco-design/web-vue/es/upload'
import { formatFileSize, formatDateTime } from '@/utils/date'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// 响应式数据
const loading = ref(false)
const packages = ref<AgentPackage[]>([])
const searchForm = reactive({
  search: '',
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
const fileList = ref<FileItem[]>([])

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
const packageFormRules = {
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
      validator: (value: any, callback: (error?: string) => void) => {
        if (!isEdit.value && !value) {
          callback('请上传文件')
        } else {
          callback()
        }
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

// 表格列定义
const columns = ref([
  {
    title: '类型',
    dataIndex: 'package_type_display',
    width: 120,
  },
  {
    title: '版本号',
    dataIndex: 'version',
    width: 120,
  },
  {
    title: '操作系统',
    dataIndex: 'os_type_display',
    width: 100,
  },
  {
    title: '架构',
    dataIndex: 'arch_display',
    width: 100,
  },
  {
    title: '存储方式',
    dataIndex: 'storage_type_display',
    width: 120,
    slotName: 'storage_type',
  },
  {
    title: '文件名',
    dataIndex: 'file_name',
    width: 100,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '文件大小',
    dataIndex: 'file_size',
    width: 120,
    slotName: 'file_size',
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    width: 100,
    slotName: 'status',
  },
  {
    title: '默认版本',
    dataIndex: 'is_default',
    width: 100,
    slotName: 'is_default',
  },
  {
    title: '创建人',
    dataIndex: 'created_by_name',
    width: 100,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 180,
    slotName: 'created_at',
  },
  {
    title: '操作',
    width: 200,
    fixed: 'right',
    slotName: 'actions',
  },
])

// 获取安装包列表
const fetchPackages = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
    }
  if (searchForm.search) {
    params.search = searchForm.search
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
  } catch (error: any) {
    Message.error(error.message || '获取安装包列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索（带防抖）
const handleSearch = () => {
  // 清除之前的防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 设置新的防抖定时器（300ms）
  searchDebounceTimer = setTimeout(() => {
  pagination.current = 1
  fetchPackages()
  }, 300)
}

// 重置搜索
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchForm.search = ''
  searchForm.os_type = ''
  searchForm.arch = ''
  searchForm.package_type = ''
  searchForm.storage_type = ''
  searchForm.is_active = undefined
  handleSearch()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchPackages()
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchPackages()
}

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

// 文件变化处理
const handleFileChange = (files: FileItem[]) => {
  // 只保留最后一个文件
  fileList.value = files.slice(-1)
  if (fileList.value.length > 0) {
    const item = fileList.value[0]
    // 尝试多种方式获取文件对象
    if (item.file) {
      packageForm.file = item.file as File
    } else if (item.originFile) {
      packageForm.file = item.originFile as File
    } else if (item.response) {
      // 如果是上传后的响应，不需要设置文件
      packageForm.file = null
    }
  } else {
    packageForm.file = null
  }
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
    Message.error('请上传文件')
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
      Message.success('安装包更新成功')
    } else {
      await packageApi.createPackage(formData)
      Message.success('安装包上传成功')
    }

    packageModalVisible.value = false
    fetchPackages()
  } catch (error: any) {
    Message.error(error.message || (isEdit.value ? '更新失败' : '上传失败'))
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
    Message.error(error.message || '下载失败')
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
    Message.success('删除成功')
    deleteModalVisible.value = false
    currentPackage.value = null
    fetchPackages()
  } catch (error: any) {
    Message.error(error.message || '删除失败')
  }
}

onMounted(() => {
  fetchPackages()
})
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

onMounted(() => {
  fetchPackages()
})
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
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
}

.package-file-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.package-file-icon {
  font-size: 16px;
  color: var(--color-text-3);
  margin-right: 8px;
}

.package-file-details {
  flex: 1;
}

.package-file-name {
  font-size: 14px;
  color: var(--color-text-1);
  font-weight: 500;
  margin-bottom: 2px;
}

.package-file-size {
  font-size: 12px;
  color: var(--color-text-3);
}

.package-file-actions {
  display: flex;
  align-items: center;
}

.package-remove-btn {
  color: var(--color-text-3);
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
  background-color: var(--color-fill-1);
  border-radius: 6px;
  color: var(--color-text-2);
  font-size: 14px;
}

.current-file-info .package-file-icon {
  margin-right: 8px;
}

.file-size-text {
  margin-left: 8px;
  color: var(--color-text-3);
  font-size: 12px;
}
</style>
