<template>
  <div class="cron-helper">
    <a-tabs v-model:active-key="activeTab">
      <a-tab-pane key="simple" title="简单模式">
        <div class="simple-mode">
          <a-form layout="vertical">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item label="执行频率">
                  <a-select v-model="simpleForm.type" @change="handleSimpleChange">
                    <a-option value="daily">每天</a-option>
                    <a-option value="weekly">每周</a-option>
                    <a-option value="monthly">每月</a-option>
                    <a-option value="hourly">每小时</a-option>
                    <a-option value="custom">自定义</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="执行时间">
                  <a-time-picker
                    v-model="simpleForm.time"
                    format="HH:mm"
                    @change="handleSimpleChange"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="8" v-if="simpleForm.type === 'weekly'">
                <a-form-item label="星期">
                  <a-select v-model="simpleForm.weekday" @change="handleSimpleChange">
                    <a-option :value="1">星期一</a-option>
                    <a-option :value="2">星期二</a-option>
                    <a-option :value="3">星期三</a-option>
                    <a-option :value="4">星期四</a-option>
                    <a-option :value="5">星期五</a-option>
                    <a-option :value="6">星期六</a-option>
                    <a-option :value="0">星期日</a-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="8" v-if="simpleForm.type === 'monthly'">
                <a-form-item label="日期">
                  <a-input-number
                    v-model="simpleForm.day"
                    :min="1"
                    :max="31"
                    @change="handleSimpleChange"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </div>
      </a-tab-pane>
      
      <a-tab-pane key="advanced" title="高级模式">
        <div class="advanced-mode">
          <a-form layout="vertical">
            <a-row :gutter="16">
              <a-col :span="4">
                <a-form-item label="分钟 (0-59)">
                  <a-input v-model="advancedForm.minute" @input="handleAdvancedChange" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="小时 (0-23)">
                  <a-input v-model="advancedForm.hour" @input="handleAdvancedChange" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="日 (1-31)">
                  <a-input v-model="advancedForm.day" @input="handleAdvancedChange" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="月 (1-12)">
                  <a-input v-model="advancedForm.month" @input="handleAdvancedChange" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="周 (0-7)">
                  <a-input v-model="advancedForm.weekday" @input="handleAdvancedChange" />
                </a-form-item>
              </a-col>
            </a-row>
            
            <a-alert type="info" show-icon>
              <template #icon><icon-info-circle /></template>
              <div>
                <div>特殊字符说明：</div>
                <div>* : 任意值</div>
                <div>? : 不指定值（日和周字段）</div>
                <div>- : 范围，如 1-5</div>
                <div>, : 列举，如 1,3,5</div>
                <div>/ : 步长，如 */5 表示每5分钟</div>
              </div>
            </a-alert>
          </a-form>
        </div>
      </a-tab-pane>
    </a-tabs>

    <div class="result-section">
      <a-form-item label="生成的Cron表达式">
        <a-input v-model="cronExpression" readonly />
      </a-form-item>
      
      <div v-if="description" class="description">
        <icon-info-circle />
        {{ description }}
      </div>
    </div>

    <!-- 常用表达式 -->
    <div class="preset-section">
      <h4>常用表达式</h4>
      <div class="preset-list">
        <a-tag
          v-for="preset in presets"
          :key="preset.expression"
          class="preset-tag"
          @click="handlePresetClick(preset.expression)"
        >
          {{ preset.description }}
        </a-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { IconInfoCircle } from '@arco-design/web-vue/es/icon'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

// 响应式数据
const activeTab = ref('simple')
const description = ref('')

// 简单模式表单
const simpleForm = reactive({
  type: 'daily',
  time: '02:00',
  weekday: 1,
  day: 1
})

// 高级模式表单
const advancedForm = reactive({
  minute: '0',
  hour: '2',
  day: '*',
  month: '*',
  weekday: '*'
})

// 计算Cron表达式
const cronExpression = computed({
  get() {
    return props.modelValue
  },
  set(value) {
    emit('update:modelValue', value)
  }
})

// 常用表达式预设
const presets = [
  { expression: '0 0 * * *', description: '每天午夜' },
  { expression: '0 2 * * *', description: '每天凌晨2点' },
  { expression: '0 9 * * 1-5', description: '工作日上午9点' },
  { expression: '0 18 * * 1-5', description: '工作日下午6点' },
  { expression: '0 0 * * 0', description: '每周日午夜' },
  { expression: '0 0 1 * *', description: '每月1号午夜' },
  { expression: '*/5 * * * *', description: '每5分钟' },
  { expression: '0 */2 * * *', description: '每2小时' }
]

// 简单模式变化处理
const handleSimpleChange = () => {
  const [hour, minute] = simpleForm.time.split(':')
  
  let expression = ''
  
  switch (simpleForm.type) {
    case 'daily':
      expression = `${minute} ${hour} * * *`
      break
    case 'weekly':
      expression = `${minute} ${hour} * * ${simpleForm.weekday}`
      break
    case 'monthly':
      expression = `${minute} ${hour} ${simpleForm.day} * *`
      break
    case 'hourly':
      expression = `${minute} * * * *`
      break
  }
  
  if (expression) {
    cronExpression.value = expression
    updateAdvancedForm(expression)
  }
}

// 高级模式变化处理
const handleAdvancedChange = () => {
  const expression = `${advancedForm.minute} ${advancedForm.hour} ${advancedForm.day} ${advancedForm.month} ${advancedForm.weekday}`
  cronExpression.value = expression
}

// 预设点击处理
const handlePresetClick = (expression) => {
  cronExpression.value = expression
  updateAdvancedForm(expression)
}

// 更新高级模式表单
const updateAdvancedForm = (expression) => {
  const parts = expression.split(' ')
  if (parts.length === 5) {
    advancedForm.minute = parts[0]
    advancedForm.hour = parts[1]
    advancedForm.day = parts[2]
    advancedForm.month = parts[3]
    advancedForm.weekday = parts[4]
  }
}

// 监听表达式变化
watch(() => props.modelValue, (newValue) => {
  if (newValue) {
    updateAdvancedForm(newValue)
  }
}, { immediate: true })
</script>

<style scoped>
.cron-helper {
  padding: 16px 0;
}

.result-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.description {
  margin-top: 8px;
  padding: 8px 12px;
  background-color: #f0f9ff;
  border: 1px solid #bae7ff;
  border-radius: 4px;
  color: #1890ff;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.preset-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.preset-section h4 {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.preset-tag:hover {
  background-color: #e6f7ff;
  border-color: #91d5ff;
}
</style>
