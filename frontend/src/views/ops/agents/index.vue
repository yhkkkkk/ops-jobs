<template>
  <div class="agents-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>Agent 管理</h2>
          <p class="header-desc">管理 Agent 状态、Token 和版本信息</p>
        </div>
        <div class="header-right">
          <a-space>
            <a-button type="primary" @click="handleInstallAgent">
              <template #icon>
                <icon-plus />
              </template>
              安装 Agent
            </a-button>
            <a-button 
              v-if="selectedAgentIds.length > 0"
              type="primary" 
              status="warning"
              @click="handleBatchRegenerateScript"
            >
              <template #icon>
                <IconCopy />
              </template>
              批量重新生成脚本 ({{ selectedAgentIds.length }})
            </a-button>
            <a-button 
              v-if="selectedAgentIds.length > 0 && hasPendingAgents"
              type="primary" 
              status="danger"
              @click="handleBatchDeletePending"
            >
              <template #icon>
                <icon-delete />
              </template>
              批量删除待激活 ({{ selectedPendingCount }})
            </a-button>
            <a-button 
              v-if="selectedAgentIds.length > 0 && hasDisableableAgents"
              type="primary" 
              status="warning"
              @click="handleBatchDisable"
            >
              <template #icon>
                <icon-close-circle />
              </template>
              批量禁用 ({{ selectedDisableableCount }})
            </a-button>
            <a-button
              v-if="selectedAgentIds.length > 0 && hasEnableableAgents"
              type="primary"
              status="success"
              @click="handleBatchEnable"
            >
              <template #icon>
                <icon-check-circle />
              </template>
              批量启用 ({{ selectedEnableableCount }})
            </a-button>
            <a-button
              v-if="selectedAgentIds.length > 0"
              type="primary"
              status="warning"
              @click="handleBatchRestart"
            >
              <template #icon>
                <icon-refresh />
              </template>
              批量重启 ({{ selectedAgentIds.length }})
            </a-button>
            <a-button type="primary" status="danger" @click="handleUninstallAgent">
              <template #icon>
                <icon-delete />
              </template>
              批量卸载
            </a-button>
            <a-button @click="handleViewInstallRecords">
              <template #icon>
                <IconHistory />
              </template>
              安装记录
            </a-button>
            <a-button @click="handleViewUninstallRecords">
              <template #icon>
                <IconDelete />
              </template>
              卸载记录
            </a-button>
            <a-button @click="fetchAgents">
              <template #icon>
                <icon-refresh />
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
            placeholder="主机名、IP、版本、错误码"
            allow-clear
            @press-enter="handleSearch"
            @clear="handleSearch"
            style="width: 250px"
          />
        </a-form-item>
        <!-- 状态筛选已移除，前端展示使用 computed_status，复杂筛选请使用运维台 Dashboard -->
        <a-form-item label="标签">
          <a-select
            v-model="searchForm.tags"
            mode="tags"
            placeholder="输入/选择标签"
            allow-clear
            allow-search
            allow-create
            @change="handleSearch"
            @clear="handleSearch"
            style="width: 220px"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch">
            <template #icon>
              <icon-search />
            </template>
            搜索
          </a-button>
          <a-button @click="handleReset" style="margin-left: 8px">
            <template #icon>
              <icon-refresh />
            </template>
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 快速状态过滤器 -->
    <a-card class="mb-4">
      <div class="filter-section">
        <div class="filter-title">快速筛选：</div>
        <a-space wrap>
          <!-- 基础状态筛选 -->
          <a-button
            :type="statusFilters.online ? 'primary' : 'outline'"
            @click="toggleStatusFilter('online')"
          >
            <template #icon>
              <icon-check-circle />
            </template>
            在线Agent ({{ onlineCount }})
          </a-button>
          <a-button
            :type="statusFilters.offline ? 'primary' : 'outline'"
            @click="toggleStatusFilter('offline')"
          >
            <template #icon>
              <icon-close-circle />
            </template>
            离线Agent ({{ offlineCount }})
          </a-button>
          <a-button
            :type="statusFilters.pending ? 'primary' : 'outline'"
            @click="toggleStatusFilter('pending')"
          >
            <template #icon>
              <icon-clock-circle />
            </template>
            待激活 ({{ pendingCount }})
          </a-button>
          <a-button
            :type="statusFilters.disabled ? 'primary' : 'outline'"
            @click="toggleStatusFilter('disabled')"
          >
            <template #icon>
              <icon-stop />
            </template>
            已禁用 ({{ disabledCount }})
          </a-button>
          <!-- 分割线 -->
          <a-divider direction="vertical" style="height: 24px; margin: 0 8px;" />
          <!-- 问题状态筛选 -->
          <a-button
            :type="statusFilters.outdated ? 'primary' : 'outline'"
            @click="toggleStatusFilter('outdated')"
          >
            <template #icon>
              <icon-arrow-up />
            </template>
            版本落后 ({{ outdatedCount }})
          </a-button>
          <a-button
            :type="statusFilters.failed ? 'primary' : 'outline'"
            @click="toggleStatusFilter('failed')"
          >
            <template #icon>
              <icon-exclamation-circle />
            </template>
            最近失败 ({{ failedCount }})
          </a-button>
          <a-button
            :type="statusFilters.inactive ? 'primary' : 'outline'"
            @click="toggleStatusFilter('inactive')"
          >
            <template #icon>
              <icon-sleep />
            </template>
            长时间未活跃 ({{ inactiveCount }})
          </a-button>
          <!-- 清除筛选按钮 -->
          <a-button
            v-if="hasActiveFilters"
            @click="clearAllFilters"
            type="outline"
            status="danger"
          >
            <template #icon>
              <icon-refresh />
            </template>
            清除筛选
          </a-button>
        </a-space>

        <!-- 筛选统计信息 -->
        <div v-if="hasActiveFilters" class="filter-stats">
          <a-space>
            <span class="stats-text">
              当前显示: {{ filteredAgents.length }} / 总计: {{ agents.length }} 个Agent
            </span>
            <a-tag v-if="statusFilters.online" color="green">在线: {{ filteredOnlineCount }}</a-tag>
            <a-tag v-if="statusFilters.offline" color="red">离线: {{ filteredOfflineCount }}</a-tag>
            <a-tag v-if="statusFilters.pending" color="orange">待激活: {{ filteredPendingCount }}</a-tag>
            <a-tag v-if="statusFilters.disabled" color="gray">已禁用: {{ filteredDisabledCount }}</a-tag>
            <a-tag v-if="statusFilters.outdated" color="purple">版本落后: {{ filteredOutdatedCount }}</a-tag>
            <a-tag v-if="statusFilters.failed" color="red">最近失败: {{ filteredFailedCount }}</a-tag>
            <a-tag v-if="statusFilters.inactive" color="yellow">未活跃: {{ filteredInactiveCount }}</a-tag>
          </a-space>
        </div>
      </div>
    </a-card>

    <!-- Agent 列表 -->
    <div class="table-container">
      <a-table
        :columns="columns"
        :data="filteredAgents"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @selection-change="handleSelectionChange"
      >
        <template #host="{ record }">
          <div class="host-info">
            <div class="host-name">{{ record.host.name }}</div>
            <div class="host-ip">{{ record.host.ip_address }}</div>
          </div>
        </template>

        <template #agent_type="{ record }">
          <a-tag :color="getAgentTypeColor(record.agent_type)" size="small">
            {{ agentTypeMap[record.agent_type || 'agent'] || (record.agent_type || '-') }}
          </a-tag>
        </template>

        <template #status="{ record }">
          <a-space>
            <a-tag
              :color="getStatusColor(record.computed_status || record.status)"
              size="small"
            >
              {{ record.computed_status_display || record.status_display }}
            </a-tag>
            <a-tooltip v-if="getStatusHint(record.computed_status || record.status)" :content="getStatusHint(record.computed_status || record.status)">
              <IconInfoCircle style="color: #ff7d00; cursor: help" />
            </a-tooltip>
          </a-space>
        </template>

        <template #version="{ record }">
          <a-space>
            <span>{{ record.version || '-' }}</span>
            <a-tooltip
              v-if="record.is_version_outdated && record.version"
              :content="getVersionTooltip(record)"
            >
              <a-tag color="red" size="small">
                版本落后
              </a-tag>
            </a-tooltip>
          </a-space>
        </template>

        <template #last_heartbeat_at="{ record }">
          <span v-if="record.last_heartbeat_at">
            {{ formatTime(record.last_heartbeat_at) }}
          </span>
          <span v-else>-</span>
        </template>

        <template #resources="{ record }">
          <div v-if="(record.computed_status || record.status) === 'online' && resourcesOverview[record.id]" class="resource-overview">
            <a-tooltip :content="`CPU: ${resourcesOverview[record.id].cpu_usage?.toFixed(1) || '-'}%`">
              <div class="resource-item">
                <span class="resource-label">CPU</span>
                <a-progress
                  :percent="resourcesOverview[record.id].cpu_usage || 0"
                  :status="getResourceStatus(resourcesOverview[record.id].cpu_usage)"
                  size="small"
                  :show-text="false"
                  style="width: 60px"
                />
                <span class="resource-value">{{ resourcesOverview[record.id].cpu_usage?.toFixed(0) || '-' }}%</span>
              </div>
            </a-tooltip>
            <a-tooltip :content="`内存: ${resourcesOverview[record.id].memory_usage?.toFixed(1) || '-'}%`">
              <div class="resource-item">
                <span class="resource-label">内存</span>
                <a-progress
                  :percent="resourcesOverview[record.id].memory_usage || 0"
                  :status="getResourceStatus(resourcesOverview[record.id].memory_usage)"
                  size="small"
                  :show-text="false"
                  style="width: 60px"
                />
                <span class="resource-value">{{ resourcesOverview[record.id].memory_usage?.toFixed(0) || '-' }}%</span>
              </div>
            </a-tooltip>
          </div>
          <span v-else-if="(record.computed_status || record.status) !== 'online'" class="text-gray">-</span>
          <span v-else class="text-gray">加载中...</span>
        </template>

        <template #last_error_code="{ record }">
          <a-tag v-if="record.last_error_code" color="red" size="small">
            {{ record.last_error_code }}
          </a-tag>
          <span v-else>-</span>
        </template>

        <template #tags="{ record }">
          <div v-if="record.host?.tags && record.host.tags.length">
            <a-space wrap>
              <a-tag v-for="tag in record.host.tags" :key="tag.key || tag" size="small">
                {{ tag.key ? (tag.value ? `${tag.key}=${tag.value}` : tag.key) : tag }}
              </a-tag>
            </a-space>
          </div>
          <span v-else class="text-gray">-</span>
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button
              type="text"
              size="small"
              @click="handleViewDetail(record.id)"
            >
              <template #icon>
                <icon-eye />
              </template>
              详情
            </a-button>
            <a-button
            v-if="(record.computed_status || record.status) === 'pending'"
              type="text"
              status="warning"
              size="small"
              @click="handleRegenerateScript(record)"
            >
              <template #icon>
                <IconCopy />
              </template>
              重新生成脚本
            </a-button>
            <a-button
            v-if="(record.computed_status || record.status) !== 'pending'"
              type="text"
              size="small"
              @click="handleIssueToken(record)"
            >
              <template #icon>
                <icon-key />
              </template>
              发Token
            </a-button>
            <a-button
            v-if="((record.computed_status || record.status) === 'online') && record.is_version_outdated"
              type="text"
              status="warning"
              size="small"
              @click="handleUpgradeAgent(record)"
            >
              <template #icon>
                <icon-arrow-up />
              </template>
              升级
            </a-button>
            <a-button
            v-if="(record.computed_status || record.status) === 'online'"
              type="text"
              size="small"
              @click="handleRestartAgent(record)"
            >
              <template #icon>
                <icon-refresh />
              </template>
              重启
            </a-button>
            <a-button
            v-if="((record.computed_status || record.status) !== 'disabled') && ((record.computed_status || record.status) !== 'pending')"
              type="text"
              status="warning"
              size="small"
              @click="handleDisable(record)"
            >
              <template #icon>
                <icon-close-circle />
              </template>
              禁用
            </a-button>
            <a-button
            v-if="(record.computed_status || record.status) === 'disabled'"
              type="text"
              status="success"
              size="small"
              @click="handleEnable(record)"
            >
              <template #icon>
                <icon-check-circle />
              </template>
              启用
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 发 Token 弹窗 -->
    <a-modal
      v-model:visible="tokenModalVisible"
      title="签发 Agent Token"
      @ok="handleIssueTokenConfirm"
      @cancel="handleTokenModalCancel"
    >
      <a-form :model="tokenForm" ref="tokenFormRef">
        <a-form-item
          label="过期时间"
          field="expired_at"
        >
          <a-date-picker
            v-model="tokenForm.expired_at"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item
          label="备注"
          field="note"
        >
          <a-textarea
            v-model="tokenForm.note"
            placeholder="请输入备注"
            :max-length="255"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </a-form-item>
        <a-form-item
          label="二次确认"
          field="confirmed"
        >
          <a-checkbox v-model="tokenForm.confirmed">
            我已确认此操作（高危操作）
          </a-checkbox>
        </a-form-item>
      </a-form>
      <template #footer>
        <a-space>
          <a-button @click="handleTokenModalCancel">取消</a-button>
          <a-button type="primary" @click="handleIssueTokenConfirm" :disabled="!tokenForm.confirmed">
            确认签发
          </a-button>
        </a-space>
      </template>
    </a-modal>

    <!-- 安装 Agent 抽屉 -->
    <a-drawer
      v-model:visible="installModalVisible"
      title="安装 Agent"
      width="900px"
      :footer="false"
      placement="right"
    >
      <a-tabs v-model:active-key="installTab">
        <a-tab-pane key="select" title="选择主机">
          <div class="install-step">
            <a-form :model="installForm" layout="vertical">
              <a-form-item label="安装类型">
            <a-radio-group v-model="installForm.install_type" @change="handleInstallTypeChange">
              <a-radio value="agent">安装 Agent</a-radio>
              <a-radio value="agent-server">安装 Agent-Server</a-radio>
            </a-radio-group>
                <template #extra>
                  <div style="color: #86909c; font-size: 12px;">
                    选择安装类型后，主机列表会自动刷新并显示符合条件的主机
                  </div>
                </template>
              </a-form-item>

              <a-form-item label="选择主机">
                <a-select
                  v-model="installForm.host_ids"
                  placeholder="请选择要安装 Agent 的主机"
                  multiple
                  :max-tag-count="3"
                  allow-search
                  :filter-option="filterHostOption"
                  style="width: 100%"
                >
                  <a-option
                    v-for="host in availableHosts"
                    :key="host.id"
                    :value="host.id"
                    :label="getHostLabel(host)"
                  >
                    {{ getHostLabel(host) }}
                  </a-option>
                </a-select>
                <template #extra>
                  <a-link @click="fetchAvailableHosts">刷新主机列表</a-link>
                </template>
              </a-form-item>
              <template v-if="installForm.install_type === 'agent'">
                <a-form-item label="Agent-Server 地址">
                  <a-input
                    v-model="installForm.agent_server_url"
                    placeholder="例如: ws://agent-server:8080"
                  />
                </a-form-item>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="WS 初始退避(ms)">
                      <a-input-number v-model="installForm.ws_backoff_initial_ms" :min="100" :max="60000" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="WS 最大退避(ms)">
                      <a-input-number v-model="installForm.ws_backoff_max_ms" :min="1000" :max="600000" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="WS 最大重试">
                      <a-input-number v-model="installForm.ws_max_retries" :min="1" :max="20" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </template>
              <template v-if="installForm.install_type === 'agent-server'">
                <a-form-item label="Agent-Server 监听地址">
                  <a-input
                    v-model="installForm.agent_server_listen_addr"
                    placeholder="例如: 0.0.0.0:8080"
                  />
                </a-form-item>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="最大连接数">
                      <a-input-number v-model="installForm.max_connections" :min="100" :max="10000" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="心跳超时(秒)">
                      <a-input-number v-model="installForm.heartbeat_timeout" :min="30" :max="300" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </template>
              <a-row :gutter="12">
                <a-col :span="12">
                  <a-form-item label="SSH 超时(秒)">
                    <a-input-number v-model="installForm.ssh_timeout" :min="60" :max="900" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-form-item label="安装包版本">
                <a-select
                  v-model="installForm.package_id"
                  placeholder="请选择安装包版本（留空使用默认版本）"
                  allow-clear
                  allow-search
                  :loading="loadingPackages"
                  @change="handlePackageChange"
                >
                  <a-option
                    v-for="pkg in availablePackages"
                    :key="pkg.id"
                    :value="pkg.id"
                  :label="`${pkg.version} - ${pkg.os_type_display} - ${pkg.arch_display}`"
                  >
                    {{ pkg.version }} - {{ pkg.os_type_display }} - {{ pkg.arch_display }}
                    <a-tag v-if="pkg.is_default" color="blue" size="small" style="margin-left: 8px">默认</a-tag>
                  </a-option>
                </a-select>
                <template #extra>
                  <a-link @click="fetchAvailablePackages">刷新安装包列表</a-link>
                </template>
              </a-form-item>
              <a-form-item>
                <a-space>
                  <a-button type="primary" @click="handleGenerateScript" :loading="generatingScript">
                    生成安装脚本
                  </a-button>
                  <a-button type="primary" status="success" @click="handleBatchInstall" :loading="installing">
                    批量安装（SSH）
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </div>
        </a-tab-pane>

        <!-- 安装进度面板 -->
        <a-tab-pane key="progress" title="安装进度" v-if="installProgress.status !== 'idle'">
          <div class="install-step">
            <a-space direction="vertical" :size="16" style="width: 100%">
              <!-- 进度信息 -->
              <a-card>
                <a-space direction="vertical" :size="12" style="width: 100%">
                  <div style="display: flex; justify-content: space-between; align-items: center">
                    <span>安装进度</span>
                    <a-tag :color="installProgress.status === 'completed' ? 'green' : installProgress.status === 'completed_with_errors' ? 'orange' : 'blue'">
                      {{ installProgress.status === 'completed' ? '已完成' : installProgress.status === 'completed_with_errors' ? '部分失败' : '进行中' }}
                    </a-tag>
                  </div>
                  <a-progress
                    :percent="installProgress.total > 0 ? Math.round((installProgress.completed / installProgress.total) * 100) : 0"
                    :status="installProgress.status === 'completed' ? 'success' : installProgress.status === 'completed_with_errors' ? 'warning' : 'normal'"
                  />
                  <div style="display: flex; gap: 24px; font-size: 14px">
                    <span>总数: <strong>{{ installProgress.total }}</strong></span>
                    <span style="color: #00b42a">成功: <strong>{{ installProgress.success_count }}</strong></span>
                    <span style="color: #f53f3f">失败: <strong>{{ installProgress.failed_count }}</strong></span>
                    <span>已完成: <strong>{{ installProgress.completed }}</strong></span>
                  </div>
                  <div v-if="installProgress.message" style="color: #86909c; font-size: 12px">
                    {{ installProgress.message }}
                  </div>
                </a-space>
              </a-card>

              <!-- 实时日志 -->
              <a-card title="实时日志">
                <div style="max-height: 400px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 12px">
                  <div
                    v-for="(log, index) in installProgress.logs"
                    :key="index"
                    :style="{
                      padding: '4px 8px',
                      marginBottom: '4px',
                      backgroundColor: log.log_type === 'error' ? '#fff2f0' : log.log_type === 'info' ? '#f0f9ff' : '#f7f8fa',
                      color: log.log_type === 'error' ? '#f53f3f' : '#1d2129'
                    }"
                  >
                    <span style="color: #86909c">[{{ log.timestamp }}]</span>
                    <span v-if="log.host_name" style="color: #165dff; margin-left: 8px">[{{ log.host_name }}]</span>
                    <span style="margin-left: 8px">{{ log.content }}</span>
                  </div>
                  <div v-if="installProgress.logs.length === 0" style="color: #86909c; text-align: center; padding: 20px">
                    暂无日志
                  </div>
                </div>
              </a-card>
            </a-space>
          </div>
        </a-tab-pane>
        <a-tab-pane key="script" title="安装脚本" v-if="installScripts">
          <div class="install-step install-step-scripts">
            <div class="install-script-tip">
              <p class="install-script-tip-title">
                <strong>重要提示：</strong>这只是生成安装脚本，Agent 尚未实际安装！
              </p>
              <p class="install-script-tip-text">
                您需要：
              </p>
              <ul class="install-script-tip-list">
                <li>将以下脚本复制到对应主机上手动执行，或</li>
                <li>使用「批量安装（SSH）」功能自动安装</li>
              </ul>
              <p class="install-script-tip-warning">
                <strong>注意：Token 仅显示一次，请妥善保存；如需重新获取，请在列表或安装记录中使用“重新生成脚本”操作。</strong>
              </p>
            </div>
            <div v-for="(scriptGroup, osType) in installScripts" :key="String(osType)">
              <h3 style="margin: 16px 0 8px 0;">{{ String(osType) === 'linux' ? 'Linux' : 'Windows' }} 安装脚本</h3>
              <div v-for="item in scriptGroup" :key="item.host_id" style="margin-bottom: 24px">
                <a-card :title="`${item.host_name} (${item.host_ip})`" size="small">
                  <template #extra>
                    <a-button type="text" size="small" @click="copyScript(item.script)">
                      <template #icon>
                        <IconCopy />
                      </template>
                      复制脚本
                    </a-button>
                  </template>
                  <div class="install-script-token-row">
                    <span class="install-script-token-label"><strong>Agent Token:</strong></span>
                    <code class="install-script-token-value">{{ item.agent_token }}</code>
                    <a-button type="text" size="mini" @click="copyText(item.agent_token)" style="margin-left: 8px">
                      <template #icon>
                        <IconCopy />
                      </template>
                    </a-button>
                  </div>
                  <a-textarea
                    :model-value="item.script"
                    auto-size
                    readonly
                    style="font-family: 'Courier New', monospace; font-size: 12px; margin-top: 8px;"
                  />
                </a-card>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <!-- 卸载 Agent 抽屉 -->
    <a-drawer
      v-model:visible="uninstallDrawerVisible"
      title="卸载 Agent"
      width="900px"
      :footer="false"
      unmount-on-close
    >
      <a-tabs v-model:active-key="uninstallTab">
        <a-tab-pane key="select" title="选择 Agent">
          <div class="install-step">
            <a-form :model="uninstallForm" layout="vertical">
              <a-form-item label="选择 Agent">
                <a-select
                  v-model="uninstallForm.agent_ids"
                  placeholder="请选择要卸载的 Agent"
                  multiple
                  :max-tag-count="3"
                  allow-search
                  :filter-option="filterAgentOption"
                  style="width: 100%"
                >
                  <a-option
                    v-for="agent in agents"
                    :key="agent.id"
                    :value="agent.id"
                    :label="`${agent.host.name} (${agent.host.ip_address})`"
                  >
                    {{ agent.host.name }} ({{ agent.host.ip_address }}) - {{ agent.computed_status_display || agent.status_display }} - {{ agent.version || '未知版本' }}
                  </a-option>
                </a-select>
                <template #extra>
                  <a-link @click="fetchAgents">刷新 Agent 列表</a-link>
                </template>
              </a-form-item>
              <a-form-item>
                <a-space>
                  <a-button type="primary" status="danger" @click="handleBatchUninstall" :loading="uninstalling">
                    批量卸载（SSH）
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </div>
        </a-tab-pane>
        <a-tab-pane key="progress" title="卸载进度" v-if="uninstallProgress.status !== 'idle'">
          <div class="install-step">
            <a-space direction="vertical" :size="16" style="width: 100%">
              <!-- 进度信息 -->
              <a-card>
                <a-space direction="vertical" :size="12" style="width: 100%">
                  <div style="display: flex; justify-content: space-between; align-items: center">
                    <span>卸载进度</span>
                    <a-tag :color="uninstallProgress.status === 'completed' ? 'green' : uninstallProgress.status === 'completed_with_errors' ? 'orange' : 'blue'">
                      {{ uninstallProgress.status === 'completed' ? '已完成' : uninstallProgress.status === 'completed_with_errors' ? '部分失败' : '进行中' }}
                    </a-tag>
                  </div>
                  <a-progress
                    :percent="uninstallProgress.total > 0 ? Math.round((uninstallProgress.completed / uninstallProgress.total) * 100) : 0"
                    :status="uninstallProgress.status === 'completed' ? 'success' : uninstallProgress.status === 'completed_with_errors' ? 'warning' : 'normal'"
                  />
                  <div style="display: flex; gap: 24px; font-size: 14px">
                    <span>总数: <strong>{{ uninstallProgress.total }}</strong></span>
                    <span style="color: #00b42a">成功: <strong>{{ uninstallProgress.success_count }}</strong></span>
                    <span style="color: #f53f3f">失败: <strong>{{ uninstallProgress.failed_count }}</strong></span>
                    <span>已完成: <strong>{{ uninstallProgress.completed }}</strong></span>
                  </div>
                  <div v-if="uninstallProgress.message" style="color: #86909c; font-size: 12px">
                    {{ uninstallProgress.message }}
                  </div>
                </a-space>
              </a-card>

              <!-- 实时日志 -->
              <a-card title="实时日志">
                <div style="max-height: 400px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 12px">
                  <div
                    v-for="(log, index) in uninstallProgress.logs"
                    :key="index"
                    :style="{
                      padding: '4px 8px',
                      marginBottom: '4px',
                      backgroundColor: log.log_type === 'error' ? '#fff2f0' : log.log_type === 'info' ? '#f0f9ff' : '#f7f8fa',
                      color: log.log_type === 'error' ? '#f53f3f' : '#1d2129'
                    }"
                  >
                    <span style="color: #86909c">[{{ log.timestamp }}]</span>
                    <span v-if="log.host_name" style="color: #165dff; margin-left: 8px">[{{ log.host_name }}]</span>
                    <span style="margin-left: 8px">{{ log.content }}</span>
                  </div>
                  <div v-if="uninstallProgress.logs.length === 0" style="color: #86909c; text-align: center; padding: 20px">
                    暂无日志
                  </div>
                </div>
              </a-card>
            </a-space>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <!-- 批量操作进度抽屉 -->
    <a-drawer
      v-model:visible="batchOperationDrawerVisible"
      :title="`${batchOperationProgress.operation}进度`"
      width="900px"
      :footer="false"
      unmount-on-close
    >
      <div class="install-step">
        <a-space direction="vertical" :size="16" style="width: 100%">
          <!-- 进度信息 -->
          <a-card>
            <a-space direction="vertical" :size="12" style="width: 100%">
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>{{ batchOperationProgress.operation }}进度</span>
                <a-tag :color="batchOperationProgress.status === 'completed' ? 'green' : batchOperationProgress.status === 'completed_with_errors' ? 'orange' : 'blue'">
                  {{ batchOperationProgress.status === 'completed' ? '已完成' : batchOperationProgress.status === 'completed_with_errors' ? '部分失败' : '进行中' }}
                </a-tag>
              </div>
              <a-progress
                :percent="batchOperationProgress.total > 0 ? Math.round((batchOperationProgress.completed / batchOperationProgress.total) * 100) : 0"
                :status="batchOperationProgress.status === 'completed' ? 'success' : batchOperationProgress.status === 'completed_with_errors' ? 'warning' : 'normal'"
              />
              <div style="display: flex; gap: 24px; font-size: 14px">
                <span>总数: <strong>{{ batchOperationProgress.total }}</strong></span>
                <span style="color: #00b42a">成功: <strong>{{ batchOperationProgress.success_count }}</strong></span>
                <span style="color: #f53f3f">失败: <strong>{{ batchOperationProgress.failed_count }}</strong></span>
                <span>已完成: <strong>{{ batchOperationProgress.completed }}</strong></span>
              </div>
              <div v-if="batchOperationProgress.message" style="color: #86909c; font-size: 12px">
                {{ batchOperationProgress.message }}
              </div>
            </a-space>
          </a-card>

          <!-- 实时日志 -->
          <a-card title="实时日志">
            <div style="max-height: 400px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 12px">
              <div
                v-for="(log, index) in batchOperationProgress.logs"
                :key="index"
                :style="{
                  padding: '4px 8px',
                  marginBottom: '4px',
                  backgroundColor: log.log_type === 'error' ? '#fff2f0' : log.log_type === 'info' ? '#f0f9ff' : '#f7f8fa',
                  color: log.log_type === 'error' ? '#f53f3f' : '#1d2129'
                }"
              >
                <span style="color: #86909c">[{{ log.timestamp }}]</span>
                <span v-if="log.host_name" style="color: #165dff; margin-left: 8px">[{{ log.host_name }}]</span>
                <span style="margin-left: 8px">{{ log.content }}</span>
              </div>
              <div v-if="batchOperationProgress.logs.length === 0" style="color: #86909c; text-align: center; padding: 20px">
                暂无日志
              </div>
            </div>
          </a-card>
        </a-space>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconCopy, IconHistory, IconDelete, IconCloseCircle, IconArrowUp, IconExclamationCircle, IconRefresh } from '@arco-design/web-vue/es/icon'
