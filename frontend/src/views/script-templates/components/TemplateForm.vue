<template>
  <div class="template-form">
    <a-form
      ref="formRef"
      :model="form"
      :rules="rules"
      layout="vertical"
    >
      <a-row :gutter="16">
        <!-- 左侧：基本信息 -->
        <a-col :span="8">
          <a-card title="基本信息" class="mb-4">
            <a-form-item label="模板名称" field="name">
              <a-input
                v-model="form.name"
                placeholder="请输入模板名称"
                allow-clear
              />
            </a-form-item>

            <a-form-item label="脚本类型" field="script_type">
              <a-select
                v-model="form.script_type"
                placeholder="请选择脚本类型"
                @change="handleScriptTypeChange"
              >
                <a-option value="shell">Shell</a-option>
                <a-option value="python">Python</a-option>
                <a-option value="powershell">PowerShell</a-option>
                <a-option value="perl">Perl</a-option>
                <a-option value="javascript">JavaScript</a-option>
                <a-option value="go">Go</a-option>
              </a-select>
            </a-form-item>

            <a-form-item label="分类" field="category">
              <a-select
                v-model="form.category"
                placeholder="请选择分类"
                allow-clear
              >
                <a-option value="deployment">部署</a-option>
                <a-option value="monitoring">监控</a-option>
                <a-option value="maintenance">维护</a-option>
                <a-option value="backup">备份</a-option>
                <a-option value="security">安全</a-option>
                <a-option value="other">其他</a-option>
              </a-select>
            </a-form-item>

            <a-form-item label="标签" field="tags_json">
              <div class="tags-kv-editor">
                <div v-if="Object.keys(form.tags_json || {}).length === 0" class="empty-tags">
                  <a-empty description="暂无标签" size="small" />
                  <a-button size="small" @click="addTag" class="mt-2">
                    <template #icon>
                      <icon-plus />
                    </template>
                    添加标签
                  </a-button>
                </div>
                <div v-else class="tags-list">
                  <div
                    v-for="(value, key) in form.tags_json"
                    :key="key"
                    class="tag-item"
                  >
                    <a-input-group compact>
                      <a-input
                        v-model="tagKeys[key]"
                        placeholder="键"
                        style="width: 40%"
                        @change="updateTagKey(key, $event)"
                      />
                      <a-input
                        v-model="form.tags_json[key]"
                        placeholder="值"
                        style="width: 50%"
                      />
                      <a-button
                        type="text"
                        status="danger"
                        style="width: 10%"
                        @click="removeTag(key)"
                      >
                        <template #icon>
                          <icon-delete />
                        </template>
                      </a-button>
                    </a-input-group>
                  </div>
                  <a-button size="small" @click="addTag" class="mt-2">
                    <template #icon>
                      <icon-plus />
                    </template>
                    添加标签
                  </a-button>
                </div>
              </div>
            </a-form-item>

            <a-form-item label="描述" field="description">
              <a-textarea
                v-model="form.description"
                placeholder="请输入模板描述"
                :rows="4"
              />
            </a-form-item>
          </a-card>

          <!-- 版本管理 -->
          <a-card title="版本管理">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="版本号" field="version">
                  <a-input
                    v-model="form.version"
                    placeholder="请输入版本号，如：1.0.0"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="状态" field="is_active">
                  <a-select v-model="form.is_active" placeholder="请选择状态">
                    <a-option :value="true">
                      <a-tag color="green">上线</a-tag>
                    </a-option>
                    <a-option :value="false">
                      <a-tag color="red">下线</a-tag>
                    </a-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>
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

            <a-form-item field="content">
              <script-editor-with-validation
                ref="editorRef"
                v-model="form.content"
                :language="form.script_type"
                :theme="editorTheme"
                :height="600"
                :readonly="false"
                :auto-validate="true"
                @validation-change="handleValidationChange"
              />
            </a-form-item>
          </a-card>
        </a-col>
      </a-row>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'
import ScriptEditorWithValidation from '@/components/ScriptEditorWithValidation.vue'
import type { ScriptTemplate } from '@/types'
import type { ScriptValidationResult } from '@/utils/scriptValidator'

interface Props {
  template?: ScriptTemplate | null
}

interface Emits {
  (e: 'submit', data: Partial<ScriptTemplate>): void
  (e: 'change', hasChanges: boolean): void
}

const props = withDefaults(defineProps<Props>(), {
  template: null,
})

const emit = defineEmits<Emits>()

