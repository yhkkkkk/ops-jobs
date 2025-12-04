<template>
  <div class="quick-execute">
    <div class="page-header">
      <h2>快速执行</h2>
      <a-space>
        <a-button @click="handleLoadTemplate" type="outline" v-if="activeTab === 'script'">
          <template #icon>
            <icon-file />
          </template>
          加载模板
        </a-button>
        <a-button @click="handleClear">
          <template #icon>
            <icon-refresh />
          </template>
          清空
        </a-button>
      </a-space>
    </div>

    <!-- 功能标签页 -->
    <a-tabs v-model:active-key="activeTab" class="mb-4">
      <a-tab-pane key="script" title="脚本执行">
        <template #title>
          <icon-code />
          脚本执行
        </template>
      </a-tab-pane>
      <a-tab-pane key="file" title="文件传输">
        <template #title>
          <icon-folder />
          文件传输
        </template>
      </a-tab-pane>
    </a-tabs>

    <a-row :gutter="16" v-if="activeTab === 'script'">
      <!-- 左侧：主机选择 -->
      <a-col :span="8">
        <a-card class="mb-4">
          <template #title>
            <div class="card-title-full">选择目标主机</div>
          </template>
          <template #extra>
            <a-space>
              <a-button type="primary" @click="showHostSelector = true">
                <template #icon>
                  <icon-computer />
                </template>
                选择主机
              </a-button>
            </a-space>
          </template>

          <!-- 选择摘要 -->
          <div class="host-selection-summary">
            <div v-if="selectedGroups.length === 0 && selectedHosts.length === 0" class="empty-selection">
              <div class="empty-icon">
                <icon-computer />
              </div>
              <div class="empty-text">请选择执行主机</div>
              <div class="empty-desc">点击上方"选择主机"按钮选择目标主机或主机分组</div>
            </div>
            
            <div v-else class="selection-content">
              <!-- 所有目标主机 -->
              <div class="selection-section">
                <div class="section-title">
                  <icon-computer />
                  目标主机 ({{ allTargetHosts.length }})
                  <div class="section-actions">
                    <a-button type="text" size="mini" @click="clearAllSelections">
                      <template #icon>
                        <icon-close />
                      </template>
                      清空
                    </a-button>
                    <a-button type="text" size="mini" @click="removeOfflineHosts">
                      <template #icon>
                        <icon-exclamation-circle />
                      </template>
                      清除异常
                    </a-button>
                  </div>
                </div>

                <!-- 所有目标主机列表 -->
                <div class="host-group-section">
                  <div class="host-list">
                    <div
                      v-for="host in allTargetHosts"
                      :key="`host-${host.id}`"
                      class="host-item"
                      :class="{ 'host-offline': host.status === 'offline' }"
                    >
                      <div class="host-info">
                        <div class="host-name">{{ host.name }}</div>
                        <div class="host-ip">{{ host.ip_address }}:{{ host.port }}</div>
                        <div class="host-meta">
                          <div class="host-os" :class="`os-${host.os_type}`">
                            {{ getOSText(host.os_type) }}
                          </div>
                          <div class="host-status" :class="`status-${host.status}`">
                            {{ getStatusText(host.status) }}
                          </div>
                        </div>
                        <div class="host-source">来自: {{ getHostGroupNames(host.id) }}</div>
                      </div>
                      <a-button
                        type="text"
                        size="mini"
                        @click.stop="removeHost(host.id)"
                        class="remove-host-btn"
                      >
                        <template #icon>
                          <icon-close />
                        </template>
                      </a-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-card>

        <!-- 执行参数 -->
        <a-card title="执行参数">
          <a-form layout="vertical">
            <a-form-item label="脚本类型">
              <a-select v-model="scriptType" @change="handleScriptTypeChange">
                <a-option value="shell">Shell</a-option>
                <a-option value="python">Python</a-option>
                <a-option value="powershell">PowerShell</a-option>
              </a-select>
            </a-form-item>

            <a-form-item label="超时时间(秒)">
              <a-input-number
                v-model="timeout"
                :min="10"
                :max="3600"
                style="width: 100%"
              />
            </a-form-item>

            <a-form-item label="执行方式">
              <a-radio-group v-model="executionMode">
                <a-radio value="parallel">并行执行</a-radio>
                <a-radio value="serial">串行执行</a-radio>
                <a-radio value="rolling">滚动执行</a-radio>
              </a-radio-group>
            </a-form-item>

            <!-- 滚动执行配置 -->
            <div v-if="executionMode === 'rolling'" class="rolling-config">
              <a-form-item label="滚动策略">
                <a-select v-model="rollingStrategy" style="width: 100%">
                  <a-option value="fail_pause">执行失败就暂停</a-option>
                  <a-option value="ignore_error">忽略错误继续执行</a-option>
                </a-select>
              </a-form-item>

              <a-form-item label="批次大小(%)">
                <a-input-number
                  v-model="rollingBatchSize"
                  :min="1"
                  :max="100"
                  style="width: 100%"
                  placeholder="每批次执行的主机百分比"
                />
                <template #help>
                  <div style="font-size: 12px; color: #666;">
                    按主机总数的百分比执行，当前将执行 {{ Math.ceil(allTargetHosts.length * rollingBatchSize / 100) }} 台主机/批次
                  </div>
                </template>
              </a-form-item>

              <a-form-item label="批次间延迟(秒)">
                <a-input-number
                  v-model="rollingBatchDelay"
                  :min="0"
                  :max="300"
                  style="width: 100%"
                  placeholder="批次间的等待时间"
                />
              </a-form-item>
            </div>

            <a-form-item label="执行引擎">
              <a-select v-model="executionEngine">
                <a-option value="fabric">Fabric (推荐)</a-option>
              </a-select>
              <template #help>
                <div style="font-size: 12px; color: #666;">
                  Fabric引擎提供稳定的SSH连接和真正的实时日志输出
                </div>
              </template>
            </a-form-item>

            <a-form-item label="执行账号">
              <a-select
                v-model="selectedAccountId"
                placeholder="选择服务器账号（可选）"
                allow-clear
                :loading="accountLoading"
              >
                <a-option
                  v-for="account in serverAccounts"
                  :key="account.id"
                  :value="account.id"
                >
                  {{ account.name }} ({{ account.username }})
                </a-option>
              </a-select>
              <div class="form-tip">
                <icon-info-circle />
                不选择时将使用主机配置的默认用户
              </div>
            </a-form-item>



            <!-- 位置参数 -->
            <a-form-item label="位置参数">
              <div class="parameter-list">
                <div
                  v-for="(arg, index) in positionalArgs"
                  :key="index"
                  class="parameter-item"
                >
                  <a-input
                    v-model="positionalArgs[index]"
                    :placeholder="`参数 ${index + 1}`"
                    style="flex: 1"
                  />
                  <a-button
                    type="text"
                    status="danger"
                    @click="removePositionalArg(index)"
                    style="margin-left: 8px"
                  >
                    <template #icon>
                      <icon-delete />
                    </template>
                  </a-button>
                </div>
                <a-button
                  type="dashed"
                  @click="addPositionalArg"
                  style="width: 100%; margin-top: 8px"
                >
                  <template #icon>
                    <icon-plus />
                  </template>
                  添加位置参数
                </a-button>
              </div>
              <div class="form-tip">
                <icon-info-circle />
                位置参数将按顺序传递给脚本，在脚本中可以使用 $1, $2, $3... 访问
              </div>
            </a-form-item>
          </a-form>
        </a-card>
      </a-col>

      <!-- 右侧：脚本编辑器 -->
      <a-col :span="16">
        <a-card title="脚本内容">
          <template #extra>
            <a-space>
              <a-select
                v-model="editorTheme"
                size="small"
                style="width: 120px"
                @change="handleThemeChange"
              >
                <a-option value="vs-dark">深色主题</a-option>
                <a-option value="vs">浅色主题</a-option>
              </a-select>
              <a-button size="small" @click="formatCode">
                <template #icon>
                  <icon-code />
                </template>
                格式化
              </a-button>
            </a-space>
          </template>

          <script-editor-with-validation
            ref="editorRef"
            v-model="scriptContent"
            :language="scriptType as 'shell' | 'python' | 'powershell'"
            :theme="editorTheme"
            :height="600"
            :readonly="false"
            :auto-validate="true"
            @validation-change="handleValidationChange"
          />

          <!-- 执行按钮 -->
          <div class="mt-4 text-center">
            <a-button
              type="primary"
              size="large"
              @click="handleExecute"
              :loading="executing"
              :disabled="!canExecute"
            >
              <template #icon>
                <icon-thunderbolt />
              </template>
              {{ hasValidationErrors ? '脚本有错误' : `立即执行 (${totalTargetCount} 个目标)` }}
            </a-button>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 文件传输界面 -->
    <a-row :gutter="16" v-if="activeTab === 'file'">
      <!-- 左侧：主机选择（完全复用脚本执行的组件） -->
      <a-col :span="8">
        <a-card class="mb-4">
          <template #title>
            <div class="card-title-full">选择目标主机</div>
          </template>
          <template #extra>
            <a-space>
              <a-button type="primary" @click="showHostSelector = true">
                <template #icon>
                  <icon-computer />
                </template>
                选择主机
              </a-button>
            </a-space>
          </template>

          <!-- 选择摘要 -->
          <div class="host-selection-summary">
            <div v-if="selectedGroups.length === 0 && selectedHosts.length === 0" class="empty-selection">
              <div class="empty-icon">
                <icon-computer />
              </div>
              <div class="empty-text">请选择目标主机</div>
              <div class="empty-desc">点击上方"选择主机"按钮选择目标主机或主机分组</div>
            </div>

            <div v-else class="selection-content">
              <!-- 所有目标主机（包含分组展开的主机和直接选择的主机） -->
              <div class="selection-section">
                <div class="section-title">
                  <icon-computer />
                  目标主机 ({{ allTargetHosts.length }})
                  <div class="section-actions">
                    <a-button type="text" size="mini" @click="clearAllSelections">
                      <template #icon>
                        <icon-close />
                      </template>
                      清空
                    </a-button>
                    <a-button type="text" size="mini" @click="removeOfflineHosts">
                      <template #icon>
                        <icon-exclamation-circle />
                      </template>
                      清除异常
                    </a-button>
                  </div>
                </div>

                <!-- 所有目标主机列表 -->
                <div class="host-group-section">
                  <div class="host-list">
                    <div
                      v-for="host in allTargetHosts"
                      :key="`host-${host.id}`"
                      class="host-item"
                      :class="{ 'host-offline': host.status === 'offline' }"
                    >
                      <div class="host-info">
                        <div class="host-name">{{ host.name }}</div>
                        <div class="host-ip">{{ host.ip_address }}:{{ host.port }}</div>
                        <div class="host-meta">
                          <div class="host-os" :class="`os-${host.os_type}`">
                            {{ getOSText(host.os_type) }}
                          </div>
                          <div class="host-status" :class="`status-${host.status}`">
                            {{ getStatusText(host.status) }}
                          </div>
                        </div>
                        <div class="host-source">来自: {{ getHostGroupNames(host.id) }}</div>
                      </div>
                      <a-button
                        type="text"
                        size="mini"
                        @click.stop="removeDirectHost(host.id)"
                        class="remove-host-btn"
                      >
                        <template #icon>
                          <icon-close />
                        </template>
                      </a-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：文件传输配置 -->
      <a-col :span="16">
        <a-card title="文件传输配置" class="mb-4">
          <a-form layout="vertical">
            <a-form-item label="传输类型">
              <a-radio-group v-model="transferType">
                <a-radio value="local_upload">从本地上传</a-radio>
                <a-radio value="server_upload">从服务器上传</a-radio>
              </a-radio-group>
            </a-form-item>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item :label="transferType === 'local_upload' ? '本地文件' : '源服务器配置'">
                  <!-- 从本地上传模式 -->
                  <div v-if="transferType === 'local_upload'" class="upload-container">
                    <a-upload
                      :file-list="fileList"
                      :auto-upload="false"
                      multiple
                      :show-upload-button="true"
                      :show-file-list="false"
                      :show-cancel-button="false"
                      :show-retry-button="false"
                      :show-upload-list-button="false"
                      @change="handleFileChange"
                      @remove="handleFileRemove"
                      class="file-upload"
                    >
                      <template #upload-button>
                        <div class="upload-btn">
                          <icon-plus />
                          <div class="upload-text">选择文件</div>
                        </div>
                      </template>
                    </a-upload>

                    <!-- 自定义文件列表 -->
                    <div v-if="fileList.length > 0" class="custom-file-list">
                      <div
                        v-for="(fileItem, index) in fileList"
                        :key="fileItem.uid || index"
                        class="custom-upload-list-item"
                      >
                        <div class="file-info">
                          <icon-file class="file-icon" />
                          <div class="file-details">
                            <div class="file-name">{{ fileItem.name }}</div>
                            <div class="file-size">{{ formatFileSize(fileItem.file?.size || 0) }}</div>
                          </div>
                        </div>
                        <div class="file-actions">
                          <a-button
                            type="text"
                            size="small"
                            @click="handleFileRemove(fileItem)"
                            class="remove-btn"
                          >
                            <template #icon>
                              <icon-delete />
                            </template>
                          </a-button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 从服务器上传模式 -->
                  <div v-else class="server-upload-container">
                    <a-space direction="vertical" style="width: 100%">
                      <a-input
                        v-model="sourceServerHost"
                        placeholder="源服务器地址，例如：192.168.1.100"
                        allow-clear
                      >
                        <template #prepend>服务器地址</template>
                      </a-input>
                      <a-input
                        v-model="sourceServerUser"
                        placeholder="SSH用户名，例如：root"
                        allow-clear
                      >
                        <template #prepend>用户名</template>
                      </a-input>
                      <a-input
                        v-model="sourceServerPath"
                        placeholder="源文件路径，例如：/data/files/app.tar.gz"
                        allow-clear
                      >
                        <template #prepend>文件路径</template>
                      </a-input>
                    </a-space>
                    <div class="path-examples">
                      <div class="example-title">配置示例：</div>
                      <div class="example-item">服务器: <code>192.168.1.100</code> 或 <code>file-server.company.com</code></div>
                      <div class="example-item">用户名: <code>root</code> 或 <code>deploy</code></div>
                      <div class="example-item">文件路径: <code>/data/releases/app-v1.2.3.tar.gz</code></div>
                    </div>
                  </div>

                  <template #extra>
                    <div class="text-xs text-gray-500">
                      {{ transferType === 'local_upload' ? '支持选择单个文件或多个文件' : '配置源服务器的SSH连接信息和文件路径' }}
                    </div>
                    <div v-if="transferType === 'local_upload' && localPath && hasVariables(localPath)" class="text-xs text-blue-600 mt-1">
                      预览: {{ previewPath(localPath) }}
                    </div>
                    <div v-if="transferType === 'server_upload' && sourceServerPath && hasVariables(sourceServerPath)" class="text-xs text-blue-600 mt-1">
                      预览: {{ previewPath(sourceServerPath) }}
                    </div>
                  </template>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="远程路径">
                  <a-input
                    v-model="remotePath"
                    placeholder="目标路径，例如：/opt/app/ 或 /var/www/[hostname]/app.tar.gz"
                    allow-clear
                  />
                  <template #extra>
                    <div class="text-xs text-gray-500">
                      文件保存到目标主机的路径，支持变量: /opt/app/[hostname]/ 或 /data/backup/[date]/
                    </div>
                    <div v-if="remotePath && hasVariables(remotePath)" class="text-xs text-blue-600 mt-1">
                      预览: {{ previewPath(remotePath) }}
                    </div>
                  </template>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item label="覆盖策略">
              <a-select v-model="overwritePolicy" style="width: 200px">
                <a-option value="overwrite">强制覆盖</a-option>
                <a-option value="skip">存在跳过</a-option>
                <a-option value="backup">备份后覆盖</a-option>
                <a-option value="fail">存在则失败</a-option>
              </a-select>
            </a-form-item>

            <!-- 传输配置 -->
            <a-row :gutter="16">
              <a-col :span="6">
                <a-form-item label="超时时间(秒)">
                  <a-input-number
                    v-model="timeout"
                    :min="10"
                    :max="3600"
                    style="width: 100%"
                    placeholder="传输超时时间"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="限速(KB/s)">
                  <a-input-number
                    v-model="bandwidthLimit"
                    :min="0"
                    :max="1000000"
                    style="width: 100%"
                    placeholder="0=不限速"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="执行模式">
                  <a-select v-model="executionMode" style="width: 100%">
                    <a-option value="parallel">并行执行</a-option>
                    <a-option value="serial">串行执行</a-option>
                    <a-option value="rolling">滚动执行</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="滚动策略" v-if="executionMode === 'rolling'">
                  <a-select v-model="rollingStrategy" style="width: 100%">
                    <a-option value="fail_pause">失败暂停</a-option>
                    <a-option value="ignore_error">忽略错误</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>

            <!-- 滚动执行配置 -->
            <a-row :gutter="16" v-if="executionMode === 'rolling'">
              <a-col :span="12">
                <a-form-item label="批次大小(%)">
                  <a-input-number
                    v-model="rollingBatchSize"
                    :min="1"
                    :max="100"
                    style="width: 100%"
                    placeholder="每批次主机百分比"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="批次延迟(秒)">
                  <a-input-number
                    v-model="rollingBatchDelay"
                    :min="0"
                    :max="300"
                    style="width: 100%"
                    placeholder="批次间延迟时间"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <!-- 通配符和变量使用说明 -->
            <a-alert
              type="info"
              show-icon
              closable
              class="mb-4"
            >
              <template #title>通配符和变量支持说明</template>
              <div class="text-sm">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p><strong>支持的通配符：</strong></p>
                    <ul class="list-disc list-inside mt-2 space-y-1">
                      <li><code>*</code> - 匹配任意数量的字符</li>
                      <li><code>?</code> - 匹配单个字符</li>
                      <li><code>[abc]</code> - 匹配方括号内的任意字符</li>
                      <li><code>[a-z]</code> - 匹配指定范围内的字符</li>
                    </ul>
                  </div>
                  <div>
                    <p><strong>支持的变量：</strong></p>
                    <ul class="list-disc list-inside mt-2 space-y-1 text-xs">
                      <li><code>[date]</code> - 当前日期 (2024-01-15)</li>
                      <li><code>[time]</code> - 当前时间 (14-30-25)</li>
                      <li><code>[datetime]</code> - 日期时间 (2024-01-15_14-30-25)</li>
                      <li><code>[timestamp]</code> - Unix时间戳</li>
                      <li><code>[year]</code> - 年份 (2024)</li>
                      <li><code>[month]</code> - 月份 (01)</li>
                      <li><code>[day]</code> - 日期 (15)</li>
                      <li><code>[hostname]</code> - 目标主机名</li>
                    </ul>
                    <p class="mt-2"><strong>高级变量：</strong></p>
                    <ul class="list-disc list-inside mt-1 space-y-1 text-xs">
                      <li><code>[date:YYYY/MM/DD]</code> - 自定义日期格式</li>
                      <li><code>[date-1]</code> - 昨天日期</li>
                      <li><code>[date+7]</code> - 7天后日期</li>
                    </ul>
                  </div>
                </div>
                <p class="mt-3"><strong>组合使用示例：</strong></p>
                <ul class="list-disc list-inside mt-1 space-y-1 text-xs">
                  <li><code>/var/log/app_[date]*.log</code> - 匹配今日的应用日志</li>
                  <li><code>/backup/[hostname]/db_backup_[datetime].sql</code> - 按主机和时间组织的备份</li>
                  <li><code>/data/[year]/[month]/report_[day]_*.xlsx</code> - 按日期层级组织的报表</li>
                  <li><code>/archive/logs_[date-1]_*.tar.gz</code> - 昨天的日志归档文件</li>
                  <li><code>/reports/[date:YYYY/MM]/daily_[date:DD].pdf</code> - 自定义格式的报表路径</li>
                  <li><code>/tmp/[hostname]_upload_[timestamp]_*.tmp</code> - 带主机名和时间戳的临时文件</li>
                </ul>
              </div>
            </a-alert>
          </a-form>

          <div class="text-right">
            <a-button
              type="primary"
              size="large"
              @click="handleFileTransfer"
              :loading="executing"
              :disabled="(selectedHosts.length === 0 && selectedGroups.length === 0) || !isTransferFormValid || !remotePath"
            >
              <template #icon>
                <icon-upload />
              </template>
              {{ transferType === 'local_upload' ? '上传文件' : '传输文件' }} ({{ totalTargetCount }} 个目标)
            </a-button>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 脚本模板选择弹窗 -->
    <a-modal
      v-model:visible="templateModalVisible"
      title="选择脚本模板"
      :width="800"
      @ok="handleTemplateSelect"
      @cancel="templateModalVisible = false"
    >
      <a-table
        :columns="templateColumns"
        :data="scriptTemplates"
        :loading="templateLoading"
        :pagination="false"
        row-key="id"
        :row-selection="{
          type: 'radio',
          selectedRowKeys: selectedTemplateKeys,
          onSelect: handleTemplateRowSelect,
          onSelectAll: handleTemplateRowSelectAll
        }"
        @row-click="handleRowClick"
      >
        <template #script_type="{ record }">
          <a-tag :color="getScriptTypeColor(record.script_type)">
            {{ getScriptTypeText(record.script_type) }}
          </a-tag>
        </template>
      </a-table>
    </a-modal>

    <!-- 执行确认弹窗 -->
    <a-modal
      v-model:visible="confirmModalVisible"
      title="确认执行"
      :width="800"
      @ok="handleConfirmExecute"
      @cancel="confirmModalVisible = false"
      :confirm-loading="executing"
      ok-text="确认执行"
      cancel-text="取消"
    >
      <a-alert
        type="warning"
        class="mb-4"
        show-icon
      >
        <template #title>
          <strong>请确认执行信息</strong>
        </template>
        脚本将在选中的主机上执行，请仔细检查脚本内容和目标主机。执行前请确保脚本内容正确无误。
      </a-alert>

      <a-descriptions :column="2" bordered size="small" class="mb-4">
        <a-descriptions-item label="脚本类型">
          <a-tag :color="getScriptTypeColor(scriptType)">
            {{ getScriptTypeText(scriptType) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行引擎">
          <a-tag color="blue">
            {{ executionEngine === 'fabric' ? 'Fabric (推荐)' : 'Paramiko' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行目标">
          <a-tag color="green">{{ allTargetHosts.length }} 台主机</a-tag>
          <span v-if="selectedGroups.length > 0" class="ml-2 text-gray-500">
            (来自 {{ selectedGroups.length }} 个分组{{ selectedHosts.length > 0 ? ' + ' + selectedHosts.length + ' 台直选主机' : '' }})
          </span>
          <span v-else-if="selectedHosts.length > 0" class="ml-2 text-gray-500">
            (直接选择)
          </span>
        </a-descriptions-item>
        <a-descriptions-item label="超时时间">
          <a-tag color="orange">{{ timeout }} 秒</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行账号">
          <div>
            <strong>{{ selectedAccount?.name || '默认账号' }}</strong>
            <span v-if="selectedAccount" class="text-gray-500 ml-2">
              ({{ selectedAccount.username }})
            </span>
          </div>
        </a-descriptions-item>
        <a-descriptions-item v-if="executionMode === 'rolling'" label="滚动策略">
          <a-tag color="blue">
            {{ getRollingStrategyText(rollingStrategy) }}
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <div class="script-preview-section">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-base font-medium text-gray-800 mb-0">脚本内容预览</h4>
          <a-tag color="gray" size="small">{{ scriptContent.split('\n').length }} 行</a-tag>
        </div>
        <div class="script-preview-container">
          <pre class="script-preview-content">{{ scriptContent }}</pre>
        </div>
      </div>
    </a-modal>
  </div>

  <!-- 主机选择器弹窗 -->
  <HostSelector
    v-model:visible="showHostSelector"
    :hosts="hosts"
    :groups="hostGroups"
    :selected-hosts="selectedHosts"
    :selected-groups="selectedGroups"
    @confirm="handleHostSelection"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { hostApi, hostGroupApi, scriptTemplateApi, quickExecuteApi } from '@/api/ops'
import { accountApi, type ServerAccount } from '@/api/account'
import HostSelector from '@/components/HostSelector.vue'
import type { Host, HostGroup, ScriptTemplate } from '@/types'
import ScriptEditorWithValidation from '@/components/ScriptEditorWithValidation.vue'
import { getScriptExample } from '@/components/ScriptExamples'
import type { ScriptValidationResult } from '@/utils/scriptValidator'

const router = useRouter()
const route = useRoute()

const editorRef = ref()
const executing = ref(false)

// 脚本验证状态
const validationResults = ref<ScriptValidationResult[]>([])
const hasValidationErrors = computed(() => {
  return validationResults.value.some(result => result.severity === 'error')
})
const templateLoading = ref(false)
const templateModalVisible = ref(false)
const confirmModalVisible = ref(false)

// 标签页
const activeTab = ref('script')

// 主机相关
const hosts = ref<Host[]>([])
const selectedHosts = ref<number[]>([])
const showHostSelector = ref(false)

// 主机分组相关
const hostGroups = ref<HostGroup[]>([])
const selectedGroups = ref<number[]>([])

// 服务器账号相关
const serverAccounts = ref<ServerAccount[]>([])
const selectedAccountId = ref<number | undefined>()
const accountLoading = ref(false)

// 脚本相关
const scriptContent = ref('')
const scriptType = ref('shell')
const editorTheme = ref('vs-dark')
const timeout = ref(300)
const executionEngine = ref('fabric')

// 执行方式相关
const executionMode = ref<'parallel' | 'serial' | 'rolling'>('parallel')
const rollingStrategy = ref<'fail_pause' | 'ignore_error'>('fail_pause')
const rollingBatchSize = ref(20) // 改为百分比，默认20%
const rollingBatchDelay = ref(0)

// 位置参数
const positionalArgs = ref<string[]>([''])

// 文件传输相关
const transferType = ref<'local_upload' | 'server_upload'>('local_upload')
const localPath = ref('')
const remotePath = ref('')
const overwritePolicy = ref<'overwrite' | 'skip' | 'backup' | 'fail'>('overwrite')
const bandwidthLimit = ref(0) // 带宽限制，0表示不限制
const fileList = ref<any[]>([]) // a-upload 的文件列表

// 服务器上传相关
const sourceServerHost = ref('')
const sourceServerUser = ref('')
const sourceServerPath = ref('')

// 模板相关
const scriptTemplates = ref<ScriptTemplate[]>([])
const selectedTemplateKeys = ref<number[]>([])

// 模板表格列
const templateColumns = [
  { title: '模板名称', dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'script_type', key: 'script_type', slotName: 'script_type' },
  { title: '描述', dataIndex: 'description', key: 'description' },
]

const totalGroupHosts = computed(() => {
  return selectedGroups.value.reduce((total, groupId) => {
    const group = hostGroups.value.find(g => g.id === groupId)
    return total + (group?.host_count || 0)
  }, 0)
})

const totalTargetCount = computed(() => {
  return allTargetHosts.value.length
})

const canExecute = computed(() => {
  return (selectedHosts.value.length > 0 || selectedGroups.value.length > 0) &&
         scriptContent.value.trim().length > 0 &&
         !hasValidationErrors.value
})

const selectedAccount = computed(() => {
  return serverAccounts.value.find(account => account.id === selectedAccountId.value)
})

// 获取所有目标主机（合并分组和直接选择的主机，去重）
const allTargetHosts = computed(() => {
  const allHostIds = new Set<number>()
  const result: any[] = []

  // 添加分组中的主机
  selectedGroups.value.forEach(groupId => {
    hosts.value.forEach(host => {
      if (host.groups_info && host.groups_info.some(g => g.id === groupId)) {
        if (!allHostIds.has(host.id)) {
          allHostIds.add(host.id)
          result.push(host)
        }
      }
    })
  })

  // 添加直接选择的主机
  selectedHosts.value.forEach(hostId => {
    if (!allHostIds.has(hostId)) {
      const host = hosts.value.find(h => h.id === hostId)
      if (host) {
        allHostIds.add(hostId)
        result.push(host)
      }
    }
  })

  return result
})

// 为了兼容模板，保留这些计算属性但基于 allTargetHosts
const groupHosts = computed(() => {
  const groupHostIds = new Set<number>()

  selectedGroups.value.forEach(groupId => {
    hosts.value.forEach(host => {
      if (host.groups_info && host.groups_info.some(g => g.id === groupId)) {
        groupHostIds.add(host.id)
      }
    })
  })

  return allTargetHosts.value.filter(host => groupHostIds.has(host.id) && !selectedHosts.value.includes(host.id))
})

const directHosts = computed(() => {
  return allTargetHosts.value.filter(host => selectedHosts.value.includes(host.id))
})

// 文件传输表单验证
const isTransferFormValid = computed(() => {
  if (transferType.value === 'local_upload') {
    return localPath.value.trim() !== ''
  } else if (transferType.value === 'server_upload') {
    return sourceServerHost.value.trim() !== '' &&
           sourceServerUser.value.trim() !== '' &&
           sourceServerPath.value.trim() !== ''
  }
  return false
})

const getHostStatus = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  return host?.status || 'unknown'
}

const getStatusText = (status: string) => {
  const statusMap = {
    'online': '在线',
    'offline': '离线',
    'unknown': '未知'
  }
  return statusMap[status as keyof typeof statusMap] || '未知'
}

const getOSText = (osType: string) => {
  const osMap = {
    'linux': 'Linux',
    'windows': 'Windows',
    'aix': 'AIX',
    'solaris': 'Solaris'
  }
  return osMap[osType as keyof typeof osMap] || osType
}

const getHostGroupNames = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  if (!host || !host.groups_info) return ''

  const selectedGroupNames = host.groups_info
    .filter(g => selectedGroups.value.includes(g.id))
    .map(g => g.name)

  return selectedGroupNames.join(', ')
}

// 获取主机列表
const fetchHosts = async () => {
  try {
    const response = await hostApi.getHosts({ page_size: 20 })
    hosts.value = response.results
  } catch (error) {
    console.error('获取主机列表失败:', error)
    hosts.value = []
  }
}

// 获取主机分组列表
const fetchHostGroups = async () => {
  console.log('QuickExecute - 开始获取主机分组数据')
  try {
    const response = await hostGroupApi.getGroups({ page_size: 50 })
    console.log('QuickExecute - API响应:', response)
    hostGroups.value = response.results
    console.log('QuickExecute - 获取到主机分组数据:', hostGroups.value)
    console.log('QuickExecute - 分组数据类型:', typeof hostGroups.value)
    console.log('QuickExecute - 分组数据长度:', hostGroups.value?.length)
    if (hostGroups.value && hostGroups.value.length > 0) {
      console.log('QuickExecute - 第一个分组:', hostGroups.value[0])
    }
  } catch (error) {
    console.error('获取主机分组失败:', error)
    hostGroups.value = []
  }
}

// 获取服务器账号列表
const fetchServerAccounts = async () => {
  try {
    accountLoading.value = true
    const response = await accountApi.getAccounts({ page_size: 20 })
    serverAccounts.value = response.results || []
  } catch (error) {
    console.error('获取服务器账号列表失败:', error)
  } finally {
    accountLoading.value = false
  }
}

// 获取脚本模板列表（用于导入，只显示启用的模板）
const fetchScriptTemplates = async () => {
  console.log('开始获取脚本模板列表')
  templateLoading.value = true
  try {
    const response = await scriptTemplateApi.getTemplatesForImport({ page_size: 20 })
    scriptTemplates.value = response.results
    console.log('成功获取脚本模板:', response.results)
  } catch (error) {
    console.error('获取脚本模板失败:', error)
    scriptTemplates.value = []
  } finally {
    templateLoading.value = false
    console.log('模板加载完成，loading状态:', templateLoading.value)
  }
}

// 路径变量预览功能
const hasVariables = (path: string) => {
  return path && path.includes('[')
}

const previewPath = (path: string) => {
  if (!path) return ''

  const now = new Date()
  const variables = {
    '[date]': now.toISOString().split('T')[0],
    '[time]': now.toTimeString().split(' ')[0].replace(/:/g, '-'),
    '[datetime]': `${now.toISOString().split('T')[0]}_${now.toTimeString().split(' ')[0].replace(/:/g, '-')}`,
    '[timestamp]': Math.floor(now.getTime() / 1000).toString(),
    '[year]': now.getFullYear().toString(),
    '[month]': (now.getMonth() + 1).toString().padStart(2, '0'),
    '[day]': now.getDate().toString().padStart(2, '0'),
    '[hour]': now.getHours().toString().padStart(2, '0'),
    '[minute]': now.getMinutes().toString().padStart(2, '0'),
    '[second]': now.getSeconds().toString().padStart(2, '0'),
    '[hostname]': 'example-host',
    '[host_ip]': '192.168.1.100',
  }

  let result = path

  // 处理日期偏移 [date-1], [date+7]
  const offsetPattern = /\[date([+-]\d+)\]/g
  result = result.replace(offsetPattern, (match, offset) => {
    const targetDate = new Date(now)
    targetDate.setDate(targetDate.getDate() + parseInt(offset))
    return targetDate.toISOString().split('T')[0]
  })

  // 处理自定义日期格式 [date:YYYY/MM/DD]
  const customDatePattern = /\[date:([^\]]+)\]/g
  result = result.replace(customDatePattern, (match, format) => {
    let formatStr = format
      .replace(/YYYY/g, now.getFullYear().toString())
      .replace(/MM/g, (now.getMonth() + 1).toString().padStart(2, '0'))
      .replace(/DD/g, now.getDate().toString().padStart(2, '0'))
      .replace(/HH/g, now.getHours().toString().padStart(2, '0'))
      .replace(/mm/g, now.getMinutes().toString().padStart(2, '0'))
      .replace(/SS/g, now.getSeconds().toString().padStart(2, '0'))
    return formatStr
  })

  // 替换基础变量
  for (const [variable, value] of Object.entries(variables)) {
    result = result.replace(new RegExp(variable.replace(/[[\]]/g, '\\$&'), 'g'), value)
  }

  return result
}

// 主机选择操作已移至 HostSelector 组件

// 位置参数操作
const addPositionalArg = () => {
  positionalArgs.value.push('')
}

const removePositionalArg = (index: number) => {
  if (positionalArgs.value.length > 1) {
    positionalArgs.value.splice(index, 1)
  } else {
    positionalArgs.value[0] = ''
  }
}

// 脚本操作
const handleScriptTypeChange = () => {
  // 如果当前内容是示例代码或为空，则自动替换为新类型的示例
  const currentContent = scriptContent.value.trim()
  const shouldReplace = !currentContent || isExampleContent(currentContent)

  if (shouldReplace) {
    insertExample()
  }
}

// 检查是否是示例内容
const isExampleContent = (content: string) => {
  // 检查内容是否包含示例代码的特征
  const exampleMarkers = [
    'job_start',
    'job_success',
    'job_fail',
    '作业平台中执行脚本成功和失败的标准',
    '可在此处开始编写您的脚本逻辑代码',
  ]

  return exampleMarkers.some(marker => content.includes(marker))
}

const handleThemeChange = () => {
  console.log('主题切换为:', editorTheme.value)
}

const formatCode = () => {
  if (editorRef.value) {
    editorRef.value.formatCode()
  }
}

// 处理脚本验证结果变化
const handleValidationChange = (results: ScriptValidationResult[]) => {
  validationResults.value = results
  const errorCount = results.filter(r => r.severity === 'error').length
  const warningCount = results.filter(r => r.severity === 'warning').length
  
  if (errorCount > 0) {
    Message.warning(`脚本中发现 ${errorCount} 个错误，${warningCount} 个警告`)
  } else if (warningCount > 0) {
    Message.info(`脚本中发现 ${warningCount} 个警告`)
  }
}

const insertExample = () => {
  scriptContent.value = getScriptExample(scriptType.value)
  console.log('插入示例代码:', scriptType.value)
}

// 模板操作
const handleLoadTemplate = async () => {
  console.log('点击加载模板按钮')
  try {
    await fetchScriptTemplates()
    templateModalVisible.value = true
    console.log('模板弹窗应该显示:', templateModalVisible.value)
  } catch (error) {
    console.error('加载模板失败:', error)
  }
}

// 处理模板行选择
const handleTemplateRowSelect = (selectedRowKeys: number[], selectedRows: any[]) => {
  selectedTemplateKeys.value = selectedRowKeys
  console.log('选择的模板:', selectedRowKeys, selectedRows)
}

// 处理全选（单选模式下不会触发）
const handleTemplateRowSelectAll = () => {
  // 单选模式下不需要处理
}

// 处理行点击
const handleRowClick = (record: any) => {
  selectedTemplateKeys.value = [record.id]
  console.log('点击行选择模板:', record.id, record.name)
}

const handleTemplateSelect = () => {
  if (selectedTemplateKeys.value.length > 0) {
    const template = scriptTemplates.value.find(t => t.id === selectedTemplateKeys.value[0])
    if (template) {
      // 使用正确的字段名
      scriptContent.value = template.script_content || template.content || ''
      scriptType.value = template.script_type
      Message.success(`已加载模板: ${template.name}`)
    }
  } else {
    Message.warning('请选择一个模板')
    return
  }
  templateModalVisible.value = false
  selectedTemplateKeys.value = []
}

// 文件大小格式化函数
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// a-upload 文件操作方法
const handleFileChange = (files: any[]) => {
  // 更新文件列表
  fileList.value = files

  // 更新localPath用于后端处理
  if (files.length === 0) {
    localPath.value = ''
  } else if (files.length === 1) {
    localPath.value = files[0].name
  } else {
    localPath.value = files.map((f: any) => f.name).join(';')
  }
}

const handleFileRemove = (fileItem: any) => {
  // 手动更新文件列表（因为我们使用自定义文件列表）
  const remainingFiles = fileList.value.filter(f => f.uid !== fileItem.uid)
  fileList.value = remainingFiles

  // 更新localPath
  if (remainingFiles.length === 0) {
    localPath.value = ''
  } else if (remainingFiles.length === 1) {
    localPath.value = remainingFiles[0].name
  } else {
    localPath.value = remainingFiles.map((f: any) => f.name).join(';')
  }
}

// 文件选择相关函数
const handleSelectLocalPath = () => {
  if (transferType.value === 'local_upload') {
    // 本地上传模式：选择文件
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.webkitdirectory = false  // 只允许选择文件
    input.style.display = 'none'
    
    input.onchange = (e) => {
      const files = Array.from((e.target as HTMLInputElement).files || [])
      if (files.length > 0) {
        // 使用第一个文件的相对路径来推断目录
        const firstFile = files[0]
        const relativePath = firstFile.webkitRelativePath || firstFile.name
        const dirPath = relativePath.substring(0, relativePath.lastIndexOf('/'))
        localPath.value = dirPath || '已选择目录'
        Message.success('已选择保存目录')
      }
    }
    
    document.body.appendChild(input)
    input.click()
    document.body.removeChild(input)
  } else {
    // 服务器上传模式：提示用户配置服务器信息
    Message.info('请在上方配置源服务器的连接信息和文件路径')
  }
}

// 文件传输相关函数
const handleFileTransfer = async () => {
  if (selectedHosts.value.length === 0 && selectedGroups.value.length === 0) {
    Message.warning('请选择至少一台主机或一个主机分组')
    return
  }

  if (!localPath.value || !remotePath.value) {
    Message.warning('请填写本地路径和远程路径')
    return
  }

  executing.value = true
  try {
    // 构建目标列表
    const targets: any[] = []
    
    // 添加选中的主机
    selectedHosts.value.forEach(hostId => {
      targets.push({ type: 'host', id: hostId })
    })
    
    // 添加选中的分组
    selectedGroups.value.forEach(groupId => {
      targets.push({ type: 'group', id: groupId })
    })

    // 构建请求数据
    const data = {
      name: `快速文件${transferType.value === 'local_upload' ? '上传' : '传输'}`,
      transfer_type: transferType.value,
      local_path: transferType.value === 'local_upload' ? localPath.value : '',
      remote_path: remotePath.value,
      overwrite_policy: overwritePolicy.value,
      timeout: timeout.value,  // 添加超时配置
      bandwidth_limit: bandwidthLimit.value || null,  // 添加带宽限制
      execution_mode: executionMode.value,  // 添加执行模式
      rolling_strategy: rollingStrategy.value,  // 添加滚动策略
      rolling_batch_size: rollingBatchSize.value,  // 添加批次大小
      rolling_batch_delay: rollingBatchDelay.value,  // 添加批次延迟
      targets: targets,
      // 服务器上传相关参数
      source_server_host: transferType.value === 'server_upload' ? sourceServerHost.value : '',
      source_server_user: transferType.value === 'server_upload' ? sourceServerUser.value : '',
      source_server_path: transferType.value === 'server_upload' ? sourceServerPath.value : '',
    }

    console.log('文件传输请求数据:', data)

    const result = await quickExecuteApi.transferFile(data)
    Message.success(`文件传输任务已启动，任务ID: ${result.task_id}`)

    // 跳转到执行记录页面
    router.push(`/execution-records/${result.execution_record_id}`)
  } catch (error) {
    console.error('文件传输失败:', error)
    Message.error('文件传输失败，请检查网络连接或联系管理员')
  } finally {
    executing.value = false
  }
}

// 清空操作
const handleClear = () => {
  // 清空脚本相关
  scriptContent.value = ''
  timeout.value = 300
  selectedAccountId.value = undefined
  positionalArgs.value = ['']

  // 清空执行方式相关
  executionMode.value = 'parallel'
  rollingStrategy.value = 'fail_pause'
  rollingBatchSize.value = 20
  rollingBatchDelay.value = 0

  // 清空文件传输相关
  transferType.value = 'local_upload'
  localPath.value = ''
  remotePath.value = ''
  overwritePolicy.value = 'overwrite'
  bandwidthLimit.value = 0
  fileList.value = [] // 清空文件列表

  // 清空服务器上传相关
  sourceServerHost.value = ''
  sourceServerUser.value = ''
  sourceServerPath.value = ''

  // 清空主机和分组选择
  selectedHosts.value = []
  selectedGroups.value = []

  Message.success('已清空所有内容')
}

// 执行操作
const handleExecute = () => {
  if (!canExecute.value) {
    if (hasValidationErrors.value) {
      Message.error('脚本存在错误，请修复后再执行')
    } else {
      Message.warning('请选择目标主机或分组并输入脚本内容')
    }
    return
  }

  confirmModalVisible.value = true
}

const handleConfirmExecute = async () => {
  executing.value = true
  try {
    // 过滤空的位置参数
    const filteredPositionalArgs = positionalArgs.value.filter(arg => arg.trim() !== '')

    // 获取所有选中的主机ID（包括分组内的主机）
    const allSelectedHostIds = new Set(selectedHosts.value)
    
    // 将分组内的主机也添加到集合中（去重）
    // 通过主机数据中的分组信息来查找
    selectedGroups.value.forEach(groupId => {
      hosts.value.forEach(host => {
        if (host.groups_info && Array.isArray(host.groups_info)) {
          const isInGroup = host.groups_info.some(g => g && g.id === groupId)
          if (isInGroup) {
            allSelectedHostIds.add(host.id)
          }
        }
      })
    })

    const data = {
      target_host_ids: Array.from(allSelectedHostIds),
      script_content: scriptContent.value,
      script_type: scriptType.value,
      timeout: timeout.value,
      use_fabric: executionEngine.value === 'fabric',
      execution_mode: executionMode.value,
      rolling_strategy: rollingStrategy.value,
      rolling_batch_size: rollingBatchSize.value,
      rolling_batch_delay: rollingBatchDelay.value,
      positional_args: filteredPositionalArgs,
      global_variables: {
        execute_user: selectedAccount.value?.username || '',
        account_id: selectedAccountId.value,
      },
    }

    const result = await quickExecuteApi.execute(data)
    Message.success('脚本执行已启动')

    // 跳转到执行记录详情页面
    router.push(`/execution-records/${result.execution_record_id}`)
  } catch (error) {
    console.error('执行失败:', error)
  } finally {
    executing.value = false
    confirmModalVisible.value = false
  }
}

// 主机状态检查功能已移至 HostSelector 组件

const getScriptTypeColor = (type: string) => {
  const colors = {
    shell: 'blue',
    python: 'green',
    powershell: 'purple',
  }
  return colors[type] || 'gray'
}

const getScriptTypeText = (type: string) => {
  const texts = {
    shell: 'Shell',
    python: 'Python',
    powershell: 'PowerShell',
  }
  return texts[type] || type
}

const getRollingStrategyText = (strategy: string) => {
  const texts = {
    fail_pause: '执行失败就暂停',
    ignore_error: '忽略错误继续执行',
  }
  return texts[strategy] || strategy
}

// 主机选择处理方法
const handleHostSelection = (selection: { selectedHosts: number[], selectedGroups: number[] }) => {
  selectedHosts.value = selection.selectedHosts
  selectedGroups.value = selection.selectedGroups
  console.log('主机选择完成:', selection)
}

// 主机管理方法
const clearAllSelections = () => {
  selectedHosts.value = []
  selectedGroups.value = []
  Message.success('已清空所有选择')
}

// 统一的主机移除方法
const removeHost = (hostId: number) => {
  const host = hosts.value.find(h => h.id === hostId)
  if (!host) return

  // 从直接选择列表中移除
  const directIndex = selectedHosts.value.indexOf(hostId)
  if (directIndex > -1) {
    selectedHosts.value.splice(directIndex, 1)
  }

  // 检查主机是否来自分组，如果是，则从分组中移除该主机
  if (host.groups_info && host.groups_info.length > 0) {
    // 找到包含此主机的分组
    const hostGroupIds = host.groups_info.map(g => g.id)
    const affectedGroups = selectedGroups.value.filter(groupId => hostGroupIds.includes(groupId))

    if (affectedGroups.length > 0) {
      // 如果主机来自选中的分组，我们需要将其他主机添加到直接选择中，然后移除分组
      affectedGroups.forEach(groupId => {
        // 获取该分组的所有其他主机
        const groupOtherHosts = hosts.value.filter(h =>
          h.id !== hostId &&
          h.groups_info &&
          h.groups_info.some(g => g.id === groupId)
        )

        // 将其他主机添加到直接选择中
        groupOtherHosts.forEach(otherHost => {
          if (!selectedHosts.value.includes(otherHost.id)) {
            selectedHosts.value.push(otherHost.id)
          }
        })

        // 从分组选择中移除该分组
        const groupIndex = selectedGroups.value.indexOf(groupId)
        if (groupIndex > -1) {
          selectedGroups.value.splice(groupIndex, 1)
        }
      })
    }
  }

  Message.success(`已移除主机: ${host.name}`)
}

// 为了兼容现有模板，保留这两个方法但都调用统一的 removeHost
const removeHostFromGroup = (hostId: number) => {
  removeHost(hostId)
}

const removeDirectHost = (hostId: number) => {
  removeHost(hostId)
}

const removeOfflineHosts = () => {
  const offlineHosts = allTargetHosts.value.filter(host => host.status === 'offline')
  if (offlineHosts.length === 0) {
    Message.info('没有找到离线主机')
    return
  }

  // 逐个移除离线主机
  offlineHosts.forEach(host => {
    removeHost(host.id)
  })

  Message.success(`已移除 ${offlineHosts.length} 台离线主机`)
}

// 生命周期
onMounted(() => {
  // 如果从脚本模板版本管理跳转而来，预填脚本内容
  try {
    const stored = sessionStorage.getItem('quickExecuteScriptData')
    if (stored) {
      const data = JSON.parse(stored)
      if (data.script_content) {
        scriptContent.value = data.script_content
      }
      if (data.script_type) {
        scriptType.value = data.script_type
      }
      // 清除一次性数据
      sessionStorage.removeItem('quickExecuteScriptData')
    }
  } catch (e) {
    console.error('预填脚本数据解析失败:', e)
  }

  fetchHosts()
  fetchHostGroups()
  fetchServerAccounts()
  insertExample() // 默认插入示例代码
})
</script>

<style scoped>
.quick-execute {
  padding: 0;
}

/* 卡片标题完整显示 */
.card-title-full {
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
}

/* 主机选择摘要样式 */
.host-selection-summary {
  min-height: 120px;
}

.empty-selection {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  text-align: center;
}

.empty-icon {
  font-size: 32px;
  color: #c9cdd4;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 14px;
  color: #4e5969;
  font-weight: 500;
  margin-bottom: 4px;
}

.empty-desc {
  font-size: 12px;
  color: #86909c;
  line-height: 1.4;
}

.selection-content {
  padding: 16px 0;
}

.selection-section {
  margin-bottom: 16px;
}

.selection-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #4e5969;
  margin-bottom: 8px;
}