import { agentsApi, packageApi, type Agent, type AgentPackage } from '@/api/agents'
import { hostApi } from '@/api/ops'
import dayjs from 'dayjs'
import { buildSseUrl } from '@/utils/env'
import { SSE } from 'sse.js'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 响应式数据
const loading = ref(false)
const agents = ref<Agent[]>([])
const tokenModalVisible = ref(false)
const currentAgent = ref<Agent | null>(null)
const tokenFormRef = ref()
// 安装相关
const installModalVisible = ref(false)
const installTab = ref('select')
const installForm = reactive({
  host_ids: [] as number[],
  install_type: 'agent' as 'agent' | 'agent-server',
  // Agent 配置
  install_mode: 'agent-server' as 'agent-server',
  agent_server_url: '',
  ws_backoff_initial_ms: 1000,
  ws_backoff_max_ms: 30000,
  ws_max_retries: 6,
  // Agent-Server 配置
  agent_server_listen_addr: '0.0.0.0:8080',
  max_connections: 1000,
  heartbeat_timeout: 60,
  // 通用配置
  ssh_timeout: 300,
  package_id: undefined as number | undefined,
  package_version: undefined as string | undefined,
})
const availableHosts = ref<any[]>([])
const availablePackages = ref<AgentPackage[]>([])
const loadingPackages = ref(false)
const installScripts = ref<any>(null)
const shouldRefreshAfterInstall = ref(false)
const generatingScript = ref(false)
const installing = ref(false)
const installProgress = ref<{
  total: number
  completed: number
  success_count: number
  failed_count: number
  status: string
  message: string
  logs: Array<{
    host_name: string
    host_ip: string
    content: string
    log_type: string
    timestamp: string
  }>
}>({
  total: 0,
  completed: 0,
  success_count: 0,
  failed_count: 0,
  status: 'idle',
  message: '',
  logs: []
})
const sseEventSource = ref<any | null>(null)

