# 运维作业平台前端

基于 Vue 3 + TypeScript + Arco Design Vue 构建的现代化运维作业平台前端。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - JavaScript 的超集，提供类型安全
- **Arco Design Vue** - 企业级 UI 组件库
- **Vue Router** - 官方路由管理器
- **Pinia** - 新一代状态管理库
- **Vite** - 下一代前端构建工具
- **Axios** - HTTP 客户端

## 功能特性

- 🔐 **用户认证** - JWT Token 认证，自动刷新
- 🖥️ **主机管理** - 主机增删改查，连接测试
- 📝 **脚本模板** - 脚本编辑器，参数配置
- ⚙️ **作业模板** - 步骤编排，流程管理
- 📋 **执行计划** - 计划创建，主机分配
- 📊 **执行记录** - 历史记录，状态跟踪
- ⏰ **定时任务** - Cron 调度，任务管理
- ⚡ **快速执行** - 即时脚本执行
- 📺 **实时监控** - 执行状态，日志查看
- 📈 **仪表盘** - 数据可视化，系统概览

## 快速开始

### 1. 安装依赖

```bash
# 使用 npm
npm install

# 使用 yarn
yarn install

# 使用 pnpm (推荐)
pnpm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

### 3. 构建生产版本

```bash
npm run build
```

## 项目结构

```
src/
├── api/           # API 接口
├── components/    # 通用组件
├── router/        # 路由配置
├── stores/        # 状态管理
├── types/         # 类型定义
├── utils/         # 工具函数
├── views/         # 页面组件
├── App.vue        # 根组件
└── main.ts        # 入口文件
```

## 开发说明

### API 配置

前端通过 Vite 代理将 `/api` 请求转发到后端服务器：

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true
    }
  }
}
```

### 认证机制

使用 JWT Token 进行认证：
- 登录成功后将 token 存储在 localStorage
- 请求拦截器自动添加 Authorization 头
- Token 过期时自动刷新
- 认证失败时跳转到登录页

### 状态管理

使用 Pinia 进行状态管理：
- `useAuthStore` - 用户认证状态
- 其他业务状态按需添加

### 实时日志

前端集成了高性能的实时日志查看功能：
- **SSE 连接**: 使用 `sse.js` 库实现安全的 WebSocket-like 连接
- **虚拟滚动**: 支持 10万+ 日志条目的高效渲染
- **日志压缩**: 自动压缩重复内容，减少内存占用
- **自动重连**: 网络异常时自动重连和状态恢复

## 部署

### 1. 构建项目

```bash
npm run build
```

### 2. 部署到服务器

将 `dist` 目录下的文件部署到 Web 服务器即可。

### 3. Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    # 处理前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 代理 API 请求
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 开发规范

### 代码风格

- 使用 TypeScript 进行类型检查
- 组件使用 Composition API
- 遵循 Vue 3 最佳实践

### 命名规范

- 组件文件使用 PascalCase
- 普通文件使用 kebab-case
- 变量和函数使用 camelCase

### Git 提交规范

- feat: 新功能
- fix: 修复问题
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具的变动
