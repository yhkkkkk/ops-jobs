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
          <n-space :size="12" class="header-actions">
            <n-button type="primary" @click="handleInstallAgent">
              <template #icon>
                <Plus  />
              </template>
              安装 Agent
            </n-button>
            <!-- 蓝鲸节点管理式：批量操作常显，勾选后可用（重装/安装/启停等） -->
            <n-dropdown trigger="click" :options="batchActionOptions" @select="onBatchAction">
              <n-button type="primary" secondary :disabled="selectedAgentIds.length === 0">
                <template #icon>
                  <MoreHorizontal />
                </template>
                批量操作{{ selectedAgentIds.length > 0 ? ` (${selectedAgentIds.length})` : '' }}
                <ChevronDown style="margin-left: 6px" />
              </n-button>
            </n-dropdown>
            <n-divider direction="vertical" style="height: 32px; margin: 0" />
            <n-button @click="handleViewInstallRecords">
              <template #icon>
                <History />
              </template>
              安装记录
            </n-button>
            <n-button @click="handleViewUninstallRecords">
              <template #icon>
                <Trash2 />
              </template>
              卸载记录
            </n-button>
            <n-button @click="fetchAgents">
              <template #icon>
                <RefreshCw  />
              </template>
              刷新
            </n-button>
          </n-space>
        </div>
      </div>
    </div>

    <n-tabs v-model:value="activeTab" type="line" class="agent-tabs">
      <n-tab-pane name="agent" tab="Agent">
        <!-- 搜索栏 -->
    <n-card class="mb-4">
      <n-form :model="searchForm">
        <div class="form-grid-row">
          <div class="form-grid-col" style="grid-column: span 4">
            <n-input
              v-model:value="searchForm.search"
              placeholder="主机名、IP"
              clearable
              @press-enter="handleSearch"
              @clear="handleSearch"
              style="width: 100%"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 3">
            <n-select
              v-model:value="searchForm.last_error_code"
              placeholder="输入错误码"
              clearable
              filterable
              allow-create
              :filter-option="false"
              :loading="errorCodeLoading"
              @search="handleErrorCodeSearch"
              @change="handleSearch"
              @clear="handleSearch"
              @dropdown-visible-change="handleErrorCodeDropdown"
              style="width: 100%"
              :options="(errorCodeOptions || []).map((c: string) => ({ label: c, value: c }))"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 3">
            <n-select
              v-model:value="searchForm.version"
              placeholder="输入版本"
              clearable
              filterable
              :filter-option="false"
              :loading="versionLoading"
              @search="handleVersionSearch"
              @change="handleSearch"
              @clear="handleSearch"
              @dropdown-visible-change="handleVersionDropdown"
              style="width: 100%"
              :options="(versionOptions || []).map((v: string) => ({ label: v, value: v }))"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 5">
            <n-select
              v-model:value="searchForm.agent_server_id"
              placeholder="请选择 Agent-Server"
              clearable
              filterable
              :filter-option="filterAgentServerOption"
              style="width: 100%"
              @change="handleSearch"
              :options="(agentServers || []).map((sv: any) => ({ label: formatAgentServerLabel(sv), value: sv.id }))"
            />
          </div>
          <div class="form-grid-col" style="grid-column: span 5">
            <div style="display: flex; justify-content: flex-end;">
              <n-space>
                <n-button type="primary" @click="handleSearch">
                  <template #icon>
                    <Search  />
                  </template>
                  搜索
                </n-button>
                <n-button @click="handleReset">
                  <template #icon>
                    <RefreshCw  />
                  </template>
                  重置
                </n-button>
              </n-space>
            </div>
          </div>
        </div>
      </n-form>
    </n-card>

    <!-- 快速状态过滤器 -->
    <n-card class="mb-4">
      <div class="filter-section">
        <div class="filter-title">快速筛选：</div>
        <n-space wrap>
          <!-- 基础状态筛选 -->
          <n-button
            :type="statusFilters.online ? 'primary' : 'default'"
            @click="toggleStatusFilter('online')"
          >
            <template #icon>
              <CircleCheck  />
            </template>
            在线Agent ({{ onlineCount }})
          </n-button>
          <n-button
            :type="statusFilters.offline ? 'primary' : 'default'"
            @click="toggleStatusFilter('offline')"
          >
            <template #icon>
              <CircleX  />
            </template>
            离线Agent ({{ offlineCount }})
          </n-button>
          <n-button
            :type="statusFilters.pending ? 'primary' : 'default'"
            @click="toggleStatusFilter('pending')"
          >
            <template #icon>
              <Clock3  />
            </template>
            待激活 ({{ pendingCount }})
          </n-button>
          <n-button
            :type="statusFilters.disabled ? 'primary' : 'default'"
            @click="toggleStatusFilter('disabled')"
          >
            <template #icon>
              <Square  />
            </template>
            已禁用 ({{ disabledCount }})
          </n-button>
          <!-- 分割线 -->
          <n-divider direction="vertical" style="height: 24px; margin: 0 8px;" />
          <!-- 问题状态筛选 -->
          <n-button
            :type="statusFilters.outdated ? 'primary' : 'default'"
            @click="toggleStatusFilter('outdated')"
          >
            <template #icon>
              <ChevronUp />
            </template>
            版本落后 ({{ outdatedCount }})
          </n-button>
          <n-button
            :type="statusFilters.failed ? 'primary' : 'default'"
            @click="toggleStatusFilter('failed')"
          >
            <template #icon>
              <CircleAlert  />
            </template>
            最近失败 ({{ failedCount }})
          </n-button>
          <!-- 清除筛选按钮 -->
          <n-button
            v-if="hasActiveFilters"
            @click="clearAllFilters" 
           type="error"
          >
            <template #icon>
              <RefreshCw  />
            </template>
            清除筛选
          </n-button>
        </n-space>

        <!-- 筛选统计信息 -->
        <div v-if="hasFilterSummary" class="filter-stats">
          <n-space>
            <span class="stats-text">
              当前显示: {{ filteredAgents.length }} / 总计: {{ agents.length }} 个Agent
            </span>
            <n-tag v-if="errorCodeFilterLabel" type="error">错误码: {{ errorCodeFilterLabel }}</n-tag>
            <n-tag v-if="statusFilters.online" type="success">在线: {{ filteredOnlineCount }}</n-tag>
            <n-tag v-if="statusFilters.offline" type="error">离线: {{ filteredOfflineCount }}</n-tag>
            <n-tag v-if="statusFilters.pending" type="warning">待激活: {{ filteredPendingCount }}</n-tag>
            <n-tag v-if="statusFilters.disabled" type="default">已禁用: {{ filteredDisabledCount }}</n-tag>
            <n-tag v-if="statusFilters.outdated" type="info">版本落后: {{ filteredOutdatedCount }}</n-tag>
            <n-tag v-if="statusFilters.failed" type="error">最近失败: {{ filteredFailedCount }}</n-tag>
          </n-space>
        </div>
      </div>
    </n-card>

    <!-- Agent 列表 -->
    <div class="table-container">
      <n-data-table
        :columns="columns"
        :data="filteredAgents"
        :loading="loading"
        :pagination="tablePagination"
        :row-key="(row: any) => row.id"
        :checked-row-keys="selectedAgentIds"
        :scroll-x="1400"
        :bordered="true"
        :single-line="false"
        @update:checked-row-keys="handleSelectionChange"
      />
    </div>

      </n-tab-pane>
      <n-tab-pane name="agent-server" tab="Agent-Server">
        <n-card class="mb-4">
          <n-form :model="agentServerSearchForm">
            <div class="form-grid-row">
              <div class="form-grid-col" style="grid-column: span 5">
                <n-input
                  v-model:value="agentServerSearchForm.search"
                  placeholder="名称/地址"
                  clearable
                  @press-enter="handleAgentServerSearch"
                  @clear="handleAgentServerSearch"
                  style="width: 100%"
                />
              </div>
              <div class="form-grid-col" style="grid-column: span 4">
                <n-select
                  v-model:value="agentServerSearchForm.version"
                  placeholder="输入版本"
                  clearable
                  filterable
                  :filter-option="false"
                  :loading="agentServerVersionLoading"
                  @search="handleAgentServerVersionSearch"
                  @change="handleAgentServerSearch"
                  @clear="handleAgentServerSearch"
                  @dropdown-visible-change="handleAgentServerVersionDropdown"
                  style="width: 100%"
                  :options="(agentServerVersionOptions || []).map((v: string) => ({ label: v, value: v }))"
                />
              </div>
              <div class="form-grid-col" style="grid-column: span 3">
                <n-select
                  :value="(agentServerSearchForm.is_active as any)"
                  placeholder="状态"
                  clearable
                  :options="[{ label: '启用', value: true }, { label: '停用', value: false }] as any"
                  style="width: 100%"
                  @update:value="(v: any) => { agentServerSearchForm.is_active = v; handleAgentServerSearch() }"
                />
              </div>
              <div class="form-grid-col" style="grid-column: span 3">
                <n-select
                  :value="(agentServerSearchForm.require_signature as any)"
                  placeholder="签名校验"
                  clearable
                  :options="[{ label: '开启', value: true }, { label: '关闭', value: false }] as any"
                  style="width: 100%"
                  @update:value="(v: any) => { agentServerSearchForm.require_signature = v; handleAgentServerSearch() }"
                />
              </div>
              <div class="form-grid-col" style="grid-column: span 5">
                <div style="display: flex; justify-content: flex-end;">
                  <n-space>
                    <n-button type="primary" @click="handleAgentServerSearch">
                      <template #icon>
                        <Search  />
                      </template>
                      搜索
                    </n-button>
                    <n-button @click="handleAgentServerReset">
                      <template #icon>
                        <RefreshCw  />
                      </template>
                      重置
                    </n-button>
                  </n-space>
                </div>
              </div>
            </div>
          </n-form>
        </n-card>
        <div class="table-container">
          <n-data-table
            :columns="agentServerColumns"
            :data="filteredAgentServers"
            :loading="agentServerTableLoading"
            :pagination="false"
            :row-key="(row: any) => row.id"
          />
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- 发 Token 弹窗 -->
    <n-modal
      preset="card"
      v-model:show="tokenModalVisible"
      title="签发 Agent Token"
      style="width: 480px"
    >
      <n-form :model="tokenForm" ref="tokenFormRef">
        <n-form-item
          label="过期时间"
          path="expired_at"
        >
          <n-date-picker
            v-model:value="tokenForm.expired_at"
            type="datetime"
            clearable
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item
          label="备注"
          path="note"
        >
          <n-input type="textarea"
            v-model:value="tokenForm.note"
            placeholder="请输入备注"
            :max-length="255"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </n-form-item>
        <n-form-item
          label="二次确认"
          path="confirmed"
        >
          <n-checkbox v-model:checked="tokenForm.confirmed">
            我已确认此操作（高危操作）
          </n-checkbox>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="handleTokenModalCancel">取消</n-button>
          <n-button type="primary" @click="handleIssueTokenConfirm" :disabled="!tokenForm.confirmed">
            确认签发
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 编辑 Agent-Server 弹窗 -->
    <n-modal preset="card"
      v-model:show="agentServerEditVisible"
      title="编辑 Agent-Server"
      @ok="handleAgentServerEditConfirm"
      @cancel="handleAgentServerEditCancel"
    >
      <n-alert type="info" show-icon style="margin-bottom: 12px;">
        仅更新控制面记录，不会自动下发/重装
      </n-alert>
      <n-form :model="agentServerEditForm" layout="vertical">
        <n-form-item label="名称" required>
          <n-input v-model:value="agentServerEditForm.name" placeholder="请输入名称" />
        </n-form-item>
        <n-form-item label="基础地址(base_url)" required>
          <n-input v-model:value="agentServerEditForm.base_url" placeholder="例如: http://agent-server.example.com:8080" />
        </n-form-item>
        <n-form-item label="启用状态">
          <n-switch v-model:value="agentServerEditForm.is_active" />
        </n-form-item>
        <n-form-item label="签名校验">
          <n-switch v-model:value="agentServerEditForm.require_signature" />
        </n-form-item>
        <n-form-item label="shared_secret">
          <n-input
            v-model:value="agentServerEditForm.shared_secret"
            placeholder="留空表示不变"
            :disabled="!agentServerEditForm.require_signature"
          />
          <div v-if="agentServerSecretHint" class="form-help">
            {{ agentServerSecretHint }}
          </div>
        </n-form-item>
        <n-form-item label="描述">
          <n-input type="textarea" v-model:value="agentServerEditForm.description" :autosize="{ minRows: 2, maxRows: 4 }" />
        </n-form-item>
      </n-form>
    </n-modal>

    <!-- 批量编辑 Agent-Server 弹窗 -->
    <n-modal preset="card"
      v-model:show="batchUpdateAgentServerVisible"
      title="批量编辑 Agent-Server"
      @ok="handleBatchUpdateAgentServerConfirm"
      @cancel="handleBatchUpdateAgentServerCancel"
    >
      <n-alert type="info" show-icon style="margin-bottom: 12px;">
        仅更新控制面记录，不会自动下发/重装
      </n-alert>
      <n-form :model="batchUpdateAgentServerForm" layout="vertical">
        <n-form-item label="关联 Agent-Server">
          <n-select
            v-model:value="batchUpdateAgentServerForm.agent_server_id"
            placeholder="请选择 Agent-Server"
            clearable
            filterable
            :filter-option="filterAgentServerOption" :options="(agentServers || []).map((sv: any) => ({ label: formatAgentServerLabel(sv), value: sv.id }))" />
          <div class="form-help">留空表示解除绑定（仅控制面记录）</div>
        </n-form-item>
      </n-form>
    </n-modal>

    <!-- 安装 Agent 抽屉 -->
    <n-drawer
      v-model:show="installModalVisible"
     
      width="900px"
     
      placement="right"
    ><n-drawer-content title="安装 Agent">
      <div class="install-content">
        <div class="install-step">
            <n-form :model="installForm" layout="vertical">
              <n-form-item label="安装类型">
                <div class="form-item-stack">
                  <n-radio-group v-model:value="installForm.install_type" @update:value="handleInstallTypeChange">
                    <n-radio value="agent">安装 Agent</n-radio>
                    <n-radio value="agent-server">安装 Agent-Server</n-radio>
                  </n-radio-group>
                  <div class="form-help">
                    选择安装类型后，主机列表会自动刷新并显示符合条件的主机
                  </div>
                </div>
              </n-form-item>

              <n-form-item label="选择主机">
                <div class="form-item-stack">
                  <n-select
                    v-model:value="installForm.host_ids"
                    placeholder="请选择要安装 Agent 的主机"
                    multiple
                    :max-tag-count="3"
                    filterable
                    clearable
                    :filter-option="filterHostOption"
                    style="width: 100%"
                    :options="(availableHosts || []).map((hst: any) => ({ label: getHostLabel(hst), value: hst.id }))"
                  />
                  <n-button text size="small" class="form-inline-action" @click="fetchAvailableHosts">刷新主机列表</n-button>
                </div>
              </n-form-item>
              <template v-if="installForm.install_type === 'agent'">
                <n-form-item label="Agent-Server 地址">
                  <div class="form-item-stack">
                    <n-input
                      v-model:value="installForm.agent_server_url"
                      placeholder="例如: ws://agent-server:8080"
                    />
                    <div class="form-help">Agent 连接 Agent-Server 的 WS 地址，仅安装 Agent 使用</div>
                  </div>
                </n-form-item>
                <n-form-item label="最大并发任务数" path="max_concurrent_tasks">
                  <div class="form-item-stack">
                    <n-input-number
                      v-model:value="installForm.max_concurrent_tasks"
                      :min="1"
                      :max="20"
                      placeholder="留空使用默认值 (5)"
                      style="width: 100%"
                    />
                    <div class="form-help">控制该 Agent 同时执行的任务数量，留空则使用默认值 5</div>
                  </div>
                </n-form-item>
                <div class="form-grid-row">
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="WS 初始退避(ms)">
                      <n-input-number v-model:value="installForm.ws_backoff_initial_ms" :min="100" :max="60000" style="width: 100%" />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="WS 最大退避(ms)">
                      <n-input-number v-model:value="installForm.ws_backoff_max_ms" :min="1000" :max="600000" style="width: 100%" />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="WS 最大重试">
                      <n-input-number v-model:value="installForm.ws_max_retries" :min="1" :max="20" style="width: 100%" />
                    </n-form-item>
                  </div>
                </div>
                <n-form-item label="启用压缩">
                  <div class="switch-with-help">
                    <n-switch v-model:value="installForm.ws_enable_compression" />
                    <span class="form-help">启用压缩（需服务端也开启）</span>
                  </div>
                </n-form-item>
              </template>
              <template v-if="installForm.install_type === 'agent-server'">
                <n-form-item label="控制面访问地址">
                  <div class="form-item-stack">
                    <n-input
                      v-model:value="installForm.agent_server_base_url"
                      placeholder="例如: http://agent-server.example.com:8080"
                      style="width: 100%"
                    />
                    <div class="form-help">控制面访问 Agent-Server 的地址(base_url)，默认使用监听地址，可按需改为域名或负载均衡地址</div>
                  </div>
                </n-form-item>
                <n-form-item label="Agent-Server 监听地址">
                  <div class="form-item-stack">
                    <n-input
                      v-model:value="installForm.agent_server_listen_addr"
                      placeholder="例如: 0.0.0.0:8080"
                      style="width: 100%"
                    />
                    <div class="form-help">Agent-Server 服务监听地址，写入 agent-server 配置</div>
                  </div>
                </n-form-item>
                <div class="form-grid-row" :gutter="12">
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="最大连接数">
                      <n-input-number v-model:value="installForm.max_connections" :min="100" :max="10000" style="width: 100%" />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="心跳超时(秒)">
                      <n-input-number v-model:value="installForm.heartbeat_timeout" :min="30" :max="300" style="width: 100%" />
                    </n-form-item>
                  </div>
                </div>
                <!-- WebSocket 配置 -->
                <n-divider>WebSocket 配置</n-divider>
                <div class="form-grid-row" :gutter="12">
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="握手超时">
                      <n-input
                        v-model:value="installForm.ws_handshake_timeout"
                        placeholder="例如: 10s"
                      />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="读缓冲区">
                      <n-input-number v-model:value="installForm.ws_read_buffer_size" :min="1024" :max="65536" style="width: 100%" />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 8">
                    <n-form-item label="写缓冲区">
                      <n-input-number v-model:value="installForm.ws_write_buffer_size" :min="1024" :max="65536" style="width: 100%" />
                    </n-form-item>
                  </div>
                </div>
                <div class="form-grid-row" :gutter="12">
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="启用压缩">
                      <n-switch v-model:value="installForm.ws_enable_compression" />
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="允许来源(逗号分隔)">
                      <n-input
                        v-model:value="ws_allowed_origins_input"
                        placeholder="例如: http://example.com,https://app.example.com"
                        @blur="handleOriginsBlur"
                      />
                    </n-form-item>
                  </div>
                </div>
                <n-divider>认证</n-divider>
                <div class="form-grid-row" :gutter="12">
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="启用签名校验">
                      <div class="switch-with-help">
                        <n-switch v-model:value="installForm.auth_require_signature" />
                        <span class="form-help">开启后控制面请求必须携带签名</span>
                      </div>
                    </n-form-item>
                  </div>
                  <div class="form-grid-col" style="grid-column: span 12">
                    <n-form-item label="shared_secret">
                      <n-input
                        v-model:value="installForm.auth_shared_secret"
                        :disabled="!installForm.auth_require_signature"
                        placeholder="请输入 shared_secret"
                      />
                      <div v-if="getSharedSecretHint()" class="form-help">
                        {{ getSharedSecretHint() }}
                      </div>
                    </n-form-item>
                  </div>
                </div>
              </template>
              <div class="form-grid-row" :gutter="12">
                <div class="form-grid-col" style="grid-column: span 8">
                  <n-form-item label="SSH 超时(秒)">
                    <n-input-number v-model:value="installForm.ssh_timeout" :min="60" :max="900" style="width: 100%" />
                  </n-form-item>
                </div>
              </div>
              <n-form-item label="安装包版本">
                <div class="form-item-stack">
                  <n-select
                    v-model:value="installForm.package_id"
                    placeholder="请选择安装包版本（留空使用默认版本）"
                    clearable
                    filterable
                    :loading="loadingPackages"
                    @update:value="handlePackageChange"
                    :options="(availablePackages || []).map((pkg: any) => ({ label: `${pkg.version} - ${pkg.os_type_display} - ${pkg.arch_display}`, value: pkg.id }))"
                  />
                  <n-button text size="small" class="form-inline-action" @click="fetchAvailablePackages">刷新安装包列表</n-button>
                </div>
              </n-form-item>
              <n-form-item>
                <n-space>
                  <n-button type="primary" @click="handleGenerateScript" :loading="generatingScript">
                    生成安装脚本
                  </n-button>
                  <n-button type="success" @click="handleBatchInstall" :loading="installing">
                    批量安装（SSH）
                  </n-button>
                </n-space>
              </n-form-item>
            </n-form>
          </div>

          <!-- 安装进度面板已移除，改用独立的 ProgressDrawer 组件 -->
          <div v-if="installScripts">
          <n-divider>安装脚本</n-divider>
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
                <n-card :title="`${item.host_name} (${item.host_ip})`" size="small">
                  <template #footer>
                    <n-button text size="small" @click="copyScript(item.script)">
                      <template #icon>
                        <Copy />
                      </template>
                      复制脚本
                    </n-button>
                  </template>
                  <div class="install-script-token-row">
                    <span class="install-script-token-label"><strong>Agent Token:</strong></span>
                    <code class="install-script-token-value">{{ item.agent_token }}</code>
                    <n-button text size="tiny" @click="copyText(item.agent_token)" style="margin-left: 8px">
                      <template #icon>
                        <Copy />
                      </template>
                    </n-button>
                  </div>
                  <n-input type="textarea"
                    :model-value="item.script"
                    auto-size
                    readonly
                    style="font-family: 'Courier New', monospace; font-size: 12px; margin-top: 8px;"
                  />
                </n-card>
              </div>
            </div>
          </div>
        </div>
      </div>
    </n-drawer-content></n-drawer>

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
import { computed, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { agentsApi, packageApi, agentServerApi, type Agent, type AgentPackage, type AgentServer } from '@/api/agents'
import { useSSEProgress, createProgressState, type ProgressState } from '@/composables/useSSEProgress'
import { useFilterQuerySync, parseBooleanQuery, parseNumberQuery, parseStringArrayQuery } from '@/composables/useFilterQuerySync'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import ProgressDrawer from '@/components/ProgressDrawer.vue'
import { NAlert, NButton, NCard, NCheckbox, NDataTable, NDatePicker, NDivider, NDrawer, NDrawerContent, NDropdown, NForm, NFormItem, NInput, NInputNumber, NModal, NProgress, NRadio, NRadioGroup, NSelect, NSpace, NSwitch, NTabPane, NTabs, NTag, NTooltip, type DataTableColumns, useDialog, useMessage } from 'naive-ui'
import { ChevronDown, ChevronUp, CircleAlert, CircleCheck, CircleX, Clock3, Copy, Eye, History, Info, Lock, MoreHorizontal, Pencil, Plus, RefreshCw, Search, Square, Trash2 } from 'lucide-vue-next'

// 搜索防抖定时器
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const resolveTabKey = (value: unknown) => {
  return value === 'agent-server' ? 'agent-server' : 'agent'
}

const activeTab = ref<'agent' | 'agent-server'>('agent')

const syncTabToQuery = (tab: string) => {
  const normalized = resolveTabKey(tab)
  const current = resolveTabKey(route.query.tab)
  if (current === normalized) return
  router.replace({
    query: {
      ...route.query,
      tab: normalized
    }
  })
}

const buildAgentServerBaseUrl = (listenAddr: string) => {
  const raw = (listenAddr || '').trim()
  if (!raw) return ''
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw
  return `http://${raw}`
}

const resolveAgentServerBaseUrl = () => {
  if (installForm.agent_server_base_url && installForm.agent_server_base_url.trim()) {
    return installForm.agent_server_base_url.trim()
  }
  return buildAgentServerBaseUrl(installForm.agent_server_listen_addr)
}

// 响应式数据
const loading = ref(false)
const agents = ref<Agent[]>([])
const agentServers = ref<AgentServer[]>([])
const agentServerTable = ref<AgentServer[]>([])
const agentServerTableLoading = ref(false)
const tokenModalVisible = ref(false)
const currentAgent = ref<Agent | null>(null)
const tokenFormRef = ref()
const errorCodeOptions = ref<string[]>([])
const errorCodeLoading = ref(false)
const versionOptions = ref<string[]>([])
const versionLoading = ref(false)
const agentServerVersionOptions = ref<string[]>([])
const agentServerVersionLoading = ref(false)

let errorCodeSearchTimer: ReturnType<typeof setTimeout> | null = null
let versionSearchTimer: ReturnType<typeof setTimeout> | null = null
let agentServerVersionSearchTimer: ReturnType<typeof setTimeout> | null = null

// Agent-Server 编辑相关
const agentServerEditVisible = ref(false)
const agentServerEditing = ref<AgentServer | null>(null)
const agentServerEditForm = reactive({
  id: null as number | null,
  name: '',
  base_url: '',
  require_signature: false,
  shared_secret: '',
  is_active: true,
  description: ''
})

const batchUpdateAgentServerVisible = ref(false)
const batchUpdateAgentServerForm = reactive({
  agent_server_id: null as number | null
})

// 安装相关
const installModalVisible = ref(false)
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
  agent_server_base_url: '',
  max_connections: 1000,
  heartbeat_timeout: 60,
  // Agent-Server WebSocket 配置
  ws_handshake_timeout: '10s',
  ws_read_buffer_size: 4096,
  ws_write_buffer_size: 4096,
  ws_allowed_origins: [] as string[],
  auth_shared_secret: '',
  auth_require_signature: false,
  // 通用配置
  ssh_timeout: 300,
  package_id: undefined as number | undefined,
  package_version: undefined as string | undefined,
})