// 卸载相关
const uninstallDrawerVisible = ref(false)
const uninstallTab = ref('select')
const uninstallForm = reactive({
  agent_ids: [] as number[],
})
const uninstalling = ref(false)
const uninstallProgress = ref<{
  total: number
  completed: number
  success_count: number
  failed_count: number
  status: string
  message: string
  logs: Array<{
    host_name: string
    host_ip: string
    content: string
    log_type: string
    timestamp: string
  }>
}>({
  total: 0,
  completed: 0,
  success_count: 0,
  failed_count: 0,
  status: 'idle',
  message: '',
  logs: []
})
const uninstallSseEventSource = ref<any | null>(null)

// 批量操作相关
const batchOperationProgress = ref<{
  total: number
  completed: number
  success_count: number
  failed_count: number
  status: string
  message: string
  operation: string
  logs: Array<{
    host_name: string
    host_ip: string
    content: string
    log_type: string
    timestamp: string
  }>
}>({
  total: 0,
  completed: 0,
  success_count: 0,
  failed_count: 0,
  status: 'idle',
  message: '',
  operation: '',
  logs: []
})
const batchOperationSseEventSource = ref<any | null>(null)
const batchOperationDrawerVisible = ref(false)

// 搜索表单
const searchForm = reactive({
  search: '',
  status: '',
  tags: [] as string[]
})

