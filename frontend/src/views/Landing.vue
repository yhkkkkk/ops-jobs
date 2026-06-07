<template>
  <main class="landing-page">
    <nav class="landing-nav">
      <div class="brand">
        <span class="brand-mark">J</span>
        <span>运维作业平台</span>
      </div>
      <div class="nav-actions">
        <a-button type="text" @click="router.push('/login')">登录</a-button>
        <a-button type="primary" @click="router.push('/login')">进入控制台</a-button>
      </div>
    </nav>

    <section class="hero-section">
      <div class="hero-copy">
        <p class="app-page-eyebrow">OPS AUTOMATION PLATFORM</p>
        <h1>把脚本、主机、调度和审计收敛到一个作业控制面。</h1>
        <p>
          面向内部运维与平台团队，提供模板化作业编排、批量执行、Agent 管控、实时日志和执行追踪。
        </p>
        <div class="hero-actions">
          <a-button type="primary" size="large" @click="router.push('/login')">开始使用</a-button>
          <a-button size="large" @click="router.push('/login?platform=ops')">查看运维台</a-button>
        </div>
      </div>

      <div class="product-preview" aria-label="产品界面预览">
        <div class="preview-topbar">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="preview-body">
          <aside class="preview-sidebar">
            <div class="sidebar-line active"></div>
            <div class="sidebar-line"></div>
            <div class="sidebar-line"></div>
            <div class="sidebar-line short"></div>
          </aside>
          <section class="preview-main">
            <div class="preview-header">
              <div>
                <strong>作业平台总览</strong>
                <p>模板、方案、调度和主机覆盖</p>
              </div>
              <span class="app-status-pill app-status-success">在线</span>
            </div>
            <div class="preview-metrics">
              <div v-for="item in previewMetrics" :key="item.label" class="preview-card">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <div class="preview-table">
              <div v-for="row in previewRows" :key="row.name" class="preview-row">
                <span>{{ row.name }}</span>
                <b :class="row.tone">{{ row.status }}</b>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>

    <section class="value-section">
      <div class="section-heading">
        <p class="app-page-eyebrow">WHY IT EXISTS</p>
        <h2>不是再做一个脚本入口，而是把执行过程产品化。</h2>
      </div>
      <div class="value-grid">
        <article v-for="item in values" :key="item.title" class="value-card">
          <span class="value-index">{{ item.index }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </article>
      </div>
    </section>

    <section class="workflow-section">
      <div class="section-heading">
        <p class="app-page-eyebrow">OPERATING MODEL</p>
        <h2>从标准化模板到可审计执行记录。</h2>
      </div>
      <div class="workflow-rail">
        <div v-for="step in workflow" :key="step.title" class="workflow-step">
          <span>{{ step.step }}</span>
          <div>
            <h3>{{ step.title }}</h3>
            <p>{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-section">
      <div>
        <p class="app-page-eyebrow">READY</p>
        <h2>进入控制台，先从 Dashboard 和执行链路开始收敛。</h2>
      </div>
      <a-button type="primary" size="large" @click="router.push('/login')">登录控制台</a-button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const previewMetrics = [
  { label: '作业模板', value: '128' },
  { label: '执行方案', value: '42' },
  { label: '在线主机', value: '96%' }
]

const previewRows = [
  { name: '批量补丁检查', status: '成功', tone: 'success' },
  { name: '日志归档清理', status: '运行中', tone: 'warn' },
  { name: 'Agent 心跳巡检', status: '关注', tone: 'danger' }
]

const values = [
  {
    index: '01',
    title: '标准化作业入口',
    desc: '脚本模板、作业模板和执行方案分层管理，减少临时命令和重复配置。'
  },
  {
    index: '02',
    title: '执行过程可观测',
    desc: '执行记录、实时日志、分步结果和重试链路集中呈现，排障不再靠聊天记录回溯。'
  },
  {
    index: '03',
    title: '运维控制面独立',
    desc: 'Agent、安装包、心跳告警和延时趋势归入运维台，和值班场景保持同一信息密度。'
  }
]

const workflow = [
  {
    step: 'A',
    title: '沉淀模板',
    desc: '把高频脚本和文件分发步骤抽成可复用模板。'
  },
  {
    step: 'B',
    title: '编排方案',
    desc: '绑定变量、目标主机、串并行策略和调度规则。'
  },
  {
    step: 'C',
    title: '执行追踪',
    desc: '在执行记录里查看日志、结果、失败节点和重试历史。'
  },
  {
    step: 'D',
    title: '审计闭环',
    desc: '保留操作留痕、权限约束和关键变更记录。'
  }
]
</script>

<style scoped>
.landing-page {
  min-height: 100vh;
  color: var(--app-fg);
  background:
    radial-gradient(circle at 80% 10%, color-mix(in srgb, var(--app-accent) 12%, transparent), transparent 28%),
    var(--app-bg);
}

.landing-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
  padding: 22px 24px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--app-fg);
  font-size: 15px;
  font-weight: 650;
}