const getSharedSecretHint = () => {
  if (installForm.auth_shared_secret) {
    const suffix = installForm.auth_shared_secret.slice(-4)
    return `当前输入尾号 ${suffix}`
  }
  return ''
}

const agentServerSecretHint = computed(() => {
  if (!agentServerEditForm.require_signature) {
    return ''
  }
  if (agentServerEditForm.shared_secret) {
    const suffix = agentServerEditForm.shared_secret.slice(-4)
    return `当前输入尾号 ${suffix}`
  }
  if (agentServerEditing.value?.shared_secret_last4) {
    return `已存在密钥尾号 ${agentServerEditing.value.shared_secret_last4}，留空表示不变`
  }
  return '启用签名校验必须提供 shared_secret'
})

const formatAgentServerLabel = (server: AgentServer) => {
  const suffix = server.shared_secret_last4 ? ` - 密钥尾号 ${server.shared_secret_last4}` : ''
  return `${server.name} (${server.base_url})${suffix}`
}
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
const uninstallForm = reactive({
  agent_ids: [] as number[],
})

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
  status: '',
  last_error_code: '',
  version: '',
  agent_server_id: undefined as number | undefined,
  quick_status: [] as string[]
})

const agentServerSearchForm = reactive({
  search: '',
  version: '',
  is_active: undefined as boolean | undefined,
  require_signature: undefined as boolean | undefined
})

