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
              v-if="!isReadOnly"
              @click="openImportModal"
            >
              <template #icon>
                <icon-upload />
              </template>
              导入主机
            </a-button>
            <a-button 
              v-permission="{ resourceType: 'host', permission: 'add' }"
              v-if="!isReadOnly"
              @click="handleCreateGroup"
            >
              <template #icon>
                <icon-folder-add />
              </template>
              新增分组
            </a-button>
            <a-button 
              v-permission="{ resourceType: 'host', permission: 'add' }"
              v-if="!isReadOnly"
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
              :read-only="isReadOnly"
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
                      placeholder="支持多IP(内外网IP混合)，可直接粘贴多行IP地址"
                      allow-clear
                      @press-enter="handleSearch"
                      @paste="handleIpPaste"
                      @input="handleIpInput"
                      :auto-size="{ minRows: 1, maxRows: 6 }"
                      style="width: 350px"
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
          <a-form-item label="标签">
          <a-select
            v-model="searchForm.tags"
            mode="tags"
            placeholder="输入/选择标签"
            allow-clear
            allow-search
            :options="tagOptions"
            style="width: 240px"
            @change="handleSearch"
            @clear="handleSearch"
          />
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
                  style="width: 250px"
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
                  style="width: 250px"
                />
              </a-form-item>
              <a-form-item label="CPU架构">
                <a-select
                  v-model="advancedForm.cpu_arch"
                  placeholder="请选择CPU架构"
                  allow-clear
                  allow-search
                  @change="handleSearch"
                  @clear="handleSearch"
                  style="width: 180px"
                >
                  <a-option value="x86_64">x86_64</a-option>
                  <a-option value="arm64">arm64</a-option>
                  <a-option value="aarch64">aarch64</a-option>
                  <a-option value="mips">mips</a-option>
                  <a-option value="ppc64le">ppc64le</a-option>
                  <a-option value="other">其他</a-option>
                </a-select>
              </a-form-item>
              <a-form-item label="CPU逻辑核心数">
                <a-input-number
                  v-model="advancedForm.cpu_cores_min"
                  placeholder="最小值"
                  :min="0"
                  @change="handleSearch"
                  style="width: 110px"
                />
                <span style="margin: 0 6px;">~</span>
                <a-input-number
                  v-model="advancedForm.cpu_cores_max"
                  placeholder="最大值"
                  :min="0"
                  @change="handleSearch"
                  style="width: 110px"
                />
              </a-form-item>
              <a-form-item label="负责人">
                <a-input
                  v-model="advancedForm.owner"
                  placeholder="请输入负责人"
                  allow-clear
                  @press-enter="handleSearch"
                  style="width: 160px"
                />
              </a-form-item>
              <a-form-item label="所属部门">
                <a-input
                  v-model="advancedForm.department"
                  placeholder="请输入所属部门"
                  allow-clear
                  @press-enter="handleSearch"
                  style="width: 160px"
                />
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
                  v-if="!isReadOnly"
                  @click="handleBatchTest"
                  :disabled="selectedRowKeys.length === 0"
                  :loading="batchTesting"
                >
                  <template #icon>
                    <icon-wifi />
                  </template>
                  批量测试连接 ({{ selectedRowKeys.length }})
                </a-button>
                <a-dropdown v-if="!isReadOnly" @select="handleCloudSync">
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
                  v-if="!isReadOnly"
                  @click="handleBatchTest"
                  :disabled="selectedRowKeys.length === 0"
                  :loading="batchTesting"
                >
                  <template #icon>
                    <icon-wifi />
                  </template>
                  批量测试连接 ({{ selectedRowKeys.length }})
                </a-button>
                <a-dropdown v-if="!isReadOnly" @select="handleCloudSync">
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
                  <a-dropdown @select="handleBatchCopy">
                    <a-button 
                      size="small"
                    >
                      <template #icon>
                        <icon-copy />
                      </template>
                      批量复制
                      <icon-down />
                    </a-button>
                    <template #content>
                      <a-doption value="ip">
                        复制 IP
                      </a-doption>
                      <a-doption value="internal_ip">
                        复制内网 IP
                      </a-doption>
                      <a-doption value="hostname">
                        复制主机名
                      </a-doption>
                      <a-doption value="instance_id">
                        复制实例 ID / 固资号
                      </a-doption>
                    </template>
                  </a-dropdown>
                  <a-dropdown v-if="!isReadOnly">
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
                    v-permission="{ resourceType: 'host', permission: 'change' }"
                    v-if="!isReadOnly"
                    size="small"
                    @click="openBatchEdit"
                  >
                    <template #icon>
                      <icon-edit />
                    </template>
                    批量编辑
                  </a-button>
                  <a-button 
                    v-permission="{ resourceType: 'host', permission: 'execute' }"
                    v-if="!isReadOnly"
                    size="small" 
                    @click="handleBatchTest"
                  >
                    <template #icon>
                      <icon-wifi />
                    </template>
                    批量测试
                  </a-button>
                  <a-popconfirm
                    v-if="!isReadOnly"
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
        <template #ip_address="{ record }">
          <div class="ip-address-cell">
            <div v-if="record.internal_ip" class="ip-display">
              <span class="ip-label">内网:</span>
              <a-typography-text :copyable="{ text: record.internal_ip }" style="font-size: 12px;">
                {{ record.internal_ip }}
              </a-typography-text>
            </div>
            <div v-if="record.public_ip" class="ip-display">
              <span class="ip-label">外网:</span>
              <a-typography-text :copyable="{ text: record.public_ip }" style="font-size: 12px;">
                {{ record.public_ip }}
              </a-typography-text>
            </div>
            <span v-if="!record.internal_ip && !record.public_ip" class="text-gray-400">--</span>
          </div>
        </template>

        <template #os_type="{ record }">
          <a-tag v-if="record.os_type === 'windows'" class="os-windows" size="small">
            Windows
          </a-tag>
          <a-tag v-else class="os-linux" size="small">
            Linux
          </a-tag>
        </template>

        <template #account="{ record }">
          <div v-if="record.account_info">
            <a-tag color="blue" size="small">
              {{ record.account_info.name }}
            </a-tag>
            <div class="text-gray-400" style="font-size: 12px; margin-top: 2px;">
              {{ record.account_info.username }}
            </div>
          </div>
          <span v-else class="text-gray-400">未配置</span>
        </template>

        <template #status="{ record }">
          <a-tag
            :color="
              record.status === 'online'
                ? 'green'
                : record.status === 'offline'
                  ? 'red'
                  : 'orange'
            "
          >
            {{
              record.status === 'online'
                ? '在线'
                : record.status === 'offline'
                  ? '离线'
                  : '未知'
            }}
          </a-tag>
        </template>

        <template #tags="{ record }">
          <div v-if="record.tags && record.tags.length">
            <a-tag
              v-for="tag in record.tags"
              :key="tag.key || tag"
              color="arcoblue"
              size="small"
              class="mr-1 mb-1"
            >
              {{ tag.key ? (tag.value ? `${tag.key}=${tag.value}` : tag.key) : tag }}
            </a-tag>
          </div>
          <span v-else class="text-gray-400">--</span>
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
              v-if="!isReadOnly"
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
            <a-dropdown v-if="!isReadOnly">
              <a-button type="text" size="small">
                <template #icon>
                  <icon-more />
                </template>
              </a-button>
              <template #content>
                <a-doption
                  :class="{ 'disabled-option': !canEditHost(record.id) }"
                  @click="handleClickEditHost(record)"
                >
                  <template #icon>
                    <icon-edit />
                  </template>
                  编辑
                </a-doption>
                <a-divider style="margin: 4px 0;" />
                <a-doption
                  :class="['danger', { 'disabled-option': !canDeleteHost(record.id) }]"
                  @click="handleClickDeleteHost(record)"
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

    <!-- 导入主机 -->
    <a-modal
      v-model:visible="importModalVisible"
      title="导入主机（Excel）"
      width="640px"
      :mask-closable="false"
      :closable="!importing"
      unmount-on-close
      destroy-on-close
      :footer="false"
    >
      <a-alert type="info" class="mb-3">
        支持 .xlsx / .xlsm 文件，必填列包含：主机名称、IP地址、服务器账号。可选列：端口、操作系统、分组。
      </a-alert>

      <ul class="import-instructions">
        <li>服务器账号列填写账号名称，认证方式由账号配置决定。</li>
        <li>分组列可填写多个分组名称，使用逗号、分号、竖线分隔；未匹配的分组会被记录在结果中。</li>
        <li>启用"覆盖已有主机"后，将按 IP + 端口覆盖更新已有记录。</li>
      </ul>

      <a-form layout="vertical" :model="importForm">
        <a-form-item label="Excel 文件">
          <a-upload
            :file-list="importFileList"
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xlsm"
            :show-file-list="false"
            @change="handleImportFileChange"
            @remove="handleImportFileRemove"
            class="import-upload"
          >
            <template #upload-button>
              <a-button type="outline">
                <template #icon>
                  <icon-upload />
                </template>
                选择文件
              </a-button>
            </template>
          </a-upload>
          <!-- 自定义文件列表，包含删除按钮 -->
          <div v-if="importFileList.length > 0" class="custom-import-file-list">
            <div
              v-for="(fileItem, index) in importFileList"
              :key="fileItem.uid || index"
              class="custom-import-file-item"
            >
              <div class="import-file-info">
                <icon-file class="import-file-icon" />
                <div class="import-file-details">
                  <div class="import-file-name">{{ fileItem.name }}</div>
                  <div class="import-file-size">{{ formatFileSize(fileItem.file?.size || 0) }}</div>
                </div>
              </div>
              <div class="import-file-actions">
                <a-button
                  type="text"
                  size="small"
                  @click="handleImportFileRemove"
                  class="import-remove-btn"
                >
                  <template #icon>
                    <icon-close />
                  </template>
                </a-button>
              </div>
            </div>
          </div>
        </a-form-item>

        <a-form-item label="默认分组（可选）">
          <a-select
            v-model="importForm.default_group_id"
            placeholder="导入时未匹配到分组将加入此分组"
            allow-clear
            :options="groupOptions"
            :disabled="groupOptions.length === 0"
          />
        </a-form-item>

        <a-form-item>
          <a-checkbox v-model="importForm.overwrite_existing">
            覆盖已有主机（按 IP + 端口）
          </a-checkbox>
          <a-button type="text" size="small" class="download-template-btn" @click="downloadImportTemplate">
            <template #icon>
              <icon-download />
            </template>
            下载模板
          </a-button>
        </a-form-item>
      </a-form>

      <div v-if="importResult" class="import-result">
        <a-divider orientation="left">导入结果</a-divider>
        <a-descriptions :column="2" size="small" layout="vertical">
          <a-descriptions-item label="总行数">{{ importResult.summary?.total ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="新增">{{ importResult.summary?.created ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="更新">{{ importResult.summary?.updated ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="跳过">{{ importResult.summary?.skipped ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="失败" :span="2">
            <a-tag :color="(importResult.summary?.failed ?? 0) > 0 ? 'red' : 'green'">
              {{ importResult.summary?.failed ?? 0 }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <p class="import-message">{{ importResult.message }}</p>
        <p v-if="importResult.limit_note" class="import-message muted">{{ importResult.limit_note }}</p>

        <a-table
          v-if="importResult.details && importResult.details.length > 0"
          :data="importResult.details"
          :pagination="false"
          size="small"
          class="import-detail-table"
          row-key="row"
        >
          <a-table-column title="行号" data-index="row" width="70" />
          <a-table-column title="主机名" data-index="name" />
          <a-table-column title="IP地址" data-index="ip_address" />
          <a-table-column title="状态" data-index="status">
            <template #cell="{ record }">
              <a-tag
                :color="record.status === 'failed' ? 'red' : (record.status === 'skipped' ? 'orange' : 'green')"
              >
                {{ record.status }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="说明" data-index="message">
            <template #cell="{ record }">
              <span>{{ record.message || '-' }}</span>
              <span v-if="record.missing_groups?.length" class="missing-groups">
                （缺少分组：{{ record.missing_groups.join(', ') }}）
              </span>
            </template>
          </a-table-column>
        </a-table>
      </div>

      <div class="import-modal-footer">
        <a-space>
          <a-button @click="closeImportModal" :disabled="importing">取消</a-button>
          <a-button type="primary" @click="submitImportHosts" :loading="importing">
            开始导入
          </a-button>
        </a-space>
      </div>
    </a-modal>

    <!-- 批量编辑主机 -->
    <a-modal
      v-model:visible="batchEditVisible"
      title="批量编辑主机"
      width="520px"
      :mask-closable="false"
      :footer="false"
    >
      <a-alert type="info" class="mb-3">
        仅会修改下方表单中<strong>填写了值</strong>的字段，其余字段保持不变。当前选中 {{ selectedRowKeys.length }} 台主机。
      </a-alert>
      <a-form :model="batchEditForm" layout="vertical">
        <a-form-item label="标签">
          <div class="tags-editor">
            <div v-for="(t, idx) in batchTagEntries" :key="idx" class="tag-row" style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
              <a-input v-model="t.key" placeholder="键" style="width:40%" />
              <a-input v-model="t.value" placeholder="值（可选）" style="width:45%" />
              <a-button type="text" status="danger" @click="batchTagEntries.splice(idx,1)" style="width:10%">
                <template #icon><icon-delete /></template>
              </a-button>
            </div>
            <div class="tags-input-row">
              <a-button type="outline" size="small" @click="batchTagEntries.push({ key: '', value: '' })">
                <template #icon><icon-plus /></template>
                添加标签
              </a-button>
            </div>
          </div>
          <div class="form-tip" style="margin-top: 4px">
            <icon-info-circle />
            将完全替换选中主机的标签（键=值 格式）
          </div>
        </a-form-item>
        <a-form-item label="负责人">
          <a-input
            v-model="batchEditForm.owner"
            allow-clear
            placeholder="填写负责人（可选）"
          />
        </a-form-item>
        <a-form-item label="所属部门">
          <a-input
            v-model="batchEditForm.department"
            allow-clear
            placeholder="填写所属部门（可选）"
          />
        </a-form-item>
        <a-form-item label="服务角色">
          <a-input
            v-model="batchEditForm.service_role"
            allow-clear
            placeholder="填写服务角色（可选）"
          />
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea
            v-model="batchEditForm.remarks"
            allow-clear
            :auto-size="{ minRows: 2, maxRows: 4 }"
            placeholder="如需统一增加备注，可在此填写（可选）"
          />
        </a-form-item>
      </a-form>
      <div style="text-align: right; margin-top: 16px">
        <a-space>
          <a-button @click="cancelBatchEdit" :disabled="batchEditLoading">取消</a-button>
          <a-button type="primary" @click="submitBatchEdit" :loading="batchEditLoading">
            保存
          </a-button>
        </a-space>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { hostApi, hostGroupApi } from '@/api/ops'
import type { Host, HostGroup, HostImportResult } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { usePermissionsStore } from '@/stores/permissions'
import HostForm from './components/HostForm.vue'
import HostGroupTree from './components/HostGroupTree.vue'
import HostGroupForm from './components/HostGroupForm.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const hosts = ref<Host[]>([])
const formVisible = ref(false)
const currentHost = ref<Host | null>(null)
const isOpsPlatform = computed(() => {
  return route.matched.some((record) => record.meta?.platform === 'ops')
})
const isReadOnly = computed(() => !isOpsPlatform.value)

// 权限store
const permissionsStore = usePermissionsStore()

// 导入相关
const importModalVisible = ref(false)
const importFileList = ref<any[]>([])
const importing = ref(false)
const importResult = ref<HostImportResult | null>(null)
const importForm = reactive({
  default_group_id: null as number | null,
  overwrite_existing: false
})

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

const groupOptions = computed(() => {
  const result: Array<{ label: string; value: number }> = []
  const traverse = (nodes: HostGroup[] | undefined, prefix = '') => {
    if (!nodes) return
    nodes.forEach((node) => {
      const label = prefix ? `${prefix} / ${node.name}` : node.name
      result.push({ label, value: node.id })
      if (node.children && node.children.length > 0) {
        traverse(node.children, label)
      }
    })
  }
  traverse(hostGroupTree.value, '')
  return result
})

// 标签选项：全局聚合（跨页），避免只显示当前页
const tagSet = ref<Set<string>>(new Set())
const tagOptions = computed(() => Array.from(tagSet.value).map(t => ({ label: t, value: t })))

const collectTags = (list: Host[]) => {
  list.forEach((host) => {
    (host.tags || []).forEach((tag: any) => {
      let label = ''
      if (tag && typeof tag === 'object') {
        const key = String(tag.key ?? '').trim()
        const value = tag.value === undefined || tag.value === null ? '' : String(tag.value).trim()
        if (!key) return
        label = value ? `${key}=${value}` : key
      } else {
        label = String(tag || '').trim()
        if (!label) return
      }
      tagSet.value.add(label)
    })
  })
}

// 批量操作相关
const selectedRowKeys = ref<number[]>([])
const batchTesting = ref(false)
const cloudSyncing = ref(false)
const batchEditVisible = ref(false)
const batchEditLoading = ref(false)
const batchEditForm = reactive({
  tags: [] as string[],
  owner: '' as string,
  department: '' as string,
  service_role: '' as string,
  remarks: '' as string,
})

// 临时 KV 编辑器数据（用于批量标签编辑界面），在打开弹窗时填充，从这里生成 batchEditForm.tags
const batchTagEntries = ref<Array<{ key: string; value: string }>>([])


// 搜索表单
const searchForm = reactive({
  name: '',
  ip_address: '',
  os_type: '',
  status: '',
  tags: [] as string[],
})

// 高级筛选表单
const advancedForm = reactive({
  cloud_provider: '',
  internal_ip: '',
  public_ip: '',
  cpu_arch: '',
  cpu_cores_min: undefined as number | undefined,
  cpu_cores_max: undefined as number | undefined,
  owner: '',
  department: '',
  region: '',
  zone: '',
})

// IP地址显示格式化
const displayIpAddress = ref('')
const displayInternalIp = ref('')
const displayPublicIp = ref('')

// 格式化IP地址显示 - 多行显示策略（粘贴/输入后美化展示）
const formatIpDisplay = (ipString: string) => {
  if (!ipString) return ''

  const ipList = ipString
    .split(/[,，\s\n\r|]+/)  // 支持逗号、空格、换行和竖线分隔
    .map(ip => ip.trim())
    .filter(ip => ip.length > 0)

  if (ipList.length <= 1) {
    return ipString
  }

  // 多IP时，每行显示3-4个IP，用竖线分隔，便于视觉分辨
  const result = []
  for (let i = 0; i < ipList.length; i += 4) {
    const lineIps = ipList.slice(i, i + 4)
    result.push(lineIps.join(' | '))
  }

  return result.join('\n')
}

// 解析IP地址输入
const parseIpInput = (input: string) => {
  if (!input) return ''

  // 将多行内容转换为空格分隔的单行，供后端搜索使用
  return input
    .split(/[\n\r|,，\s]+/)      // 统一按换行、竖线、逗号和空格拆分
    .map(ip => ip.trim())
    .filter(ip => ip.length > 0)
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
    width: 150,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: 'IP地址',
    dataIndex: 'ip_address',
    key: 'ip_address',
    slotName: 'ip_address',
    width: 150,
  },
  {
    title: '端口',
    dataIndex: 'port',
    key: 'port',
    width: 80,
    align: 'center',
  },
  {
    title: '操作系统',
    dataIndex: 'os_type',
    key: 'os_type',
    slotName: 'os_type',
    width: 120,
    align: 'center',
  },
  {
    title: '服务器账号',
    dataIndex: 'account_info',
    key: 'account',
    slotName: 'account',
    width: 120,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    slotName: 'status',
    width: 100,
    align: 'center',
  },
  {
    title: '标签',
    dataIndex: 'tags',
    key: 'tags',
    slotName: 'tags',
    width: 180,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '所属分组',
    dataIndex: 'groups_info',
    key: 'groups_info',
    slotName: 'groups',
    width: 150,
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '云厂商',
    dataIndex: 'cloud_provider_display',
    key: 'cloud_provider_display',
    slotName: 'cloud_provider',
    width: 100,
    align: 'center',
  },
  {
    title: '操作',
    key: 'actions',
    slotName: 'actions',
    width: 300,
    fixed: 'right',
    align: 'center',
  },
]


// 获取主机列表
const fetchHosts = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchForm,
      ...advancedForm,
    }

    // 构建搜索参数（后端只有 search 一个入口）
    const searchTerms: string[] = []
    if (searchForm.name) searchTerms.push(searchForm.name)

    // 处理多IP搜索 - 支持逗号、空格、换行符、竖线分隔
    if (searchForm.ip_address) {
      const ipList = searchForm.ip_address
        .split(/[,，\s\n\r|]+/)
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)

      if (ipList.length > 0) {
        searchTerms.push(...ipList)
      }
    }

    // 处理内/外网 IP 批量搜索
    if (advancedForm.internal_ip) {
      const internalIpList = advancedForm.internal_ip
        .split(/[,，\s\n\r|]+/)
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)
      if (internalIpList.length > 0) {
        searchTerms.push(...internalIpList)
      }
    }
    if (advancedForm.public_ip) {
      const publicIpList = advancedForm.public_ip
        .split(/[,，\s\n\r|]+/)
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0)
      if (publicIpList.length > 0) {
        searchTerms.push(...publicIpList)
      }
    }

    if (searchTerms.length > 0) {
      params.search = searchTerms.join(' ')
    } else {
      delete params.search
    }

    // 清理可选高级筛选参数
    if (!advancedForm.cpu_arch) delete params.cpu_arch
    if (!advancedForm.owner) delete params.owner
    if (!advancedForm.department) delete params.department
    if (advancedForm.cpu_cores_min === undefined || advancedForm.cpu_cores_min === null) {
      delete params.cpu_cores_min
    }
    if (advancedForm.cpu_cores_max === undefined || advancedForm.cpu_cores_max === null) {
      delete params.cpu_cores_max
    }

    // 标签数组转逗号分隔（对对象/空值做清洗，保持与脚本模板列表一致）
    if (Array.isArray(searchForm.tags)) {
      const cleanedTags = searchForm.tags
        .map((t: any) => {
          if (t && typeof t === 'object') {
            return String(t.value ?? t.label ?? '').trim()
          }
          return String(t ?? '').trim()
        })
        .filter(t => t.length > 0)
      if (cleanedTags.length > 0) {
        params.tags = cleanedTags.join(',')
      } else {
        delete params.tags
      }
    }

    // name 和 ip_address 只用于拼接 search，不单独传
    delete params.name
    delete params.ip_address

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
    hosts.value = response.results.map((host: any) => ({
      ...host,
      ip_address: host.ip_address || host.internal_ip || host.public_ip || '',
      account_info: host.account_info || null,
    }))
    collectTags(hosts.value)
    pagination.total = response.total ?? hosts.value.length
    totalHostCount.value = pagination.total
  } catch (error: any) {
    console.error('获取主机列表失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '获取主机列表失败'
    Message.error(errorMsg)
    hosts.value = []
    pagination.total = 0
    totalHostCount.value = 0
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
  tags: [],
})
  Object.assign(advancedForm, {
    cloud_provider: '',
    internal_ip: '',
    public_ip: '',
    cpu_arch: '',
    cpu_cores_min: undefined,
    cpu_cores_max: undefined,
    owner: '',
    department: '',
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
    linux: 'Linux',
    windows: 'Windows',
  }
  return osMap[osType as keyof typeof osMap] || 'Linux'
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
  // 判断当前是否在运维台
  const isOpsPlatform = route.path.startsWith('/ops')
  
  if (isOpsPlatform) {
    // 运维台使用 OpsHostDetail 路由
    router.push({
      name: 'OpsHostDetail',
      params: { id: record.id.toString() }
    })
  } else {
    // 作业平台使用 HostDetail 路由
    router.push({
      name: 'HostDetail',
      params: { id: record.id.toString() }
    })
  }
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
    const errMsg = error?.response?.data?.message || error?.message || '连接测试失败'
    Message.error(`主机 ${record.name} 连接测试失败：${errMsg}`)
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

const resetImportState = () => {
  importFileList.value = []
  importResult.value = null
  importForm.default_group_id = null
  importForm.overwrite_existing = false
}

const openImportModal = () => {
  importModalVisible.value = true
  importResult.value = null
}

const closeImportModal = () => {
  if (importing.value) return
  importModalVisible.value = false
  resetImportState()
}

// 文件大小格式化函数
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const handleImportFileChange = (files: any[]) => {
  importFileList.value = files.slice(-1)
}

const handleImportFileRemove = () => {
  importFileList.value = []
}

const submitImportHosts = async () => {
  if (importFileList.value.length === 0) {
    Message.warning('请先选择Excel文件')
    return
  }

  const rawFile = importFileList.value[0].file
  if (!rawFile) {
    Message.error('无法读取文件，请重新选择')
    return
  }

  const formData = new FormData()
  formData.append('file', rawFile)
  if (importForm.default_group_id) {
    formData.append('default_group_id', String(importForm.default_group_id))
  }
  formData.append('overwrite_existing', importForm.overwrite_existing ? 'true' : 'false')

  importing.value = true
  try {
    const result = await hostApi.importHostsFromExcel(formData)
    importResult.value = result
    Message.success(result?.message || '导入完成')
    fetchHosts()
    fetchGroups()
  } catch (error) {
    console.error('导入主机失败:', error)
    Message.error('导入主机失败')
  } finally {
    importing.value = false
  }
}

const downloadImportTemplate = async () => {
  try {
    const blob = await hostApi.downloadImportTemplate()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'hosts_import_template.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    Message.success('模板下载成功')
  } catch (error) {
    console.error('下载模板失败:', error)
    Message.error('模板下载失败')
  }
}

watch(importModalVisible, (visible) => {
  if (!visible && !importing.value) {
    resetImportState()
  }
})

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

// 预加载所有标签（取较大页容量），避免仅当前页
const preloadAllTags = async () => {
  try {
    const resp = await hostApi.getHosts({ page: 1, page_size: 1000 })
    const list = resp.results || []
    collectTags(list.map((h: any) => ({
      ...h,
      ip_address: h.ip_address || h.internal_ip || h.public_ip || '',
      account_info: h.account_info || null,
    })))
  } catch (err) {
    console.warn('预加载标签失败', err)
  }
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
  let loadingMessage: any
  try {
    // 使用正确的Message.loading API
    loadingMessage = Message.loading({
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
    const errMsg = error?.response?.data?.message || error?.message || '连接测试失败'
    Message.error(`分组"${group.name}"连接测试失败：${errMsg}`)
  } finally {
    if (loadingMessage) {
      loadingMessage.close()
    }
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
    const errMsg = error?.response?.data?.message || error?.message || '批量测试失败'
    Message.error(errMsg)
  } finally {
    batchTesting.value = false
  }
}

// 复制到剪贴板
const copyTextToClipboard = async (text: string, successMessage: string) => {
  if (!text) return

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    Message.success(successMessage)
  } catch (error) {
    console.error('复制到剪贴板失败:', error)
    Message.error('复制失败，请手动复制')
  }
}

// 批量复制字段
const handleBatchCopy = async (type: string) => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择主机')
    return
  }

  const selectedHosts = hosts.value.filter(host =>
    selectedRowKeys.value.includes(host.id)
  )

  let values: string[] = []
  let label = ''

  switch (type) {
    case 'ip':
      values = selectedHosts.map(h => h.internal_ip || h.public_ip || h.ip_address || '').filter(Boolean)
      label = 'IP 地址'
      break
    case 'internal_ip':
      values = selectedHosts.map(h => h.internal_ip || '').filter(Boolean)
      label = '内网 IP'
      break
    case 'hostname':
      values = selectedHosts.map(h => (h.hostname || h.name || '')).filter(Boolean)
      label = '主机名'
      break
    case 'instance_id':
      values = selectedHosts.map(h => h.instance_id || '').filter(Boolean)
      label = '实例 ID / 固资号'
      break
    default:
      return
  }

  if (!values.length) {
    Message.warning(`选中的主机没有可用的 ${label}`)
    return
  }

  const text = values.join('\n')
  await copyTextToClipboard(text, `已复制 ${values.length} 条 ${label}`)
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

// 检查当前页是否全选
const isAllCurrentPageSelected = computed(() => {
  if (hosts.value.length === 0) return false
  return hosts.value.every(host => selectedRowKeys.value.includes(host.id))
})

const canEditHost = (hostId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('host', 'change', hostId) ||
    permissionsStore.hasPermission('host', 'change')
  )
}

const canDeleteHost = (hostId: number): boolean => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('host', 'delete', hostId) ||
    permissionsStore.hasPermission('host', 'delete')
  )
}

const handleClickEditHost = (record: Host) => {
  if (!canEditHost(record.id)) {
    Message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleEdit(record)
}

const handleClickDeleteHost = (record: Host) => {
  if (!canDeleteHost(record.id)) {
    Message.warning('没有权限执行此操作，请联系管理员开放权限')
    return
  }
  handleDelete(record)
}

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

const openBatchEdit = () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要编辑的主机')
    return
  }
  // 将现有 batchEditForm.tags（字符串数组）解析为 KV 结构供编辑器使用
  batchTagEntries.value.splice(0, batchTagEntries.value.length)
  if (Array.isArray(batchEditForm.tags) && batchEditForm.tags.length > 0) {
    batchEditForm.tags.forEach((t: any) => {
      if (t && typeof t === 'string') {
        const [k, ...rest] = t.split('=')
        const key = (k || '').trim()
        const value = rest.length ? rest.join('=').trim() : ''
        if (key) batchTagEntries.value.push({ key, value })
      } else if (t && typeof t === 'object') {
        const key = String(t.key ?? '').trim()
        const value = t.value === undefined || t.value === null ? '' : String(t.value).trim()
        if (key) batchTagEntries.value.push({ key, value })
      }
    })
  }
  // 如果没有条目，初始化一个空行，方便添加
  if (batchTagEntries.value.length === 0) batchTagEntries.value.push({ key: '', value: '' })
  batchEditVisible.value = true
}

const resetBatchEditForm = () => {
  batchEditForm.tags = []
  batchEditForm.owner = ''
  batchEditForm.department = ''
  batchEditForm.service_role = ''
  batchEditForm.remarks = ''
}


const cancelBatchEdit = () => {
  batchEditVisible.value = false
  resetBatchEditForm()
}

const submitBatchEdit = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要编辑的主机')
    return
  }

  const data: Record<string, any> = {}
  Object.entries(batchEditForm).forEach(([key, value]) => {
    if (key === 'tags') {
      // 将 batchTagEntries 转换为字符串数组 "key=value" 或 "key"
      const cleanedTagsFromEntries = batchTagEntries.value
        .map(e => {
          const k = (e.key || '').trim()
          const v = e.value === undefined || e.value === null ? '' : String(e.value).trim()
          if (!k) return null
          return v ? `${k}=${v}` : k
        })
        .filter((x): x is string => !!x)
      if (cleanedTagsFromEntries.length > 0) {
        data[key] = cleanedTagsFromEntries
      }
    } else if (Array.isArray(value)) {
      const cleaned = value.map(item => String(item).trim()).filter(item => item.length > 0)
      if (cleaned.length > 0) {
        data[key] = cleaned
      }
    } else if (typeof value === 'string') {
      const trimmed = value.trim()
      if (trimmed !== '') {
        data[key] = trimmed
      }
    }
  })

  if (Object.keys(data).length === 0) {
    Message.warning('请至少填写一个要修改的字段')
    return
  }

  batchEditLoading.value = true
  try {
    const result = await hostApi.batchUpdateHosts(selectedRowKeys.value, data)
    Message.success(`批量编辑成功，已更新 ${result.updated_count} 台主机`)
    batchEditVisible.value = false
    resetBatchEditForm()
    fetchHosts()
  } catch (error) {
    console.error('批量编辑主机失败:', error)
    Message.error('批量编辑主机失败')
  } finally {
    batchEditLoading.value = false
  }
}

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
  preloadAllTags()
  fetchGroups()
})