.brand-mark {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: var(--app-accent);
  border-radius: 10px;
  font-family: var(--app-mono);
  font-weight: 750;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(520px, 1.08fr);
  gap: 44px;
  align-items: center;
  max-width: 1200px;
  min-height: 620px;
  margin: 0 auto;
  padding: 44px 24px 74px;
}

.hero-copy h1 {
  margin: 0;
  max-width: 720px;
  color: var(--app-fg);
  font-size: clamp(40px, 5vw, 64px);
  line-height: 1.08;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.hero-copy > p:not(.app-page-eyebrow) {
  max-width: 580px;
  margin: 22px 0 0;
  color: var(--app-muted);
  font-size: 17px;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 30px;
  flex-wrap: wrap;
}

.product-preview {
  overflow: hidden;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 18px;
  box-shadow: 0 24px 70px rgb(15 23 42 / 12%);
}

.preview-topbar {
  display: flex;
  gap: 7px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--app-border);
}

.preview-topbar span {
  width: 10px;
  height: 10px;
  background: var(--app-border-strong);
  border-radius: 999px;
}

.preview-body {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  min-height: 390px;
}

.preview-sidebar {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 26px 18px;
  background: var(--app-surface-soft);
  border-right: 1px solid var(--app-border);
}

.sidebar-line {
  height: 34px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.sidebar-line.active {
  background: var(--app-accent-soft);
  border-color: color-mix(in srgb, var(--app-accent) 36%, var(--app-border));
}

.sidebar-line.short {
  width: 70%;
}

.preview-main {
  padding: 28px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
}

.preview-header strong {
  display: block;
  font-size: 20px;
}

.preview-header p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-size: 13px;
}

.preview-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 24px;
}

.preview-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  background: var(--app-surface-soft);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.preview-card span {
  color: var(--app-muted);
  font-size: 12px;
}

.preview-card strong {
  font-family: var(--app-mono);
  font-size: 24px;
}

.preview-table {
  display: grid;
  margin-top: 22px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.preview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--app-border);
  font-size: 13px;
}

.preview-row:last-child {
  border-bottom: 0;
}

.preview-row b {
  font-size: 12px;
  font-weight: 650;
}

.preview-row b.success {
  color: var(--app-success);
}

.preview-row b.warn {
  color: var(--app-warn);
}

.preview-row b.danger {
  color: var(--app-danger);
}

.value-section,
.workflow-section,
.cta-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 80px 24px;
}

.section-heading {
  max-width: 760px;
}

.section-heading h2,
.cta-section h2 {
  margin: 0;
  color: var(--app-fg);
  font-size: clamp(30px, 4vw, 44px);
  line-height: 1.18;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.value-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 34px;
}

.value-card {
  padding: 24px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.value-index {
  color: var(--app-accent);
  font-family: var(--app-mono);
  font-size: 12px;
  font-weight: 750;
}

.value-card h3,
.workflow-step h3 {
  margin: 14px 0 8px;
  color: var(--app-fg);
  font-size: 18px;
  line-height: 1.35;
}

.value-card p,
.workflow-step p {
  margin: 0;
  color: var(--app-muted);
  font-size: 14px;
  line-height: 1.7;
}

.workflow-rail {
  display: grid;
  gap: 12px;
  margin-top: 34px;
}

.workflow-step {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 18px;
  padding: 20px 0;
  border-bottom: 1px solid var(--app-border);
}

.workflow-step > span {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  color: var(--app-accent);
  background: var(--app-accent-soft);
  border-radius: 999px;
  font-family: var(--app-mono);
  font-weight: 750;
}

.workflow-step h3 {
  margin-top: 0;
}

.cta-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 30px;
  margin-bottom: 40px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 20px;
}

@media (max-width: 980px) {
  .hero-section {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .product-preview {
    max-width: 760px;
  }

  .value-grid {
    grid-template-columns: 1fr;
  }

  .cta-section {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 620px) {
  .landing-nav {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }

  .hero-section,
  .value-section,
  .workflow-section,
  .cta-section {
    padding-left: 18px;
    padding-right: 18px;
  }

  .preview-body {
    grid-template-columns: 1fr;
  }

  .preview-sidebar {
    display: none;
  }

  .preview-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
