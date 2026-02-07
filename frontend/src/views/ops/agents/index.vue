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
          <a-space :size="12" class="header-actions">
            <a-button type="primary" @click="handleInstallAgent">
              <template #icon>
                <icon-plus />
              </template>
              安装 Agent
            </a-button>
            <!-- 使用 CSS 过渡动画替代 v-if，避免选择时按钮闪烁和布局抖动 -->
            <div class="batch-actions" :class="{ 'batch-actions-visible': selectedAgentIds.length > 0 }">
              <a-space :size="8">
            <a-button 
                  v-show="selectedAgentIds.length > 0"
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
                  v-show="hasPendingAgents"
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
                  v-show="hasDisableableAgents"
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
                  v-show="hasEnableableAgents"
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
                  v-show="selectedAgentIds.length > 0"
              type="primary"
              status="warning"
              @click="handleBatchRestart"
            >
              <template #icon>
                <icon-refresh />
              </template>
              批量重启 ({{ selectedAgentIds.length }})
            </a-button>
              </a-space>
            </div>
            <a-divider direction="vertical" style="height: 32px; margin: 0" />
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
            <a-tag v-if="statusFilters.inactive" color="arcoblue">未活跃: {{ filteredInactiveCount }}</a-tag>
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
        row-key="id"
        :row-selection="rowSelection"
        :scroll="scrollConfig"
        :virtual-list-props="virtualListProps"
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

        <template #task_stats="{ record }">
          <a-tooltip v-if="record.task_stats && record.task_stats.total > 0" :content="getTaskStatsTooltip(record.task_stats)">
            <div class="task-stats-cell">
              <a-progress
                type="circle"
                :percent="record.task_stats.success_rate"
                :stroke-color="getSuccessRateColor(record.task_stats.success_rate)"
                :width="40"
                :show-text="false"
              />
              <span class="task-stats-text">
                {{ record.task_stats.success_rate?.toFixed(0) || 0 }}%
              </span>
            </div>
          </a-tooltip>
          <span v-else class="text-gray">-</span>
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
                <a-form-item label="最大并发任务数" field="max_concurrent_tasks">
                  <a-input-number
                    v-model="installForm.max_concurrent_tasks"
                    :min="1"
                    :max="20"
                    placeholder="留空使用默认值 (5)"
                    style="width: 100%"
                  />
                  <div class="form-help">控制该 Agent 同时执行的任务数量，留空则使用默认值 5</div>
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
                  <a-col :span="8">
                    <a-form-item label="启用压缩">
                      <a-switch v-model="installForm.ws_enable_compression" />
                      <div class="form-help">启用压缩（需服务端也开启）</div>
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
                <!-- WebSocket 配置 -->
                <a-divider>WebSocket 配置</a-divider>
                <a-row :gutter="12">
                  <a-col :span="8">
                    <a-form-item label="握手超时">
                      <a-input
                        v-model="installForm.ws_handshake_timeout"
                        placeholder="例如: 10s"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="读缓冲区">
                      <a-input-number v-model="installForm.ws_read_buffer_size" :min="1024" :max="65536" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="写缓冲区">
                      <a-input-number v-model="installForm.ws_write_buffer_size" :min="1024" :max="65536" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                </a-row>
                <a-row :gutter="12">
                  <a-col :span="12">
                    <a-form-item label="启用压缩">
                      <a-switch v-model="installForm.ws_enable_compression" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="允许来源(逗号分隔)">
                      <a-input
                        v-model="ws_allowed_origins_input"
                        placeholder="例如: http://example.com,https://app.example.com"
                        @blur="handleOriginsBlur"
                      />
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

        <!-- 安装进度面板已移除，改用独立的 ProgressDrawer 组件 -->
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

    <!-- 卸载进度抽屉 -->
    <ProgressDrawer
      v-model:visible="uninstallDrawerVisible"
      title="卸载 Agent"
      :progress="uninstallProgress"
      @close="handleUninstallDrawerClose"
    />

    <!-- 批量操作进度抽屉 -->
    <ProgressDrawer
      v-model:visible="batchOperationDrawerVisible"
      :title="`${batchOperationProgress.operation}进度`"
      :progress="batchOperationProgress"
      @close="handleBatchOperationDrawerClose"
    />

    <!-- 安装进度抽屉 -->
    <ProgressDrawer
      v-model:visible="installDrawerVisible"
      title="安装 Agent"
      :progress="installProgress"
      @close="handleInstallDrawerClose"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { IconCopy, IconHistory, IconDelete, IconCloseCircle, IconArrowUp, IconExclamationCircle, IconRefresh } from '@arco-design/web-vue/es/icon'