.section-actions {
  display: flex;
  gap: 4px;
}

.selection-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.selection-stats {
  font-size: 12px;
  color: #86909c;
}

.selection-total {
  padding-top: 12px;
  border-top: 1px solid #e5e6eb;
  text-align: center;
}

/* 主机列表样式 */
.host-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.host-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  transition: all 0.2s;
}

.host-item:hover {
  background-color: var(--color-fill-2);
  border-color: var(--color-border-3);
}

.host-item.host-offline {
  background-color: var(--color-danger-light-1);
  border-color: var(--color-danger-light-3);
}

.host-info {
  flex: 1;
  min-width: 0;
}

.host-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1);
  margin-bottom: 2px;
}

.host-ip {
  font-size: 11px;
  color: var(--color-text-3);
  font-family: 'Courier New', monospace;
  margin-bottom: 4px;
}

.host-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 2px;
}

.host-os {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
  background-color: var(--color-fill-3);
  color: var(--color-text-2);
}

.os-linux {
  background-color: var(--color-blue-light-1);
  color: var(--color-blue);
}

.os-windows {
  background-color: var(--color-cyan-light-1);
  color: var(--color-cyan);
}

.os-aix {
  background-color: var(--color-purple-light-1);
  color: var(--color-purple);
}

.os-solaris {
  background-color: var(--color-orange-light-1);
  color: var(--color-orange);
}