// 状态过滤器
const statusFilters = reactive({
  online: false,
  offline: false,
  pending: false,
  disabled: false,
  outdated: false,
  failed: false,
  inactive: false
})

// Token 表单
const tokenForm = reactive({
  expired_at: null as string | null,
  note: '',
  confirmed: false
})

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true
})

// 资源概览数据
const resourcesOverview = ref<Record<number, {
  cpu_usage: number | null
  memory_usage: number | null
  load_avg_1m: number | null
}>>({})

// 统计信息
const statistics = reactive({
  pending: 0,
  online: 0,
  offline: 0,
  disabled: 0
})

// 表格选择
const selectedAgentIds = ref<number[]>([])
const rowSelection = reactive({
  type: 'checkbox',
  showCheckedAll: true,
  onlyCurrent: false
})

// 计算选中的 pending 状态 Agent 数量
const selectedPendingCount = computed(() => {
  return agents.value.filter(a => selectedAgentIds.value.includes(a.id) && (a.computed_status || a.status) === 'pending').length
})

// 是否有选中的 pending 状态 Agent
const hasPendingAgents = computed(() => {
  return selectedPendingCount.value > 0
})

// 计算选中的可禁用 Agent 数量（非 disabled 且非 pending）
const selectedDisableableCount = computed(() => {
  return agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    ((a.computed_status || a.status) !== 'disabled') && 
    ((a.computed_status || a.status) !== 'pending')
  ).length
})

// 是否有选中的可禁用 Agent
const hasDisableableAgents = computed(() => {
  return selectedDisableableCount.value > 0
})

// 计算选中的可启用 Agent 数量（disabled 状态）
const selectedEnableableCount = computed(() => {
  return agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    (a.computed_status || a.status) === 'disabled'
  ).length
})

// 是否有选中的可启用 Agent
const hasEnableableAgents = computed(() => {
  return selectedEnableableCount.value > 0
})

// 状态过滤器相关计算属性
const onlineCount = computed(() => {
  return agents.value.filter(a => (a.computed_status || a.status) === 'online').length
})

const offlineCount = computed(() => {
  return agents.value.filter(a => (a.computed_status || a.status) === 'offline').length
})

const pendingCount = computed(() => {
  return agents.value.filter(a => a.status === 'pending').length
})

const disabledCount = computed(() => {
  return agents.value.filter(a => a.status === 'disabled').length
})

const outdatedCount = computed(() => {
  return agents.value.filter(a => a.is_version_outdated).length
})

const failedCount = computed(() => {
  return agents.value.filter(a => a.last_error_code).length
})

const inactiveCount = computed(() => {
  const sevenDaysAgo = new Date()
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
  return agents.value.filter(a => {
    if (!a.last_heartbeat_at) return true
    const lastHeartbeat = new Date(a.last_heartbeat_at)
    return lastHeartbeat < sevenDaysAgo
  }).length
})

const hasActiveFilters = computed(() => {
  return statusFilters.online || statusFilters.offline || statusFilters.pending ||
         statusFilters.disabled || statusFilters.outdated || statusFilters.failed ||
         statusFilters.inactive
})

// 筛选统计信息
const filteredOnlineCount = computed(() => {
  return filteredAgents.value.filter(a => (a.computed_status || a.status) === 'online').length
})

const filteredOfflineCount = computed(() => {
  return filteredAgents.value.filter(a => (a.computed_status || a.status) === 'offline').length
})

const filteredPendingCount = computed(() => {
  return filteredAgents.value.filter(a => a.status === 'pending').length
})

const filteredDisabledCount = computed(() => {
  return filteredAgents.value.filter(a => a.status === 'disabled').length
})

const filteredOutdatedCount = computed(() => {
  return filteredAgents.value.filter(a => a.is_version_outdated).length
})

const filteredFailedCount = computed(() => {
  return filteredAgents.value.filter(a => a.last_error_code).length
})

const filteredInactiveCount = computed(() => {
  const sevenDaysAgo = new Date()
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
  return filteredAgents.value.filter(a => {
    if (!a.last_heartbeat_at) return true
    const lastHeartbeat = new Date(a.last_heartbeat_at)
    return lastHeartbeat < sevenDaysAgo
  }).length
})

// 过滤后的Agent列表
const filteredAgents = computed(() => {
  let filtered = agents.value

  if (statusFilters.online) {
    filtered = filtered.filter(a => (a.computed_status || a.status) === 'online')
  }
  if (statusFilters.offline) {
    filtered = filtered.filter(a => (a.computed_status || a.status) === 'offline')
  }
  if (statusFilters.pending) {
    filtered = filtered.filter(a => a.status === 'pending')
  }
  if (statusFilters.disabled) {
    filtered = filtered.filter(a => a.status === 'disabled')
  }
  if (statusFilters.outdated) {
    filtered = filtered.filter(a => a.is_version_outdated)
  }
  if (statusFilters.failed) {
    filtered = filtered.filter(a => a.last_error_code)
  }
  if (statusFilters.inactive) {
    const sevenDaysAgo = new Date()
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    filtered = filtered.filter(a => {
      if (!a.last_heartbeat_at) return true
      const lastHeartbeat = new Date(a.last_heartbeat_at)
      return lastHeartbeat < sevenDaysAgo
    })
  }

  return filtered
})

// Agent 类型显示文本
const agentTypeMap: Record<string, string> = {
  agent: 'Agent',
  'agent-server': 'Agent-Server'
}

// 表格列配置
const columns = [
  {
    title: '关联主机',
    dataIndex: 'host',
    slotName: 'host',
    width: 150
  },
  {
    title: '类型',
    dataIndex: 'agent_type',
    slotName: 'agent_type',
    width: 120
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 100
  },
  {
    title: '版本',
    dataIndex: 'version',
    slotName: 'version',
    width: 120
  },
  {
    title: '最后心跳',
    dataIndex: 'last_heartbeat_at',
    slotName: 'last_heartbeat_at',
    width: 180
  },
  {
    title: '资源使用',
    dataIndex: 'resources',
    slotName: 'resources',
    width: 200
  },
  {
    title: '错误码',
    dataIndex: 'last_error_code',
    slotName: 'last_error_code',
    width: 120
  },
  {
    title: '标签',
    dataIndex: 'tags',
    slotName: 'tags',
    width: 180
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 250,
    fixed: 'right'
  }
]

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    online: 'green',
    offline: 'red',
    disabled: 'gray'
  }
  return colorMap[status] || 'blue'
}

// 状态说明（hover 提示）
const getStatusHint = (status: string) => {
  const hintMap: Record<string, string> = {
    pending: '已生成安装脚本但尚未安装/上线，可点击「重新生成脚本」获取脚本并执行安装',
    online: 'Agent 正常运行中，正在接收和执行任务',
    offline: '最近未收到心跳，请检查：1) Agent 进程是否运行 2) Agent 与 Agent-Server/控制面的网络连接 3) 防火墙规则 4) 可尝试重启 Agent',
    disabled: 'Agent 已被禁用，不会接收新任务。如需恢复，请点击「启用」按钮'
  }
  return hintMap[status] || ''
}

// 版本落后提示文案
const getVersionTooltip = (agent: Agent & { expected_min_version?: string }) => {
  if (agent.expected_min_version) {
    return `当前版本 ${agent.version} 落后于期望版本 ${agent.expected_min_version}`
  }
  return `当前版本 ${agent.version} 落后于平台期望版本`
}