const formRef = ref()
const editorRef = ref()
const editorTheme = ref('vs-dark')

// 表单数据
const form = reactive<Partial<ScriptTemplate>>({
  name: '',
  script_type: 'shell',
  category: '',
  tags_json: {},
  description: '',
  content: '',
  version: '1.0.0',
  is_active: true,
})

// 用于跟踪标签键的变化
const tagKeys = ref<Record<string, string>>({})

// 验证状态
const validationResults = ref<ScriptValidationResult[]>([])
const hasValidationErrors = ref(false)

// 编辑器选项已移至SimpleMonacoEditor组件内部

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入模板名称' },
    { minLength: 2, message: '模板名称至少2个字符' },
  ],
  script_type: [
    { required: true, message: '请选择脚本类型' },
  ],
  content: [
    { required: true, message: '请输入脚本内容' },
    { minLength: 10, message: '脚本内容至少10个字符' },
  ],
}

// 脚本模板
const scriptTemplates = {
  shell: `#!/bin/bash
# Shell脚本模板
# 作者: {{author}}
# 创建时间: {{date}}

# 定义获取当前时间和PID的函数
function job_get_now
{
    echo "[\`date +'%Y-%m-%d %H:%M:%S'\`][PID:$$]"
}

# 在脚本开始运行时调用，打印当前的时间戳及PID
function job_start
{
    echo "$(job_get_now) job_start"
}

# 在脚本执行成功的逻辑分支处调用，打印当前的时间戳及PID
function job_success
{
    local msg="$*"
    echo "$(job_get_now) job_success:[$msg]"
    exit 0
}

# 在脚本执行失败的逻辑分支处调用，打印当前的时间戳及PID
function job_fail
{
    local msg="$*"
    echo "$(job_get_now) job_fail:[$msg]"
    exit 1
}

# 在当前脚本执行时，第一行输出当前时间和进程ID，详见上面函数：job_get_now
job_start

###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### 可在此处开始编写您的脚本逻辑代码`,

  python: `#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
Python脚本模板
作者: {{author}}
创建时间: {{date}}
"""

import datetime
import os
import sys

def _now(format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.now().strftime(format)

##### 可在脚本开始运行时调用，打印当时的时间戳及PID。
def job_start():
    print("[%s][PID:%s] job_start" % (_now(), os.getpid()))
    sys.stdout.flush()

##### 可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
def job_success(msg):
    print("[%s][PID:%s] job_success:[%s]" % (_now(), os.getpid(), msg))
    sys.stdout.flush()
    sys.exit(0)

##### 可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
def job_fail(msg):
    print("[%s][PID:%s] job_fail:[%s]" % (_now(), os.getpid(), msg))
    sys.stdout.flush()
    sys.exit(1)

if __name__ == '__main__':

    job_start()

###### 脚本执行成功和失败的标准只取决于最后一段执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### Python脚本为了避免因长时间未刷新缓冲区导致标准输出异常，
###### 建议在print的下一行使用 sys.stdout.flush() 来强制将被缓存的输出信息刷新到控制台上
###### 可在此处开始编写您的脚本逻辑代码`,

  powershell: `# PowerShell脚本模板
# 作者: {{author}}
# 创建时间: {{date}}

##### 可在脚本开始运行时调用，打印当时的时间戳及PID。
function job_start
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[{0}][PID:{1}] job_start" -f $cu_date,$pid
}

##### 可在脚本执行成功的逻辑分支处调用，打印当时的时间戳及PID。
function job_success
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    if($args.count -ne 0)
    {
        $args | foreach {$arg_str=$arg_str + " " + $_}
        "[{0}][PID:{1}] job_success:[{2}]" -f $cu_date,$pid,$arg_str.TrimStart(' ')
    }
    else
    {
        "[{0}][PID:{1}] job_success:[]" -f $cu_date,$pid
    }
    exit 0
}

##### 可在脚本执行失败的逻辑分支处调用，打印当时的时间戳及PID。
function job_fail
{
    $cu_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    if($args.count -ne 0)
    {
        $args | foreach {$arg_str=$arg_str + " " + $_}
        "[{0}][PID:{1}] job_fail:[{2}]" -f $cu_date,$pid,$arg_str.TrimStart(' ')
    }
    else
    {
        "[{0}][PID:{1}] job_fail:[]" -f $cu_date,$pid
    }
    exit 1
}

job_start

###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为脚本执行失败
###### 可在此处开始编写您的脚本逻辑代码`,

  perl: `#!/usr/bin/env perl
use strict;
use warnings;
use POSIX qw(strftime);

# Perl脚本模板
# 作者: {{author}}
# 创建时间: {{date}}

sub _now {
    return strftime("%Y-%m-%d %H:%M:%S", localtime);
}

sub job_start {
    print "[" . _now() . "][PID:$$] job_start\n";
}

sub job_success {
    my ($msg) = @_;
    $msg = '' unless defined $msg;
    print "[" . _now() . "][PID:$$] job_success:[$msg]\n";
    exit 0;
}

sub job_fail {
    my ($msg) = @_;
    $msg = '' unless defined $msg;
    print STDERR "[" . _now() . "][PID:$$] job_fail:[$msg]\n";
    exit 1;
}

job_start();

###### 作业平台中执行脚本成功和失败的标准只取决于脚本最后一条执行语句的返回值
###### 如果返回值为0，则认为此脚本执行成功，如果非0，则认为此脚本执行失败
###### 可在此处开始编写您的脚本逻辑代码`,

  javascript: `// JavaScript 脚本模板
// 作者: {{author}}
// 创建时间: {{date}}
// 说明：在 Node.js 环境下执行，最后一行的退出码决定作业平台中的成功/失败

function jobStart() {
  const now = new Date().toISOString()
  console.log(\`[\${now}][PID:\${process.pid}] job_start\`)
}

function jobSuccess(message = '') {
  const now = new Date().toISOString()
  console.log(\`[\${now}][PID:\${process.pid}] job_success:[\${message}]\`)
  process.exit(0)
}

function jobFail(message = '') {
  const now = new Date().toISOString()
  console.error(\`[\${now}][PID:\${process.pid}] job_fail:[\${message}]\`)
  process.exit(1)
}

jobStart()

// TODO: 在此处编写你的业务逻辑
// 示例：模拟执行
console.log('hello from javascript script')

// 根据逻辑结果选择调用 jobSuccess 或 jobFail
jobSuccess('done')`,

  go: `// Go 脚本模板
// 作者: {{author}}
// 创建时间: {{date}}
// 说明：建议通过 'go run' 执行此文件，最后程序退出码决定作业平台中的成功/失败
package main

import (
  "fmt"
  "os"
  "time"
)

func jobStart() {
  now := time.Now().Format("2006-01-02 15:04:05")
  fmt.Printf("[%s][PID:%d] job_start\\n", now, os.Getpid())
}

func jobSuccess(message string) {
  now := time.Now().Format("2006-01-02 15:04:05")
  fmt.Printf("[%s][PID:%d] job_success:[%s]\\n", now, os.Getpid(), message)
  os.Exit(0)
}

func jobFail(message string) {
  now := time.Now().Format("2006-01-02 15:04:05")
  fmt.Fprintf(os.Stderr, "[%s][PID:%d] job_fail:[%s]\\n", now, os.Getpid(), message)
  os.Exit(1)
}

func main() {
  jobStart()

  // TODO: 在此处编写你的业务逻辑
  fmt.Println("hello from go script")

  // 根据逻辑结果选择调用 jobSuccess 或 jobFail
  jobSuccess("done")
}`,

}