import { agentsApi, packageApi, type Agent, type AgentPackage } from '@/api/agents'
import { useSSEProgress, createProgressState, type ProgressState } from '@/composables/useSSEProgress'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import ProgressDrawer from '@/components/ProgressDrawer.vue'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

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
const installDrawerVisible = ref(false)  // 安装进度抽屉
const installForm = reactive({
  host_ids: [] as number[],
  install_type: 'agent' as 'agent' | 'agent-server',
  // Agent 配置
  install_mode: 'agent-server' as 'agent-server',
  agent_server_url: '',
  ws_backoff_initial_ms: 1000,
  ws_backoff_max_ms: 30000,
  ws_max_retries: 6,
  ws_enable_compression: false,
  // 最大并发任务数
  max_concurrent_tasks: undefined as number | undefined,
  // Agent-Server 配置
  agent_server_listen_addr: '0.0.0.0:8080',
  max_connections: 1000,
  heartbeat_timeout: 60,
  // Agent-Server WebSocket 配置
  ws_handshake_timeout: '10s',
  ws_read_buffer_size: 4096,
  ws_write_buffer_size: 4096,
  ws_allowed_origins: [] as string[],
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

// 安装进度 - 使用工厂函数创建
const installProgress = ref<ProgressState>(createProgressState())
const sseEventSource = ref<any | null>(null)

// WebSocket 允许来源输入
const ws_allowed_origins_input = ref('')

// 处理来源输入框失焦
const handleOriginsBlur = () => {
  if (ws_allowed_origins_input.value.trim()) {
    installForm.ws_allowed_origins = ws_allowed_origins_input.value
      .split(',')
      .map((o: string) => o.trim())
      .filter((o: string) => o.length > 0)
  } else {
    installForm.ws_allowed_origins = []
  }
}

// 卸载相关
const uninstallDrawerVisible = ref(false)
const uninstallTab = ref('select')
const uninstallForm = reactive({
  agent_ids: [] as number[],
})
const uninstalling = ref(false)

// 卸载进度 - 使用工厂函数创建
const uninstallProgress = ref<ProgressState>(createProgressState())
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
  status: ''
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
  onlyCurrent: false,
  selectedRowKeys: selectedAgentIds
})

// 表格滚动配置（支持虚拟滚动）
const scrollConfig = computed(() => ({
  x: 1300,
  y: 600
}))