const { initFromQuery: initAgentServerFromQuery, syncToQuery: syncAgentServerToQuery } = useFilterQuerySync({
  searchForm: agentServerSearchForm,
  fields: [
    { key: 'search', queryKey: 'as_search' },
    { key: 'version', queryKey: 'as_version' },
    { key: 'is_active', queryKey: 'as_is_active', fromQuery: parseBooleanQuery },
    { key: 'require_signature', queryKey: 'as_require_signature', fromQuery: parseBooleanQuery }
  ]
})

// 状态过滤器
const statusFilters = reactive({
  online: false,
  offline: false,
  pending: false,
  disabled: false,
  outdated: false,
  failed: false
})

const statusFilterKeys = Object.keys(statusFilters) as Array<keyof typeof statusFilters>

const normalizeQuickStatusList = (list: string[] = []) => {
  const allowed = new Set(statusFilterKeys.map(key => String(key)))
  return list.filter(item => allowed.has(String(item)))
}

const syncStatusFiltersFromList = (list: string[]) => {
  statusFilterKeys.forEach(key => {
    statusFilters[key] = list.includes(key)
  })
}

const updateQuickStatusFromFilters = () => {
  searchForm.quick_status = statusFilterKeys.filter(key => statusFilters[key])
}

watch(
  () => searchForm.quick_status,
  (value) => {
    const normalized = normalizeQuickStatusList(value || [])
    if (normalized.length !== (value || []).length) {
      searchForm.quick_status = normalized
      return
    }
    syncStatusFiltersFromList(normalized)
  },
  { deep: true, immediate: true }
)

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