// 初始化表单数据
const initForm = () => {
  if (props.template) {
    // 处理字段映射
    Object.assign(form, {
      name: props.template.name || '',
      script_type: props.template.script_type || 'shell',
      category: props.template.category || '',
      tags_json: props.template.tags_json || {},
      description: props.template.description || '',
      content: props.template.script_content || props.template.content || '',
      version: props.template.version || '1.0.0',
      is_active: props.template.is_active !== undefined ? props.template.is_active : true,
    })

    // 初始化tagKeys映射
    tagKeys.value = {}
    if (form.tags_json) {
      Object.keys(form.tags_json).forEach(key => {
        tagKeys.value[key] = key
      })
    }
  } else {
    Object.assign(form, {
      name: '',
      script_type: 'shell',
      category: '',
      tags_json: {},
      description: '',
      content: '',
      version: '1.0.0',
      is_active: true,
    })
    tagKeys.value = {}
    // 新建模板时插入默认模板
    insertTemplate()
  }

  // 延迟设置初始化完成标记，避免初始化时触发变更事件
  nextTick(() => {
    isFormInitialized.value = true
  })
}



// 脚本类型变化
const handleScriptTypeChange = () => {
  // 每次切换类型时都插入对应的模板
  insertTemplate()
}

// 插入模板
const insertTemplate = () => {
  const template = scriptTemplates[form.script_type as keyof typeof scriptTemplates]
  if (template) {
    const content = template
      .replace(/\{\{author\}\}/g, '系统管理员')
      .replace(/\{\{date\}\}/g, new Date().toISOString().split('T')[0])
    
    form.content = content
  }
}

