# 平台壳层 Naive 恢复设计

## 目标

把作业平台 / 运维台壳层从「被压缩改写、体验偏离旧版」恢复为：**视觉与交互对齐旧 Arco 壳层，组件使用 Naive UI + Lucide**。不恢复自定义 `compact-nav`，折叠态使用 Naive 原生折叠菜单。

## 背景与根因

- HEAD 上的 `Layout.vue` / `OpsLayout.vue` 仍是 Arco 实现（约 692 / 486 行），含折叠态 `compact-nav`。
- 工作区在 Naive 迁移中被压成约 104 / 63 行：语义大致在，但结构不可读，折叠导航换成 Naive 默认行为，视觉密度依赖零散 `:deep` 选择器，体验显得「面目全非」。
- 现有 `layoutShell.test.ts` 已要求 Naive 原语，并明确禁止 `compactNavItems`。

## 决策

| 选项 | 结论 |
| --- | --- |
| 总体策略 | 忠实移植旧壳层行为与视觉到 Naive（不抽共享 `PlatformShell`） |
| 折叠导航 | Naive 原生 `collapsed` 菜单（图标 + 弹出子项），不恢复 `compact-nav` |
| 移动端 | 保留 ≤520 断点 + 左侧 drawer |
| 范围 | 仅壳层与 shell 测试；不动业务页、路由表、权限模型 |

### 未采纳方案

- **仅调样式、保留压缩结构**：治标不治本，交互回归难。
- **抽出共享 PlatformShell**：长期更干净，但与本次恢复叠加重构风险。
- **恢复 compact-nav**：与「用 Naive 折叠菜单」决策冲突，且与当前测试契约冲突。

## 架构

继续两套文件：

- `frontend/src/views/Layout.vue` — 作业平台
- `frontend/src/views/OpsLayout.vue` — 运维台

组件：`n-layout`（`has-sider`）/ `n-layout-sider` / `n-menu` / `n-drawer` / `n-layout-header` / `n-layout-content` / `n-breadcrumb` / `n-dropdown` + Lucide。

### 布局行为

- **桌面**：侧栏宽 200、折叠宽 64；折叠时依赖 Naive `collapsed` 菜单。
- **移动端（≤520）**：隐藏 sider；顶栏按钮打开左侧 drawer，内放完整菜单；路由变化或断点切换时关闭 drawer。
- **作业台 `workspaceMode`**：进入强制折叠并记住先前状态，离开后恢复；运维台无此逻辑。
- **菜单**：`menuConfig` + `findMenuInfo` 驱动选中与父级展开；折叠时清空 `openKeys`。
- **平台切换 / 退出**：语义与旧版一致（`selected_platform`、超管可见切换、登出后清选择并 `replace('/login')`）。

代码恢复可读分块（template / script / style），禁止再压成单行脚本。

## 视觉密度

以旧壳层 Token 为准，映射到 Naive scoped + `:deep`：

- 侧栏 / logo：`--app-surface`，logo 高 68px；折叠时 brand-mark 居中
- 顶栏：高 64px，半透明 surface + blur，底边 `--app-border`
- 内容区：padding 28px；`content--workspace` 为 16px
- 菜单：项高 40 / 子项 36，圆角 `--app-radius-sm`，悬停/选中 `--app-accent-soft` + `--app-accent`
- 品牌文案：作业台「J / 作业平台 / Ops Job」；运维台「O / 运维台 / Ops Console」

全局色仍由 `platformThemeOverrides` 管理；壳层局部密度不散落到业务页。不引入新视觉语言。

## 交互细节

- 路由变化 → 更新 `selectedKeys`；有父级且未折叠时确保父菜单在 `openKeys` 中
- 折叠 → 清空 `openKeys`
- 菜单点击：同路径不重复 `push`；仅忽略 `NavigationDuplicated`
- 面包屑：过滤无 `meta.title` 的匹配路由
- 顶栏：折叠/移动端按钮 + 面包屑 | 平台切换（超管）+ 用户下拉（退出登录）
- a11y：折叠/抽屉按钮保留 `title` / `aria-label`

## 错误处理

- 登出失败：打日志，仍清平台选择并跳转登录
- 菜单导航：只吞 `NavigationDuplicated`
- 面包屑：无 title 静默跳过
- 不新增全局错误边界

## 测试与验收

更新 `frontend/src/views/__tests__/layoutShell.test.ts`：

- 两套布局：`n-layout has-sider`、`:collapsed`、`n-drawer`、`MOBILE_BREAKPOINT = 520`、resize 监听、Lucide、无 Arco、无 `compactNavItems`
- 作业台：`workspaceMode` / `content--workspace`
- 两套布局：平台切换文案、`selected_platform`、仪表盘、登出后 `replace('/login')`

落地后跑定向 Vitest；必要时 `pnpm type-check`。本阶段不上 Playwright E2E。

### 验收标准

- 桌面展开/折叠密度接近旧版
- 折叠态为 Naive 图标 + 弹出子菜单
- 移动端 drawer 可用
- 作业台 workspace 自动收起可恢复
- 超管可切换平台；登出行为正确
- 无 Arco / `compact-nav` 残留

## 非目标（YAGNI）

- 不抽 `PlatformShell`
- 不改业务页、路由、权限
- 不做主题切换、可配置菜单、通知铃铛等新功能
- 不恢复 `compact-nav`