const { initFromQuery, syncToQuery } = useFilterQuerySync({
  searchForm,
  pagination,
  fields: [
    { key: 'search' },
    { key: 'last_error_code' },
    { key: 'version' },
    { key: 'status' },
    { key: 'agent_server_id', fromQuery: parseNumberQuery },
    { key: 'quick_status', fromQuery: parseStringArrayQuery }
  ]
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

const selectedAgentServerId = computed(() => {
  if (searchForm.agent_server_id) {
    return searchForm.agent_server_id
  }
  const selectedAgents = agents.value.filter(agent => selectedAgentIds.value.includes(agent.id))
  const serverIds = Array.from(new Set(
    selectedAgents
      .map(agent => agent.agent_server_id)
      .filter((id): id is number => id !== undefined && id !== null)
  ))
  return serverIds.length === 1 ? serverIds[0] : null
})

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

const hasActiveFilters = computed(() => {
  return statusFilters.online || statusFilters.offline || statusFilters.pending ||
         statusFilters.disabled || statusFilters.outdated || statusFilters.failed
})

const normalizeFilterValue = (value: string) => {
  if (!value) return ''
  return value
    .replace(/,/g, ' ')
    .split(' ')
    .map(v => v.trim())
    .filter(Boolean)
    .join(',')
}

const errorCodeFilterLabel = computed(() => normalizeFilterValue(searchForm.last_error_code))

const hasFilterSummary = computed(() => {
  return hasActiveFilters.value || Boolean(errorCodeFilterLabel.value)
})

const normalizeErrorCodes = (items: string[]) => {
  const seen = new Set<string>()
  const result: string[] = []
  items.forEach(item => {
    const value = String(item || '').trim()
    if (!value || seen.has(value)) return
    seen.add(value)
    result.push(value)
  })
  return result
}

const ensureErrorCodeOption = (value?: string) => {
  const normalized = (value || '').trim()
  if (!normalized) return
  if (!errorCodeOptions.value.includes(normalized)) {
    errorCodeOptions.value = [normalized, ...errorCodeOptions.value]
  }
}

const fetchErrorCodes = async (searchValue?: string) => {
  errorCodeLoading.value = true
  try {
    const params = searchValue ? { search: searchValue } : undefined
    const response = await agentsApi.getErrorCodes(params)
    const items = Array.isArray(response?.items) ? response.items : []
    errorCodeOptions.value = normalizeErrorCodes(items)
    ensureErrorCodeOption(searchForm.last_error_code)
  } catch (error) {
    console.error('获取错误码列表失败:', error)
    errorCodeOptions.value = []
  } finally {
    errorCodeLoading.value = false
  }
}

const handleErrorCodeSearch = (value: string) => {
  if (errorCodeSearchTimer) {
    clearTimeout(errorCodeSearchTimer)
  }
  errorCodeSearchTimer = setTimeout(() => {
    fetchErrorCodes(value)
  }, 200)
}

const handleErrorCodeDropdown = (visible: boolean) => {
  if (visible && errorCodeOptions.value.length === 0) {
    fetchErrorCodes()
  }
}

const normalizeVersionOptions = (items: string[]) => {
  const seen = new Set<string>()
  const result: string[] = []
  items.forEach(item => {
    const value = String(item || '').trim()
    if (!value || seen.has(value)) return
    seen.add(value)
    result.push(value)
  })
  return result
}

const ensureVersionOption = (value?: string) => {
  const normalized = (value || '').trim()
  if (!normalized) return
  if (!versionOptions.value.includes(normalized)) {
    versionOptions.value = [normalized, ...versionOptions.value]
  }
}

const ensureAgentServerVersionOption = (value?: string) => {
  const normalized = (value || '').trim()
  if (!normalized) return
  if (!agentServerVersionOptions.value.includes(normalized)) {
    agentServerVersionOptions.value = [normalized, ...agentServerVersionOptions.value]
  }
}

const fetchAgentVersions = async (searchValue?: string) => {
  versionLoading.value = true
  try {
    const params = searchValue ? { search: searchValue } : undefined
    const response = await agentsApi.getAgentVersions(params)
    const items = Array.isArray(response?.items) ? response.items : []
    versionOptions.value = normalizeVersionOptions(items)
    ensureVersionOption(searchForm.version)
  } catch (error) {
    console.error('获取版本列表失败:', error)
    versionOptions.value = []
  } finally {
    versionLoading.value = false
  }
}

const fetchAgentServerVersions = async (searchValue?: string) => {
  agentServerVersionLoading.value = true
  try {
    const params: any = { agent_type: 'agent-server' }
    if (searchValue) {
      params.search = searchValue
    }
    const response = await agentsApi.getAgentVersions(params)
    const items = Array.isArray(response?.items) ? response.items : []
    agentServerVersionOptions.value = normalizeVersionOptions(items)
    ensureAgentServerVersionOption(agentServerSearchForm.version)
  } catch (error) {
    console.error('获取Agent-Server版本列表失败:', error)
    agentServerVersionOptions.value = []
  } finally {
    agentServerVersionLoading.value = false
  }
}

const handleVersionSearch = (value: string) => {
  if (versionSearchTimer) {
    clearTimeout(versionSearchTimer)
  }
  versionSearchTimer = setTimeout(() => {
    fetchAgentVersions(value)
  }, 200)
}

const handleVersionDropdown = (visible: boolean) => {
  if (visible && versionOptions.value.length === 0) {
    fetchAgentVersions()
  }
}

const handleAgentServerVersionSearch = (value: string) => {
  if (agentServerVersionSearchTimer) {
    clearTimeout(agentServerVersionSearchTimer)
  }
  agentServerVersionSearchTimer = setTimeout(() => {
    fetchAgentServerVersions(value)
  }, 200)
}

const handleAgentServerVersionDropdown = (visible: boolean) => {
  if (visible && agentServerVersionOptions.value.length === 0) {
    fetchAgentServerVersions()
  }
}

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

// 过滤后的Agent列表
const filteredAgents = computed(() => {
  const source = agents.value
  const predicates: Array<(agent: Agent) => boolean> = []

  if (statusFilters.online) {
    predicates.push(a => (a.computed_status || a.status) === 'online')
  }
  if (statusFilters.offline) {
    predicates.push(a => (a.computed_status || a.status) === 'offline')
  }
  if (statusFilters.pending) {
    predicates.push(a => a.status === 'pending')
  }
  if (statusFilters.disabled) {
    predicates.push(a => a.status === 'disabled')
  }
  if (statusFilters.outdated) {
    predicates.push(a => Boolean(a.is_version_outdated))
  }
  if (statusFilters.failed) {
    predicates.push(a => Boolean(a.last_error_code))
  }

  if (!predicates.length) {
    return source
  }

  return source.filter(agent => predicates.some(check => check(agent)))
})

const filteredAgentServers = computed(() => {
  return agentServerTable.value
})

// Agent 类型显示文本
const agentTypeMap: Record<string, string> = {
  agent: 'Agent',
  'agent-server': 'Agent-Server'
}

// 表格列配置
const agentRowActions = (row: any) => {
  const buttons = [
    h(NButton, { text: true, size: 'small', onClick: () => handleViewDetail(row.id) }, {
      icon: () => h(Eye, { size: 14 }),
      default: () => '详情',
    }),
  ]
  const st = row.computed_status || row.status
  if (st === 'pending') {
    buttons.push(h(NButton, { type: 'warning', size: 'small', onClick: () => handleRegenerateScript(row) }, {
      icon: () => h(Copy, { size: 14 }),
      default: () => '重新生成脚本',
    }))
  } else {
    buttons.push(h(NButton, { text: true, size: 'small', onClick: () => handleIssueToken(row) }, {
      icon: () => h(Lock, { size: 14 }),
      default: () => '发Token',
    }))
  }
  if (st === 'online' && row.is_version_outdated) {
    buttons.push(h(NButton, { type: 'warning', size: 'small', onClick: () => handleUpgradeAgent(row) }, {
      icon: () => h(ChevronUp, { size: 14 }),
      default: () => '升级',
    }))
  }
  if (st === 'online') {
    buttons.push(h(NButton, { text: true, size: 'small', onClick: () => handleRestartAgent(row) }, {
      icon: () => h(RefreshCw, { size: 14 }),
      default: () => '重启',
    }))
  }
  if (st !== 'disabled' && st !== 'pending') {
    buttons.push(h(NButton, { type: 'warning', size: 'small', onClick: () => handleDisable(row) }, {
      icon: () => h(CircleX, { size: 14 }),
      default: () => '禁用',
    }))
  }
  if (st === 'disabled') {
    buttons.push(h(NButton, { type: 'success', size: 'small', onClick: () => handleEnable(row) }, {
      icon: () => h(CircleCheck, { size: 14 }),
      default: () => '启用',
    }))
  }
  return buttons
}

const columns: DataTableColumns<any> = [
  {
    type: 'selection',
  },
  {
    title: '关联主机',
    key: 'host',
    width: 150,
    render: (row) =>
      h('div', { class: 'host-info' }, [
        h('div', { class: 'host-name' }, row.host.name),
        h('div', { class: 'host-ip' }, [
          h('span', { class: 'host-ip-label' }, 'IP'),
          h('span', { class: 'host-ip-value' }, row.host.ip_address),
        ]),
      ]),
  },
  {
    title: '类型',
    key: 'agent_type',
    width: 120,
    render: (row) =>
      h(NTag, { type: getAgentTypeColor(row.agent_type) as any, size: 'small' }, {
        default: () => agentTypeMap[row.agent_type || 'agent'] || (row.agent_type || '-'),
      }),
  },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) => {
      const st = row.computed_status || row.status
      return h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h(NTag, { type: getStatusColor(st) as any, size: 'small' }, {
            default: () => row.computed_status_display || row.status_display,
          }),
          getStatusHint(st)
            ? h(NTooltip, {}, {
                trigger: () => h(Info, { style: 'color: #d97706; cursor: help' }),
                default: () => getStatusHint(st),
              })
            : null,
        ],
      })
    },
  },
  {
    title: '版本',
    key: 'version',
    width: 120,
    render: (row) =>
      h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => [
          h('span', row.version || '-'),
          row.is_version_outdated && row.version
            ? h(NTooltip, {}, {
                trigger: () => h(NTag, { type: 'error', size: 'small' }, { default: () => '版本落后' }),
                default: () => getVersionTooltip(row),
              })
            : null,
        ],
      }),
  },
  {
    title: '最后心跳',
    key: 'last_heartbeat_at',
    width: 120,
    render: (row) => (row.last_heartbeat_at ? formatTime(row.last_heartbeat_at) : '-'),
  },
  {
    title: '任务统计',
    key: 'task_stats',
    width: 120,
    render: (row) => {
      if (row.task_stats && row.task_stats.total > 0) {
        return h(NTooltip, {}, {
          trigger: () =>
            h('div', { class: 'task-stats-cell' }, [
              h(NProgress, {
                type: 'circle',
                percentage: row.task_stats.success_rate,
                strokeColor: getSuccessRateColor(row.task_stats.success_rate),
                showIndicator: false,
              }),
              h('span', { class: 'task-stats-text' }, `${row.task_stats.success_rate?.toFixed(0) || 0}%`),
            ]),
          default: () => getTaskStatsTooltip(row.task_stats),
        })
      }
      return h('span', { class: 'text-gray' }, '-')
    },
  },
  {
    title: '错误码',
    key: 'last_error_code',
    width: 120,
    render: (row) => (row.last_error_code
      ? h(NTag, { type: 'error', size: 'small' }, { default: () => row.last_error_code })
      : h('span', { class: 'text-gray' }, '-')),
  },
  {
    title: '标签',
    key: 'tags',
    width: 180,
    render: (row) => {
      if (row.host?.tags && row.host.tags.length) {
        return h(NSpace, { wrap: true, size: 4 }, {
          default: () => row.host.tags.map((tag: any) =>
            h(NTag, { size: 'small' }, {
              default: () => (tag.key ? (tag.value ? `${tag.key}=${tag.value}` : tag.key) : tag),
            })),
        })
      }
      return h('span', { class: 'text-gray' }, '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 300,
    render: (row) =>
      h(NSpace, { size: 4, wrap: false, wrapItem: false, align: 'center' }, {
        default: () => agentRowActions(row),
      }),
  },
]

const agentServerColumns: DataTableColumns<any> = [
  { title: '名称', key: 'name', width: 180, render: (row) => row.name },
  { title: '地址', key: 'base_url', width: 240, render: (row) => row.base_url },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render: (row) =>
      h(NTag, { type: (row.is_active ? 'success' : 'default') as any, size: 'small' }, {
        default: () => (row.is_active ? '启用' : '停用'),
      }),
  },
  {
    title: '签名校验',
    key: 'require_signature',
    width: 120,
    render: (row) =>
      h(NTag, { type: (row.require_signature ? 'primary' : 'default') as any, size: 'small' }, {
        default: () => (row.require_signature ? '开启' : '关闭'),
      }),
  },
  {
    title: '密钥尾号',
    key: 'shared_secret_last4',
    width: 120,
    render: (row) => (row.shared_secret_last4 ? `****${row.shared_secret_last4}` : '-'),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render: (row) => (row.updated_at ? formatTime(row.updated_at) : '-'),
  },
  {
    title: '操作',
    key: 'agent_server_actions',
    width: 160,
    render: (row) =>
      h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { text: true, size: 'small', onClick: () => handleEditAgentServer(row) }, {
            icon: () => h(Pencil, { size: 14 }),
            default: () => '编辑',
          }),
          h(NButton, { text: true, size: 'small', onClick: () => copyText(row.base_url) }, {
            icon: () => h(Copy, { size: 14 }),
            default: () => '复制地址',
          }),
        ],
      }),
  },
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
    if (searchForm.last_error_code) params.last_error_code = searchForm.last_error_code
    if (searchForm.version) params.version = searchForm.version
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.agent_server_id) params.agent_server_id = searchForm.agent_server_id

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
    message.error(errorMsg)
    agents.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const fetchAgentServers = async () => {
  try {
    const response = await agentServerApi.getAgentServers({ page_size: 200, is_active: true })
    agentServers.value = response.results || []
    if (!searchForm.agent_server_id && agentServers.value.length === 1) {
      searchForm.agent_server_id = agentServers.value[0].id
    }
  } catch (error: any) {
    console.error('获取 Agent-Server 列表失败:', error)
    message.error(error?.message || '获取 Agent-Server 列表失败')
    agentServers.value = []
  }
}