// 格式化代码
const formatCode = () => {
  editorRef.value?.formatCode()
}

// 处理验证结果变化
const handleValidationChange = (results: ScriptValidationResult[]) => {
  validationResults.value = results
  hasValidationErrors.value = results.some(r => r.severity === 'error')
  
  // 如果有错误，触发变更事件
  if (isFormInitialized.value) {
    emit('change', true)
  }
}

// 标签管理函数
const addTag = () => {
  const newKey = `tag_${Date.now()}`
  if (!form.tags_json) {
    form.tags_json = {}
  }
  form.tags_json[newKey] = ''
  tagKeys.value[newKey] = newKey
}

const removeTag = (key: string) => {
  if (form.tags_json) {
    delete form.tags_json[key]
    delete tagKeys.value[key]
  }
}

const updateTagKey = (oldKey: string, newKey: string) => {
  if (!form.tags_json || !newKey || newKey === oldKey) return

  // 检查新键是否已存在
  if (newKey in form.tags_json) {
    // 如果新键已存在，恢复原键名
    tagKeys.value[oldKey] = oldKey
    return
  }

  // 更新键名
  const value = form.tags_json[oldKey]
  delete form.tags_json[oldKey]
  form.tags_json[newKey] = value

  // 更新tagKeys映射
  delete tagKeys.value[oldKey]
  tagKeys.value[newKey] = newKey
}

// 提交表单
const submit = async () => {
  try {
    // Arco Design 的 validate 方法在验证成功时返回 undefined，失败时抛出异常
    await formRef.value?.validate()

    // 检查脚本验证错误
    if (hasValidationErrors.value) {
      console.warn('脚本存在验证错误，但允许提交')
      // 可以选择是否阻止提交
      // return false
    }

    // 验证成功，触发提交事件
    emit('submit', form)
    return true
  } catch (error) {
    console.error('表单验证失败:', error)
    // 验证失败，不触发提交事件
    return false
  }
}

// 重置表单
const reset = () => {
  formRef.value?.resetFields()
  initForm()
}

// 获取当前表单数据（用于预览，不触发提交）
const getCurrentData = async () => {
  try {
    // 验证表单
    await formRef.value?.validate()
    // 返回当前表单数据
    return { ...form }
  } catch (error) {
    console.error('表单验证失败:', error)
    throw error
  }
}

// 获取当前编辑器主题
const getCurrentTheme = () => {
  return editorTheme.value
}

// 暴露方法
defineExpose({
  submit,
  reset,
  getCurrentData,
  getCurrentTheme,
  triggerValidation: () => editorRef.value?.triggerValidation(),
  clearValidation: () => editorRef.value?.clearValidation(),
  getValidationResults: () => validationResults.value,
  hasValidationErrors: () => hasValidationErrors.value,
})

// 监听template属性变化
watch(
  () => props.template,
  () => {
    initForm()
  },
  { immediate: true }
)

// 表单初始化标记
const isFormInitialized = ref(false)

// 监听表单数据变化
watch(
  form,
  () => {
    // 只有在表单初始化完成后才触发变更事件
    if (isFormInitialized.value) {
      nextTick(() => {
        emit('change', true)
      })
    }
  },
  { deep: true }
)

// 监听各个字段的变化，确保变更检测更准确
watch(
  () => form.name,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  }
)

watch(
  () => form.script_type,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  }
)

watch(
  () => form.content,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  }
)

watch(
  () => form.description,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  }
)

watch(
  () => form.category,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  }
)

watch(
  () => form.tags_json,
  () => {
    if (isFormInitialized.value) {
      emit('change', true)
    }
  },
  { deep: true }
)

// 初始化
onMounted(() => {
  // no-op for now
})
</script>

<style scoped>
.template-form {
  padding: 0;
}

.mb-4 {
  margin-bottom: 16px;
}



/* 标签编辑器样式 */
.tags-kv-editor {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  background-color: #fafafa;
}

.empty-tags {
  text-align: center;
  padding: 20px;
}

.tags-list {
  max-height: 200px;
  overflow-y: auto;
}

.tag-item {
  margin-bottom: 8px;
}

.tag-item:last-child {
  margin-bottom: 0;
}

.mt-2 {
  margin-top: 8px;
}
</style>