// 格式化时间
const formatTime = (time: string) => {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

// 获取资源使用状态颜色
const getResourceStatus = (usage: number | null | undefined): 'success' | 'warning' | 'danger' | 'normal' => {
  if (usage === null || usage === undefined) return 'normal'
  if (usage >= 90) return 'danger'
  if (usage >= 70) return 'warning'
  return 'success'
}

// 获取 Agent 列表
const fetchAgents = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    if (searchForm.search) params.search = searchForm.search
    if (searchForm.status) params.status = searchForm.status
    if (Array.isArray(searchForm.tags) && searchForm.tags.length > 0) {
      params.tags = searchForm.tags.join(',')
    }

    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null || params[key] === undefined) {
        delete params[key]
      }
    })

    const response = await agentsApi.getAgents(params)
    // 响应拦截器已返回 content 部分，直接使用
    if (response && response.results) {
      agents.value = response.results
      pagination.total = response.total || 0
      // 更新统计信息
      updateStatistics()
      // 获取在线 Agent 的资源概览
      fetchResourcesOverview()
    } else {
      agents.value = []
      pagination.total = 0
      resetStatistics()
    }
  } catch (error: any) {
    console.error('获取 Agent 列表失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '获取 Agent 列表失败'
    Message.error(errorMsg)
    agents.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 获取资源概览（用于列表展示）
const fetchResourcesOverview = async () => {
  try {
    // 获取在线 Agent 的 ID 列表
    const onlineAgentIds = agents.value
      .filter(a => (a.computed_status || a.status) === 'online')
      .map(a => a.id)

    if (onlineAgentIds.length === 0) {
      resourcesOverview.value = {}
      return
    }

    const response = await agentsApi.getResourcesOverview(onlineAgentIds)
    if (response && response.resources) {
      resourcesOverview.value = response.resources
    }
  } catch (error) {
    console.error('获取资源概览失败:', error)
    // 不显示错误消息，静默失败
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  fetchAgents()
}

// 重置
const handleReset = () => {
  searchForm.search = ''
  searchForm.status = ''
  searchForm.tags = []
  handleSearch()
}

// 状态过滤器处理
const toggleStatusFilter = (filterType: keyof typeof statusFilters) => {
  statusFilters[filterType] = !statusFilters[filterType]
  // 过滤器改变时重置分页
  pagination.current = 1
}

const clearAllFilters = () => {
  statusFilters.online = false
  statusFilters.offline = false
  statusFilters.pending = false
  statusFilters.disabled = false
  statusFilters.outdated = false
  statusFilters.failed = false
  statusFilters.inactive = false
  pagination.current = 1
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  fetchAgents()
}

const handlePageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchAgents()
}

// 查看详情
const handleViewDetail = (id: number) => {
  router.push(`/ops/agents/${id}`)
}

// 发 Token
const handleIssueToken = (agent: Agent) => {
  currentAgent.value = agent
  tokenForm.expired_at = null
  tokenForm.note = ''
  tokenForm.confirmed = false
  tokenModalVisible.value = true
}

// 确认发 Token
const handleIssueTokenConfirm = async () => {
  if (!tokenForm.confirmed) {
    Message.warning('请先确认此操作')
    return
  }
  if (!currentAgent.value) return

  try {
    const params: any = {
      confirmed: true
    }
    if (tokenForm.expired_at) {
      params.expired_at = dayjs(tokenForm.expired_at).format('YYYY-MM-DD HH:mm:ss')
    }
    if (tokenForm.note) {
      params.note = tokenForm.note
    }

    const result = await agentsApi.issueToken(currentAgent.value.id, params)
    Message.success('Token 签发成功')
    // 显示 Token（仅此一次）
    Modal.info({
      title: 'Token 签发成功',
      content: `Token: ${result.token}\n\n请妥善保管，此 Token 仅显示一次！`,
      okText: '我已保存'
    })
    tokenModalVisible.value = false
    fetchAgents()
  } catch (error: any) {
    console.error('Token 签发失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || 'Token 签发失败'
    Message.error(errorMsg)
  }
}

// 取消发 Token
const handleTokenModalCancel = () => {
  tokenModalVisible.value = false
  currentAgent.value = null
  tokenForm.expired_at = null
  tokenForm.note = ''
  tokenForm.confirmed = false
}

// 禁用 Agent
const handleDisable = (agent: Agent) => {
  Modal.confirm({
    title: '确认禁用',
    content: `确定要禁用 Agent (${agent.host.name}) 吗？`,
    okText: '确认禁用',
    cancelText: '取消',
    onOk: async () => {
      try {
        await agentsApi.disableAgent(agent.id, { confirmed: true })
        Message.success('禁用成功')
        fetchAgents()
      } catch (error: any) {
        console.error('禁用失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '禁用失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 启用 Agent
const handleEnable = async (agent: Agent) => {
  try {
    await agentsApi.enableAgent(agent.id)
    Message.success('启用成功')
    fetchAgents()
  } catch (error: any) {
    console.error('启用失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '启用失败'
    Message.error(errorMsg)
  }
}

// 重启 Agent
const handleRestartAgent = (agent: Agent) => {
  Modal.confirm({
    title: '确认重启',
    content: `确定要重启 Agent (${agent.host.name}) 吗？重启期间 Agent 将短暂离线。`,
    okText: '确认重启',
    cancelText: '取消',
    onOk: async () => {
      try {
        await agentsApi.controlAgent(agent.id, {
          action: 'restart',
          reason: '用户手动重启'
        })
        Message.success('重启指令已下发，Agent 将在几秒内重启')
        // 延迟刷新，等待 Agent 重启完成
        setTimeout(() => fetchAgents(), 3000)
      } catch (error: any) {
        console.error('重启失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '重启失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 升级 Agent
const handleUpgradeAgent = (agent: Agent) => {
  Modal.confirm({
    title: '确认升级',
    content: `确定要升级 Agent (${agent.host.name}) 吗？\n\n当前版本: ${agent.version}\n期望版本: ${agent.expected_min_version || '最新版本'}\n\n升级期间 Agent 将短暂离线。`,
    okText: '确认升级',
    cancelText: '取消',
    onOk: async () => {
      try {
        await agentsApi.upgradeAgent(agent.id, {
          target_version: agent.expected_min_version,
          confirmed: true
        })
        Message.success('升级指令已下发，Agent 将在几秒内完成升级')
        setTimeout(() => fetchAgents(), 5000)
      } catch (error: any) {
        console.error('升级失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '升级失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 查看安装记录
const handleViewInstallRecords = () => {
  router.push({ name: 'OpsAgentInstallRecords' })
}

// 查看卸载记录
const handleViewUninstallRecords = () => {
  router.push({ name: 'OpsAgentUninstallRecords' })
}

// 卸载 Agent
const handleUninstallAgent = () => {
  uninstallDrawerVisible.value = true
  uninstallTab.value = 'select'
  uninstallForm.agent_ids = []
  // 重置进度
  uninstallProgress.value = {
    total: 0,
    completed: 0,
    success_count: 0,
    failed_count: 0,
    status: 'idle',
    message: '',
    logs: []
  }
  // 关闭之前的 SSE 连接
  if (uninstallSseEventSource.value) {
    uninstallSseEventSource.value.close()
    uninstallSseEventSource.value = null
  }
}

// Agent 选项过滤
const filterAgentOption = (inputValue: string, option: any) => {
  const label = option.label || ''
  return label.toLowerCase().includes(inputValue.toLowerCase())
}

const getAccessToken = () => {
  return (
    authStore.token ||
    sessionStorage.getItem('access_token') ||
    localStorage.getItem('access_token') ||
    ''
  )
}

// 连接 SSE 查看卸载进度
const connectUninstallProgressSSE = (uninstallTaskId: string) => {
  // 关闭之前的连接
  if (uninstallSseEventSource.value) {
    uninstallSseEventSource.value.close()
  }

  // 重置进度
  uninstallProgress.value = {
    total: 0,
    completed: 0,
    success_count: 0,
    failed_count: 0,
    status: 'running',
    message: '正在连接...',
    logs: []
  }

  // 获取 token
  const token = getAccessToken()
  // 使用相对路径，因为 SSE 请求会通过代理
  // backend route is /api/realtime/sse/agent-uninstall/<id>/
  const sseUrl = buildSseUrl(`agent-uninstall/${uninstallTaskId}/`)

  // 使用 sse.js 建立连接并通过 Authorization header 认证（比把 token 放在 URL 更安全）
  const eventSource = new SSE(sseUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    start: true,
    debug: process.env.NODE_ENV === 'development',
    autoReconnect: true,
    reconnectDelay: 3000,
    maxRetries: 3,
    withCredentials: true
  })
  uninstallSseEventSource.value = eventSource

  // 定义卸载终态集合
  const uninstallTerminalStatuses = new Set(['completed', 'completed_with_errors', 'failed', 'success', 'error', 'stopped'])

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'connection_established') {
        uninstallProgress.value.message = data.message || '已连接到卸载进度流'
        uninstallProgress.value.status = 'running'
      } else if (data.type === 'status') {
        uninstallProgress.value.total = data.total || data.total_hosts || 0
        uninstallProgress.value.completed = data.completed || 0
        uninstallProgress.value.success_count = data.success_count || data.success_hosts || 0
        uninstallProgress.value.failed_count = data.failed_count || data.failed_hosts || 0
        uninstallProgress.value.status = data.status || 'running'
        uninstallProgress.value.message = data.message || ''

        // 检测终态：收到终态后主动关闭连接，避免自动重连
        const statusValue = (data.status || '').toLowerCase()
        if (uninstallTerminalStatuses.has(statusValue)) {
          console.log(`卸载任务已达终态: ${statusValue}，关闭 SSE 连接`)
          // 禁用自动重连并关闭连接
          try {
            eventSource.autoReconnect = false
            eventSource.close()
          } catch (e) {
            console.warn('关闭 SSE 连接失败:', e)
          }
          uninstallSseEventSource.value = null
          // 刷新 Agent 列表
          fetchAgents()
        }
      } else if (data.type === 'log') {
        uninstallProgress.value.logs.push({
          host_name: data.host_name || '',
          host_ip: data.host_ip || '',
          content: data.content || '',
          log_type: data.log_type || 'info',
          timestamp: data.timestamp || new Date().toISOString()
        })
        // 限制日志数量，保留最近 500 条
        if (uninstallProgress.value.logs.length > 500) {
          uninstallProgress.value.logs = uninstallProgress.value.logs.slice(-500)
        }
      } else if (data.type === 'error') {
        uninstallProgress.value.status = 'error'
        uninstallProgress.value.message = data.message || '发生错误'
        uninstallProgress.value.logs.push({
          host_name: '',
          host_ip: '',
          content: `错误: ${data.message}`,
          log_type: 'error',
          timestamp: new Date().toISOString()
        })
        // 关闭连接
        try {
          eventSource.autoReconnect = false
          eventSource.close()
        } catch (e) {}
        uninstallSseEventSource.value = null
      }
    } catch (error) {
      console.error('解析 SSE 消息失败:', error)
    }
  }

  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)

    // 检查是否已达终态，如果是则不需要标记为 error
    const currentStatus = (uninstallProgress.value.status || '').toLowerCase()
    if (!uninstallTerminalStatuses.has(currentStatus)) {
      // 只有在非终态时才标记为 error
      if (uninstallProgress.value.status === 'running') {
        uninstallProgress.value.status = 'error'
        uninstallProgress.value.message = '连接已断开'
      }
    }

    // 禁用自动重连并关闭连接
    try {
      eventSource.autoReconnect = false
      eventSource.close()
    } catch (e) {}
    uninstallSseEventSource.value = null
  }

  // 切换到进度标签页
  uninstallTab.value = 'progress'
}

// 批量卸载
const handleBatchUninstall = async () => {
  if (!uninstallForm.agent_ids || uninstallForm.agent_ids.length === 0) {
    Message.warning('请至少选择一个 Agent')
    return
  }

  Modal.confirm({
    title: '确认批量卸载',
    content: `确定要卸载 ${uninstallForm.agent_ids.length} 个 Agent 吗？此操作不可恢复！`,
    okText: '确认卸载',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      uninstalling.value = true
      try {
        const response = await agentsApi.batchUninstall({
          agent_ids: uninstallForm.agent_ids,
          confirmed: true,
        })

        // 如果有 uninstall_task_id，连接 SSE 查看实时进度
        if (response.uninstall_task_id) {
          connectUninstallProgressSSE(response.uninstall_task_id)
          Message.info('卸载已启动，正在查看实时进度...')
        } else {
          // 如果没有 SSE，显示最终结果
          Message.success(
            `批量卸载完成：成功 ${response.success_count} 个，失败 ${response.failed_count} 个`
          )

          // 显示详细结果
          if (response.failed_count > 0) {
            const failedAgents = response.results
              .filter((r: any) => !r.success)
              .map((r: any) => `${r.host_name}: ${r.message}`)
              .join('\n')
            Modal.warning({
              title: '部分 Agent 卸载失败',
              content: failedAgents,
              width: 600,
            })
          }

          // 刷新列表
          uninstallDrawerVisible.value = false
          fetchAgents()
        }
      } catch (error: any) {
        console.error('批量卸载失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '批量卸载失败'
        Message.error(errorMsg)
      } finally {
        uninstalling.value = false
      }
    },
  })
}

// 安装 Agent
const handleInstallAgent = () => {
  installModalVisible.value = true
  installTab.value = 'select'
  installForm.host_ids = []
  installForm.install_type = 'agent'
  installForm.install_mode = 'agent-server'
  installForm.agent_server_url = ''
  installForm.ws_backoff_initial_ms = 1000
  installForm.ws_backoff_max_ms = 30000
  installForm.ws_max_retries = 6
  installForm.agent_server_listen_addr = '0.0.0.0:8080'
  installForm.max_connections = 1000
  installForm.heartbeat_timeout = 60
  installForm.ssh_timeout = 300
  installForm.package_id = undefined
  installForm.package_version = undefined
  installScripts.value = null
  shouldRefreshAfterInstall.value = false
  // 重置进度
  installProgress.value = {
    total: 0,
    completed: 0,
    success_count: 0,
    failed_count: 0,
    status: 'idle',
    message: '',
    logs: []
  }
  // 关闭之前的sse连接
  if (sseEventSource.value) {
    sseEventSource.value.close()
    sseEventSource.value = null
  }
  fetchAvailableHosts()
  fetchAvailablePackages()
}

// 获取可用安装包列表
const fetchAvailablePackages = async () => {
  loadingPackages.value = true
  try {
    const packages = await packageApi.getActivePackages({ package_type: installForm.install_type })
    availablePackages.value = packages
  } catch (error: any) {
    Message.error(error.message || '获取安装包列表失败')
    availablePackages.value = []
  } finally {
    loadingPackages.value = false
  }
}

// 安装包选择变化
const handlePackageChange = (packageId: number | undefined) => {
  if (packageId) {
    const selectedPackage = availablePackages.value.find(pkg => pkg.id === packageId)
    if (selectedPackage) {
      installForm.package_version = selectedPackage.version
    }
  } else {
    installForm.package_version = undefined
  }
}

const handleInstallTypeChange = () => {
  // 切换安装类型时重置包选择，并刷新可用主机/包
  installForm.package_id = undefined
  installForm.package_version = undefined
  fetchAvailableHosts()
  fetchAvailablePackages()
}

// 获取可用主机列表（显示所有主机并标识Agent状态）
const fetchAvailableHosts = async () => {
  try {
    // 获取主机和Agent状态信息
    const response = await agentsApi.getHostAgentStatus()
    availableHosts.value = response.hosts || []
  } catch (error) {
    console.error('获取主机列表失败:', error)
    Message.error('获取主机列表失败')
  }
}

// 获取主机标签（包含Agent状态）
const getHostLabel = (host: any) => {
  const baseLabel = `${host.name} (${host.ip_address})`
  const targetType = installForm.install_type === 'agent-server' ? 'Agent-Server' : 'Agent'

  // 已安装的主机：显示实际 agent 类型、版本和状态
  if (host.agent_status) {
    const statusText = host.computed_status_display || (
      host.computed_status === 'online' ? '在线' :
      host.computed_status === 'offline' ? '离线' :
      host.computed_status === 'pending' ? '待激活' :
      host.computed_status || host.agent_status
    )

    const typeText = host.agent_type_display
      || (host.agent_type === 'agent-server' ? 'Agent-Server' : 'Agent')

    const versionText = host.agent_version ? ` v${host.agent_version}` : ''

    return `${baseLabel} - ${typeText}${versionText} (${statusText})`
  }

  // 未安装：根据当前选择的安装类型显示更明确的提示（Agent / Agent-Server）
  return `${baseLabel} - 未安装${targetType}`
}

// 主机选项过滤
const filterHostOption = (inputValue: string, option: any) => {
  const label = option.label || ''
  return label.toLowerCase().includes(inputValue.toLowerCase())
}

const getAgentTypeColor = (type?: string) => {
  return 'purple'
}

// 生成安装脚本
const handleGenerateScript = async () => {
  if (!installForm.host_ids || installForm.host_ids.length === 0) {
    Message.warning('请至少选择一个主机')
    return
  }
  if (installForm.install_type === 'agent' && !installForm.agent_server_url) {
    Message.warning('安装 Agent 需要填写 Agent-Server 地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !installForm.agent_server_listen_addr) {
    Message.warning('安装 Agent-Server 需要填写监听地址')
    return
  }

  generatingScript.value = true
  try {
    const params: any = {
      host_ids: installForm.host_ids,
      install_type: installForm.install_type,
      package_id: installForm.package_id,
      package_version: installForm.package_version,
    }

    if (installForm.install_type === 'agent') {
      params.install_mode = installForm.install_mode
      params.agent_server_url = installForm.agent_server_url
      // 备地址已移除，不传递
      params.ws_backoff_initial_ms = installForm.ws_backoff_initial_ms
      params.ws_backoff_max_ms = installForm.ws_backoff_max_ms
      params.ws_max_retries = installForm.ws_max_retries
    } else if (installForm.install_type === 'agent-server') {
      params.agent_server_listen_addr = installForm.agent_server_listen_addr
      params.max_connections = installForm.max_connections
      params.heartbeat_timeout = installForm.heartbeat_timeout
    }

    const response = await agentsApi.generateInstallScript(params)

    installScripts.value = response.scripts
    shouldRefreshAfterInstall.value = true
    
    // 显示提示信息
    if (response.notice) {
      Message.warning(response.notice)
    }
    if (response.errors && response.errors.length > 0) {
      Message.warning(`部分主机生成脚本失败: ${response.errors.join('; ')}`)
    }
    
    installTab.value = 'script'
    Message.success('安装脚本生成成功')
  } catch (error: any) {
    console.error('生成安装脚本失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '生成安装脚本失败'
    Message.error(errorMsg)
  } finally {
    generatingScript.value = false
  }
}

// 连接 SSE 查看安装进度
const connectInstallProgressSSE = (installTaskId: string) => {
  // 关闭之前的连接
  if (sseEventSource.value) {
    sseEventSource.value.close()
  }

  // 重置进度
  installProgress.value = {
    total: 0,
    completed: 0,
    success_count: 0,
    failed_count: 0,
    status: 'running',
    message: '正在连接...',
    logs: []
  }

  // 获取 token
  const token = getAccessToken()
  // 使用相对路径，因为sse请求会通过代理
  const sseUrl = buildSseUrl(`agent-install/${installTaskId}/`)

  // 使用 sse.js 创建连接并通过 Authorization header 认证（避免把 token 放在 URL）
  const eventSource = new SSE(sseUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    start: true,
    debug: process.env.NODE_ENV === 'development',
    autoReconnect: true,
    reconnectDelay: 3000,
    maxRetries: 3,
    withCredentials: true
  })
  sseEventSource.value = eventSource
  // 确保显示进度抽屉并切到进度标签页，避免在连接过程中因异常导致界面仍停留在选择页
  installModalVisible.value = true
  installTab.value = 'progress'

  // 定义安装终态集合
  const terminalStatuses = new Set(['completed', 'completed_with_errors', 'failed', 'success', 'error', 'stopped'])

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'connection_established') {
        installProgress.value.message = data.message || '已连接到安装进度流'
        installProgress.value.status = 'running'
      } else if (data.type === 'status') {
        installProgress.value.total = data.total || data.total_hosts || 0
        installProgress.value.completed = data.completed || 0
        installProgress.value.success_count = data.success_count || data.success_hosts || 0
        installProgress.value.failed_count = data.failed_count || data.failed_hosts || 0
        installProgress.value.status = data.status || 'running'
        installProgress.value.message = data.message || ''

        // 检测终态：收到终态后主动关闭连接，避免自动重连
        const statusValue = (data.status || '').toLowerCase()
        if (terminalStatuses.has(statusValue)) {
          console.log(`安装任务已达终态: ${statusValue}，关闭 SSE 连接`)
          // 禁用自动重连并关闭连接
          try {
            eventSource.autoReconnect = false
            eventSource.close()
          } catch (e) {
            console.warn('关闭 SSE 连接失败:', e)
          }
          sseEventSource.value = null
          // 刷新 Agent 列表
          fetchAgents()
        }
      } else if (data.type === 'log') {
        installProgress.value.logs.push({
          host_name: data.host_name || '',
          host_ip: data.host_ip || '',
          content: data.content || '',
          log_type: data.log_type || 'info',
          timestamp: data.timestamp || new Date().toISOString()
        })
        // 限制日志数量，保留最近 500 条
        if (installProgress.value.logs.length > 500) {
          installProgress.value.logs = installProgress.value.logs.slice(-500)
        }
      } else if (data.type === 'error') {
        installProgress.value.status = 'error'
        installProgress.value.message = data.message || '发生错误'
        installProgress.value.logs.push({
          host_name: '',
          host_ip: '',
          content: `错误: ${data.message}`,
          log_type: 'error',
          timestamp: new Date().toISOString()
        })
        // 切换到进度页并关闭连接，确保用户能看到错误并避免悬挂的连接
        installTab.value = 'progress'
        try {
          eventSource.autoReconnect = false
          eventSource.close()
        } catch (e) {}
        sseEventSource.value = null
      }
    } catch (error) {
      console.error('解析 SSE 消息失败:', error)
    }
  }

  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)
    // 作为保险：切换到进度页并标记连接断开，关闭连接
    installTab.value = 'progress'

    // 检查是否已达终态，如果是则不需要标记为 error
    const currentStatus = (installProgress.value.status || '').toLowerCase()
    if (!terminalStatuses.has(currentStatus)) {
      // 只有在非终态时才标记为 error
      if (installProgress.value.status === 'running') {
        installProgress.value.status = 'error'
        installProgress.value.message = '连接已断开'
      }
    }

    // 禁用自动重连并关闭连接
    try {
      eventSource.autoReconnect = false
      eventSource.close()
    } catch (e) {}
    sseEventSource.value = null
  }
}

// 批量安装
const handleBatchInstall = async () => {
  if (!installForm.host_ids || installForm.host_ids.length === 0) {
    Message.warning('请至少选择一个主机')
    return
  }
  if (installForm.install_type === 'agent' && !installForm.agent_server_url) {
    Message.warning('安装 Agent 需要填写 Agent-Server 地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !installForm.agent_server_listen_addr) {
    Message.warning('安装 Agent-Server 需要填写监听地址')
    return
  }

  // 检查是否有需要覆盖的Agent
  const hostsToReinstall = availableHosts.value.filter((host: any) =>
    installForm.host_ids.includes(host.id) &&
    host.agent_type === installForm.install_type &&
    host.agent_status === 'online'
  )

  const installTarget = installForm.install_type === 'agent' ? 'Agent' : 'Agent-Server'

  if (hostsToReinstall.length > 0) {
    // 有需要覆盖的Agent，先确认覆盖
    Modal.confirm({
      title: `确认覆盖安装${installTarget}`,
      content: `${hostsToReinstall.length} 台主机已安装${installTarget}，确定要覆盖安装吗？此操作将停止现有服务并重新安装。`,
      onOk: () => {
        performInstall(true) // allow_reinstall = true
      }
    })
  } else {
    // 没有需要覆盖的Agent，直接安装
    Modal.confirm({
      title: `确认批量安装${installTarget}`,
      content: `确定要在 ${installForm.host_ids.length} 台主机上安装 ${installTarget} 吗？`,
      onOk: () => {
        performInstall(false) // allow_reinstall = false
      }
    })
  }
}

// 执行安装
const performInstall = async (allowReinstall: boolean) => {
  installing.value = true
  try {
    const params: any = {
      host_ids: installForm.host_ids,
      install_type: installForm.install_type,
      ssh_timeout: installForm.ssh_timeout,
      allow_reinstall: allowReinstall, // 使用传递的参数
      package_id: installForm.package_id,
      package_version: installForm.package_version,
      confirmed: true,
    }

    if (installForm.install_type === 'agent') {
      params.install_mode = installForm.install_mode
      params.agent_server_url = installForm.agent_server_url
      // 备地址已移除，不传递
      params.ws_backoff_initial_ms = installForm.ws_backoff_initial_ms
      params.ws_backoff_max_ms = installForm.ws_backoff_max_ms
      params.ws_max_retries = installForm.ws_max_retries
    } else if (installForm.install_type === 'agent-server') {
      params.agent_server_listen_addr = installForm.agent_server_listen_addr
      params.max_connections = installForm.max_connections
      params.heartbeat_timeout = installForm.heartbeat_timeout
    }

    const response = await agentsApi.batchInstall(params)

    // 如果有 install_task_id，连接sse查看实时进度
    if (response.install_task_id) {
      connectInstallProgressSSE(response.install_task_id)
      Message.info('安装已启动，正在查看实时进度...')
    } else {
      // 如果没有sse，显示最终结果
      Message.success(
        `批量安装完成：成功 ${response.success_count} 个，失败 ${response.failed_count} 个`
      )

      // 显示详细结果
      if (response.failed_count > 0) {
        const failedHosts = response.results
          .filter((r: any) => !r.success)
          .map((r: any) => `${r.host_name}: ${r.message}`)
          .join('\n')
        Modal.warning({
          title: '部分主机安装失败',
          content: failedHosts,
          width: 600,
        })
      }

      // 刷新列表
      installModalVisible.value = false
      fetchAgents()
    }
  } catch (error: any) {
    console.error('批量安装失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '批量安装失败'
    Message.error(errorMsg)
  } finally {
    installing.value = false
  }
}

// 复制脚本
const copyScript = (script: string) => {
  navigator.clipboard.writeText(script).then(() => {
    Message.success('脚本已复制到剪贴板')
  }).catch(() => {
    Message.error('复制失败，请手动复制')
  })
}

// 复制文本
const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    Message.success('已复制到剪贴板')
  }).catch(() => {
    Message.error('复制失败')
  })
}

// 更新统计信息
const updateStatistics = () => {
  statistics.pending = agents.value.filter(a => (a.computed_status || a.status) === 'pending').length
  statistics.online = agents.value.filter(a => (a.computed_status || a.status) === 'online').length
  statistics.offline = agents.value.filter(a => (a.computed_status || a.status) === 'offline').length
  statistics.disabled = agents.value.filter(a => (a.computed_status || a.status) === 'disabled').length
}

// 重置统计信息
const resetStatistics = () => {
  statistics.pending = 0
  statistics.online = 0
  statistics.offline = 0
  statistics.disabled = 0
}

// 表格选择变化
const handleSelectionChange = (rowKeys: (string | number)[]) => {
  selectedAgentIds.value = rowKeys as number[]
}

// 查看安装脚本（用于 pending 状态的 Agent）
const handleRegenerateScript = async (agent: any) => {
  try {
    await Modal.confirm({
      title: '重新生成安装脚本',
      content: '将为该 Agent 签发新 token 并生成新的安装脚本，旧 token 将失效，确认继续？',
      okText: '重新生成',
      async onOk() {
        try {
          const response = await agentsApi.regenerateScript(agent.id)
          installScripts.value = response.scripts
          installModalVisible.value = true
          installTab.value = 'script'

          if (response.notice) {
            Message.warning(response.notice)
          }
          Message.success('已重新生成安装脚本并签发新 token')
        } catch (error: any) {
          console.error('获取安装脚本失败:', error)
          const errorMsg = error?.response?.data?.message || error?.message || '获取安装脚本失败'
          Message.error(errorMsg)
          throw error
        }
      },
    })
  } catch {
    // 用户取消时无需处理，错误已在 onOk 中提示
  }
}

// 批量重新生成脚本
const handleBatchRegenerateScript = async () => {
  if (selectedAgentIds.value.length === 0) {
    Message.warning('请至少选择一个 Agent')
    return
  }
  
  const pendingAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && (a.computed_status || a.status) === 'pending'
  )
  
  if (pendingAgents.length === 0) {
    Message.warning('选中的 Agent 中没有待激活状态的 Agent')
    return
  }
  
  Modal.confirm({
    title: '确认批量重新生成脚本',
    content: `将为 ${pendingAgents.length} 个待激活的 Agent 签发新 token 并重新生成安装脚本，旧 token 将失效，确认继续？`,
    onOk: async () => {
      try {
        // 为每个 Agent 生成脚本
        const scripts: any = {}
        let successCount = 0
        let failCount = 0
        
        for (const agent of pendingAgents) {
          try {
            const response = await agentsApi.regenerateScript(agent.id)
            // 合并脚本
            for (const [osType, scriptList] of Object.entries(response.scripts)) {
              if (!scripts[osType]) {
                scripts[osType] = []
              }
              if (Array.isArray(scriptList)) {
                scripts[osType].push(...scriptList)
              }
            }
            successCount++
          } catch (error: any) {
            console.error(`为 Agent ${agent.id} 生成脚本失败:`, error)
            failCount++
          }
        }
        
        if (successCount > 0) {
          installScripts.value = scripts
          installModalVisible.value = true
          installTab.value = 'script'
          Message.success(`成功为 ${successCount} 个 Agent 重新生成脚本${failCount > 0 ? `，${failCount} 个失败` : ''}`)
        } else {
          Message.error('批量生成脚本失败')
        }
      } catch (error: any) {
        console.error('批量生成脚本失败:', error)
        Message.error('批量生成脚本失败')
      }
    }
  })
}

// 批量删除待激活的 Agent
// 批量禁用 Agent
const handleBatchDisable = async () => {
  if (selectedAgentIds.value.length === 0) {
    Message.warning('请先选择要禁用的 Agent')
    return
  }

  const disableableAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    ((a.computed_status || a.status) !== 'disabled') && 
    ((a.computed_status || a.status) !== 'pending')
  )

  if (disableableAgents.length === 0) {
    Message.warning('选中的 Agent 中没有可禁用的（只有非 pending 且非 disabled 状态的 Agent 可以禁用）')
    return
  }

  // 检查生产环境
  const prodAgents = disableableAgents.filter(a =>
    (a.host?.tags || []).some(t => {
      const normalized = String((t as any)?.value ?? (t as any)?.label ?? t ?? '').toLowerCase()
      if (normalized === 'prod') return true
      const key = String((t as any)?.key ?? '').toLowerCase()
      const val = String((t as any)?.value ?? '').toLowerCase()
      return key === 'prod' || val === 'prod'
    })
  )
  if (prodAgents.length > 0 && disableableAgents.length > 10) {
    Message.warning('生产环境批量操作最多支持 10 个 Agent')
    return
  }

  try {
    await Modal.confirm({
      title: '确认批量禁用',
      content: `确定要禁用选中的 ${disableableAgents.length} 个 Agent 吗？禁用后这些 Agent 将不再接收新任务。`,
      onOk: async () => {
        try {
          const result = await agentsApi.batchDisable({
            agent_ids: disableableAgents.map(a => a.id),
            confirmed: true
          })
          Message.success(`批量禁用成功，共 ${result.count} 个 Agent`)
          selectedAgentIds.value = []
          fetchAgents()
        } catch (error: any) {
          console.error('批量禁用失败:', error)
          Message.error(error?.message || '批量禁用失败')
        }
      }
    })
  } catch (error) {
    // 用户取消
  }
}

// 批量启用 Agent
const handleBatchEnable = async () => {
  if (selectedAgentIds.value.length === 0) {
    Message.warning('请先选择要启用的 Agent')
    return
  }

  const enableableAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    (a.computed_status || a.status) === 'disabled'
  )

  if (enableableAgents.length === 0) {
    Message.warning('选中的 Agent 中没有可启用的（只有 disabled 状态的 Agent 可以启用）')
    return
  }

  // 检查生产环境
  const prodAgents = enableableAgents.filter(a =>
    (a.host?.tags || []).some(t => {
      const normalized = String((t as any)?.value ?? (t as any)?.label ?? t ?? '').toLowerCase()
      if (normalized === 'prod') return true
      const key = String((t as any)?.key ?? '').toLowerCase()
      const val = String((t as any)?.value ?? '').toLowerCase()
      return key === 'prod' || val === 'prod'
    })
  )
  if (prodAgents.length > 0 && enableableAgents.length > 10) {
    Message.warning('生产环境批量操作最多支持 10 个 Agent')
    return
  }

  try {
    await Modal.confirm({
      title: '确认批量启用',
      content: `确定要启用选中的 ${enableableAgents.length} 个 Agent 吗？启用后这些 Agent 将恢复接收新任务。`,
      onOk: async () => {
        try {
          const result = await agentsApi.batchEnable({
            agent_ids: enableableAgents.map(a => a.id),
            confirmed: true
          })
          Message.success(`批量启用成功，共 ${result.count} 个 Agent`)
          selectedAgentIds.value = []
          fetchAgents()
        } catch (error: any) {
          console.error('批量启用失败:', error)
          Message.error(error?.message || '批量启用失败')
        }
      }
    })
  } catch (error) {
    // 用户取消
  }
}

// 批量重启 Agent
const handleBatchRestart = async () => {
  if (selectedAgentIds.value.length === 0) {
    Message.warning('请先选择要重启的 Agent')
    return
  }

  try {
    await Modal.confirm({
      title: '确认批量重启',
      content: `确定要重启选中的 ${selectedAgentIds.value.length} 个 Agent 吗？重启期间这些 Agent 将短暂离线。`,
      onOk: async () => {
        try {
          const result = await agentsApi.batchRestart({
            agent_ids: selectedAgentIds.value,
            confirmed: true
          })

          // 如果有 batch_task_id，连接 SSE 查看实时进度
          if (result.batch_task_id) {
            connectBatchOperationSSE(result.batch_task_id, '重启')
            Message.info('重启已启动，正在查看实时进度...')
          } else {
            // 如果没有 SSE，显示最终结果
            Message.success(`批量重启已启动`)
            selectedAgentIds.value = []
            fetchAgents()
          }
        } catch (error: any) {
          console.error('批量重启失败:', error)
          Message.error(error?.message || '批量重启失败')
        }
      }
    })
  } catch (error) {
    // 用户取消
  }
}

const handleBatchDeletePending = async () => {
  if (selectedAgentIds.value.length === 0) {
    Message.warning('请至少选择一个 Agent')
    return
  }
  
  const pendingAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && (a.computed_status || a.status) === 'pending'
  )
  
  if (pendingAgents.length === 0) {
    Message.warning('选中的 Agent 中没有待激活状态的 Agent')
    return
  }
  
  Modal.confirm({
    title: '确认批量删除',
    content: `确定要删除 ${pendingAgents.length} 个待激活的 Agent 吗？此操作不可恢复！`,
    okText: '确认删除',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        const agentIds = pendingAgents.map(a => a.id)
        const response = await agentsApi.batchDelete({
          agent_ids: agentIds,
          confirmed: true
        })
        
        Message.success(`成功删除 ${response.count} 个 Agent`)
        selectedAgentIds.value = []
        fetchAgents()
      } catch (error: any) {
        console.error('批量删除失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '批量删除失败'
        Message.error(errorMsg)
      }
    }
  })
}

// 清理卸载 SSE 连接
const cleanupUninstallSSE = () => {
  if (uninstallSseEventSource.value) {
    uninstallSseEventSource.value.close()
    uninstallSseEventSource.value = null
  }
}

// 连接批量操作进度 SSE
const connectBatchOperationSSE = (batchTaskId: string, operation: string) => {
  // 关闭之前的连接
  if (batchOperationSseEventSource.value) {
    batchOperationSseEventSource.value.close()
  }

  // 重置进度
  batchOperationProgress.value = {
    total: 0,
    completed: 0,
    success_count: 0,
    failed_count: 0,
    status: 'running',
    message: '正在连接...',
    operation: operation,
    logs: []
  }

  // 获取 token
  const token = getAccessToken()
  // 使用相对路径，因为 SSE 请求会通过代理
  // backend route is /api/realtime/sse/agent-batch/<id>/
  const sseUrl = buildSseUrl(`agent-batch/${batchTaskId}/`)

  // 使用 sse.js 建立连接并通过 Authorization header 认证
  const eventSource = new SSE(sseUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    start: true,
    debug: process.env.NODE_ENV === 'development',
    autoReconnect: true,
    reconnectDelay: 3000,
    maxRetries: 3,
    withCredentials: true
  })
  batchOperationSseEventSource.value = eventSource

  // 定义批量操作终态集合
  const batchTerminalStatuses = new Set(['completed', 'completed_with_errors', 'failed', 'success', 'error', 'stopped'])

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'connection_established') {
        batchOperationProgress.value.message = data.message || `已连接到${operation}进度流`
        batchOperationProgress.value.status = 'running'
      } else if (data.type === 'status') {
        batchOperationProgress.value.total = data.total || data.total_hosts || 0
        batchOperationProgress.value.completed = data.completed || 0
        batchOperationProgress.value.success_count = data.success_count || data.success_hosts || 0
        batchOperationProgress.value.failed_count = data.failed_count || data.failed_hosts || 0
        batchOperationProgress.value.status = data.status || 'running'
        batchOperationProgress.value.message = data.message || ''

        // 检测终态：收到终态后主动关闭连接，避免自动重连
        const statusValue = (data.status || '').toLowerCase()
        if (batchTerminalStatuses.has(statusValue)) {
          console.log(`${operation}任务已达终态: ${statusValue}，关闭 SSE 连接`)
          // 禁用自动重连并关闭连接
          try {
            eventSource.autoReconnect = false
            eventSource.close()
          } catch (e) {
            console.warn('关闭 SSE 连接失败:', e)
          }
          batchOperationSseEventSource.value = null
          // 刷新 Agent 列表
          fetchAgents()
        }
      } else if (data.type === 'log') {
        batchOperationProgress.value.logs.push({
          host_name: data.host_name || '',
          host_ip: data.host_ip || '',
          content: data.content || '',
          log_type: data.log_type || 'info',
          timestamp: data.timestamp || new Date().toISOString()
        })
        // 限制日志数量，保留最近 500 条
        if (batchOperationProgress.value.logs.length > 500) {
          batchOperationProgress.value.logs = batchOperationProgress.value.logs.slice(-500)
        }
      } else if (data.type === 'error') {
        batchOperationProgress.value.status = 'error'
        batchOperationProgress.value.message = data.message || '发生错误'
        batchOperationProgress.value.logs.push({
          host_name: '',
          host_ip: '',
          content: `错误: ${data.message}`,
          log_type: 'error',
          timestamp: new Date().toISOString()
        })
        // 关闭连接
        try {
          eventSource.autoReconnect = false
          eventSource.close()
        } catch (e) {}
        batchOperationSseEventSource.value = null
      }
    } catch (error) {
      console.error('解析 SSE 消息失败:', error)
    }
  }

  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)

    // 检查是否已达终态，如果是则不需要标记为 error
    const currentStatus = (batchOperationProgress.value.status || '').toLowerCase()
    if (!batchTerminalStatuses.has(currentStatus)) {
      // 只有在非终态时才标记为 error
      if (batchOperationProgress.value.status === 'running') {
        batchOperationProgress.value.status = 'error'
        batchOperationProgress.value.message = '连接已断开'
      }
    }

    // 禁用自动重连并关闭连接
    try {
      eventSource.autoReconnect = false
      eventSource.close()
    } catch (e) {}
    batchOperationSseEventSource.value = null
  }

  // 打开批量操作进度抽屉
  batchOperationDrawerVisible.value = true
}

