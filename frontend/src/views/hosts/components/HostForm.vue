<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEdit ? '编辑主机' : '新增主机'"
    :width="600"
    :footer="false"
    :mask-closable="false"
    :esc-to-close="false"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item label="主机名称" field="name">
        <a-input
          v-model="form.name"
          placeholder="请输入主机名称"
          allow-clear
        />
      </a-form-item>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="端口" field="port">
            <a-input-number
              v-model="form.port"
              :min="1"
              :max="65535"
              placeholder="22"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="操作系统" field="os_type">
            <a-select
              v-model="form.os_type"
              placeholder="请选择操作系统"
              allow-clear
            >
              <a-option value="linux">Linux</a-option>
              <a-option value="windows">Windows</a-option>
              <a-option value="aix">AIX</a-option>
              <a-option value="solaris">Solaris</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="服务器账号" field="account">
        <a-select
          v-model="form.account"
          placeholder="请选择服务器账号"
          allow-clear
          allow-search
          :loading="accountsLoading"
        >
          <a-option
            v-for="account in serverAccounts"
            :key="account.id"
            :value="account.id"
            :label="account.name"
          >
            {{ account.name }} ({{ account.username }})
          </a-option>
        </a-select>
        <div class="form-tip">
          <icon-info-circle />
          <span>用于SSH连接的服务器账号，请先在服务器账号管理中创建</span>
        </div>
      </a-form-item>

      <a-form-item label="所属分组" field="groups">
        <a-select
          v-model="form.groups"
          placeholder="请选择主机分组（可选）"
          multiple
          allow-clear
          allow-search
          :loading="groupsLoading"
        >
          <a-option
            v-for="group in hostGroups"
            :key="group.id"
            :value="group.id"
            :label="group.full_path || group.name"
          >
            <div class="group-option">
              <span
                class="group-name"
                :style="{ paddingLeft: (group.level || 0) * 16 + 'px' }"
              >
                {{ group.full_path || group.name }}
              </span>
              <span v-if="group.description" class="group-desc">
                （{{ group.description }}）
              </span>
            </div>
          </a-option>
        </a-select>
      </a-form-item>

      <!-- 网络信息 -->
      <a-divider orientation="left">网络信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="外网IP" field="public_ip">
            <a-input
              v-model="form.public_ip"
              placeholder="请输入外网IP（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="内网IP" field="internal_ip">
            <a-input
              v-model="form.internal_ip"
              placeholder="请输入内网IP（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item label="主机名称" field="hostname">
        <a-input
          v-model="form.hostname"
          placeholder="请输入主机名称（可选）"
          allow-clear
        />
      </a-form-item>

      <!-- 云厂商信息 -->
      <a-divider orientation="left">云厂商信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="云厂商" field="cloud_provider">
            <a-select
              v-model="form.cloud_provider"
              placeholder="请选择云厂商（可选）"
              allow-clear
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
        </a-col>
        <a-col :span="12">
          <a-form-item label="实例ID" field="instance_id">
            <a-input
              v-model="form.instance_id"
              placeholder="请输入实例ID（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="地域" field="region">
            <a-input
              v-model="form.region"
              placeholder="请输入地域（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="可用区" field="zone">
            <a-input
              v-model="form.zone"
              placeholder="请输入可用区（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 硬件信息 -->
      <a-divider orientation="left">硬件信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="设备类型" field="device_type">
            <a-select
              v-model="form.device_type"
              placeholder="请选择设备类型（可选）"
              allow-clear
            >
              <a-option value="vm">虚拟机</a-option>
              <a-option value="container">容器</a-option>
              <a-option value="physical">物理机</a-option>
              <a-option value="k8s_node">K8s节点</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="CPU核心数" field="cpu_cores">
            <a-input-number
              v-model="form.cpu_cores"
              :min="1"
              :max="256"
              placeholder="请输入CPU核心数"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="内存(GB)" field="memory_gb">
            <a-input-number
              v-model="form.memory_gb"
              :min="0.5"
              :max="1024"
              :precision="1"
              placeholder="请输入内存大小"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="磁盘(GB)" field="disk_gb">
            <a-input-number
              v-model="form.disk_gb"
              :min="1"
              :max="10240"
              placeholder="请输入磁盘大小"
              style="width: 100%"
            />
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 系统信息 -->
      <a-divider orientation="left">系统信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="操作系统版本" field="os_version">
            <a-input
              v-model="form.os_version"
              placeholder="请输入操作系统版本（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="内核版本" field="kernel_version">
            <a-input
              v-model="form.kernel_version"
              placeholder="请输入内核版本（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 业务信息 -->
      <a-divider orientation="left">业务信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item label="环境类型" field="environment">
            <a-select
              v-model="form.environment"
              placeholder="请选择环境类型（可选）"
              allow-clear
            >
              <a-option value="dev">开发环境</a-option>
              <a-option value="test">测试环境</a-option>
              <a-option value="staging">预生产环境</a-option>
              <a-option value="prod">生产环境</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="业务系统" field="business_system">
            <a-input
              v-model="form.business_system"
              placeholder="请输入业务系统（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item label="服务角色" field="service_role">
            <a-input
              v-model="form.service_role"
              placeholder="请输入服务角色（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>

      <!-- 管理信息 -->
      <a-divider orientation="left">管理信息</a-divider>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="负责人" field="owner">
            <a-input
              v-model="form.owner"
              placeholder="请输入负责人（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="所属部门" field="department">
            <a-input
              v-model="form.department"
              placeholder="请输入所属部门（可选）"
              allow-clear
            />
          </a-form-item>
        </a-col>
      </a-row>



      <a-form-item label="描述" field="description">
        <a-textarea
          v-model="form.description"
          placeholder="请输入主机描述（可选）"
          :rows="3"
        />
      </a-form-item>

      <!-- 自定义按钮 -->
      <a-form-item>
        <div style="text-align: right; margin-top: 20px;">
          <a-space>
            <a-button @click="handleCancel">
              取消
            </a-button>
            <a-button
              type="outline"
              @click="handleConnectionTest"
              :loading="testLoading"
              :disabled="!canTestConnection"
            >
              <template #icon>
                <icon-link />
              </template>
              连接测试
            </a-button>
            <a-button
              type="primary"
              @click="handleSubmit"
              :loading="loading"
            >
              保存
            </a-button>
          </a-space>
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<style scoped>
.form-tip {
  display: flex;
  align-items: center;
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
}