const fetchAgentServerTable = async () => {
  agentServerTableLoading.value = true
  try {
    const params: any = { page_size: 200 }
    if (agentServerSearchForm.search) {
      params.search = agentServerSearchForm.search
    }
    if (agentServerSearchForm.version) {
      params.version = agentServerSearchForm.version
    }
    if (agentServerSearchForm.is_active !== undefined && agentServerSearchForm.is_active !== null) {
      params.is_active = agentServerSearchForm.is_active
    }
    if (agentServerSearchForm.require_signature !== undefined && agentServerSearchForm.require_signature !== null) {
      params.require_signature = agentServerSearchForm.require_signature
    }

    const response = await agentServerApi.getAgentServers(params)
    agentServerTable.value = response.results || []
  } catch (error: any) {
    console.error('获取 Agent-Server 列表失败:', error)
    message.error(error?.message || '获取 Agent-Server 列表失败')
    agentServerTable.value = []
  } finally {
    agentServerTableLoading.value = false
  }
}

watch(
  () => route.query,
  () => {
    const tab = resolveTabKey(route.query.tab)
    if (activeTab.value !== tab) {
      activeTab.value = tab
    }
    if (tab === 'agent') {
      initFromQuery()
      searchForm.quick_status = normalizeQuickStatusList(searchForm.quick_status || [])
      ensureErrorCodeOption(searchForm.last_error_code)
      ensureVersionOption(searchForm.version)
      fetchAgents()
    } else {
      initAgentServerFromQuery()
      ensureAgentServerVersionOption(agentServerSearchForm.version)
      fetchAgentServerTable()
    }
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

// 重置
const handleReset = () => {
  // 清除防抖定时器
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  searchForm.search = ''
  searchForm.status = ''
  searchForm.last_error_code = ''
  searchForm.version = ''
  searchForm.agent_server_id = undefined
  searchForm.quick_status = []
  statusFilters.online = false
  statusFilters.offline = false
  statusFilters.pending = false
  statusFilters.disabled = false
  statusFilters.outdated = false
  statusFilters.failed = false
  pagination.current = 1
  syncToQuery()
}

watch(activeTab, (tab) => {
  if (tab !== 'agent' && selectedAgentIds.value.length) {
    selectedAgentIds.value = []
  }
  syncTabToQuery(tab)
})

const handleAgentServerSearch = () => {
  syncAgentServerToQuery()
}

const handleAgentServerReset = () => {
  agentServerSearchForm.search = ''
  agentServerSearchForm.version = ''
  agentServerSearchForm.is_active = undefined
  agentServerSearchForm.require_signature = undefined
  syncAgentServerToQuery()
}

const resetAgentServerEditForm = () => {
  agentServerEditing.value = null
  agentServerEditForm.id = null
  agentServerEditForm.name = ''
  agentServerEditForm.base_url = ''
  agentServerEditForm.require_signature = false
  agentServerEditForm.shared_secret = ''
  agentServerEditForm.is_active = true
  agentServerEditForm.description = ''
}

const handleEditAgentServer = (record: AgentServer) => {
  agentServerEditing.value = record
  agentServerEditForm.id = record.id
  agentServerEditForm.name = record.name
  agentServerEditForm.base_url = record.base_url
  agentServerEditForm.require_signature = Boolean(record.require_signature)
  agentServerEditForm.shared_secret = ''
  agentServerEditForm.is_active = Boolean(record.is_active)
  agentServerEditForm.description = record.description || ''
  agentServerEditVisible.value = true
}

const handleAgentServerEditCancel = () => {
  agentServerEditVisible.value = false
  resetAgentServerEditForm()
}

const handleAgentServerEditConfirm = async () => {
  if (!agentServerEditForm.id) {
    message.error('缺少 Agent-Server ID')
    return
  }
  if (!agentServerEditForm.name.trim()) {
    message.error('请输入名称')
    return
  }
  if (!agentServerEditForm.base_url.trim()) {
    message.error('请输入基础地址(base_url)')
    return
  }
  if (agentServerEditForm.require_signature && !agentServerEditForm.shared_secret && !agentServerEditing.value?.has_secret) {
    message.error('启用签名校验必须提供 shared_secret')
    return
  }

  const payload: any = {
    name: agentServerEditForm.name.trim(),
    base_url: agentServerEditForm.base_url.trim(),
    require_signature: agentServerEditForm.require_signature,
    is_active: agentServerEditForm.is_active,
    description: agentServerEditForm.description?.trim() || ''
  }
  if (agentServerEditForm.shared_secret.trim()) {
    payload.shared_secret = agentServerEditForm.shared_secret.trim()
  }

  try {
    await agentServerApi.updateAgentServer(agentServerEditForm.id, payload)
    message.success('更新 Agent-Server 成功')
    agentServerEditVisible.value = false
    resetAgentServerEditForm()
    fetchAgentServerTable()
    fetchAgentServers()
  } catch (error: any) {
    message.error(error?.response?.data?.message || error?.message || '更新 Agent-Server 失败')
  }
}

// 状态过滤器处理
const toggleStatusFilter = (filterType: keyof typeof statusFilters) => {
  statusFilters[filterType] = !statusFilters[filterType]
  // 过滤器改变时重置分页
  pagination.current = 1
  updateQuickStatusFromFilters()
  syncToQuery()
}

const clearAllFilters = () => {
  statusFilters.online = false
  statusFilters.offline = false
  statusFilters.pending = false
  statusFilters.disabled = false
  statusFilters.outdated = false
  statusFilters.failed = false
  pagination.current = 1
  updateQuickStatusFromFilters()
  syncToQuery()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  syncToQuery()
}

const handlePageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  syncToQuery()
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
    message.warning('请先确认此操作')
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
    message.success('Token 签发成功')
    const issuedToken = result?.token || ''
    tokenModalVisible.value = false
    showIssuedTokenDialog(issuedToken)
    fetchAgents()
  } catch (error: any) {
    console.error('Token 签发失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || 'Token 签发失败'
    message.error(errorMsg)
  }
}

/** One-time token dialog with copy (蓝鲸式：签发后立即可复制) */
const showIssuedTokenDialog = (token: string) => {
  const tokenText = token || ''
  if (!tokenText) {
    message.warning('未返回 Token，请检查接口响应')
    return
  }
  dialog.create({
    title: 'Token 签发成功',
    content: () =>
      h('div', { style: 'display:flex;flex-direction:column;gap:12px;' }, [
        h(NAlert, { type: 'warning', bordered: false }, {
          default: () => '此 Token 仅显示一次，请立即复制并妥善保管。',
        }),
        h('div', { style: 'display:flex;gap:8px;align-items:flex-start;' }, [
          h(NInput, {
            value: tokenText,
            readonly: true,
            type: 'textarea',
            autosize: { minRows: 2, maxRows: 4 },
            style: 'flex:1;',
          }),
          h(
            NButton,
            {
              type: 'primary',
              onClick: () => copyText(tokenText),
            },
            {
              icon: () => h(Copy, { size: 14 }),
              default: () => '复制',
            },
          ),
        ]),
      ]),
    positiveText: '我已保存',
  })
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
  dialog.warning({
    title: '确认禁用',
    content: `确定要禁用 Agent (${agent.host.name}) 吗？`,
    positiveText: '确认禁用',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await agentsApi.disableAgent(agent.id, { confirmed: true })
        message.success('禁用成功')
        fetchAgents()
      } catch (error: any) {
        console.error('禁用失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '禁用失败'
        message.error(errorMsg)
      }
    }
  })
}