// 虚拟列表配置（数据量大时启用）
const virtualListProps = computed(() => {
  return agents.value.length > 100 ? {
    height: 600,
    threshold: 100
  } : undefined
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
    title: '任务统计',
    dataIndex: 'task_stats',
    slotName: 'task_stats',
    width: 150
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

// 格式化时长
const formatDuration = (ms?: number) => {
  if (!ms) return '0ms'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

// 获取成功率颜色
const getSuccessRateColor = (rate: number | undefined): string => {
  if (rate === undefined || rate === null) return 'gray'
  if (rate >= 95) return '#0fbf60'
  if (rate >= 80) return '#ffb940'
  return '#f53f3f'
}

// 获取任务统计 Tooltip 内容
const getTaskStatsTooltip = (stats: any) => {
  if (!stats) return '暂无任务统计'
  return `总任务: ${stats.total || 0}
成功: ${stats.success || 0}
失败: ${stats.failed || 0}
取消: ${stats.cancelled || 0}
平均时长: ${formatDuration(stats.avg_duration_ms)}`
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

// 搜索（带防抖）
const handleSearch = () => {
  // 清除之前的防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  // 设置新的防抖定时器（300ms）
  searchDebounceTimer = setTimeout(() => {
  pagination.current = 1
  fetchAgents()
  }, 300)
}

// 重置
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchForm.search = ''
  searchForm.status = ''
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
  uninstallProgress.value = createProgressState()
  // 关闭之前的 SSE 连接
  if (uninstallSseEventSource.value) {
    uninstallSseEventSource.value.close()
    uninstallSseEventSource.value = null
  }
}

// 卸载抽屉关闭处理
const handleUninstallDrawerClose = () => {
  // 刷新列表
  fetchAgents()
}

// 批量操作抽屉关闭处理
const handleBatchOperationDrawerClose = () => {
  // 刷新列表
  fetchAgents()
}

// 安装抽屉关闭处理
const handleInstallDrawerClose = () => {
  // 刷新列表
  fetchAgents()
}

// Agent 选项过滤
const filterAgentOption = (inputValue: string, option: any) => {
  const label = option.label || ''
  return label.toLowerCase().includes(inputValue.toLowerCase())
}

// 连接 SSE 查看卸载进度
const uninstallSse = useSSEProgress({
  endpoint: 'agent-uninstall',
  progress: uninstallProgress.value,
  eventSource: uninstallSseEventSource,
  onSuccess: () => {
          // 刷新 Agent 列表
          fetchAgents()
        }
})

const connectUninstallProgressSSE = (uninstallTaskId: string) => {
  // 显示卸载进度抽屉
  uninstallDrawerVisible.value = true
  uninstallSse.connect(uninstallTaskId)
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
  installForm.ws_handshake_timeout = '10s'
  installForm.ws_read_buffer_size = 4096
  installForm.ws_write_buffer_size = 4096
  installForm.ws_enable_compression = true
  installForm.ws_allowed_origins = []
  ws_allowed_origins_input.value = ''
  installForm.ssh_timeout = 300
  installForm.package_id = undefined
  installForm.package_version = undefined
  installScripts.value = null
  shouldRefreshAfterInstall.value = false
  // 重置进度
  installProgress.value = createProgressState()
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
      params.ws_enable_compression = installForm.ws_enable_compression
    } else if (installForm.install_type === 'agent-server') {
      params.agent_server_listen_addr = installForm.agent_server_listen_addr
      params.max_connections = installForm.max_connections
      params.heartbeat_timeout = installForm.heartbeat_timeout
      // WebSocket 配置
      params.ws_handshake_timeout = installForm.ws_handshake_timeout
      params.ws_read_buffer_size = installForm.ws_read_buffer_size
      params.ws_write_buffer_size = installForm.ws_write_buffer_size
      params.ws_enable_compression = installForm.ws_enable_compression
      params.ws_allowed_origins = installForm.ws_allowed_origins
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
const installSse = useSSEProgress({
  endpoint: 'agent-install',
  progress: installProgress.value,
  eventSource: sseEventSource,
  onSuccess: () => {
          // 刷新 Agent 列表
          fetchAgents()
        }
})

const connectInstallProgressSSE = (installTaskId: string) => {
  // 显示独立的安装进度抽屉
  installDrawerVisible.value = true
  installSse.connect(installTaskId)
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
      // WebSocket 配置
      params.ws_handshake_timeout = installForm.ws_handshake_timeout
      params.ws_read_buffer_size = installForm.ws_read_buffer_size
      params.ws_write_buffer_size = installForm.ws_write_buffer_size
      params.ws_enable_compression = installForm.ws_enable_compression
      params.ws_allowed_origins = installForm.ws_allowed_origins
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
const batchOperationSse = useSSEProgress({
  endpoint: 'agent-batch',
  progress: batchOperationProgress.value,
  eventSource: batchOperationSseEventSource,
  onSuccess: () => {
          // 刷新 Agent 列表
          fetchAgents()
  },
  onProgress: (data) => {
    // 保持 operation 字段
    batchOperationProgress.value.operation = batchOperationProgress.value.operation || ''
  }
})

const connectBatchOperationSSE = (batchTaskId: string, operation: string) => {
  // 设置操作名称
  batchOperationProgress.value.operation = operation
  // 显示批量操作抽屉
  batchOperationDrawerVisible.value = true
  batchOperationSse.connect(batchTaskId)
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 批量操作按钮组过渡动画 - 使用 width + flex 避免布局抖动 */
.batch-actions {
  flex-shrink: 0;
  width: 0;
  overflow: hidden;
  opacity: 0;
  transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease;
  white-space: nowrap;
}

.batch-actions-visible {
  width: auto;
  opacity: 1;
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

/* 任务统计单元格 */
.task-stats-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  
  .task-stats-text {
    font-size: 12px;
    font-weight: 500;
    color: var(--color-text-2);
  }
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
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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