// 关闭安装抽屉时按需刷新列表
watch(installModalVisible, (visible, wasVisible) => {
  if (!visible && wasVisible && shouldRefreshAfterInstall.value) {
    fetchAgents()
    shouldRefreshAfterInstall.value = false
  }
})

// 初始化
onMounted(() => {
  fetchAgents()
})

// 清理安装 SSE 连接
const cleanupSSE = () => {
  if (sseEventSource.value) {
    sseEventSource.value.close()
    sseEventSource.value = null
  }
}

// 清理批量操作 SSE 连接
const cleanupBatchOperationSSE = () => {
  if (batchOperationSseEventSource.value) {
    batchOperationSseEventSource.value.close()
    batchOperationSseEventSource.value = null
  }
}

// 组件卸载时清理 SSE 连接
onBeforeUnmount(() => {
  cleanupSSE()
  cleanupUninstallSSE()
  cleanupBatchOperationSSE()
})
</script>

<style scoped>
.agents-page {
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

.filter-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-title {
  font-weight: 500;
  color: #1d2129;
  white-space: nowrap;
}

.table-container {
  background: white;
  border-radius: 6px;
  overflow: hidden;
}

.install-step-scripts {
  padding-bottom: 16px;
}

.install-script-tip {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 4px;
  background-color: #f7f8fa;
  border: 1px solid #e5e6eb;
  font-size: 13px;
  color: #1d2129;
}

.install-script-tip-title {
  margin: 0 0 8px 0;
}

.install-script-tip-text {
  margin: 0 0 4px 0;
}

.install-script-tip-list {
  margin: 0;
  padding-left: 20px;
}

.install-script-tip-warning {
  margin: 8px 0 0 0;
  color: #f53f3f;
}

.install-script-token-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.install-script-token-label {
  color: #1d2129;
}

.install-script-token-value {
  font-family: 'Courier New', monospace;
  padding: 2px 6px;
  border-radius: 3px;
  background-color: #f2f3f5;
}

.host-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.host-name {
  font-weight: 500;
  color: var(--color-text-1);
}

.host-ip {
  font-size: 12px;
  color: var(--color-text-3);
  font-family: 'Courier New', monospace;
}

.text-gray {
  color: var(--color-text-3);
}

/* 资源使用概览样式 */
.resource-overview {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.resource-label {
  width: 28px;
  color: var(--color-text-3);
  flex-shrink: 0;
}

.resource-value {
  width: 32px;
  text-align: right;
  color: var(--color-text-2);
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

/* 表格样式优化 */
:deep(.arco-table) {
  /* 普通表头背景色 */
  .arco-table-th {
    background-color: #fff !important;
  }

  /* 固定列样式 */
  .arco-table-col-fixed-right {
    background-color: transparent !important;
  }

  .arco-table-col-fixed-right .arco-table-td {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right .arco-table-cell {
    background-color: inherit !important;
  }

  .arco-table-col-fixed-right::before {
    background-color: transparent !important;
    box-shadow: none !important;
  }
}

/* 筛选器样式 */
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-2);
  margin: 0;
}

.filter-stats {
  padding-top: 12px;
  border-top: 1px solid var(--color-border-2);
}

.stats-text {
  font-size: 13px;
  color: var(--color-text-3);
  font-weight: 500;
}
</style>