// 启用 Agent
const handleEnable = async (agent: Agent) => {
  try {
    await agentsApi.enableAgent(agent.id)
    message.success('启用成功')
    fetchAgents()
  } catch (error: any) {
    console.error('启用失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '启用失败'
    message.error(errorMsg)
  }
}

// 重启 Agent
const handleRestartAgent = (agent: Agent) => {
  dialog.warning({
    title: '确认重启',
    content: `确定要重启 Agent (${agent.host.name}) 吗？重启期间 Agent 将短暂离线。`,
    positiveText: '确认重启',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await agentsApi.controlAgent(agent.id, {
          action: 'restart',
          reason: '用户手动重启',
          agent_server_id: searchForm.agent_server_id || undefined
        })
        message.success('重启指令已下发，Agent 将在几秒内重启')
        // 延迟刷新，等待 Agent 重启完成
        setTimeout(() => fetchAgents(), 3000)
      } catch (error: any) {
        console.error('重启失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '重启失败'
        message.error(errorMsg)
      }
    }
  })
}

// 升级 Agent
const handleUpgradeAgent = (agent: Agent) => {
  dialog.warning({
    title: '确认升级',
    content: `确定要升级 Agent (${agent.host.name}) 吗？\n\n当前版本: ${agent.version}\n期望版本: ${agent.expected_min_version || '最新版本'}\n\n升级期间 Agent 将短暂离线。`,
    positiveText: '确认升级',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await agentsApi.upgradeAgent(agent.id, {
          target_version: agent.expected_min_version,
          confirmed: true,
          agent_server_id: searchForm.agent_server_id || undefined
        })
        message.success('升级指令已下发，Agent 将在几秒内完成升级')
        setTimeout(() => fetchAgents(), 5000)
      } catch (error: any) {
        console.error('升级失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '升级失败'
        message.error(errorMsg)
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

const filterAgentServerOption = (inputValue: string, option: any) => {
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
  installForm.host_ids = []
  installForm.install_type = 'agent'
  installForm.install_mode = 'agent-server'
  installForm.agent_server_url = ''
  installForm.ws_backoff_initial_ms = 1000
  installForm.ws_backoff_max_ms = 30000
  installForm.ws_max_retries = 6
  installForm.agent_server_listen_addr = '0.0.0.0:8080'
  installForm.agent_server_base_url = buildAgentServerBaseUrl(installForm.agent_server_listen_addr)
  installForm.max_connections = 1000
  installForm.heartbeat_timeout = 60
  installForm.ws_handshake_timeout = '10s'
  installForm.ws_read_buffer_size = 4096
  installForm.ws_write_buffer_size = 4096
  installForm.ws_enable_compression = true
  installForm.ws_allowed_origins = []
  installForm.auth_shared_secret = ''
  installForm.auth_require_signature = false
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
    message.error(error.message || '获取安装包列表失败')
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
  if (installForm.install_type === 'agent-server') {
    if (!installForm.agent_server_base_url) {
      installForm.agent_server_base_url = buildAgentServerBaseUrl(installForm.agent_server_listen_addr)
    }
  } else {
    installForm.agent_server_base_url = ''
  }
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
    message.error('获取主机列表失败')
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
    message.warning('请至少选择一个主机')
    return
  }
  if (installForm.install_type === 'agent' && !installForm.agent_server_url) {
    message.warning('安装 Agent 需要填写 Agent-Server 地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !installForm.agent_server_listen_addr) {
    message.warning('安装 Agent-Server 需要填写监听地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !resolveAgentServerBaseUrl()) {
    message.warning('安装 Agent-Server 需要填写控制面访问地址')
    return
  }
  if (
    installForm.install_type === 'agent-server' &&
    installForm.auth_require_signature &&
    !installForm.auth_shared_secret
  ) {
    message.warning('启用签名校验需要填写 shared_secret')
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
      params.agent_server_base_url = resolveAgentServerBaseUrl()
      params.max_connections = installForm.max_connections
      params.heartbeat_timeout = installForm.heartbeat_timeout
      // WebSocket 配置
      params.ws_handshake_timeout = installForm.ws_handshake_timeout
      params.ws_read_buffer_size = installForm.ws_read_buffer_size
      params.ws_write_buffer_size = installForm.ws_write_buffer_size
      params.ws_enable_compression = installForm.ws_enable_compression
      params.ws_allowed_origins = installForm.ws_allowed_origins
      params.auth_shared_secret = installForm.auth_shared_secret
      params.auth_require_signature = installForm.auth_require_signature
    }

    const response = await agentsApi.generateInstallScript(params)

    installScripts.value = response.scripts
    shouldRefreshAfterInstall.value = true
    
    // 显示提示信息
    if (response.notice) {
      message.warning(response.notice)
    }
    if (response.errors && response.errors.length > 0) {
      message.warning(`部分主机生成脚本失败: ${response.errors.join('; ')}`)
    }
    
    message.success('安装脚本生成成功')
  } catch (error: any) {
    console.error('生成安装脚本失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '生成安装脚本失败'
    message.error(errorMsg)
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
    message.warning('请至少选择一个主机')
    return
  }
  if (installForm.install_type === 'agent' && !installForm.agent_server_url) {
    message.warning('安装 Agent 需要填写 Agent-Server 地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !installForm.agent_server_listen_addr) {
    message.warning('安装 Agent-Server 需要填写监听地址')
    return
  }
  if (installForm.install_type === 'agent-server' && !resolveAgentServerBaseUrl()) {
    message.warning('安装 Agent-Server 需要填写控制面访问地址')
    return
  }
  if (
    installForm.install_type === 'agent-server' &&
    installForm.auth_require_signature &&
    !installForm.auth_shared_secret
  ) {
    message.warning('启用签名校验需要填写 shared_secret')
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
    dialog.warning({
      title: `确认覆盖安装${installTarget}`,
      content: `${hostsToReinstall.length} 台主机已安装${installTarget}，确定要覆盖安装吗？此操作将停止现有服务并重新安装。`,
      onPositiveClick: () => {
        performInstall(true) // allow_reinstall = true
      }
    })
  } else {
    // 没有需要覆盖的Agent，直接安装
    dialog.warning({
      title: `确认批量安装${installTarget}`,
      content: `确定要在 ${installForm.host_ids.length} 台主机上安装 ${installTarget} 吗？`,
      onPositiveClick: () => {
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
      params.agent_server_base_url = resolveAgentServerBaseUrl()
      params.max_connections = installForm.max_connections
      params.heartbeat_timeout = installForm.heartbeat_timeout
      // WebSocket 配置
      params.ws_handshake_timeout = installForm.ws_handshake_timeout
      params.ws_read_buffer_size = installForm.ws_read_buffer_size
      params.ws_write_buffer_size = installForm.ws_write_buffer_size
      params.ws_enable_compression = installForm.ws_enable_compression
      params.ws_allowed_origins = installForm.ws_allowed_origins
      params.auth_shared_secret = installForm.auth_shared_secret
      params.auth_require_signature = installForm.auth_require_signature
    }

    const response = await agentsApi.batchInstall(params)

    // 如果有 install_task_id，连接sse查看实时进度
    if (response.install_task_id) {
      connectInstallProgressSSE(response.install_task_id)
      message.info('安装已启动，正在查看实时进度...')
    } else {
      // 如果没有sse，显示最终结果
      message.success(
        `批量安装完成：成功 ${response.success_count} 个，失败 ${response.failed_count} 个`
      )

      // 显示详细结果
      if (response.failed_count > 0) {
        const failedHosts = response.results
          .filter((r: any) => !r.success)
          .map((r: any) => `${r.host_name}: ${r.message}`)
          .join('\n')
        dialog.warning({
          title: '部分主机安装失败',
          content: failedHosts,
          style: { width: '600px' },
        })
      }

      // 刷新列表
      installModalVisible.value = false
      fetchAgents()
    }
  } catch (error: any) {
    console.error('批量安装失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '批量安装失败'
    message.error(errorMsg)
  } finally {
    installing.value = false
  }
}

// 复制脚本
const copyScript = (script: string) => {
  navigator.clipboard.writeText(script).then(() => {
    message.success('脚本已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败，请手动复制')
  })
}

// 复制文本
const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败')
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
  selectedAgentIds.value = rowKeys.map((key) => Number(key)).filter((key) => !Number.isNaN(key))
}

// 蓝鲸节点管理式：勾选 Agent 后批量重装（预填安装抽屉，允许覆盖）
const handleBatchReinstall = () => {
  if (selectedAgentIds.value.length === 0) {
    message.warning('请先勾选要重装的 Agent')
    return
  }
  const selected = agents.value.filter((agent: any) => selectedAgentIds.value.includes(agent.id))
  const hostIds = selected
    .map((agent: any) => agent.host?.id)
    .filter((id: any) => id !== undefined && id !== null)

  if (hostIds.length === 0) {
    message.warning('所选 Agent 缺少关联主机，无法重装')
    return
  }

  dialog.warning({
    title: '确认批量重装',
    content: `将对 ${hostIds.length} 台关联主机执行 Agent 重装（覆盖安装）。请在安装抽屉中确认 Agent-Server 地址与安装包版本后，点击「批量安装（SSH）」。`,
    positiveText: '继续',
    negativeText: '取消',
    onPositiveClick: () => {
      installForm.install_type = 'agent'
      installForm.host_ids = [...new Set(hostIds)] as number[]
      activeTab.value = 'agent'
      installModalVisible.value = true
      fetchAvailableHosts()
      fetchAvailablePackages()
      message.info('已预填所选主机，请确认参数后执行批量安装')
    },
  })
}

// 查看安装脚本（用于 pending 状态的 Agent）
const handleRegenerateScript = async (agent: any) => {
  try {
    dialog.warning({
      title: '重新生成安装脚本',
      content: '将为该 Agent 签发新 token 并生成新的安装脚本，旧 token 将失效，确认继续？',
      positiveText: '重新生成',
      async onPositiveClick() {
        try {
          const response = await agentsApi.regenerateScript(agent.id)
          installScripts.value = response.scripts
          installModalVisible.value = true

          if (response.notice) {
            message.warning(response.notice)
          }
          message.success('已重新生成安装脚本并签发新 token')
        } catch (error: any) {
          console.error('获取安装脚本失败:', error)
          const errorMsg = error?.response?.data?.message || error?.message || '获取安装脚本失败'
          message.error(errorMsg)
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
    message.warning('请至少选择一个 Agent')
    return
  }
  
  const pendingAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && (a.computed_status || a.status) === 'pending'
  )
  
  if (pendingAgents.length === 0) {
    message.warning('选中的 Agent 中没有待激活状态的 Agent')
    return
  }
  
  dialog.warning({
    title: '确认批量重新生成脚本',
    content: `将为 ${pendingAgents.length} 个待激活的 Agent 签发新 token 并重新生成安装脚本，旧 token 将失效，确认继续？`,
    onPositiveClick: async () => {
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
          message.success(`成功为 ${successCount} 个 Agent 重新生成脚本${failCount > 0 ? `，${failCount} 个失败` : ''}`)
        } else {
          message.error('批量生成脚本失败')
        }
      } catch (error: any) {
        console.error('批量生成脚本失败:', error)
        message.error('批量生成脚本失败')
      }
    }
  })
}

// 批量删除待激活的 Agent
// 批量禁用 Agent
const handleBatchDisable = async () => {
  if (selectedAgentIds.value.length === 0) {
    message.warning('请先选择要禁用的 Agent')
    return
  }

  const disableableAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    ((a.computed_status || a.status) !== 'disabled') && 
    ((a.computed_status || a.status) !== 'pending')
  )

  if (disableableAgents.length === 0) {
    message.warning('选中的 Agent 中没有可禁用的（只有非 pending 且非 disabled 状态的 Agent 可以禁用）')
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
    message.warning('生产环境批量操作最多支持 10 个 Agent')
    return
  }

  try {
    dialog.warning({
      title: '确认批量禁用',
      content: `确定要禁用选中的 ${disableableAgents.length} 个 Agent 吗？禁用后这些 Agent 将不再接收新任务。`,
      onPositiveClick: async () => {
        try {
          const result = await agentsApi.batchDisable({
            agent_ids: disableableAgents.map(a => a.id),
            confirmed: true
          })
          message.success(`批量禁用成功，共 ${result.count} 个 Agent`)
          selectedAgentIds.value = []
          fetchAgents()
        } catch (error: any) {
          console.error('批量禁用失败:', error)
          message.error(error?.message || '批量禁用失败')
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
    message.warning('请先选择要启用的 Agent')
    return
  }

  const enableableAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && 
    (a.computed_status || a.status) === 'disabled'
  )

  if (enableableAgents.length === 0) {
    message.warning('选中的 Agent 中没有可启用的（只有 disabled 状态的 Agent 可以启用）')
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
    message.warning('生产环境批量操作最多支持 10 个 Agent')
    return
  }

  try {
    dialog.warning({
      title: '确认批量启用',
      content: `确定要启用选中的 ${enableableAgents.length} 个 Agent 吗？启用后这些 Agent 将恢复接收新任务。`,
      onPositiveClick: async () => {
        try {
          const result = await agentsApi.batchEnable({
            agent_ids: enableableAgents.map(a => a.id),
            confirmed: true
          })
          message.success(`批量启用成功，共 ${result.count} 个 Agent`)
          selectedAgentIds.value = []
          fetchAgents()
        } catch (error: any) {
          console.error('批量启用失败:', error)
          message.error(error?.message || '批量启用失败')
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
    message.warning('请先选择要重启的 Agent')
    return
  }
  if (!selectedAgentServerId.value) {
    message.warning('请先选择 Agent-Server')
    return
  }

  try {
    dialog.warning({
      title: '确认批量重启',
      content: `确定要重启选中的 ${selectedAgentIds.value.length} 个 Agent 吗？重启期间这些 Agent 将短暂离线。`,
      onPositiveClick: async () => {
        try {
          const result = await agentsApi.batchRestart({
            agent_ids: selectedAgentIds.value,
            confirmed: true,
            agent_server_id: selectedAgentServerId.value
          })

          // 如果有 batch_task_id，连接 SSE 查看实时进度
          if (result.batch_task_id) {
            connectBatchOperationSSE(result.batch_task_id, '重启')
            message.info('重启已启动，正在查看实时进度...')
          } else {
            // 如果没有 SSE，显示最终结果
            message.success(`批量重启已启动`)
            selectedAgentIds.value = []
            fetchAgents()
          }
        } catch (error: any) {
          console.error('批量重启失败:', error)
          message.error(error?.message || '批量重启失败')
        }
      }
    })
  } catch (error) {
    // 用户取消
  }
}

const handleBatchUpdateAgentServer = () => {
  if (selectedAgentIds.value.length === 0) {
    message.warning('请先选择要更新的 Agent')
    return
  }
  batchUpdateAgentServerForm.agent_server_id = selectedAgentServerId.value ?? null
  batchUpdateAgentServerVisible.value = true
}

const handleBatchUpdateAgentServerCancel = () => {
  batchUpdateAgentServerVisible.value = false
  batchUpdateAgentServerForm.agent_server_id = null
}

const handleBatchUpdateAgentServerConfirm = async () => {
  if (selectedAgentIds.value.length === 0) {
    message.warning('请先选择要更新的 Agent')
    return
  }

  try {
    const result = await agentsApi.batchUpdateAgentServer({
      agent_ids: selectedAgentIds.value,
      agent_server_id: batchUpdateAgentServerForm.agent_server_id,
      confirmed: true
    })
    message.success(`批量更新完成：成功 ${result.success_count} 个，失败 ${result.failed_count} 个`)
    batchUpdateAgentServerVisible.value = false
    batchUpdateAgentServerForm.agent_server_id = null
    selectedAgentIds.value = []
    fetchAgents()
  } catch (error: any) {
    console.error('批量更新 Agent-Server 失败:', error)
    const errorMsg = error?.response?.data?.message || error?.message || '批量更新 Agent-Server 失败'
    message.error(errorMsg)
  }
}

const handleBatchDeletePending = async () => {
  if (selectedAgentIds.value.length === 0) {
    message.warning('请至少选择一个 Agent')
    return
  }
  
  const pendingAgents = agents.value.filter(a => 
    selectedAgentIds.value.includes(a.id) && (a.computed_status || a.status) === 'pending'
  )
  
  if (pendingAgents.length === 0) {
    message.warning('选中的 Agent 中没有待激活状态的 Agent')
    return
  }
  
  dialog.warning({
    title: '确认批量删除',
    content: `确定要删除 ${pendingAgents.length} 个待激活的 Agent 吗？此操作不可恢复！`,
    positiveText: '确认删除',
    positiveButtonProps: { type: 'error' },
    onPositiveClick: async () => {
      try {
        const agentIds = pendingAgents.map(a => a.id)
        const response = await agentsApi.batchDelete({
          agent_ids: agentIds,
          confirmed: true
        })
        
        message.success(`成功删除 ${response.count} 个 Agent`)
        selectedAgentIds.value = []
        fetchAgents()
      } catch (error: any) {
        console.error('批量删除失败:', error)
        const errorMsg = error?.response?.data?.message || error?.message || '批量删除失败'
        message.error(errorMsg)
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
  fetchAgentServers()
  fetchAgentServerTable()
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
  if (errorCodeSearchTimer) {
    clearTimeout(errorCodeSearchTimer)
    errorCodeSearchTimer = null
  }
  if (versionSearchTimer) {
    clearTimeout(versionSearchTimer)
    versionSearchTimer = null
  }
  if (agentServerVersionSearchTimer) {
    clearTimeout(agentServerVersionSearchTimer)
    agentServerVersionSearchTimer = null
  }
})

const batchActionOptions = computed<any[]>(() => [
  { label: `批量重装 (${selectedAgentIds.value.length})`, key: 'reinstall', disabled: selectedAgentIds.value.length === 0 },
  { label: `重新生成脚本 (${selectedAgentIds.value.length})`, key: 'regen', disabled: selectedAgentIds.value.length === 0 },
  { label: `编辑 Agent-Server (${selectedAgentIds.value.length})`, key: 'updateServer', disabled: selectedAgentIds.value.length === 0 },
  { type: 'divider', key: 'd0' },
  { label: `启用 (${selectedEnableableCount.value})`, key: 'enable', disabled: !hasEnableableAgents.value },
  { label: `禁用 (${selectedDisableableCount.value})`, key: 'disable', disabled: !hasDisableableAgents.value },
  { label: `重启 (${selectedAgentIds.value.length})`, key: 'restart', disabled: selectedAgentIds.value.length === 0 },
  { type: 'divider', key: 'd1' },
  { label: `删除待激活 (${selectedPendingCount.value})`, key: 'deletePending', disabled: !hasPendingAgents.value, props: { class: 'danger' } },
  { label: `卸载 (${selectedAgentIds.value.length})`, key: 'uninstall', disabled: selectedAgentIds.value.length === 0, props: { class: 'danger' } },
])

const onBatchAction = (key: string) => {
  if (key === 'reinstall') handleBatchReinstall()
  if (key === 'regen') handleBatchRegenerateScript()
  if (key === 'updateServer') handleBatchUpdateAgentServer()
  if (key === 'enable') handleBatchEnable()
  if (key === 'disable') handleBatchDisable()
  if (key === 'restart') handleBatchRestart()
  if (key === 'deletePending') handleBatchDeletePending()
  if (key === 'uninstall') handleUninstallAgent()
}

const tablePagination = computed(() => ({
  page: pagination.current,
  pageSize: pagination.pageSize,
  itemCount: pagination.total,
  onChange: (page: number) => handlePageChange(page),
  onUpdatePageSize: (size: number) => handlePageSizeChange(size),
}))
</script>

<style scoped>
.agents-page {
  padding: 0;
}

.agent-tabs {
  margin: 0 0 16px 0;
}

.agent-tabs :deep(.arco-tabs-nav) {
  margin: 0 0 12px 0;
  padding: 0 24px;
}

.agent-tabs :deep(.arco-tabs-content) {
  padding-top: 0;
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

.agent-tabs {
  margin: 0 0 16px 0;
}

.agent-tabs :deep(.arco-tabs-nav) {
  margin: 0;
  padding: 0 24px;
}

.agent-tabs :deep(.arco-tabs-content) {
  padding-top: 12px;
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
  overflow: visible;
  padding-bottom: 20px;
  box-sizing: border-box;
}

.table-container :deep(.n-data-table-th) {
  background: #fafafa;
  font-weight: 600;
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
  color: var(--app-fg);
}

.host-ip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--app-muted);
  font-family: 'Courier New', monospace;
}

.host-ip-label {
  font-size: 11px;
  color: #86909c;
  background: #f2f3f5;
  padding: 0 4px;
  border-radius: 2px;
}

.host-ip-value {
  color: var(--app-fg-secondary);
}

.text-gray {
  color: var(--app-muted);
}

/* 任务统计单元格 */
.task-stats-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  
  .task-stats-text {
    font-size: 12px;
    font-weight: 500;
    color: var(--app-fg-secondary);
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
    background-color: #fff !important;
  }

  .arco-table-th.arco-table-col-fixed-right,
  .arco-table-td.arco-table-col-fixed-right,
  .arco-table-col-fixed-right .arco-table-td,
  .arco-table-col-fixed-right .arco-table-th,
  .arco-table-col-fixed-right .arco-table-cell {
    background-color: #fff !important;
  }

  .arco-table-col-fixed-right::before {
    background-color: transparent !important;
    box-shadow: none !important;
  }

  /* 操作列按钮间距 */
  .arco-space-item {
    margin-right: 8px;
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
  color: var(--app-fg-secondary);
  margin: 0;
}

.filter-stats {
  width: 100%;
  flex-basis: 100%;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}

.stats-text {
  font-size: 13px;
  color: var(--app-muted);
  font-weight: 500;
}

:deep(.dropdown-divider) {
  margin: 4px 0;
}

:deep(.arco-dropdown-option.danger-option),
:deep(.danger-option) {
  color: #f53f3f;
}

:deep(.arco-dropdown-option.danger-option:hover),
:deep(.danger-option:hover) {
  background-color: #fff1f0;
  color: #f53f3f;
}

:deep(.arco-dropdown-option:hover .danger-text) {
  color: #f53f3f;
}

:deep(.danger-text) {
  color: inherit;
}

:deep(.arco-dropdown-option.danger-option.arco-dropdown-option-disabled),
:deep(.danger-option.arco-dropdown-option-disabled) {
  color: #fcbfbe;
}

:deep(.danger-option .arco-dropdown-option-content) {
  color: inherit;
}

.form-item-stack {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  width: 100%;
}

.form-inline-action {
  align-self: flex-start;
}

.form-help {
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.4;
}

.switch-with-help {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 28px;
}

.switch-with-help .form-help {
  margin: 0;
}
</style>