// 标签筛选变化时自动触发搜索，避免选择后未发送请求
watch(
  () => [...searchForm.tags],
  () => {
    pagination.current = 1
    fetchHosts()
  }
)
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
  /* 普通表头背景色 */
  .arco-table-th {
    background-color: #fff !important;
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

.import-instructions {
  margin: 0 0 12px 0;
  padding-left: 18px;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.6;
}

.import-instructions code {
  background: #f2f3f5;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
  color: #1d2129;
}

.selected-file {
  margin-top: 8px;
  font-size: 13px;
  color: #1d2129;
}

.import-result {
  margin-top: 16px;
}

.import-message {
  margin: 8px 0 0;
  font-size: 13px;
  color: #1d2129;
}

.import-message.muted {
  color: #86909c;
}

.import-detail-table {
  margin-top: 12px;
  max-height: 240px;
  overflow-y: auto;
}

.missing-groups {
  display: inline-block;
  margin-left: 6px;
  color: #fa8c16;
  font-size: 12px;
}

.import-modal-footer {
  margin-top: 20px;
  text-align: right;
}

.download-template-btn {
  margin-left: 12px;
  padding-left: 0;
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

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
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

/* IP地址显示样式 */
.ip-address-cell {
  min-width: 150px;
}

.ip-display {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
  font-size: 12px;
}

.ip-display:last-child {
  margin-bottom: 0;
}

.ip-label {
  color: #86909c;
  font-size: 11px;
  flex-shrink: 0;
}

/* IP地址复制按钮样式优化 */
.ip-display :deep(.arco-typography) {
  margin: 0;
  display: inline-flex;
  align-items: center;
}

.ip-display :deep(.arco-typography-copy) {
  margin-left: 4px;
}

/* 导入文件列表样式 */
.custom-import-file-list {
  margin-top: 12px;
}

.custom-import-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
}

.import-file-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.import-file-icon {
  font-size: 16px;
  color: var(--color-text-3);
  margin-right: 8px;
}

.import-file-details {
  flex: 1;
}

.import-file-name {
  font-size: 14px;
  color: var(--color-text-1);
  font-weight: 500;
  margin-bottom: 2px;
}

.import-file-size {
  font-size: 12px;
  color: var(--color-text-3);
}

.import-file-actions {
  display: flex;
  align-items: center;
}

.import-remove-btn {
  color: var(--color-text-3);
  transition: color 0.3s;
}

.import-remove-btn:hover {
  color: var(--color-danger-6);
}
</style>
