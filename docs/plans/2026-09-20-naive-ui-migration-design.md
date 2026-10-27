# OPS Job UI 组件库迁移设计

## 目标

在不改变现有业务信息架构、路由、API 和交互语义的前提下，移除 Arco Design Vue，迁移到 Naive UI，并使用 Lucide 图标统一操作图标。迁移完成后，平台仍保留现有两套工作台壳层、流程编辑器、Monaco、Vue Flow 和 Cron 组件。

## 当前边界

- Arco 已被约 86 个前端文件使用，包含布局、表单、表格、菜单、弹窗、抽屉、描述列表和图标。
- 迁移不是标签名批量替换；`a-table`、`a-form`、`a-modal`、`a-menu` 等组件的事件和数据模型不同，需要逐模块验证。
- 本阶段只替换组件库和公共视觉 Token，不重做业务信息架构，不新增业务功能。
- 旧组件库不长期并存；分阶段迁移期间允许按模块存在过渡代码，最终验收必须移除 Arco 依赖、解析器、全局样式和图标注册。

## 技术选择

### 推荐方案：Naive UI + Lucide

- Naive UI 对 Vue 3 和 TypeScript 支持完整，覆盖当前使用的表单、数据表格、树、分页、抽屉、弹窗、菜单、描述列表和反馈组件。
- 通过 `NConfigProvider` 集中管理主题 Token，保留当前克制、密集的运维台视觉密度。
- 通过 `lucide-vue-next` 替换 Arco 图标，操作图标保持统一，并为不熟悉的图标保留 tooltip。

### 备选方案

- Element Plus：生态和资料最多，但默认视觉更重，组件体积和样式覆盖面更大；需要额外处理与当前工作台密度的冲突。
- Headless UI + 自建组件：视觉自由度最高，但要重新实现表格、树、表单校验、弹层和键盘交互，迁移周期和回归风险明显更高。

## 迁移架构

### 基础层

- `frontend/src/main.ts`：注册 `NConfigProvider`、消息/通知/对话框 Provider，移除 Arco 全局注册。
- `frontend/src/components/app/`：补齐平台级按钮、页面头部、数据工具栏、详情面板、状态徽标和空态约定；业务页面优先使用这些组件。
- `frontend/src/styles/app.css`：把颜色、间距、圆角、阴影和密度收敛为平台 Token，不把 Naive UI 的默认值散落到页面。
- `frontend/vite.config.ts`：移除 Arco Resolver 和 Arco 分包配置，配置 Naive UI Resolver 或显式导入策略。

### 组件映射

| Arco | Naive UI / 平台层 | 重点差异 |
| --- | --- | --- |
| `a-layout*` | `n-layout*` | 侧栏折叠和插槽结构需验证 |
| `a-menu*` | `n-menu` | 菜单项配置改为 options，路由高亮需保留 |
| `a-button` | `n-button` / `AppButton` | icon、status、loading 属性需统一 |
| `a-form*` | `n-form*` | rules 和校验触发时机需回归 |
| `a-table` | `n-data-table` | columns、slot、分页对象需要适配 |
| `a-modal` / `a-drawer` | `n-modal` / `n-drawer` | footer、关闭和焦点行为需逐页验证 |
| `a-select` / `a-option` | `n-select` / options | 选项结构和远程搜索 API 不同 |
| `a-descriptions*` | `n-descriptions*` | 标签宽度和响应式布局需检查 |
| `icon-*` | Lucide 图标 | 图标名和尺寸需要显式映射 |

## 实施阶段

1. **基线和依赖层**：锁定当前测试/构建基线，引入 Naive UI、Lucide，建立主题 Provider、图标映射和 Token。
2. **平台壳层**：迁移 `Layout.vue`、`OpsLayout.vue`、登录/错误页和公共 App 组件；验证导航高亮、折叠菜单、消息反馈和权限指令。
3. **资源与系统模块**：迁移主机、账号、权限、用户、系统配置页面；重点验证表格分页、表单校验、弹窗和敏感字段行为。
4. **作业与流程模块**：迁移脚本、作业模板、执行方案、流程列表、流程工作台和调度页面；重点验证 Vue Flow、Monaco、拖拽和节点属性面板不受影响。
5. **运维工作台和收尾**：迁移 Agent、记录、审计和剩余页面，移除 Arco 依赖与配置，更新测试 mock 和组件契约。

每个阶段都执行定向 Vitest、`pnpm type-check`；阶段 2、4、5 额外执行 `pnpm build`，最终执行全量 Vitest 和独立 Playwright E2E。

## 验收标准

- `package.json`、锁文件、源码和 Vite 配置中不再依赖 Arco。
- 关键页面的导航、筛选、分页、弹窗、表单提交、流程编排、调度和权限行为与迁移前一致。
- 不再存在 `a-*` 组件标签、Arco 全局注册或 Arco 图标导入。
- `pnpm type-check`、`pnpm test`、`pnpm build` 通过；Playwright 在浏览器依赖可用时通过。
- 页面视觉统一使用平台 Token，移动端不出现横向溢出或操作控件重叠。