.host-status {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
}

.status-online {
  background-color: var(--color-success-light-1);
  color: var(--color-success);
}

.status-offline {
  background-color: var(--color-danger-light-1);
  color: var(--color-danger);
}

.status-unknown {
  background-color: var(--color-warning-light-1);
  color: var(--color-warning);
}

.remove-host-btn {
  color: var(--color-text-3);
  flex-shrink: 0;
}

.remove-host-btn:hover {
  color: var(--color-danger);
}

/* 主机分组样式 */
.host-group-section {
  margin-bottom: 16px;
}

.host-group-section:last-child {
  margin-bottom: 0;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-2);
  margin-bottom: 8px;
  padding: 4px 8px;
  background-color: var(--color-fill-2);
  border-radius: 4px;
}

.host-source {
  font-size: 10px;
  color: var(--color-text-4);
  font-style: italic;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.mb-4 {
  margin-bottom: 16px;
}

.mb-3 {
  margin-bottom: 12px;
}

.mt-3 {
  margin-top: 12px;
}

.mt-4 {
  margin-top: 16px;
}

.form-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

.pt-3 {
  padding-top: 12px;
}

.border-t {
  border-top: 1px solid #e5e7eb;
}

.host-list {
  max-height: 300px;
  overflow-y: auto;
}

.host-item {
  padding: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background-color: #fafafa;
  margin-bottom: 8px;
}

.host-item:hover {
  background-color: #f0f0f0;
}

.host-item:last-child {
  margin-bottom: 0;
}

.host-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.host-name {
  font-weight: 500;
  font-size: 14px;
}

.host-ip {
  font-size: 12px;
  color: #6b7280;
}

.space-y-2 > * + * {
  margin-top: 8px;
}

.space-x-2 > * + * {
  margin-left: 8px;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.justify-between {
  justify-content: space-between;
}

.w-full {
  width: 100%;
}

.font-medium {
  font-weight: 500;
}

.text-sm {
  font-size: 12px;
}

.text-gray-500 {
  color: #6b7280;
}

.text-gray-600 {
  color: #4b5563;
}

.bg-gray-100 {
  background-color: #f3f4f6;
}

.p-3 {
  padding: 12px;
}

.rounded {
  border-radius: 6px;
}

.max-h-32 {
  max-height: 8rem;
}

.overflow-auto {
  overflow: auto;
}

:deep(.arco-checkbox-group) {
  width: 100%;
}

:deep(.arco-checkbox) {
  width: 100%;
  margin-right: 0;
}

/* 位置参数样式 */
.parameter-list {
  width: 100%;
}

.parameter-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

/* 文件路径选择样式 */
.path-selection-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.path-select-btn {
  width: 100%;
}

.path-input {
  width: 100%;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

.path-input :deep(.arco-textarea) {
  width: 100%;
  min-width: 300px;
}

.path-input :deep(.arco-textarea) {
  background-color: #f8f9fa;
  border: 1px solid #e5e6eb;
}

.path-input :deep(.arco-textarea:focus) {
  background-color: #fff;
  border-color: #165dff;
}

/* 文件上传样式 */
.upload-container {
  width: 100%;
}

.file-upload {
  width: 100%;
}

/* 服务器上传样式 */
.server-upload-container {
  width: 100%;
}

/* 自定义文件列表容器 */
.custom-file-list {
  margin-top: 12px;
}

/* 自定义文件列表样式 */
.custom-upload-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
  margin-bottom: 8px;
}

.file-info {
  display: flex;
  align-items: center;
  flex: 1;
}

.file-icon {
  font-size: 16px;
  color: var(--color-text-3);
  margin-right: 8px;
}

.file-details {
  flex: 1;
}

.file-name {
  font-size: 14px;
  color: var(--color-text-1);
  font-weight: 500;
  margin-bottom: 2px;
}

.file-size {
  font-size: 12px;
  color: var(--color-text-3);
}

.file-actions {
  display: flex;
  align-items: center;
}

.remove-btn {
  color: var(--color-text-3);
  transition: color 0.3s;
}

.remove-btn:hover {
  color: var(--color-danger-6);
}

.upload-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  border: 2px dashed var(--color-border-2);
  border-radius: 6px;
  background-color: var(--color-fill-1);
  cursor: pointer;
  transition: all 0.3s;
}

.upload-btn:hover {
  border-color: var(--color-primary-light-4);
  background-color: var(--color-primary-light-1);
}

.upload-text {
  margin-top: 8px;
  font-size: 14px;
  color: var(--color-text-2);
}

/* 路径示例样式 */
.path-examples {
  padding: 8px 12px;
  background-color: var(--color-fill-1);
  border-radius: 4px;
  border: 1px solid var(--color-border-2);
  margin-top: 8px;
}

.example-title {
  font-size: 12px;
  color: var(--color-text-2);
  font-weight: 500;
  margin-bottom: 4px;
}

.example-item {
  color: var(--color-text-2);
  margin-bottom: 2px;
  font-size: 12px;
}

.example-item code {
  background-color: var(--color-fill-3);
  padding: 2px 4px;
  border-radius: 2px;
  font-family: 'Courier New', monospace;
  font-size: 11px;
}

/* 脚本预览样式 */
.script-preview-section {
  margin-top: 16px;
}

.script-preview-container {
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background-color: #f8f9fa;
  overflow: hidden;
}

.script-preview-content {
  margin: 0;
  padding: 16px;
  background-color: #f8f9fa;
  color: #333;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.script-preview-content::-webkit-scrollbar {
  width: 6px;
}

.script-preview-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.script-preview-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.script-preview-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.example-item {
  font-size: 11px;
  color: var(--color-text-3);
  margin-bottom: 2px;
}

.example-item code {
  background-color: var(--color-fill-2);
  padding: 1px 4px;
  border-radius: 2px;
  font-family: 'Courier New', monospace;
  font-size: 10px;
}
</style>