.form-tip .arco-icon {
  margin-right: 4px;
}

.group-option {
  display: flex;
  align-items: center;
  width: 100%;
}

.group-name {
  flex: 1;
  font-weight: 500;
}

.group-desc {
  font-size: 12px;
  color: #86909c;
  margin-left: 8px;
}
</style>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconInfoCircle, IconLink } from '@arco-design/web-vue/es/icon'
import { hostApi, hostGroupApi } from '@/api/ops'
import { accountApi } from '@/api/account'
import type { Host, HostGroup } from '@/types'
import { useAuthStore } from '@/stores/auth'

interface Props {
  visible: boolean
  host?: Host | null
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
  (e: 'success'): void
}

const props = withDefaults(defineProps<Props>(), {
  host: null,
})

const emit = defineEmits<Emits>()

const formRef = ref()
const loading = ref(false)
const testLoading = ref(false)
const groupsLoading = ref(false)
const accountsLoading = ref(false)
const hostGroups = ref<HostGroup[]>([])
const serverAccounts = ref<any[]>([])

// 表单数据
const form = reactive({
  name: '',
  port: 22,
  account: null as number | null,
  os_type: 'linux',
  groups: [] as number[],
  description: '',
  // 网络信息
  public_ip: '',
  internal_ip: '',
  hostname: '',
  // 云厂商信息
  cloud_provider: '',
  instance_id: '',
  region: '',
  zone: '',
  // 硬件信息
  device_type: 'vm',
  cpu_cores: null as number | null,
  memory_gb: null as number | null,
  disk_gb: null as number | null,
  // 系统信息
  os_version: '',
  kernel_version: '',
  // 业务信息
  environment: '',
  business_system: '',
  service_role: '',
  // 管理信息
  owner: '',
  department: '',
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入主机名称' },
    { minLength: 2, message: '主机名称至少2个字符' },
  ],
  port: [
    { required: true, message: '请输入端口号' },
    { type: 'number', min: 1, max: 65535, message: '端口号范围：1-65535' },
  ],
  account: [
    { required: true, message: '请选择服务器账号' },
  ],
  os_type: [
    { required: true, message: '请选择操作系统' },
  ],
  internal_ip: [
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (!value && !form.public_ip) {
          callback('至少需要配置内网IP或外网IP之一')
        } else if (value) {
          const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
          if (!ipRegex.test(value)) {
            callback('请输入有效的IP地址')
          } else {
            callback()
          }
        } else {
          callback()
        }
      },
    },
  ],
  public_ip: [
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (!value && !form.internal_ip) {
          callback('至少需要配置内网IP或外网IP之一')
        } else if (value) {
          const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/
          if (!ipRegex.test(value)) {
            callback('请输入有效的IP地址')
          } else {
            callback()
          }
        } else {
          callback()
        }
      },
    },
  ],
}

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const isEdit = computed(() => !!props.host?.id)

