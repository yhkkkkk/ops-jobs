<template>
  <div 
    class="execution-detail-container"
    v-page-permissions="{ 
      resourceType: 'executionrecord', 
      permissions: ['view', 'execute'],
      resourceIds: executionInfo?.id ? [executionInfo.id] : []
    }"
  >
    <!-- 基本信息 -->
    <a-card class="info-card" title="执行信息">
      <template #extra>
        <a-space>
          <a-button @click="goBack">
            <template #icon><icon-arrow-left /></template>
            返回
          </a-button>
          <a-button
            v-if="executionInfo.execution_type === 'job_workflow' && executionInfo.related_object_info?.type === 'executionplan'"
            type="outline"
            @click="goPlanDetail(executionInfo.related_object_info.id)"
          >
            查看执行方案
          </a-button>
          <a-button
            v-if="executionInfo.status === 'failed'"
            type="primary"
            v-permission="{ resourceType: 'executionrecord', permission: 'execute', resourceId: executionInfo.id }"
            @click="handleRetry"
          >
            <template #icon><icon-refresh /></template>
            重试
          </a-button>
          <a-button
            v-if="executionInfo.status === 'success' || executionInfo.status === 'cancelled'"
            type="primary"
            v-permission="{ resourceType: 'executionrecord', permission: 'execute', resourceId: executionInfo.id }"
            @click="handleRetry"
          >
            <template #icon><icon-refresh /></template>
            重做
          </a-button>
          <a-button
            v-if="executionInfo.status === 'running'"
            status="danger"
            v-permission="{ resourceType: 'executionrecord', permission: 'execute', resourceId: executionInfo.id }"
            @click="handleCancel"
          >
            <template #icon><icon-close /></template>
            取消执行
          </a-button>
        </a-space>
      </template>
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="执行名称">
          {{ displayName || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="执行ID">
          <a-typography-text copyable>{{ executionInfo.execution_id || '-' }}</a-typography-text>
        </a-descriptions-item>
        <a-descriptions-item label="执行类型">
          <a-tag :color="getExecutionTypeColor(executionInfo.execution_type)">
            {{ getExecutionTypeText(executionInfo.execution_type) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行状态">
          <a-tag :color="getStatusColor(executionInfo.status)">
            <template #icon>
              <component :is="getStatusIcon(executionInfo.status)" />
            </template>
            {{ getStatusText(executionInfo.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行用户">
          {{ executionInfo.executed_by_name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="创建时间">
          {{ formatDateTime(executionInfo.created_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="开始时间">
          {{ formatDateTime(executionInfo.started_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="结束时间">
          {{ formatDateTime(executionInfo.finished_at) }}
        </a-descriptions-item>
        <a-descriptions-item label="执行时长">
          <span v-if="executionInfo.started_at && executionInfo.finished_at">
            {{ formatDuration(executionInfo.started_at, executionInfo.finished_at) }}
          </span>
          <span v-else-if="executionInfo.started_at">
            {{ formatDuration(executionInfo.started_at, new Date()) }}
          </span>
          <span v-else>-</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- 实时日志 -->
    <a-card v-if="executionInfo.is_running && executionId" class="realtime-card" title="实时日志">
      <RealtimeLog :execution-id="executionId" :auto-connect="true" />
    </a-card>

    <!-- 执行日志 -->
    <a-card v-if="!executionInfo.is_running" class="logs-card" title="执行流程">
      <template #extra>
        <a-space>
          <a-button
            v-if="executionInfo.execution_type === 'job_workflow' && executionInfo.execution_parameters"
            size="small"
            type="outline"
            status="primary"
            @click="openGlobalVarDrawer"
          >
            <IconSettings /> 全局变量
          </a-button>
          <a-button size="small" type="outline" status="primary" @click="openOperationDrawer">
            <template #icon><IconEye /></template>
            查看操作记录
          </a-button>
          <a-button size="small" type="outline" @click="openChainDrawer">
            <template #icon><IconLink /></template>
            链路视图
          </a-button>
          <a-button size="small" @click="refreshLogs">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
        </a-space>
      </template>

      <div v-if="loading" class="loading-container">
        <a-spin size="large" />
      </div>

      <div v-else-if="(!stepLogs || Object.keys(stepLogs).length === 0) && (!hostLogs || Object.keys(hostLogs).length === 0)" class="empty-logs">
        <a-empty :description="getEmptyLogsDescription()" />
      </div>

      <div v-else class="execution-flow-layout" :class="{ 'has-selected-step': selectedStepId }">
        <!-- 流程头部 -->
            <div class="timeline-header">
          <h4>步骤进度</h4>
              <div class="timeline-progress">
                <span class="progress-text">
                  已完成 {{ completedStepsCount }} / {{ sortedSteps.length }} 步骤
                </span>
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    :style="{ width: `${progressPercentage}%` }"
                  ></div>
                </div>
              </div>
            </div>

        <!-- 主容器：单栏或双栏布局 -->
        <div class="execution-flow-container">
          <!-- 左侧：时间线（始终显示） -->
          <div class="timeline-sidebar" :class="{ 'collapsed': selectedStepId }">
            <div class="vertical-timeline" ref="timelineRef">
                <div
                  v-for="(step, index) in sortedSteps"
                  :key="step.id"
                class="timeline-step-item"
              >
                <!-- 时间线连接线 -->
                <div
                  v-if="index < sortedSteps.length - 1"
                  class="timeline-connector"
                  :class="getConnectorClass(step.status, sortedSteps[index + 1]?.status)"
                ></div>

                <!-- 步骤节点 -->
                <div class="timeline-step-node">
                  <!-- 左侧时间线圆点 -->
                  <div class="timeline-dot" :class="`dot-${step.status}`">
                    <div class="dot-inner">
                      <span class="step-number">{{ step.step_order }}</span>
                    </div>
                  </div>

                  <!-- 右侧步骤卡片 -->
                  <div
                    class="timeline-step-card"
                    :class="{
                      'step-active': selectedStepKey === String(step.id),
                      [`step-${step.status}`]: true
                    }"
                    @click="selectStep(step.id)"
                  >
                    <div class="step-card-content">
                      <div class="step-title-row">
                        <h5 class="step-title">{{ step.step_name }}</h5>
                        <a-tag
                          :color="getStepStatusColor(step.status)"
                          size="small"
                          class="step-status-tag"
                        >
                          {{ getStepStatusText(step.status) }}
                        </a-tag>
                      </div>
                      <div class="step-meta-row">
                        <span class="step-hosts">
                          <icon-user /> {{ getTotalHostCountInStep(step.id) }} 台主机
                        </span>
                        <span v-if="step.finished_at || step.end_time" class="step-duration">
                        耗时: {{ formatDuration(step.started_at || step.start_time, step.finished_at || step.end_time) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧：日志详情面板（仅当选中步骤时显示） -->
          <div v-if="selectedStepKey && stepLogs[selectedStepKey]" class="logs-detail-panel">
            <div class="step-detail-content">
              <!-- 步骤信息头部 -->
              <div class="step-detail-header">
                <div class="step-detail-info">
                  <h3>{{ stepLogs[selectedStepKey].step_name }}</h3>
                  <div class="step-detail-meta">
                    <a-tag :color="getStepStatusColor(stepLogs[selectedStepKey].status)">
                      {{ getStepStatusText(stepLogs[selectedStepKey].status) }}
                    </a-tag>
                    <span class="step-order-text">步骤 {{ stepLogs[selectedStepKey].step_order }}</span>
                  </div>
                </div>
                <div class="step-detail-actions">
                  <a-space>
                    <a-dropdown
                      v-if="canRetryStep(stepLogs[selectedStepKey])"
                      trigger="click"
                    >
                      <a-button size="small">
                        <IconRefresh /> 步骤操作 <IconDown />
                      </a-button>
                      <template #content>
                        <a-doption
                          :class="{ 'disabled-option': !canExecuteStep(executionInfo.id) }"
                          @click.stop="() => handleClickStepRetry('failed_only', selectedStepKey)"
                        >
                          <IconExclamation /> 仅重试失败主机
                        </a-doption>
                        <a-doption
                          :class="{ 'disabled-option': !canExecuteStep(executionInfo.id) }"
                          @click.stop="() => handleClickStepRetry('all', selectedStepKey)"
                        >
                          <IconRefresh /> 重试该步骤
                        </a-doption>
                        <a-doption
                          :class="{ 'disabled-option': !canExecuteStep(executionInfo.id) }"
                          @click.stop="() => handleClickStepIgnoreError(selectedStepKey)"
                        >
                          <IconCheck /> 忽略错误继续
                        </a-doption>
                      </template>
                    </a-dropdown>

                    <a-dropdown trigger="click">
                      <a-button size="small">
                        批量复制 <IconDown />
                      </a-button>
                      <template #content>
                        <a-doption @click.stop="() => copyHostsByStatusInStep(selectedStepKey, 'success')">
                          <IconCopy /> 复制成功主机IP
                        </a-doption>
                        <a-doption @click.stop="() => copyHostsByStatusInStep(selectedStepKey, 'failed')">
                          <IconCopy /> 复制失败主机IP
                        </a-doption>
                        <a-doption @click.stop="() => copyHostsByStatusInStep(selectedStepKey, 'running')">
                          <IconCopy /> 复制运行中主机IP
                        </a-doption>
                        <a-doption @click.stop="() => copyHostsByStatusInStep(selectedStepKey, 'pending')">
                          <IconCopy /> 复制等待中主机IP
                        </a-doption>
                        <a-doption @click.stop="() => copyHostsByStatusInStep(selectedStepKey, 'all')">
                          <IconCopy /> 复制所有主机IP
                        </a-doption>
                      </template>
                    </a-dropdown>

                    <a-button size="small" type="secondary" @click="openStepContentDrawer(selectedStepKey)">
                      <IconEye /> 查看步骤内容
                    </a-button>
                    <a-button size="small" type="secondary" @click="exportStepLogs(selectedStepKey)">
                      <IconDownload /> 导出步骤日志
                    </a-button>
                  </a-space>
                </div>
              </div>
              <!-- 主机列表概览 -->
              <div class="host-overview">
                <div class="host-overview-header">
                  <h4>主机概览</h4>
                  <span class="host-total">共 {{ getTotalHostCountInStep(selectedStepKey) }} 台主机</span>
                </div>
                <div class="host-status-summary">
                  <div class="status-summary-item success">
                    <icon-check-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepKey, 'success') }}</span>
                    <span class="status-label">成功</span>
                  </div>
                  <div class="status-summary-item failed">
                    <icon-close-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepKey, 'failed') }}</span>
                    <span class="status-label">失败</span>
                  </div>
                  <div class="status-summary-item running">
                    <icon-clock-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepKey, 'running') }}</span>
                    <span class="status-label">执行中</span>
                  </div>
                  <div class="status-summary-item pending">
                    <icon-minus-circle />
                    <span class="status-count">{{ getHostCountByStatusInStep(selectedStepKey, 'pending') }}</span>
                    <span class="status-label">等待中</span>
                  </div>
                </div>
              </div>

                <!-- 搜索栏 -->
                <div class="search-bar">
                  <a-space>
                    <a-input-search
                      :value="hostSearchTexts[selectedStepKey] || ''"
                      placeholder="搜索主机名称或IP"
                      size="small"
                      style="width: 200px;"
                      @change="(value) => updateSearchText(selectedStepKey, value)"
                      @search="(value) => updateSearchText(selectedStepKey, value)"
                      @update:value="(value) => updateSearchText(selectedStepKey, value)"
                      allow-clear
                    />
                    <a-input-search
                      :value="logSearchTexts[selectedStepKey] || ''"
                      placeholder="搜索日志内容"
                      size="small"
                      style="width: 200px;"
                      @change="(value) => updateLogSearchText(selectedStepKey, value)"
                      @search="(value) => updateLogSearchText(selectedStepKey, value)"
                      @update:value="(value) => updateLogSearchText(selectedStepKey, value)"
                      allow-clear
                    />
                  </a-space>
              </div>

              <!-- 主机分组显示 -->
              <div class="host-groups-container">
                <div
                  v-for="(group, status) in stepHostGroups[selectedStepKey]"
                  :key="status"
                  class="host-group"
                  v-show="group.hosts.length > 0"
                >
                  <div class="host-group-header" @click="toggleGroupInStep(selectedStepKey, String(status))">
                    <div class="group-info">
                      <a-tag
                        :color="getHostStatusColor(String(status))"
                        class="group-status-tag"
                      >
                        {{ getHostStatusText(String(status)) }}
                      </a-tag>
                      <span class="group-count">{{ group.hosts.length }}台主机</span>
                      <!-- 失败主机分组显示选中数量和批量重试按钮 -->
                      <template v-if="String(status) === 'failed' && group.expanded">
                        <span class="selected-count" v-if="getSelectedFailedHostIds(selectedStepKey).length > 0">
                          已选中 {{ getSelectedFailedHostIds(selectedStepKey).length }} 台
                        </span>
                        <a-button
                          v-if="getSelectedFailedHostIds(selectedStepKey).length > 0"
                          size="small"
                          type="primary"
                          status="warning"
                          @click.stop="handleBatchRetrySelectedHosts(selectedStepKey)"
                          :loading="batchRetrying[selectedStepKey]"
                        >
                          <template #icon><IconRefresh /></template>
                          批量重试选中主机
                        </a-button>
                      </template>
                    </div>
                    <div class="group-actions">
                      <a-button
                        size="small"
                        type="text"
                        @click.stop="copyHostsByStatusInStep(selectedStepKey, String(status))"
                        title="复制该状态下的所有主机IP"
                      >
                        <template #icon><IconCopy /></template>
                        复制IP
                      </a-button>
                      <a-button
                        size="small"
                        type="text"
                        @click.stop="toggleGroupInStep(selectedStepKey, String(status))"
                        title="展开/收起分组"
                      >
                      <IconDown
                        :class="{ 'rotate-180': group.expanded }"
                        class="expand-icon"
                      />
                      </a-button>
                    </div>
                  </div>

                  <div v-show="group.expanded" class="host-group-content">
                    <div v-if="group.hosts.length === 0" class="no-hosts">
                      <a-empty description="该状态下暂无主机" />
                    </div>
                    <!-- 失败主机分组：显示复选框列表 -->
                    <div v-else-if="String(status) === 'failed'" class="failed-hosts-list">
                      <div class="failed-hosts-header">
                        <a-checkbox
                          :model-value="isAllFailedHostsSelected(selectedStepKey)"
                          :indeterminate="isIndeterminateFailedHosts(selectedStepKey)"
                          @change="handleToggleAllFailedHosts(selectedStepKey, $event)"
                        >
                          全选
                        </a-checkbox>
                        <span class="selected-info">
                          已选中 {{ getSelectedFailedHostIds(selectedStepKey).length }} / {{ group.hosts.length }} 台主机
                        </span>
                      </div>
                      <div class="failed-hosts-checkboxes">
                        <a-checkbox-group
                          :model-value="selectedFailedHostIds[selectedStepKey] || []"
                          @change="(values) => handleFailedHostSelectionChange(selectedStepKey, values)"
                        >
                          <div
                            v-for="hostLog in group.hosts"
                            :key="hostLog.host_id"
                            class="failed-host-item"
                          >
                            <a-checkbox :value="hostLog.host_id">
                              {{ getHostDisplayName(hostLog) }}
                            </a-checkbox>
                          </div>
                        </a-checkbox-group>
                      </div>
                    </div>
                    <!-- 其他状态的主机：使用标签页显示 -->
                    <a-tabs
                      v-else
                      v-model:active-key="selectedHostIds[selectedStepKey]"
                      type="card"
                      size="small"
                      class="host-tabs"
                      :tab-position="'top'"
                      :scrollable="true"
                    >
                      <a-tab-pane
                        v-for="hostLog in group.hosts"
                        :key="hostLog.host_id"
                        :class="`host-tab-${hostLog.status}`"
                      >
                        <template #title>
                          <div class="host-tab-title">
                            <div class="host-name">{{ getHostDisplayName(hostLog) }}</div>
                          </div>
                        </template>

                  <!-- 主机日志内容 -->
                  <div class="host-log-content">
                    <!-- 主机信息头部 -->
                    <div class="host-info-header">
                      <div class="host-info">
                        <h5>{{ getHostDisplayName(hostLog) }}</h5>
                        <a-space>
                          <a-tag :color="getHostStatusColor(hostLog.status)">
                            {{ getHostStatusText(hostLog.status) }}
                          </a-tag>
                          <a-tag
                            v-if="executionMode === 'agent'"
                            color="blue"
                            size="small"
                          >
                            Agent 模式
                          </a-tag>
                          <a-tag
                            v-else-if="executionMode === 'ssh'"
                            color="gray"
                            size="small"
                          >
                            SSH 模式
                          </a-tag>
                          <a-button
                            size="small"
                            type="text"
                            @click="copyHostIP(getHostIP(hostLog))"
                            title="复制IP地址"
                          >
                            <template #icon><IconCopy /></template>
                            {{ getHostIP(hostLog) }}
                          </a-button>
                        </a-space>
                      </div>
                    </div>

                    <!-- 合并输出 -->
                    <div class="log-section">
                      <div class="log-section-header">
                        <h5>输出</h5>
                        <a-space>
                          <a-button size="small" @click="zoomLogs(getMergedLogs(hostLog), '输出')">
                            <template #icon><IconEye /></template>
                            放大查看
                          </a-button>
                          <a-button size="small" @click="copyLogs(getMergedLogs(hostLog))">
                            <template #icon><IconCopy /></template>
                            复制日志
                          </a-button>
                        </a-space>
                      </div>
                      <div class="log-text-container">
                        <pre class="log-text" v-html="highlightLogContent(getMergedLogs(hostLog), selectedStepId)"></pre>
                      </div>
                    </div>

                    <div v-if="!getMergedLogs(hostLog)" class="no-logs">
                      <a-empty description="该主机在此步骤暂无日志数据" />
                    </div>
                  </div>
                </a-tab-pane>
              </a-tabs>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
</div>
</a-card>
  </div>

  <!-- 日志放大模态框 -->
  <a-modal
    v-model:visible="logZoomVisible"
    :title="logZoomTitle"
    width="90%"
    :footer="false"
    :mask-closable="false"
  >
    <div class="log-zoom-container">
      <div class="log-zoom-header">
        <a-space>
          <a-button @click="copyZoomLogs">
            <template #icon><IconCopy /></template>
            复制全部
          </a-button>
          <a-button @click="logZoomVisible = false">
            <template #icon><IconClose /></template>
            关闭
          </a-button>
        </a-space>
      </div>
    <div class="log-zoom-content">
      <pre class="log-zoom-text" v-html="logZoomContent"></pre>
    </div>
  </div>
</a-modal>

  <!-- 步骤内容抽屉 -->
  <a-drawer
    v-model:visible="stepContentDrawerVisible"
    width="50%"
    unmount-on-close
    :mask-closable="true"
    title="步骤内容"
  >
    <div v-if="!currentStepForContent">
      <a-empty description="请选择步骤后查看" />
    </div>
    <div v-else>
      <div class="step-content-toolbar">
        <a-button size="small" type="outline" @click="loadStepContent(currentStepForContent, { force: true })">
          <template #icon><IconRefresh /></template>
          刷新步骤内容
        </a-button>
      </div>

      <div v-if="stepContentLoading[currentStepForContent]" class="step-content-body loading">
        <a-spin />
      </div>
      <div v-else-if="stepContentError[currentStepForContent]" class="step-content-body error">
        <a-result
          status="warning"
          :title="stepContentError[currentStepForContent]"
          subtitle="加载失败，可重试"
        >
          <template #extra>
            <a-button type="primary" size="small" @click="loadStepContent(currentStepForContent, { force: true })">
              重新加载
            </a-button>
          </template>
        </a-result>
      </div>
      <div v-else-if="stepContent[currentStepForContent]" class="step-content-body">
        <div class="step-content-card">
          <div class="step-content-header">
            <h4>基础信息</h4>
          </div>
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item label="步骤名称">
              {{ stepContent[currentStepForContent].step_name || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="步骤类型">
              {{ stepContent[currentStepForContent].step_type === 'file_transfer' ? '文件传输' : '脚本执行' }}
            </a-descriptions-item>
            <a-descriptions-item label="超时">
              {{ stepContent[currentStepForContent].timeout ?? '-' }}s
            </a-descriptions-item>
            <a-descriptions-item label="忽略错误">
              {{ stepContent[currentStepForContent].ignore_error ? '是' : '否' }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="stepContent[currentStepForContent].step_type === 'script'"
              label="脚本类型"
            >
              {{ stepContent[currentStepForContent].script_type || '-' }}
            </a-descriptions-item>
          </a-descriptions>
        </div>

        <div
          v-if="stepContent[currentStepForContent].step_type === 'file_transfer' && stepContent[currentStepForContent].file_sources?.length"
          class="step-content-card"
        >
          <div class="step-content-header">
            <h4>文件来源</h4>
          </div>
          <div class="file-sources">
            <a-tag
              v-for="(file, index) in stepContent[currentStepForContent].file_sources"
              :key="index"
              color="arcoblue"
            >
              {{ typeof file === 'string' ? file : (file?.path || file?.name || String(file)) }}
            </a-tag>
          </div>
        </div>

        <div
          v-if="stepContent[currentStepForContent].step_type === 'script' && stepContent[currentStepForContent].script_content"
          class="step-content-card"
        >
          <div class="step-content-header">
            <h4>脚本内容</h4>
            <a-button
              size="mini"
              type="text"
              @click="copyLogs(stepContent[currentStepForContent].script_content)"
            >
              <template #icon><IconCopy /></template>
              复制
            </a-button>
          </div>
          <div class="script-block">
            <pre class="script-pre">{{ stepContent[currentStepForContent].script_content }}</pre>
          </div>
        </div>

        <div class="step-content-card">
          <div class="step-content-header">
            <h4>执行参数</h4>
            <a-space size="small">
              <span class="switch-label">显示敏感值</span>
              <a-switch
                size="small"
                :model-value="stepContentShowSensitive[currentStepForContent] === true"
                @change="(val) => toggleSensitive(currentStepForContent, val)"
              />
            </a-space>
          </div>
          <div class="params-block">
            <div v-if="stepContent[currentStepForContent].rendered_parameters?.length" class="params-list">
              <div
                v-for="param in stepContent[currentStepForContent].rendered_parameters"
                :key="param.key"
                class="param-row"
                :class="{ 'param-row--ip': param.key === 'ip_list' }"
              >
                <span class="param-key">{{ param.key }}</span>
                <template v-if="param.key === 'ip_list'">
                  <div class="param-row-head">
                    <span class="param-value">{{ formatIpListPreview(param.display_value) }}</span>
                  </div>
                  <div class="param-row-body">
                    <a-collapse
                      v-model:active-key="ipListActiveKeys"
                      class="ip-list-collapse"
                      :bordered="false"
                    >
                      <a-collapse-item key="ip_list" :header="`IP列表 (${ipListPagination.total})`">
                        <a-table
                          :columns="ipListColumns"
                          :data="ipListRows"
                          :pagination="false"
                          size="small"
                          row-key="ip"
                          :loading="ipListLoading"
                        />
                        <a-empty v-if="ipListPagination.total === 0" description="暂无IP" />
                        <div v-if="ipListPagination.total > ipListPagination.pageSize" class="table-pagination">
                          <a-pagination
                            :current="ipListPagination.page"
                            :page-size="ipListPagination.pageSize"
                            :total="ipListPagination.total"
                            size="small"
                            show-total
                            @change="handleIpListPageChange"
                          />
                        </div>
                      </a-collapse-item>
                    </a-collapse>
                  </div>
                </template>
                <template v-else>
                  <span class="param-value" :class="{ masked: param.is_masked }">
                    {{ param.display_value }}
                  </span>
                  <a-tag v-if="param.is_masked" size="small" color="gray">已掩码</a-tag>
                </template>
              </div>
            </div>
            <a-empty v-else description="暂无参数" />
          </div>
        </div>
      </div>
      <div v-else class="step-content-body">
        <a-empty description="暂无步骤内容" />
      </div>
    </div>
  </a-drawer>

  <!-- 操作记录抽屉 -->
  <a-drawer
    v-model:visible="operationDrawerVisible"
    :width="DRAWER_WIDTH"
    title="操作记录"
    unmount-on-close
  >
    <div v-if="operationLoading" class="operation-loading">
      <a-spin />
    </div>
    <div v-else-if="operationError" class="operation-error">
      <a-result status="warning" :title="operationError">
        <template #extra>
          <a-button size="small" type="primary" @click="loadOperationLogs(true)">重新加载</a-button>
        </template>
      </a-result>
    </div>
    <div v-else-if="operationLogs.length === 0">
      <a-empty description="暂无操作记录" />
    </div>
    <div v-else class="operation-list">
      <a-timeline mode="left">
        <a-timeline-item
          v-for="item in operationLogs"
          :key="item.id"
          :dotColor="item.success ? 'green' : 'red'"
        >
          <div class="op-item">
            <div class="op-meta">
              <a-tag :color="item.success ? 'green' : 'red'">{{ item.action_display || item.action }}</a-tag>
              <span class="op-user">{{ item.user_name || '-' }}</span>
              <span class="op-time">{{ formatDateTime(item.created_at) }}</span>
            </div>
            <div class="op-desc">{{ item.description || '-' }}</div>
            <div v-if="item.extra_data && Object.keys(item.extra_data || {}).length" class="op-extra">
              <span
                v-for="(val, key) in item.extra_data"
                :key="key"
                class="op-extra-item"
              >
                {{ key }}: {{ val }}
              </span>
            </div>
          </div>
        </a-timeline-item>
      </a-timeline>
      <div v-if="operationPagination.total > operationPagination.page_size" class="op-pagination">
        <a-pagination
          :total="operationPagination.total"
          :page-size="operationPagination.page_size"
          :current="operationPagination.page"
          size="small"
          show-total
          @change="handleOperationPageChange"
        />
      </div>
    </div>
  </a-drawer>

  <!-- 链路视图 -->
  <a-drawer
    v-model:visible="chainDrawerVisible"
    :width="DRAWER_WIDTH"
    title="链路视图"
    unmount-on-close
  >
    <div v-if="chainLoading" class="chain-loading">
      <a-spin />
    </div>
    <div v-else-if="chainError" class="chain-error">
      <a-result status="warning" :title="chainError" subtitle="加载失败，可重试">
        <template #extra>
          <a-button size="small" type="primary" @click="loadChainTrace(true)">重新加载</a-button>
        </template>
      </a-result>
    </div>
    <div v-else>
      <a-empty
        v-if="!chainData.chain && chainTimeline.length === 0"
        description="暂无链路数据"
      />

      <template v-else>
        <div class="chain-section">
          <div class="chain-header">
            <h4>链路概览</h4>
          </div>
          <div class="chain-path">
            <div
              v-for="(node, index) in chainNodes"
              :key="node.key"
              class="chain-node"
            >
              <div class="node-card">
                <div class="node-head">
                  <span class="node-label">{{ node.label }}</span>
                  <a-tag
                    v-if="node.status"
                    size="small"
                    :color="getStatusColor(node.status)"
                  >
                    {{ getStatusText(node.status) }}
                  </a-tag>
                </div>
                <div class="node-name">{{ node.name }}</div>
                <div class="node-meta">
                  <span v-if="node.id">ID: {{ node.id }}</span>
                  <span v-else>未关联</span>
                </div>
                <div class="node-actions">
                  <a-button
                    size="mini"
                    type="text"
                    :disabled="!getNodePath(node)"
                    class="chain-link"
                    @click="openNodeInNewTab(node)"
                  >
                    新标签打开
                  </a-button>
                </div>
              </div>
              <div v-if="index < chainNodes.length - 1" class="chain-arrow">→</div>
            </div>
          </div>

          <div v-if="scheduledJobList.length > 1" class="chain-sublist">
            <div class="chain-subtitle">定时任务列表</div>
            <div class="chain-subitems">
              <a-button
                v-for="job in scheduledJobList"
                :key="job.id"
                size="mini"
                type="text"
                class="chain-link"
                @click="openScheduledJobInNewTab(job.id)"
              >
                {{ job.name }}
              </a-button>
            </div>
          </div>
        </div>

        <a-divider />

        <div class="chain-section">
          <div class="chain-header">
            <h4>最近执行</h4>
          </div>
          <a-empty v-if="chainTimeline.length === 0" description="暂无执行记录" />
          <a-timeline v-else mode="left" class="chain-timeline">
            <a-timeline-item
              v-for="item in chainTimeline"
              :key="item.id"
              :dotColor="getStatusColor(item.statusRaw)"
            >
              <div class="chain-item">
                <div class="chain-item-title">
                  <a-button
                    size="mini"
                    type="text"
                    class="chain-link"
                    @click="openExecutionRecordInNewTab(item.id)"
                  >
                    {{ item.name }}
                  </a-button>
                  <a-tag :color="getStatusColor(item.statusRaw)" size="small">{{ item.status }}</a-tag>
                </div>
                <div class="chain-item-meta">{{ item.time }}</div>
              </div>
            </a-timeline-item>
          </a-timeline>
        </div>
      </template>
    </div>
  </a-drawer>

  <!-- 全局变量抽屉（仅 job_workflow） -->
  <a-drawer
    v-model:visible="globalVarDrawerVisible"
    :width="DRAWER_WIDTH"
    title="全局变量"
    unmount-on-close
  >
    <div v-if="!executionInfo.execution_parameters || Object.keys(executionInfo.execution_parameters).length === 0" class="var-empty">
      <a-empty description="暂无全局变量" />
    </div>
    <div v-else class="global-parameters">
      <div
        v-for="(val, key) in executionInfo.execution_parameters"
        :key="key"
        class="parameter-item global"
      >
        <div class="param-key">{{ key }}</div>
        <div class="param-value">
          <template v-if="isObject(val)">
            <pre>{{ formatVar(val, key, true) }}</pre>
          </template>
          <template v-else>
            {{ formatVar(val, key, true) }}
          </template>
        </div>
        <div
          v-if="getVarDescription(val)"
          class="param-description"
        >
          {{ getVarDescription(val) }}
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconRefresh,
  IconClose,
  IconCopy,
  IconDown,
  IconArrowLeft,
  IconCheck,
  IconCheckCircle,
  IconCloseCircle,
  IconClockCircle,
  IconMinusCircle,
  IconExclamation,
  IconEye,
  IconUser,
  IconDownload,
  IconLink,
  IconSettings
} from '@arco-design/web-vue/es/icon'
import { executionRecordApi, hostApi } from '@/api/ops'
import RealtimeLog from '@/components/RealtimeLog.vue'
import { usePermissionsStore } from '@/stores/permissions'

type HostLog = {
  host_id?: string | number
  host_ip?: string
  ip?: string
  host?: string
  hostname?: string
  status?: string
  return_code?: number
  stdout?: string
  stderr?: string
  logs?: string
  error_logs?: string
  [k: string]: any
}

type StepLog = {
  id?: string | number
  step_order?: number
  step_name?: string
  status?: string
  hosts?: Record<string, HostLog>
  host_logs?: Record<string, HostLog>
  [k: string]: any
}

type ExecutionInfo = Record<string, any>

type ChainNode = {
  key: string
  label: string
  name: string
  id?: number | string | null
  type: 'job_template' | 'execution_plan' | 'scheduled_task' | 'execution_record'
  status?: string
}

const toKey = (id: any) => String(id ?? '')

const route = useRoute()
const router = useRouter()
const permissionsStore = usePermissionsStore()

// 响应式数据
const loading = ref(false)
const executionInfo = ref<ExecutionInfo>({})
const stepLogs = ref<Record<string | number, StepLog>>({})
const selectedStepId = ref<string | null>(null)
const selectedHostId = ref<string | null>(null)
const selectedStepKey = computed(() => selectedStepId.value != null ? String(selectedStepId.value) : '')

const hostSearchTexts = ref<Record<string | number, string>>({}) // 每个步骤的主机搜索文本
const logSearchTexts = ref<Record<string | number, string>>({}) // 每个步骤的日志搜索文本
const selectedHostIds = ref<Record<string | number, string>>({}) // 每个步骤选中的主机ID
const selectedFailedHostIds = ref<Record<string | number, Array<string | number>>>({}) // 每个步骤选中的失败主机ID列表
const batchRetrying = ref<Record<string | number, boolean>>({}) // 每个步骤的批量重试状态
const groupExpandedState = ref<Record<string | number, boolean>>({})
const expandedSteps = ref<Record<string | number, boolean>>({}) // 控制每个步骤的展开/收起状态
const stepContent = ref<Record<string, any>>({}) // 每个步骤的脚本/参数内容
const stepContentLoading = ref<Record<string, boolean>>({})
const stepContentError = ref<Record<string, any>>({})
const stepContentShowSensitive = ref<Record<string, boolean>>({})
const stepContentDrawerVisible = ref(false)

const ipListLoading = ref(false)
const ipListRows = ref<Array<{ ip: string }>>([])
const ipListPagination = reactive({ page: 1, pageSize: 10, total: 0 })
const ipListSource = ref<Array<string | number | Record<string, any>>>([])
const ipListActiveKeys = ref(['ip_list'])
const ipListColumns = [
  { title: 'IP', dataIndex: 'ip' }
]
const ipListHostCache = reactive<Record<number, string>>({})
const currentStepForContent = ref(null)

const operationDrawerVisible = ref(false)
const operationLogs = ref([])
const operationLoading = ref(false)
const operationError = ref('')
const operationPagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
})
const DRAWER_WIDTH = '45%'

const chainDrawerVisible = ref(false)
const chainLoading = ref(false)
const chainError = ref('')
const chainData = ref<{ chain: any | null; recent_executions: any[] }>({
  chain: null,
  recent_executions: []
})
const globalVarDrawerVisible = ref(false)

// 日志放大相关
const logZoomVisible = ref(false)
const logZoomTitle = ref('')
const logZoomContent = ref('')
const logZoomRawContent = ref('')

// 时间线引用
const timelineRef = ref(null)

// 获取步骤的主机分组（带搜索过滤）
const getHostGroupsForStep = (stepId) => {
  const stepLog = stepLogs.value[stepId]
  if (!stepLog) {
    return {}
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    return {}
  }

  // 确保搜索文本是响应式的
  const hostSearchText = (hostSearchTexts.value[stepId] || '').toLowerCase().trim()
  const logSearchText = (logSearchTexts.value[stepId] || '').toLowerCase().trim()



  const groups = {
    success: { hosts: [], expanded: groupExpandedState.value[`${stepId}_success`] !== false },
    failed: { hosts: [], expanded: groupExpandedState.value[`${stepId}_failed`] !== false },
    running: { hosts: [], expanded: groupExpandedState.value[`${stepId}_running`] !== false },
    pending: { hosts: [], expanded: groupExpandedState.value[`${stepId}_pending`] !== false }
  }

  let totalHosts = 0
  let filteredHosts = 0

  Object.values(hosts).forEach(hostLog => {
    totalHosts++

    // 应用主机名称/IP搜索过滤
    if (hostSearchText) {
      const hostName = (hostLog.hostname || hostLog.host_name || '').toLowerCase()
      const hostIP = (hostLog.host_ip || '').toLowerCase()
      if (!hostName.includes(hostSearchText) && !hostIP.includes(hostSearchText)) {
        return // 跳过不匹配的主机
      }
    }

    // 应用日志内容搜索过滤
    if (logSearchText) {
      const logs = (hostLog.stdout || hostLog.logs || '').toLowerCase()
      const errorLogs = (hostLog.stderr || hostLog.error_logs || '').toLowerCase()
      if (!logs.includes(logSearchText) && !errorLogs.includes(logSearchText)) {
        return // 跳过日志内容不匹配的主机
      }
    }

    filteredHosts++

    // 处理unknown状态，根据return_code判断
    let actualStatus = hostLog.status
    if (hostLog.status === 'unknown') {
      actualStatus = hostLog.return_code === 0 ? 'success' : 'failed'
    }

    if (groups[actualStatus]) {
      groups[actualStatus].hosts.push(hostLog)
    }
  })



  return groups
}

// 创建响应式的步骤主机分组计算属性
const stepHostGroups = computed<Record<string | number, any>>(() => {
  // 包含搜索触发器以确保响应式更新
  searchTrigger.value

  // 确保追踪 hostSearchTexts 和 groupExpandedState 的变化
  const searchTexts = hostSearchTexts.value
  const expandedState = groupExpandedState.value

  const result = {}
  Object.keys(stepLogs.value).forEach(stepId => {
    result[stepId] = getHostGroupsForStep(stepId)
  })

  return result
})

// 监听搜索文本变化，强制更新计算属性
const searchTrigger = ref(0)
const triggerSearchUpdate = () => {
  searchTrigger.value++
}

// 计算属性 - 优化显示名称
const displayName = computed(() => {
  if (!executionInfo.value.name) return '-'

  // 移除 "执行方案: " 前缀
  let name = executionInfo.value.name
  if (name.startsWith('执行方案: ')) {
    name = name.replace('执行方案: ', '')
  }

  // 移除 #数字 后缀
  name = name.replace(/ #\d+$/, '')

  return name
})

// 计算属性 - 获取执行ID（用于SSE连接）
const executionId = computed(() => {
  return executionInfo.value.execution_id || null
})

// 计算属性 - 执行模式（用于区分 SSH / Agent 视角）
const executionMode = computed(() => {
  const params = executionInfo.value.execution_parameters || {}
  if (params.execution_mode === 'agent' || params.agent_server_url) {
    return 'agent'
  }
  if (params.execution_mode === 'ssh') {
    return 'ssh'
  }
  return null
})

const openChainDrawer = () => {
  chainDrawerVisible.value = true
  loadChainTrace(true)
}

const loadChainTrace = async (force = false) => {
  if (chainLoading.value && !force) return
  const recordId = Number(route.params.id)
  if (!recordId) return
  if (!force && chainData.value.chain) return

  chainLoading.value = true
  chainError.value = ''
  try {
    const res = await executionRecordApi.getTrace(recordId)
    chainData.value = {
      chain: res?.chain || null,
      recent_executions: res?.recent_executions || []
    }
  } catch (error) {
    console.error('加载链路失败:', error)
    chainError.value = error?.message || '加载失败'
    Message.error('加载链路失败')
  } finally {
    chainLoading.value = false
  }
}

const getNodePath = (node: ChainNode) => {
  if (!node.id) {
    return ''
  }
  if (node.type === 'job_template') {
    return `/job-templates/detail/${node.id}`
  }
  if (node.type === 'execution_plan') {
    return `/execution-plans/detail/${node.id}`
  }
  if (node.type === 'scheduled_task') {
    return `/scheduled-tasks/detail/${node.id}`
  }
  if (node.type === 'execution_record') {
    return `/execution-records/${node.id}`
  }
  return ''
}

const openNodeInNewTab = (node: ChainNode) => {
  const path = getNodePath(node)
  if (!path) {
    return
  }
  const url = router.resolve(path).href
  window.open(url, '_blank')
}

const openScheduledJobInNewTab = (id?: number | string | null) => {
  if (!id) return
  const url = router.resolve(`/scheduled-tasks/detail/${id}`).href
  window.open(url, '_blank')
}

const openExecutionRecordInNewTab = (id?: number | string | null) => {
  if (!id) return
  const url = router.resolve(`/execution-records/${id}`).href
  window.open(url, '_blank')
}

const scheduledJobList = computed(() => {
  return chainData.value.chain?.scheduled_jobs || []
})

const scheduledJobSummary = computed(() => {
  const jobs = scheduledJobList.value
  if (!jobs.length) return '未关联'
  if (jobs.length === 1) return jobs[0].name || '定时任务'
  return `关联 ${jobs.length} 个定时任务`
})

const chainNodes = computed<ChainNode[]>(() => {
  const chain = chainData.value.chain || {}
  const template = chain.job_template
  const plan = chain.execution_plan
  const execution = chain.execution_record || {}

  return [
    {
      key: 'job_template',
      label: '作业模板',
      name: template?.name || '未关联',
      id: template?.id || null,
      type: 'job_template'
    },
    {
      key: 'execution_plan',
      label: '执行方案',
      name: plan?.name || '未关联',
      id: plan?.id || null,
      type: 'execution_plan'
    },
    {
      key: 'scheduled_task',
      label: '定时任务',
      name: scheduledJobSummary.value,
      id: scheduledJobList.value.length === 1 ? scheduledJobList.value[0].id : null,
      type: 'scheduled_task'
    },
    {
      key: 'execution_record',
      label: '执行记录',
      name: execution?.name || displayName.value || '执行记录',
      id: execution?.id || executionInfo.value?.id || null,
      status: execution?.status || executionInfo.value?.status,
      type: 'execution_record'
    }
  ]
})

const chainTimeline = computed(() => {
  const list = chainData.value.recent_executions || []
  return list.map((item) => ({
    id: item.id,
    name: item.name || `执行记录 ${item.execution_id || item.id}`,
    status: item.status_display || getStatusText(item.status),
    statusRaw: item.status,
    time: formatDateTime(item.created_at)
  }))
})

// 计算属性 - 排序后的步骤列表
const sortedSteps = computed<any[]>(() => {
  const steps = Object.entries(stepLogs.value).map(([id, step]) => ({
    ...(step as StepLog),
    id: String(id),
  }))
  return steps.sort((a, b) => {
    const orderA = (a.step_order as number) || 0
    const orderB = (b.step_order as number) || 0
    return orderA - orderB
  })
})

// 计算属性 - 已完成步骤数
const completedStepsCount = computed(() => {
  return sortedSteps.value.filter(step =>
    ['success', 'failed', 'cancelled'].includes(step.status)
  ).length
})

// 计算属性 - 流程进度百分比
const progressPercentage = computed(() => {
  if (sortedSteps.value.length === 0) return 0
  return (completedStepsCount.value / sortedSteps.value.length) * 100
})

// 计算属性 - 兼容旧格式的主机日志
const hostLogs = computed<Record<string, Record<string, HostLog>>>(() => {
  // 如果有步骤日志，返回空对象（使用步骤格式）
  if (Object.keys(stepLogs.value).length > 0) {
    return {}
  }

  // 如果没有步骤日志，检查是否有旧格式的主机日志
  const results = executionInfo.value.execution_results || {}
  return results.host_logs || {}
})

// 获取执行记录详情
const fetchExecutionDetail = async () => {
  loading.value = true
  try {
    const response = await executionRecordApi.getRecord(Number(route.params.id))
    executionInfo.value = response

    // 处理日志数据 —— 现在只支持统一结构：{ summary, steps }
    if (response.execution_results) {
      const results = response.execution_results
      const steps = Array.isArray(results.steps) ? results.steps : []
      const normalizedStepLogs = {}

      steps.forEach((step, index) => {
        if (!step) return

        const stepId =
          step.id ||
          `step_${step.order || index + 1}_${step.name || 'step'}`

        const hosts = Array.isArray(step.hosts) ? step.hosts : []
        const hostLogsMap = {}

        hosts.forEach((host) => {
          if (!host) return

          const hostId =
            host.id ?? host.host_id ?? host.ip ?? host.name ?? `${Math.random()}`

          const stdout = host.stdout || ''
          const stderr = host.stderr || ''

          hostLogsMap[hostId] = {
            host_id: hostId,
            host_name: host.name || host.host_name || `Host-${hostId}`,
            host_ip: host.ip || host.host_ip || '',
            status: host.status || 'unknown',
            stdout,
            stderr,
            logs: stdout,
            error_logs: stderr,
            log_count: stdout
              .split('\n')
              .filter(line => line.trim()).length,
          }
        })

        normalizedStepLogs[stepId] = {
          step_name: step.name || stepId,
          step_order: step.order || index + 1,
          status: step.status || 'unknown',
          host_logs: hostLogsMap,
        }
      })

      stepLogs.value = normalizedStepLogs

      // 初始化所有步骤的状态
      const stepIds = Object.keys(stepLogs.value)

      // 初始化所有步骤的搜索文本和展开状态
      stepIds.forEach(stepId => {
        if (!hostSearchTexts.value[stepId]) {
          hostSearchTexts.value[stepId] = ''
        }
        if (!logSearchTexts.value[stepId]) {
          logSearchTexts.value[stepId] = ''
        }
        // 默认不展开任何步骤
        if (expandedSteps.value[stepId] === undefined) {
          expandedSteps.value[stepId] = false
        }
      })
    }
  } catch (error) {
    console.error('获取执行记录详情失败:', error)
  } finally {
    loading.value = false
  }
}

// 刷新日志
const refreshLogs = () => {
  fetchExecutionDetail()
}

// 加载步骤内容（脚本/参数）
const loadStepContent = async (stepId, options = { force: false }) => {
  if (!stepId) return
  if (!options.force && stepContent.value[stepId]) return

  stepContentLoading.value = { ...stepContentLoading.value, [stepId]: true }
  stepContentError.value = { ...stepContentError.value, [stepId]: null }

  try {
    const res = await executionRecordApi.getStepContent(
      Number(route.params.id),
      stepId,
      { show_sensitive: stepContentShowSensitive.value[stepId] === true }
    )
    stepContent.value = { ...stepContent.value, [stepId]: res }
    syncIpListSource(stepId)
  } catch (error) {
    console.error('加载步骤内容失败:', error)
    stepContentError.value = {
      ...stepContentError.value,
      [stepId]: error?.message || '加载失败'
    }
    Message.error('加载步骤内容失败')
  } finally {
    stepContentLoading.value = { ...stepContentLoading.value, [stepId]: false }
  }
}

// 切换敏感值显示
const toggleSensitive = (stepId, val) => {
  stepContentShowSensitive.value = { ...stepContentShowSensitive.value, [stepId]: val }
  loadStepContent(stepId, { force: true })
}

const formatIpListPreview = (value: any) => {
  const list = normalizeIpList(value)
  if (!list.length) return '-'
  return `IP列表 (${list.length})`
}

const normalizeIpList = (value: any) => {
  if (!value) return []
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    return value.split(/[\s,;]+/).filter(Boolean)
  }
  return []
}

const isNumeric = (value: any) => /^\d+$/.test(String(value))
const isIp = (value: any) => /^(\d{1,3}\.){3}\d{1,3}$/.test(String(value))

const syncIpListSource = (stepId: string | number) => {
  const params = stepContent.value?.[stepId]?.rendered_parameters || []
  const ipParam = params.find((item: any) => item?.key === 'ip_list')
  ipListSource.value = normalizeIpList(ipParam?.display_value)
  ipListPagination.page = 1
  ipListActiveKeys.value = ['ip_list']
  loadIpListPage()
}

const handleIpListPageChange = (page: number) => {
  ipListPagination.page = page
  loadIpListPage()
}

const loadIpListPage = async () => {
  const list = ipListSource.value || []
  ipListPagination.total = list.length
  if (list.length === 0) {
    ipListRows.value = []
    return
  }

  const start = (ipListPagination.page - 1) * ipListPagination.pageSize
  const end = start + ipListPagination.pageSize
  const pageItems = list.slice(start, end)

  if (pageItems.every(item => item && typeof item === 'object' && (item.ip_address || item.ip))) {
    ipListRows.value = pageItems.map((item: any) => ({ ip: item.ip_address || item.ip || '-' }))
    return
  }

  if (pageItems.every(item => isIp(item))) {
    ipListRows.value = pageItems.map(item => ({ ip: String(item) }))
    return
  }

  if (pageItems.every(item => isNumeric(item))) {
    ipListLoading.value = true
    try {
      const results = await Promise.all(pageItems.map(async (id) => {
        const numericId = Number(id)
        if (ipListHostCache[numericId]) {
          return { ip: ipListHostCache[numericId] }
        }
        try {
          const host = await hostApi.getHost(numericId)
          const ip = host?.ip_address || host?.internal_ip || '-'
          ipListHostCache[numericId] = ip
          return { ip }
        } catch (error) {
          return { ip: '-' }
        }
      }))
      ipListRows.value = results
    } finally {
      ipListLoading.value = false
    }
    return
  }

  ipListRows.value = pageItems.map(item => ({ ip: String(item) }))
}

const getMergedLogs = (hostLog: any) => {
  const out = hostLog?.stdout || hostLog?.logs || ''
  const err = hostLog?.stderr || hostLog?.error_logs || ''
  if (!out && !err) return ''
  const lines = []
  out.split('\n').forEach(l => {
    if (l.trim()) lines.push(l)
  })
  err.split('\n').forEach(l => {
    if (l.trim()) lines.push(`[ERR] ${l}`)
  })
  return lines.join('\n')
}

const openStepContentDrawer = (stepId) => {
  if (!stepId) return
  currentStepForContent.value = stepId
  stepContentDrawerVisible.value = true
  loadStepContent(stepId, { force: true })
}

const openGlobalVarDrawer = () => {
  globalVarDrawerVisible.value = true
}

// 操作记录
const loadOperationLogs = async (force = false) => {
  if (operationLoading.value && !force) return
  operationLoading.value = true
  operationError.value = ''
  try {
    const res = await executionRecordApi.getExecutionOperations(Number(route.params.id), {
      page: operationPagination.page,
      page_size: operationPagination.page_size,
    })
    const results = res.results ?? []
    operationLogs.value = results
    operationPagination.total = res.total ?? results.length
  } catch (error) {
    console.error('加载操作记录失败:', error)
    operationError.value = error?.message || '加载失败'
    Message.error('加载操作记录失败')
  } finally {
    operationLoading.value = false
  }
}

const handleOperationPageChange = (page) => {
  operationPagination.page = page
  loadOperationLogs(true)
}

const openOperationDrawer = () => {
  operationDrawerVisible.value = true
  loadOperationLogs(true)
}

// 选择步骤（点击步骤时切换选中状态）
const selectStep = (stepId: string | number) => {
  const sid = String(stepId)
  // 如果点击的是已选中的步骤，则取消选中（回到单栏布局）
  if (selectedStepId.value === sid) {
    selectedStepId.value = null
  } else {
    selectedStepId.value = sid
    loadStepContent(sid, { force: true })

    // 自动选择该步骤的第一个主机
    const step = stepLogs.value[sid]
    if (step) {
      // 兼容新旧格式：优先使用hosts，其次使用host_logs
      const hosts = step.hosts || step.host_logs
      if (hosts) {
        const hostIds = Object.keys(hosts)
        if (hostIds.length > 0) {
          // 如果没有选中主机或选中的主机不在当前步骤中，选择第一个主机
          if (!selectedHostIds.value[sid] || !hostIds.includes(selectedHostIds.value[sid])) {
            selectedHostIds.value[sid] = hostIds[0]
          }
          selectedHostId.value = String(selectedHostIds.value[sid])
        }
      }
    }
  }
}

// 复制日志
const copyLogs = async (logContent) => {
  try {
    await navigator.clipboard.writeText(logContent)
    Message.success('日志已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 放大查看日志
const zoomLogs = (logContent, logType) => {
  logZoomTitle.value = `${logType} - 放大查看`
  logZoomRawContent.value = logContent
  logZoomContent.value = highlightLogContent(logContent, selectedStepId.value)
  logZoomVisible.value = true
}

// 复制放大日志
const copyZoomLogs = async () => {
  try {
    await navigator.clipboard.writeText(logZoomRawContent.value)
    Message.success('日志已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 复制主机IP
const copyHostIP = async (ip) => {
  try {
    await navigator.clipboard.writeText(ip)
    Message.success(`IP地址 ${ip} 已复制到剪贴板`)
  } catch (error) {
    console.error('复制失败:', error)
    Message.error('复制失败')
  }
}

// 导出单个步骤日志为 zip
const exportStepLogs = (stepId) => {
  const step = stepLogs.value[stepId]
  if (!step) {
    Message.warning('未找到步骤日志')
    return
  }
  const hosts = step.hosts || step.host_logs || {}
  if (Object.keys(hosts).length === 0) {
    Message.warning('该步骤没有可导出的日志')
    return
  }

  let lines = ''
  Object.values(hosts).forEach(hostLog => {
    const ip = hostLog.host_ip || hostLog.ip || hostLog.host || '未知IP'
    const merged = [
      ...(hostLog.stdout || hostLog.logs || '').split('\n').filter(l => l.trim()).map(l => `✓ ${l}`),
      ...(hostLog.stderr || hostLog.error_logs || '').split('\n').filter(l => l.trim()).map(l => `✗ ${l}`)
    ]
    merged.forEach(line => {
      lines += `${ip} | ${line}\n`
    })
  })

  if (!lines) {
    Message.warning('该步骤没有日志内容')
    return
  }

  const filename = `step_${step.step_order || stepId}_${step.step_name || 'step'}.txt`
  const zip = buildZipFromText(filename, lines)
  const url = URL.createObjectURL(zip)
  const a = document.createElement('a')
  a.href = url
  a.download = `步骤日志_${step.step_order || stepId}_${new Date().getTime()}.zip`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)

  Message.success('步骤日志已导出')
}

// 获取步骤状态颜色
const getStepStatusColor = (status: string | number) => {
  const s = String(status)
  const colorMap: Record<string, string> = {
    success: 'green',
    failed: 'red',
    running: 'blue',
    pending: 'gray'
  }
  return colorMap[s] || 'gray'
}

// 获取步骤状态文本
const getStepStatusText = (status: string | number) => {
  const s = String(status)
  const textMap: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '执行中',
    pending: '等待中'
  }
  return textMap[s] || s
}

// 获取连接线样式类
const getConnectorClass = (currentStatus, nextStatus) => {
  // 如果当前步骤失败，连接线显示为失败状态
  if (currentStatus === 'failed') {
    return 'connector-failed'
  }
  // 如果当前步骤成功且下一步骤存在，连接线显示为成功状态
  if (currentStatus === 'success' && nextStatus) {
    return 'connector-success'
  }
  // 如果当前步骤运行中，连接线显示为运行中状态
  if (currentStatus === 'running') {
    return 'connector-running'
  }
  // 默认等待状态
  return 'connector-pending'
}

// 获取主机状态颜色
const getHostStatusColor = (status) => {
  const colorMap = {
    'success': 'green',
    'failed': 'red',
    'running': 'blue',
    'pending': 'gray',
    'unknown': 'orange'
  }
  return colorMap[status] || 'gray'
}

// 获取主机状态文本
const getHostStatusText = (status) => {
  const textMap = {
    'success': '成功',
    'failed': '失败',
    'running': '执行中',
    'pending': '等待中',
    'unknown': '未知'
  }
  return textMap[status] || status
}

// 获取错误输出标题（区分 SSH / Agent）
const getErrorTitle = () => {
  if (executionMode.value === 'agent') {
    return 'Agent 错误输出'
  }
  if (executionMode.value === 'ssh') {
    return 'SSH 错误输出'
  }
  return '错误输出'
}

// 返回
const goBack = () => {
  router.back()
}

const goPlanDetail = (planId: string | number | undefined | null) => {
  if (!planId) return
  router.push(`/execution-plans/detail/${planId}`)
}

const secretKeyRegex = /(password|secret|token|key|credential|pwd)/i
const isObject = (v: unknown): v is Record<string, any> => v !== null && typeof v === 'object'

const formatVar = (val: unknown, key: any = '', mask = false): string => {
  if (val === null || val === undefined) return '-'
  const isSecretKey = key && secretKeyRegex.test(key)
  if (isObject(val)) {
    if (val.type === 'secret' || val?.is_secret || isSecretKey || mask) {
      return '******'
    }
    if ('value' in val) {
      return formatVar((val as any).value, key, mask)
    }
    try {
      return JSON.stringify(val, null, 2)
    } catch {
      return String(val)
    }
  }
  if (mask && isSecretKey) return '******'
  return String(val)
}

const getVarDescription = (val: unknown) => {
  if (!isObject(val)) return ''
  return val.description || ''
}

// 重试执行
const handleRetry = async () => {
  const isRetry = executionInfo.value.status === 'failed'
  const title = isRetry ? '确认重试' : '确认重做'
  const content = isRetry
    ? `确定要重试执行"${executionInfo.value.name}"吗？`
    : `确定要重做"${executionInfo.value.name}"吗？`

  try {
    Modal.confirm({
      title,
      content,
      onOk: async () => {
        try {
          console.log('开始调用重做API, 执行记录ID:', route.params.id)
          const result = await executionRecordApi.retryExecution(Number(route.params.id))
          console.log('重做API返回结果:', result)

          const successMessage = isRetry ? '重试成功' : '重做成功'
          Message.success(successMessage)

          // 如果返回了新的执行记录ID，跳转到新的执行记录详情页面
          // 注意：由于响应拦截器会自动提取content字段，result就是content的内容
          if (result && result.execution_record_id) {
            console.log('跳转到新的执行记录:', result.execution_record_id)
            await router.push(`/execution-records/${result.execution_record_id}`)
            console.log('跳转完成')
          } else {
            console.log('没有返回execution_record_id，刷新当前页面')
            console.log('result结构:', result)
            // 如果没有返回新的执行记录ID，刷新当前页面
            fetchExecutionDetail()
          }
        } catch (error) {
          console.error('重做操作失败:', error)
          Message.error('重做操作失败')
        }
      }
    })
  } catch (error) {
    console.error('重试失败:', error)
  }
}

// 取消执行
const handleCancel = async () => {
  try {
    await Modal.confirm({
      title: '确认取消',
      content: `确定要取消执行"${executionInfo.value.name}"吗？`,
      onOk: async () => {
        await executionRecordApi.cancelExecution(Number(route.params.id))
        Message.success('取消成功')
        fetchExecutionDetail()
      }
    })
  } catch (error) {
    console.error('取消失败:', error)
  }
}

// 判断步骤是否可以重试
const canRetryStep = (step) => {
  if (!step) return false

  // 支持重试的步骤状态：失败、超时、取消
  const retryableStatuses = ['failed', 'timeout', 'cancelled']
  if (!retryableStatuses.includes(step.status)) return false

  // 支持重试的执行记录状态：失败、超时、取消、成功（可以重做）
  const retryableExecutionStatuses = ['failed', 'timeout', 'cancelled', 'success']
  if (!retryableExecutionStatuses.includes(executionInfo.value.status)) return false

  return true
}

// 步骤重试
const handleStepRetry = async (retryType, stepId) => {
  if (!stepId || !stepLogs.value[stepId]) {
    Message.warning('请先选择要重试的步骤')
    return
  }

  const step = stepLogs.value[stepId]
  const retryTypeText = {
    'failed_only': '仅重试失败主机',
    'all': '重试该步骤'
  }

  try {
    Modal.confirm({
      title: '确认步骤重试',
      content: `确定要${retryTypeText[retryType]}执行步骤"${step.step_name}"吗？`,
      onOk: async () => {
        try {
          await executionRecordApi.retryStepInplace(Number(route.params.id), {
            step_id: stepId,
            retry_type: retryType
          })
          Message.success('步骤重试成功')
          fetchExecutionDetail()
        } catch (error) {
          console.error('步骤重试API调用失败:', error)
          Message.error('步骤重试失败')
        }
      }
    })
  } catch (error) {
    console.error('步骤重试失败:', error)
  }
}

// 权限检查函数
const canExecuteStep = (recordId) => {
  if (permissionsStore.isSuperUser) return true
  return (
    permissionsStore.hasPermission('executionrecord', 'execute', recordId) ||
    permissionsStore.hasPermission('executionrecord', 'execute')
  )
}

// 显示无权限提示
const showNoPermissionMessage = () => {
  Message.warning('没有权限执行此操作，请联系管理员开放权限')
}

// 获取选中失败主机ID列表
const getSelectedFailedHostIds = (stepId: any) => {
  const key = toKey(stepId)
  return selectedFailedHostIds.value[key] || []
}

// 判断是否所有失败主机都被选中
const isAllFailedHostsSelected = (stepId: any) => {
  const key = toKey(stepId)
  const stepLog = stepLogs.value[key]
  if (!stepLog) return false

  const failedHosts = stepHostGroups.value[key]?.failed?.hosts || []
  const selectedIds = getSelectedFailedHostIds(stepId)

  return failedHosts.length > 0 && selectedIds.length === failedHosts.length
}

// 判断是否为部分选中状态
const isIndeterminateFailedHosts = (stepId: any) => {
  const key = toKey(stepId)
  const stepLog = stepLogs.value[key]
  if (!stepLog) return false

  const failedHosts = stepHostGroups.value[key]?.failed?.hosts || []
  const selectedIds = getSelectedFailedHostIds(stepId)

  return selectedIds.length > 0 && selectedIds.length < failedHosts.length
}

// 切换全选/取消全选失败主机
const handleToggleAllFailedHosts = (stepId: any, checked: boolean) => {
  const key = toKey(stepId)
  const failedHosts = stepHostGroups.value[key]?.failed?.hosts || []

  if (checked) {
    // 全选
    selectedFailedHostIds.value[key] = failedHosts.map((h: any) => h.host_id)
  } else {
    // 取消全选
    selectedFailedHostIds.value[key] = []
  }
}

// 处理失败主机选择变化
const handleFailedHostSelectionChange = (stepId: any, values: Array<string | number>) => {
  const key = toKey(stepId)
  selectedFailedHostIds.value[key] = values
}

// 批量重试选中的失败主机
const handleBatchRetrySelectedHosts = async (stepId) => {
  if (!canExecuteStep(executionInfo.value?.id)) {
    showNoPermissionMessage()
    return
  }

  const selectedIds = getSelectedFailedHostIds(stepId)
  if (selectedIds.length === 0) {
    Message.warning('请先选择要重试的主机')
    return
  }

  const step = stepLogs.value[stepId]
  if (!step) {
    Message.warning('步骤不存在')
    return
  }

  try {
    Modal.confirm({
      title: '确认批量重试',
      content: `确定要重试选中的 ${selectedIds.length} 台失败主机吗？`,
      onOk: async () => {
        batchRetrying.value[stepId] = true
        try {
          await executionRecordApi.retryStepInplace(Number(route.params.id), {
            step_id: stepId,
            retry_type: 'failed_only',
            host_ids: selectedIds as any
          })
          Message.success(`批量重试已启动，共 ${selectedIds.length} 台主机`)
          // 清空选择
          selectedFailedHostIds.value[stepId] = []
          // 刷新详情
          fetchExecutionDetail()
        } catch (error) {
          console.error('批量重试失败:', error)
          Message.error(error?.message || '批量重试失败')
        } finally {
          batchRetrying.value[stepId] = false
        }
      }
    })
  } catch (error) {
    // 用户取消
  }
}

// 点击处理函数（带权限检查）
const handleClickStepRetry = (retryType, stepId) => {
  if (!canExecuteStep(executionInfo.value?.id)) {
    showNoPermissionMessage()
    return
  }
  handleStepRetry(retryType, stepId)
}

const handleClickStepIgnoreError = (stepId) => {
  if (!canExecuteStep(executionInfo.value?.id)) {
    showNoPermissionMessage()
    return
  }
  handleStepIgnoreError(stepId)
}

// 忽略错误继续
const handleStepIgnoreError = async (stepId) => {
  if (!stepId || !stepLogs.value[stepId]) {
    Message.warning('请先选择要忽略错误的步骤')
    return
  }

  const step = stepLogs.value[stepId]

  try {
    Modal.confirm({
      title: '确认忽略错误',
      content: `确定要忽略步骤"${step.step_name}"的错误并继续执行后续步骤吗？`,
      onOk: async () => {
        try {
          await executionRecordApi.ignoreStepError(Number(route.params.id), stepId)
          Message.success('已忽略错误，继续执行')
          fetchExecutionDetail()
        } catch (error) {
          console.error('忽略错误API调用失败:', error)
          Message.error('忽略错误失败')
        }
      }
    })
  } catch (error) {
    console.error('忽略错误失败:', error)
  }
}

// 获取空日志描述
const getEmptyLogsDescription = () => {
  if (executionInfo.value.status === 'cancelled') {
    return '任务已取消，暂无执行日志'
  } else if (executionInfo.value.status === 'pending') {
    return '任务尚未开始执行'
  } else {
    return '暂无日志数据'
  }
}

// 工具函数
const getExecutionTypeText = (type) => {
  const typeMap = {
    'quick_script': '快速脚本执行',
    'quick_file_transfer': '快速文件传输',
    'job_workflow': 'Job工作流执行',
    'scheduled_job': '定时作业执行'
  }
  return typeMap[type] || type
}

const getExecutionTypeColor = (type) => {
  const colorMap = {
    'quick_script': 'blue',
    'quick_file_transfer': 'green',
    'job_workflow': 'purple',
    'scheduled_job': 'orange'
  }
  return colorMap[type] || 'gray'
}

const getStatusText = (status) => {
  const statusMap = {
    'pending': '等待中',
    'running': '执行中',
    'success': '成功',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return statusMap[status] || status
}

const getStatusColor = (status) => {
  const colorMap = {
    'pending': 'gray',
    'running': 'blue',
    'success': 'green',
    'failed': 'red',
    'cancelled': 'orange'
  }
  return colorMap[status] || 'gray'
}

const getStatusIcon = (status) => {
  const iconMap = {
    'pending': 'icon-pause',
    'running': 'icon-loading',
    'success': 'icon-check',
    'failed': 'icon-exclamation',
    'cancelled': 'icon-close'
  }
  return iconMap[status] || 'icon-pause'
}

const formatDuration = (startTime: any, endTime: any) => {
  if (!startTime || !endTime) {
    return '-'
  }

  const start = new Date(startTime as any)
  const end = new Date(endTime as any)

  // 检查日期是否有效
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return '-'
  }

  const duration = (end.getTime() - start.getTime()) / 1000

  if (duration < 0) {
    return '-'
  }

  if (duration < 60) {
    return `${duration.toFixed(1)}秒`
  } else if (duration < 3600) {
    const minutes = Math.floor(duration / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${minutes}分${seconds}秒`
  } else {
    const hours = Math.floor(duration / 3600)
    const minutes = Math.floor((duration % 3600) / 60)
    const seconds = (duration % 60).toFixed(1)
    return `${hours}时${minutes}分${seconds}秒`
  }
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}



// 主机分组展开/收起
const toggleGroupInStep = (stepId: string | number, status: string | number) => {
  const stepKey = `${toKey(stepId)}_${String(status)}`
  const currentState = groupExpandedState.value[stepKey]
  groupExpandedState.value[stepKey] = !currentState
  // 强制更新计算属性
  triggerSearchUpdate()
}

// 更新主机搜索文本
const updateSearchText = (stepId: any, value: string) => {
  // 确保 hostSearchTexts 是响应式的
  const key = toKey(stepId)
  if (!hostSearchTexts.value[key]) {
    hostSearchTexts.value[key] = ''
  }

  // 更新搜索文本
  hostSearchTexts.value[key] = value

  // 触发搜索更新
  triggerSearchUpdate()
}

// 更新日志搜索文本
const updateLogSearchText = (stepId: any, value: string) => {
  // 确保 logSearchTexts 是响应式的
  const key = toKey(stepId)
  if (!logSearchTexts.value[key]) {
    logSearchTexts.value[key] = ''
  }

  // 更新搜索文本
  logSearchTexts.value[key] = value

  // 触发搜索更新
  triggerSearchUpdate()
}

// 获取步骤中指定状态的主机数量
const getHostCountByStatusInStep = (stepId: any, status: string | number) => {
  const key = toKey(stepId)
  const stepLog = stepLogs.value[key]
  if (!stepLog) {
    return 0
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    console.log('No hosts found for step:', stepId, stepLog)
    return 0
  }

  const statusKey = String(status)
  const count = Object.values(hosts).filter(hostLog => {
    // 如果状态是unknown，根据return_code判断
    if (hostLog.status === 'unknown') {
      return hostLog.return_code === 0 ? statusKey === 'success' : statusKey === 'failed'
    }
    return hostLog.status === statusKey
  }).length

  console.log(`Step ${stepId} status ${status} count:`, count, hosts)
  return count
}

// 获取步骤中的总主机数量
const getTotalHostCountInStep = (stepId: any) => {
  const key = toKey(stepId)
  const stepLog = stepLogs.value[key]
  if (!stepLog) {
    return 0
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hosts = stepLog.hosts || stepLog.host_logs
  if (!hosts) {
    console.log('No hosts found for step total count:', stepId, stepLog)
    return 0
  }

  const count = Object.keys(hosts).length
  console.log(`Step ${stepId} total host count:`, count, hosts)
  return count
}

// 获取主机显示名称
const getHostDisplayName = (hostLog: any) => {
  // 优先使用host_name，其次host_ip，最后hostname
  return hostLog.host_name || hostLog.host_ip || hostLog.hostname || '未知主机'
}

// 获取主机IP
const getHostIP = (hostLog: any) => {
  return hostLog.host_ip || '未知IP'
}

// 复制步骤中指定状态的主机IP
const copyHostsByStatusInStep = async (stepId: any, status: string | number) => {
  const key = toKey(stepId)
  const stepLog = stepLogs.value[key]
  if (!stepLog) {
    Message.warning('该步骤暂无主机数据')
    return
  }

  // 兼容新旧格式：优先使用hosts，其次使用host_logs
  const hostData: Record<string, any> = stepLog.hosts || stepLog.host_logs
  if (!hostData) {
    Message.warning('该步骤暂无主机数据')
    return
  }

  const statusKey = String(status)
  let hosts = []
  if (statusKey === 'all') {
    hosts = Object.values(hostData)
  } else {
    hosts = Object.values(hostData).filter(hostLog => hostLog.status === statusKey)
  }

  if (hosts.length === 0) {
    Message.warning(`该步骤下没有${statusKey === 'all' ? '' : statusKey}状态的主机`)
    return
  }

  const ips = hosts.map(host => host.host_ip || host.ip_address).join('\n')
  try {
    await navigator.clipboard.writeText(ips)
    Message.success(`已复制 ${hosts.length} 台主机的IP地址`)
  } catch (err) {
    Message.error('复制失败，请手动复制')
  }
}

// 高亮日志内容中的搜索关键词
const highlightLogContent = (content: string, stepId: any) => {
  if (!content) return ''

  const key = toKey(stepId)
  const searchText = logSearchTexts.value[key] || ''

  // 转义HTML特殊字符
  const escapedContent = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

  if (!searchText) return escapedContent

  // 高亮搜索关键词（不区分大小写）
  const regex = new RegExp(`(${searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return escapedContent.replace(regex, '<mark class="log-highlight">$1</mark>')
}

// zip 工具（单文件，无压缩）
const crcTable = (() => {
  const table = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1)
    }
    table[n] = c >>> 0
  }
  return table
})()

const crc32 = (buf) => {
  let crc = 0 ^ -1
  for (let i = 0; i < buf.length; i++) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ buf[i]) & 0xff]
  }
  return (crc ^ -1) >>> 0
}

const toDosTime = (date) => {
  const dt = new Date(date)
  const dosTime =
    (dt.getHours() << 11) |
    (dt.getMinutes() << 5) |
    (Math.floor(dt.getSeconds() / 2))
  const dosDate =
    ((dt.getFullYear() - 1980) << 9) |
    ((dt.getMonth() + 1) << 5) |
    dt.getDate()
  return { dosTime, dosDate }
}

const buildZipFromText = (filename, text) => {
  const encoder = new TextEncoder()
  const data = encoder.encode(text)
  const crc = crc32(data)
  const { dosTime, dosDate } = toDosTime(new Date())

  const fileNameBytes = encoder.encode(filename)
  const localHeader = new DataView(new ArrayBuffer(30 + fileNameBytes.length))
  let o = 0
  localHeader.setUint32(o, 0x04034b50, true); o += 4 // local file header signature
  localHeader.setUint16(o, 20, true); o += 2 // version needed to extract
  localHeader.setUint16(o, 0, true); o += 2 // general purpose bit flag
  localHeader.setUint16(o, 0, true); o += 2 // compression method (store)
  localHeader.setUint16(o, dosTime, true); o += 2
  localHeader.setUint16(o, dosDate, true); o += 2
  localHeader.setUint32(o, crc, true); o += 4
  localHeader.setUint32(o, data.length, true); o += 4 // compressed size
  localHeader.setUint32(o, data.length, true); o += 4 // uncompressed size
  localHeader.setUint16(o, fileNameBytes.length, true); o += 2
  localHeader.setUint16(o, 0, true); o += 2 // extra length
  new Uint8Array(localHeader.buffer, o, fileNameBytes.length).set(fileNameBytes); o += fileNameBytes.length

  const centralHeader = new DataView(new ArrayBuffer(46 + fileNameBytes.length))
  o = 0
  centralHeader.setUint32(o, 0x02014b50, true); o += 4 // central file header signature
  centralHeader.setUint16(o, 20, true); o += 2 // version made by
  centralHeader.setUint16(o, 20, true); o += 2 // version needed
  centralHeader.setUint16(o, 0, true); o += 2 // flags
  centralHeader.setUint16(o, 0, true); o += 2 // method
  centralHeader.setUint16(o, dosTime, true); o += 2
  centralHeader.setUint16(o, dosDate, true); o += 2
  centralHeader.setUint32(o, crc, true); o += 4
  centralHeader.setUint32(o, data.length, true); o += 4
  centralHeader.setUint32(o, data.length, true); o += 4
  centralHeader.setUint16(o, fileNameBytes.length, true); o += 2
  centralHeader.setUint16(o, 0, true); o += 2 // extra
  centralHeader.setUint16(o, 0, true); o += 2 // comment
  centralHeader.setUint16(o, 0, true); o += 2 // disk number
  centralHeader.setUint16(o, 0, true); o += 2 // internal attrs
  centralHeader.setUint32(o, 0, true); o += 4 // external attrs
  centralHeader.setUint32(o, 0, true); o += 4 // relative offset (after local header start)
  new Uint8Array(centralHeader.buffer, o, fileNameBytes.length).set(fileNameBytes); o += fileNameBytes.length

  const eocd = new DataView(new ArrayBuffer(22))
  o = 0
  eocd.setUint32(o, 0x06054b50, true); o += 4 // EOCD signature
  eocd.setUint16(o, 0, true); o += 2 // disk number
  eocd.setUint16(o, 0, true); o += 2 // start disk
  eocd.setUint16(o, 1, true); o += 2 // number of entries this disk
  eocd.setUint16(o, 1, true); o += 2 // total entries
  const centralSize = centralHeader.byteLength
  const centralOffset = localHeader.byteLength + data.length
  eocd.setUint32(o, centralSize, true); o += 4
  eocd.setUint32(o, centralOffset, true); o += 4
  eocd.setUint16(o, 0, true); o += 2 // comment length

  const out = new Uint8Array(localHeader.byteLength + data.length + centralSize + eocd.byteLength)
  out.set(new Uint8Array(localHeader.buffer), 0)
  out.set(data, localHeader.byteLength)
  out.set(new Uint8Array(centralHeader.buffer), localHeader.byteLength + data.length)
  out.set(new Uint8Array(eocd.buffer), localHeader.byteLength + data.length + centralSize)
  return new Blob([out], { type: 'application/zip' })
}

// 初始化
onMounted(() => {
  fetchExecutionDetail()
  // 初始化搜索文本和展开状态
  nextTick(() => {
    Object.keys(stepLogs.value).forEach(stepId => {
      if (!hostSearchTexts.value[stepId]) {
        hostSearchTexts.value[stepId] = ''
      }
      if (!logSearchTexts.value[stepId]) {
        logSearchTexts.value[stepId] = ''
      }
      // 默认不展开任何步骤
      if (expandedSteps.value[stepId] === undefined) {
        expandedSteps.value[stepId] = false
      }
    })
  })
})
</script>

<style scoped>
.execution-detail-container {
  padding: 16px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.info-card,
.realtime-card {
  margin-bottom: 16px;
}

.logs-card {
  margin-bottom: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.realtime-urls {
  margin-top: 16px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.empty-logs {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.log-text {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
  max-height: 600px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.step-list-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

/* 右侧主机日志内容 */
.host-logs-content {
  display: flex;
  flex-direction: column;
  background-color: #fff;
  overflow: hidden;
}

.selected-step-logs {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.step-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.step-info-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.step-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.step-order-tag, .step-status-tag {
  font-weight: 500;
  border-radius: 6px;
}

.step-actions {
  display: flex;
  align-items: center;
}

.step-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.host-log-content {
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.log-section {
  margin-bottom: 16px;
}

.log-section:last-child {
  margin-bottom: 0;
}

.log-section-header {
  padding: 8px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-section-header h5 {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
}

.log-text-container {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
}

.log-text {
  margin: 0;
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  height: 400px;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  border: none;
  border-radius: 0;
}

/* 日志滚动条样式 */
.log-text::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.log-text::-webkit-scrollbar-track {
  background-color: #2d2d2d;
  border-radius: 4px;
}

.log-text::-webkit-scrollbar-thumb {
  background-color: #555;
  border-radius: 4px;
}

.log-text::-webkit-scrollbar-thumb:hover {
  background-color: #777;
}

.error-section .log-text {
  background-color: #2d1b1b;
  color: #ff6b6b;
}

.no-logs, .no-step-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 主机标签页样式 */
.host-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.host-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 2px solid #e8e8e8;
  padding: 12px 20px 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.host-tabs :deep(.ant-tabs-nav-wrap) {
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: #d9d9d9 transparent;
  max-width: 100%;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar {
  height: 6px;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-track {
  background-color: transparent;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-thumb {
  background-color: #d9d9d9;
  border-radius: 3px;
}

.host-tabs :deep(.ant-tabs-nav-wrap)::-webkit-scrollbar-thumb:hover {
  background-color: #bfbfbf;
}

.host-tabs :deep(.ant-tabs-nav-list) {
  display: flex;
  flex-wrap: nowrap;
  min-width: 0;
}

.host-tabs :deep(.ant-tabs-tab) {
  margin-right: 12px;
  padding: 12px 24px;
  border-radius: 12px 12px 0 0;
  border: 2px solid #e8e8e8;
  background-color: #fff;
  transition: all 0.3s ease;
  white-space: nowrap;
  min-width: 160px;
  text-align: center;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.host-tabs :deep(.ant-tabs-tab:hover) {
  border-color: #40a9ff;
  color: #40a9ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(64, 169, 255, 0.3);
}

.host-tabs :deep(.ant-tabs-tab-active) {
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border-color: #1890ff;
  color: #fff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
}

.host-tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #fff;
}

.host-tabs :deep(.ant-tabs-content-holder) {
  flex: 1;
  overflow: hidden;
}

.host-tabs :deep(.ant-tabs-content) {
  height: 100%;
}

.host-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
  padding: 0;
}

/* 主机标签标题样式 */
.host-tab-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.host-name {
  font-weight: 600;
  font-size: 14px;
  color: inherit;
}

/* 失败主机复选框列表样式 */
.failed-hosts-list {
  padding: 16px;
}

.failed-hosts-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 8px 12px;
  background-color: var(--color-fill-1);
  border-radius: 6px;
}

.selected-info {
  font-size: 14px;
  color: var(--color-text-2);
  margin-left: 12px;
}

.failed-hosts-checkboxes {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-bg-1);
}

.failed-host-item {
  padding: 8px 12px;
  margin-bottom: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.failed-host-item:hover {
  background-color: var(--color-fill-1);
}

.selected-count {
  font-size: 14px;
  color: var(--color-text-2);
  margin-left: 12px;
  margin-right: 8px;
}

.host-status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
}

/* 根据主机状态调整标签样式 */
.host-tabs :deep(.host-tab-success .ant-tabs-tab) {
  border-color: #52c41a;
}

.host-tabs :deep(.host-tab-success.ant-tabs-tab-active) {
  background-color: #52c41a;
  border-color: #52c41a;
}

.host-tabs :deep(.host-tab-failed .ant-tabs-tab) {
  border-color: #ff4d4f;
}

.host-tabs :deep(.host-tab-failed.ant-tabs-tab-active) {
  background-color: #ff4d4f;
  border-color: #ff4d4f;
}

.host-tabs :deep(.host-tab-running .ant-tabs-tab) {
  border-color: #1890ff;
}

.host-tabs :deep(.host-tab-running.ant-tabs-tab-active) {
  background-color: #1890ff;
  border-color: #1890ff;
}

/* 主机信息头部样式 */
.host-info-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.host-info h5 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

/* 主机分组样式 */
.host-groups-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  background-color: #fafafa;
  min-height: 0;
  max-width: 100%;
}

.host-group {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 16px;
  overflow: visible;
  background-color: #fff;
}

.host-group:last-child {
  margin-bottom: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.host-group-header {
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.host-group-header:hover {
  background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
}

.group-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.group-status-tag {
  font-weight: 600;
  border-radius: 6px;
}

.group-count {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  transition: transform 0.2s;
  color: #666;
}

.expand-icon.rotate-180 {
  transform: rotate(180deg);
}

.host-group-content {
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 16px;
  background-color: #fafafa;
}

.no-hosts {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 150px;
  color: #999;
}

/* 步骤卡片头部样式 */
.step-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  cursor: pointer;
  transition: background-color 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-card-header:hover {
  background-color: #f8f9fa;
}

.step-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-order {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.step-name {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.step-summary {
  display: flex;
  align-items: center;
  gap: 16px;
}

.host-status-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
}

.status-item.success {
  color: #52c41a;
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.status-item.success .arco-icon {
  color: #52c41a;
}

.status-item.failed {
  color: #ff4d4f;
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.status-item.failed .arco-icon {
  color: #ff4d4f;
}

.status-item.running {
  color: #1890ff;
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.status-item.running .arco-icon {
  color: #1890ff;
}

.status-item.pending {
  color: #666;
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.status-item.pending .arco-icon {
  color: #666;
}

.step-actions {
  display: flex;
  align-items: center;
}

.step-expanded-content {
  padding: 16px;
  background-color: #fafafa;
}

.step-detail-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 执行流程布局样式 */
.execution-flow-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 900px;
}

/* 主容器：单栏或双栏布局 */
.execution-flow-container {
  display: flex;
  flex-direction: row;
  flex: 1;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.logs-card :deep(.arco-card-body) {
  display: flex;
  flex-direction: column;
  min-height: 960px;
}

/* 左侧：时间线侧边栏 */
.timeline-sidebar {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: all 0.3s ease;
  border-right: 1px solid #e8e8e8;
}

/* 当选中步骤时，左侧时间线收缩 */
.timeline-sidebar.collapsed {
  flex: 0 0 350px;
  min-width: 350px;
  max-width: 350px;
}

/* 右侧：日志详情面板 */
.logs-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background-color: #fff;
  overflow: hidden;
}

/* 流程头部 */
.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
  border-bottom: 2px solid #e8e8e8;
}

.timeline-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.timeline-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-text {
  font-size: 13px;
  color: #666;
  font-weight: 500;
  white-space: nowrap;
}

.progress-bar {
  width: 200px;
  height: 8px;
  background-color: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
  box-shadow: 0 2px 4px rgba(82, 196, 26, 0.3);
}

/* 垂直时间线主体 */
.vertical-timeline {
  flex: 1;
  padding: 24px 40px;
  overflow-y: auto;
  overflow-x: hidden;
  background-color: #fafafa;
}

.timeline-step-item {
  position: relative;
  display: flex;
  margin-bottom: 24px;
}

.timeline-step-item:last-child {
  margin-bottom: 0;
}

/* 时间线连接线 */
.timeline-connector {
  position: absolute;
  left: 20px;
  top: 40px; /* 从圆点底部开始（圆点高度40px） */
  width: 2px;
  height: calc(100% - 40px + 24px); /* 覆盖整个步骤项高度 + margin-bottom间距 */
  background-color: #e8e8e8;
  z-index: 0;
}

.timeline-connector.connector-success {
  background: linear-gradient(180deg, #52c41a 0%, #73d13d 100%);
}

.timeline-connector.connector-failed {
  background: linear-gradient(180deg, #ff4d4f 0%, #ff7875 100%);
  border-style: dashed;
}

.timeline-connector.connector-running {
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
  animation: flowAnimation 2s infinite;
}

.timeline-connector.connector-pending {
  background-color: #e8e8e8;
}

/* 时间线节点容器 */
.timeline-step-node {
  position: relative;
  display: flex;
  width: 100%;
  z-index: 1;
}

/* 时间线圆点 */
.timeline-dot {
  position: absolute;
  left: 0;
  top: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 3px solid;
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.timeline-dot.dot-success {
  border-color: #52c41a;
  background: linear-gradient(135deg, #f6ffed 0%, #ffffff 100%);
}

.timeline-dot.dot-failed {
  border-color: #ff4d4f;
  background: linear-gradient(135deg, #fff2f0 0%, #ffffff 100%);
}

.timeline-dot.dot-running {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #ffffff 100%);
  animation: dotPulse 2s infinite;
}

.timeline-dot.dot-pending {
  border-color: #d9d9d9;
  background: linear-gradient(135deg, #f5f5f5 0%, #ffffff 100%);
}

.dot-inner {
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-number {
  font-size: 14px;
  font-weight: 700;
  color: #262626;
}

.timeline-dot.dot-success .step-number {
  color: #52c41a;
}

.timeline-dot.dot-failed .step-number {
  color: #ff4d4f;
}

.timeline-dot.dot-running .step-number {
  color: #1890ff;
}

.timeline-dot.dot-pending .step-number {
  color: #666;
}

@keyframes dotPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(24, 144, 255, 0);
  }
}

/* 步骤卡片 */
.timeline-step-card {
  margin-left: 60px;
  width: calc(100% - 60px);
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  padding: 12px 16px;
}

.timeline-step-card:hover {
  border-color: #40a9ff;
  box-shadow: 0 4px 12px rgba(64, 169, 255, 0.15);
}

.timeline-step-card.step-active {
  border-color: #1890ff;
  box-shadow: 0 4px 16px rgba(24, 144, 255, 0.2);
}

.timeline-step-card.step-expanded {
  border-color: #1890ff;
  box-shadow: 0 4px 16px rgba(24, 144, 255, 0.2);
}

.timeline-step-card.step-success {
  border-left: 3px solid #52c41a;
}

.timeline-step-card.step-failed {
  border-left: 3px solid #ff4d4f;
}

.timeline-step-card.step-running {
  border-left: 3px solid #1890ff;
}

.timeline-step-card.step-pending {
  border-left: 3px solid #d9d9d9;
}

.step-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background-color: #fff;
  }

.step-card-content {
  flex: 1;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin: 0;
  flex: 1;
}

.step-status-tag {
  font-weight: 500;
  border-radius: 4px;
}

.step-meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #666;
}

.step-hosts {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-duration {
  color: #999;
}

.step-card-arrow {
  color: #999;
  transition: transform 0.3s ease;
}

.step-card-arrow .rotate-180 {
  transform: rotate(180deg);
}

/* 步骤详情内容 */
.step-detail-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #fff;
}

.step-detail-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.step-detail-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.step-detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-order-text {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.step-detail-actions {
  padding: 16px 0;
  border-bottom: 1px solid #e8e8e8;
}

/* 旧样式已移除，改用卡片式流程布局 */

/* 旧样式已移除，改用时间线布局 */

.step-item {
  margin-bottom: 8px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background-color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.step-item:hover {
  border-color: #40a9ff;
  box-shadow: 0 2px 8px rgba(64, 169, 255, 0.2);
  transform: translateY(-1px);
}

.step-item.step-active {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
  position: relative;
}

.step-item.step-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 2px;
}

.step-item-content {
  padding: 16px;
}

.step-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-order {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.step-status-tag {
  font-weight: 500;
}

.step-name {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 12px;
  line-height: 1.4;
}

.step-summary-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
}

.stat-item.success {
  color: #52c41a;
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.stat-item.success .arco-icon {
  color: #52c41a;
}

.stat-item.failed {
  color: #ff4d4f;
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.stat-item.failed .arco-icon {
  color: #ff4d4f;
}

.stat-item.running {
  color: #1890ff;
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.stat-item.running .arco-icon {
  color: #1890ff;
}

.stat-item.pending {
  color: #666;
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.stat-item.pending .arco-icon {
  color: #666;
}

.step-item-actions {
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
  background-color: #fafafa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-item-indicator {
  display: flex;
  align-items: center;
}

.step-status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #d9d9d9;
}

.step-status-indicator.status-success {
  background-color: #52c41a;
  box-shadow: 0 0 0 2px rgba(82, 196, 26, 0.2);
}

.step-status-indicator.status-failed {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.2);
}

.step-status-indicator.status-running {
  background-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
  animation: pulse 2s infinite;
}

.step-status-indicator.status-pending {
  background-color: #d9d9d9;
  box-shadow: 0 0 0 2px rgba(217, 217, 217, 0.2);
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.7);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(24, 144, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0);
  }
}

/* 步骤详情面板 */
.step-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  overflow: hidden;
  border-top: 1px solid #e8e8e8;
}

.no-step-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fafafa;
}

.step-detail-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.step-detail-header {
  padding: 20px;
  border-bottom: 1px solid #e8e8e8;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.step-detail-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.step-detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-order-text {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.step-detail-actions {
  display: flex;
  align-items: center;
}

/* 主机概览样式 */
.host-overview {
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  flex-shrink: 0;
}

.host-overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.host-overview-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.host-total {
  font-size: 12px;
  color: #666;
  background-color: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
}

.host-status-summary {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.status-summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  border-radius: 6px;
  background-color: #f8f9fa;
  border: 1px solid #e8e8e8;
  min-width: 50px;
}

.status-summary-item.success {
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.status-summary-item.success .arco-icon {
  color: #52c41a;
}

.status-summary-item.failed {
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.status-summary-item.failed .arco-icon {
  color: #ff4d4f;
}

.status-summary-item.running {
  background-color: #e6f7ff;
  border-color: #91d5ff;
}

.status-summary-item.running .arco-icon {
  color: #1890ff;
}

.status-summary-item.pending {
  background-color: #f5f5f5;
  border-color: #d9d9d9;
}

.status-summary-item.pending .arco-icon {
  color: #666;
}

.status-count {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
}

.status-label {
  font-size: 10px;
  color: #666;
  font-weight: 500;
}

/* 日志提示区域 */
.logs-prompt-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  padding: 40px 20px;
}

.prompt-content {
  text-align: center;
  max-width: 400px;
  padding: 30px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border: 1px solid #e8e8e8;
}

.prompt-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 20px;
  background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);
}

.prompt-content h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.prompt-content p {
  margin: 0;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

/* 日志详情区域 */
.logs-detail-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-bar {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  background-color: #fff;
  flex-shrink: 0;
}

/* 日志搜索高亮样式 */
.log-highlight {
  background-color: #ffeb3b;
  color: #000;
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: bold;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* 滚动条样式优化 */
.steps-list::-webkit-scrollbar,
.host-groups-container::-webkit-scrollbar {
  width: 6px;
}

.steps-list::-webkit-scrollbar-track,
.host-groups-container::-webkit-scrollbar-track {
  background-color: #f1f1f1;
  border-radius: 3px;
}

.steps-list::-webkit-scrollbar-thumb,
.host-groups-container::-webkit-scrollbar-thumb {
  background-color: #c1c1c1;
  border-radius: 3px;
}

.steps-list::-webkit-scrollbar-thumb:hover,
.host-groups-container::-webkit-scrollbar-thumb:hover {
  background-color: #a8a8a8;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .execution-flow-container {
    flex-direction: column;
    height: auto;
    min-height: 1000px;
  }

  .flow-step-card {
    min-width: 180px;
    max-width: 240px;
    padding: 12px 16px;
  }

  .step-icon-circle {
    width: 48px;
    height: 48px;
  }

  .step-number {
    font-size: 14px;
  }

  .step-title {
    font-size: 14px;
  }

  .host-status-summary {
    flex-wrap: wrap;
    gap: 12px;
  }

  .status-summary-item {
    min-width: 70px;
    padding: 8px 12px;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-detail-content {
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.disabled-option {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 日志放大模态框样式 */
.log-zoom-container {
  display: flex;
  flex-direction: column;
  height: 80vh;
}

.log-zoom-header {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0;
  border-bottom: 1px solid #e8e8e8;
  margin-bottom: 16px;
}

.log-zoom-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  background-color: #1e1e1e;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 16px;
  min-height: 0;
}

.log-zoom-content::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.log-zoom-content::-webkit-scrollbar-track {
  background-color: #2d2d2d;
  border-radius: 4px;
}

.log-zoom-content::-webkit-scrollbar-thumb {
  background-color: #555;
  border-radius: 4px;
}

.log-zoom-content::-webkit-scrollbar-thumb:hover {
  background-color: #777;
}

.log-zoom-text {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.5;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  background: transparent;
}

.log-zoom-text .highlight {
  background-color: #ffeb3b;
  color: #000;
  padding: 2px 4px;
  border-radius: 3px;
}

/* 步骤内容卡片 */
.step-content-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.step-content-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-content-card {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
}

.step-content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.step-content-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d1d1f;
}

.switch-label {
  font-size: 12px;
  color: #666;
}

.file-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.step-content-body.loading,
.step-content-body.error {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100px;
}

.script-block {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 10px;
  background: #fafafa;
}

.script-pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
}

.params-block .params-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  background: #fafafa;
}

.param-row--ip {
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}

.param-row--ip .param-key {
  min-width: auto;
}

.param-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.param-row-body {
  width: 100%;
}

.ip-list-collapse :deep(.arco-collapse-item-content) {
  padding: 0;
}

.param-key {
  min-width: 120px;
  font-weight: 600;
  color: #1d1d1f;
}

.param-value {
  flex: 1;
  color: #333;
  word-break: break-all;
}

.param-value.masked {
  color: #999;
  font-style: italic;
}

/* 操作记录 */
.operation-loading,
.operation-error {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 120px;
}

.operation-list .op-item {
  padding: 8px 0;
}

.op-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.op-user {
  color: #333;
}

.op-time {
  color: #888;
  font-size: 12px;
}

.op-desc {
  color: #1f1f1f;
  margin-bottom: 4px;
}

.op-extra {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: #666;
  font-size: 12px;
}

.op-extra-item {
  background: #f7f7f7;
  border-radius: 4px;
  padding: 2px 6px;
}

.op-pagination {
  margin-top: 12px;
  text-align: right;
}

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.global-parameters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--color-fill-1);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
}

.global-parameters .parameter-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-1);
  background: #fff;
  border-radius: 4px;
}

.global-parameters .param-key {
  font-weight: 500;
  color: var(--color-text-1);
  min-width: auto;
}

.global-parameters .param-value {
  padding: 4px 6px;
  font-size: 13px;
  word-break: break-all;
  background: var(--color-bg-2);
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.global-parameters .param-description {
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
}

.chain-loading,
.chain-error {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 120px;
}

.chain-section {
  margin-bottom: 16px;
}

.chain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.chain-header h4 {
  margin: 0;
  font-size: 16px;
  color: #1d1d1f;
}

.chain-path {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.chain-node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-card {
  width: 220px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
  padding: 10px 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.node-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.node-label {
  font-weight: 600;
  color: #1d1d1f;
}

.node-name {
  font-size: 13px;
  color: #1f1f1f;
  margin-bottom: 6px;
  word-break: break-word;
}

.node-meta {
  font-size: 12px;
  color: #86909c;
}

.node-actions {
  margin-top: 6px;
}

.chain-sublist {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fafafa;
}

.chain-subtitle {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
}

.chain-subitems {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chain-link {
  color: #165dff;
  padding: 0;
}

.chain-arrow {
  font-size: 18px;
  color: #86909c;
}

.chain-timeline {
  margin-top: 8px;
}

.chain-item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.chain-item-meta {
  font-size: 12px;
  color: #86909c;
}
</style>
