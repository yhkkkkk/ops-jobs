# 流水线：SOPS 风全局变量 + 通知 + 公共目录

**Goal:** 全局变量编辑/启动体验贴近蓝鲸标准运维；补最小通知与公共流程目录。  
**Not goal:** 完整 CMDB IP 选择器、企业微信/邮件通道矩阵、跨租户流程市场。

## 范围

1. **全局变量**
   - 编辑器：自定义变量表（Key / 名称 / 类型 / 默认 / 选项 / 校验 / 启动显示 / 必填 / 引用）
   - 类型增补：`select`（枚举 options）
   - 系统变量只读区：对齐 SOPS `TaskContext.flat_details`（task_url / task_start_time / language / bk_biz_* / operator / executor / task_id / task_name）
   - 启动时注入 `_system.*`；解析支持带点 key
2. **通知**：模板 `notify_config`（事件 + webhook）；终态/暂停时 POST
3. **公共目录**：`is_public` + `category`；列表「我的 / 公共」；公共可新建任务与复制

## 验收

- [x] 变量编辑器有系统变量区与 select 类型
- [x] 新建任务可填 select/boolean；必填校验
- [x] 运行 inputs 含 `_system.task_id`
- [x] 配置 webhook 后失败/成功可触发（测试可 mock）
- [x] 公共流程列表可筛到 `is_public=true`
