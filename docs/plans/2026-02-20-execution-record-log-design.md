# 执行记录按需日志改造设计

日期: 2026-02-20

## 背景
当前执行记录详情接口会携带大量日志结构，导致接口慢、页面加载重。希望对齐蓝鲸 Job 的交互方式：详情仅返回元信息，点击步骤与主机后再按需拉取执行结果与日志。

## 目标
- 详情接口轻量化，仅包含执行记录元信息 + 步骤列表元数据。
- 步骤执行结果与主机日志按需加载，支持 pointer+limit 分页。
- 兼容运行中实时日志（SSE）与历史记录日志。
- 明确错误提示与权限失败反馈。

## 非目标
- 不改动执行引擎或日志采集方式。
- 不引入新的存储系统（仍用 Redis Stream + 归档结果）。

## 方案概述
按蓝鲸 Job 思路拆分三类数据：
1) 详情元数据：ExecutionRecord + ExecutionStep 列表（不含日志）。
2) 步骤结果：返回步骤内主机执行结果（状态/耗时/exit_code）。
3) 主机日志：返回单主机聚合日志文本，支持 pointer+limit 分页。

## API 设计
### 1) 执行记录详情（元数据）
GET `/api/executor/execution-records/:id/`
- 返回：ExecutionRecord 基础字段 + steps 简要列表（id/step_name/step_order/status/start/end/duration 等）。
- 不包含 step_logs/logs。

### 2) 步骤结果
GET `/api/executor/execution-records/:id/steps/:step_id/result/`
- 返回：步骤元数据 + 主机结果列表。
- 主机结果来源优先 ExecutionStep.host_results / step_results。

示例响应（示意）：
```
{
  "id": 12,
  "step_id": 12,
  "name": "初始化",
  "status": "success",
  "started_at": "...",
  "finished_at": "...",
  "duration": 3.2,
  "hosts": [
    {"id": 1, "ip": "1.1.1.1", "name": "node-1", "status": "success", "exit_code": 0}
  ]
}
```

### 3) 主机日志
GET `/api/executor/execution-records/:id/steps/:step_id/hosts/:host_id/logs/?pointer=&limit=500`
- 返回：logContent 聚合文本 + next_pointer。
- pointer 格式：`redis:agent_logs/<execution_id>@<last_id>`。
- 后端用 pointer 的 max_id 拉取 Redis Stream，按 execution_id + step_id + host_id 过滤。

示例响应：
```
{
  "logContent": "[2026-02-20 ...] ...\n",
  "finished": true,
  "next_pointer": "redis:agent_logs/123@170000-0"
}
```

## Pointer 分页策略
- 使用 `xrevrange(max=max_id, count=N)` 拉取最新日志。
- 过滤 execution_id/step_id/host_id 后不足 limit 时，继续向前翻。
- 返回 next_pointer（取本次最早一条 id），前端用于“加载更多”。
- 为避免重复：若结果首条 id == max_id，则跳过该条。

## 数据来源与兼容
- 首选 ExecutionStep.host_results（结构化、轻量）。
- 日志来源优先 Redis Stream；若 pointer 为空或 Redis 不可用，fallback 到 execution_results.step_logs（仅历史记录、不可分页）。
- 修复 realtime_log_service.get_logs_by_pointer：必须过滤 execution_id，避免跨任务混日志。

## 前端改造
- 详情页仅加载元数据，步骤列表来自 steps。
- 点击步骤后请求 step result，渲染主机列表与状态。
- 点击主机后请求 host log，支持“加载更多/自动滚动”。
- 执行中仍使用 SSE 实时日志，不走历史接口。

## 错误处理
- pointer 缺失/解析失败：返回明确错误。
- 无日志：返回空内容 + finished=false。
- 权限不足：返回统一权限错误提示。

## 性能与索引
- 详情查询 select_related + prefetch steps。
- Step result 与 Host log 均按需加载，避免大字段出现在详情接口。

## 迁移与上线
- 前端先切按需加载；后端保留原 logs 接口用于兼容。
- 若出现问题，可切回旧逻辑（仅前端回退）。