// 是否可以进行连接测试
const canTestConnection = computed(() => {
  return (form.internal_ip || form.public_ip) &&
         form.port &&
         form.account
})

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    name: '',
    port: 22,
    account: null,
    os_type: 'linux',
    groups: [],
    description: '',
    // 网络信息
    public_ip: '',
    internal_ip: '',
    hostname: '',
    // 云厂商信息
    cloud_provider: '',
    instance_id: '',
    region: '',
    zone: '',
    // 硬件信息
    device_type: 'vm',
    cpu_cores: null,
    memory_gb: null,
    disk_gb: null,
    // 系统信息
    os_version: '',
    kernel_version: '',
    // 业务信息
    environment: '',
    business_system: '',
    service_role: '',
    // 管理信息
    owner: '',
    department: '',
  })
  formRef.value?.resetFields()
}

// 监听主机数据变化
watch(
  () => props.host,
  (host) => {
    if (host) {
      // 编辑模式，填充表单数据
      Object.assign(form, {
        name: host.name,
        port: host.port,
        account: host.account || null,
        os_type: host.os_type || 'linux',
        groups: host.groups || [],
        description: host.description || '',
        // 网络信息
        public_ip: host.public_ip || '',
        internal_ip: host.internal_ip || '',
        hostname: host.hostname || '',
        // 云厂商信息
        cloud_provider: host.cloud_provider || '',
        instance_id: host.instance_id || '',
        region: host.region || '',
        zone: host.zone || '',
        // 硬件信息
        device_type: host.device_type || 'vm',
        cpu_cores: host.cpu_cores || null,
        memory_gb: host.memory_gb || null,
        disk_gb: host.disk_gb || null,
        // 系统信息
        os_version: host.os_version || '',
        kernel_version: host.kernel_version || '',
        // 业务信息
        environment: host.environment || '',
        business_system: host.business_system || '',
        service_role: host.service_role || '',
        // 管理信息
        owner: host.owner || '',
        department: host.department || '',
      })
    } else {
      // 新增模式，重置表单
      resetForm()
    }
  },
  { immediate: true }
)

// 提交表单
const handleSubmit = async () => {
  console.log('=== 开始提交表单 ===')
  console.log('isEdit:', isEdit.value)
  console.log('当前主机数据:', props.host)

  try {
    console.log('开始表单验证...')
    console.log('formRef.value:', formRef.value)

    // 使用简化的验证逻辑
    try {
      await formRef.value?.validate()
      console.log('表单验证通过')
    } catch (error) {
      console.log('表单验证失败:', error)
      Message.error('请检查表单输入')
      return
    }

    console.log('设置loading状态')
    loading.value = true

    const data = {
      name: form.name,
      port: form.port,
      account: form.account,
      os_type: form.os_type,
      groups: form.groups,
      description: form.description,
      // 网络信息
      public_ip: form.public_ip || null,
      internal_ip: form.internal_ip || null,
      hostname: form.hostname || null,
      // 云厂商信息
      cloud_provider: form.cloud_provider || null,
      instance_id: form.instance_id || null,
      region: form.region || null,
      zone: form.zone || null,
      // 硬件信息
      device_type: form.device_type || null,
      cpu_cores: form.cpu_cores,
      memory_gb: form.memory_gb,
      disk_gb: form.disk_gb,
      // 系统信息
      os_version: form.os_version || null,
      kernel_version: form.kernel_version || null,
      // 业务信息
      environment: form.environment || null,
      business_system: form.business_system || null,
      service_role: form.service_role || null,
      // 管理信息
      owner: form.owner || null,
      department: form.department || null,
    }

    console.log('准备调用API，数据:', data)
    console.log('groups字段详细信息:', {
      groups: data.groups,
      groupsType: typeof data.groups,
      groupsLength: data.groups?.length,
      groupsContent: data.groups?.map(g => ({ id: g, type: typeof g }))
    })
    console.log('可用的分组列表:', hostGroups.value.map(g => ({ id: g.id, name: g.name })))

    // 验证分组ID是否有效
    if (data.groups && data.groups.length > 0) {
      const validGroupIds = hostGroups.value.map(g => g.id)
      const invalidGroups = data.groups.filter(id => !validGroupIds.includes(id))
      if (invalidGroups.length > 0) {
        console.error('发现无效的分组ID:', invalidGroups)
        Message.error(`选择的分组不存在: ${invalidGroups.join(', ')}`)
        return
      }
    }

    if (isEdit.value) {
      console.log('调用更新主机API，ID:', props.host!.id)
      const result = await hostApi.updateHost(props.host!.id, data)
      console.log('更新API返回结果:', result)
      Message.success('主机更新成功')
    } else {
      console.log('调用创建主机API')
      const result = await hostApi.createHost(data)
      console.log('创建API返回结果:', result)
      Message.success('主机创建成功')
    }

    console.log('API调用成功，触发success事件')
    emit('success')
    console.log('关闭模态框')
    modalVisible.value = false
  } catch (error: any) {
    console.error('保存主机失败:', error)

    // 详细的错误信息
    let errorMessage = isEdit.value ? '主机更新失败' : '主机创建失败'
    if (error.response?.data?.message) {
      errorMessage += ': ' + error.response.data.message
    } else if (error.response?.data?.detail) {
      errorMessage += ': ' + error.response.data.detail
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }

    Message.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 扁平化树形分组数据
const flattenGroups = (groups: HostGroup[], level = 0, parentPath = ''): HostGroup[] => {
  const result: HostGroup[] = []

  for (const group of groups) {
    const fullPath = parentPath ? `${parentPath} / ${group.name}` : group.name
    const flatGroup = {
      ...group,
      level,
      full_path: fullPath
    }
    result.push(flatGroup)

    // 递归处理子分组
    if (group.children && group.children.length > 0) {
      result.push(...flattenGroups(group.children, level + 1, fullPath))
    }
  }

  return result
}

// 获取分组列表
const fetchGroups = async () => {
  groupsLoading.value = true
  try {
    // 优先尝试获取简单列表（如果后端已实现）
    try {
      const simpleResponse = await hostGroupApi.getSimpleList()
      if (simpleResponse && simpleResponse.length > 0) {
        console.log('使用简单列表API获取分组:', simpleResponse)
        hostGroups.value = simpleResponse
        return
      }
    } catch (simpleError) {
      console.log('简单列表API不可用，尝试其他方式')
    }

    // 尝试获取树形结构并扁平化
    try {
      const treeResponse = await hostGroupApi.getGroupTree()
      if (treeResponse && treeResponse.length > 0) {
        console.log('使用树形API获取分组:', treeResponse)
        hostGroups.value = flattenGroups(treeResponse)
        return
      }
    } catch (treeError) {
      console.log('树形API不可用，尝试分页API')
    }

    // 最后尝试分页API
    const paginatedResponse = await hostGroupApi.getGroups({ page_size: 20 })
    console.log('使用分页API获取分组:', paginatedResponse)
    hostGroups.value = paginatedResponse.results || []

  } catch (error) {
    console.error('获取分组列表失败:', error)
    hostGroups.value = []
    Message.warning('获取分组列表失败，请刷新重试')
  } finally {
    groupsLoading.value = false
  }
}

// 获取服务器账号列表
const fetchAccounts = async () => {
  accountsLoading.value = true
  try {
    const response = await accountApi.getAccounts({ page_size: 1000 })
    serverAccounts.value = response.results || []
  } catch (error) {
    console.error('获取服务器账号列表失败:', error)
    serverAccounts.value = []
    Message.warning('获取服务器账号列表失败')
  } finally {
    accountsLoading.value = false
  }
}

// 连接测试
const handleConnectionTest = async () => {
  if (!canTestConnection.value) {
    Message.warning('请先填写完整的连接信息（至少需要IP地址、端口和服务器账号）')
    return
  }

  if (!props.host?.id) {
    Message.warning('请先保存主机后再进行连接测试')
    return
  }

  testLoading.value = true
  try {
    const result = await hostApi.testConnection(props.host.id)
    if (result.success) {
      Message.success('连接测试成功！')
    } else {
      Message.error(result.message || '连接测试失败')
    }
  } catch (error: any) {
    console.error('连接测试失败:', error)
    let errorMessage = '连接测试失败'
    if (error.response?.data?.message) {
      errorMessage += ': ' + error.response.data.message
    } else if (error.message) {
      errorMessage += ': ' + error.message
    }
    Message.error(errorMessage)
  } finally {
    testLoading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  modalVisible.value = false
  resetForm()
}

// 监听模态框显示状态，每次打开时重新获取分组数据和账号列表
watch(
  () => props.visible,
  async (newVisible) => {
    if (newVisible) {
      // 模态框打开时重新获取分组数据和账号列表，确保数据是最新的
      await Promise.all([fetchGroups(), fetchAccounts()])
    }
  },
  { immediate: false }
)

// 组件挂载时获取分组列表
onMounted(async () => {
  // 等待认证状态确认后再发送请求
  await nextTick()

  // 检查认证状态
  const authStore = useAuthStore()
  if (!authStore.token) {
    console.warn('用户未登录，跳过分组数据获取')
    return
  }

  console.log('用户已登录，开始获取分组数据和账号列表')
  await Promise.all([fetchGroups(), fetchAccounts()])
})

// 暴露给父组件的方法
defineExpose({
  refreshGroups: fetchGroups
})
</script>

<style scoped>
.group-desc {
  color: #999;
  font-size: 12px;
}
</style>
