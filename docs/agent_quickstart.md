# Ops-Job Agent 快速入门指南

本文档为开发、运维、前端三类角色提供快速入门指南。

---

## 一、开发：如何新增一个 Agent 能力

### 1.1 从控制面到 Agent-Server 再到 Agent 的完整流程

#### 步骤 1：控制面（Django）添加任务类型

在 `apps/agents/execution_service.py` 中：

1. **定义任务规范（TaskSpec）**：
   ```python
   task_spec = AgentExecutionService.create_task_spec(
       task_id="unique_task_id",
       name="任务名称",
       task_type="script",  # 或 "file_transfer", "command"
       command="要执行的命令或脚本",
       script_type="shell",  # 或 "python", "powershell"
       timeout_sec=300,
       run_as="username",  # 可选：执行用户
       # ... 其他参数
   )
   ```

2. **推送到 Agent-Server**：
   ```python
   result = AgentExecutionService.push_task_to_agent(
       agent=agent_instance,
       task_spec=task_spec,
       agent_server_url="http://agent-server:8080"
   )
   ```

#### 步骤 2：Agent-Server（Go）处理任务

Agent-Server 已经实现了任务分发逻辑，无需修改：

- 控制面通过 `POST /api/agents/{id}/tasks` 推送任务
- Agent-Server 通过 `requireScope()` 中间件校验多租户隔离
- 任务分发器（Dispatcher）根据 Agent 在线状态选择直接推送或入队

#### 步骤 3：Agent（Go）执行任务

Agent 已经实现了多语言执行器，支持：

- **Shell 执行器**：`/bin/sh -c` (Linux) 或 `cmd /c` (Windows)
- **PowerShell 执行器**：`powershell.exe` (Windows)
- **Python 执行器**：`python` / `python3 -c`
- **JS 执行器**：`node -e`

如需新增执行器，在 `agent/agent-go/internal/executor/` 中添加。

#### 步骤 4：结果上报

Agent 执行完成后，通过以下方式上报结果：

1. **任务结果**：通过 WebSocket 或 HTTP 上报到 Agent-Server
2. **日志流**：通过 Redis Streams 写入日志流
3. **结果流**：通过 Redis Streams 写入结果流

控制面通过 `consume_agent_results` 和 `consume_agent_logs` 命令消费。

### 1.2 示例：新增一个自定义脚本执行能力

```python
# apps/agents/execution_service.py
def execute_custom_script(agent, script_content, script_type="shell"):
    task_spec = AgentExecutionService.create_task_spec(
        task_id=f"custom_{uuid.uuid4()}",
        name="自定义脚本执行",
        task_type="script",
        command=script_content,
        script_type=script_type,
        timeout_sec=600,
    )
    
    return AgentExecutionService.push_task_to_agent(
        agent=agent,
        task_spec=task_spec
    )
```

---

## 二、运维：如何排查 Agent 安装失败/心跳异常/卸载失败

### 2.1 Agent 安装失败排查

#### 检查点 1：安装脚本生成

```bash
# 查看安装脚本
python manage.py shell
>>> from apps.agents.models import Agent
>>> agent = Agent.objects.get(id=1)
>>> print(agent.install_script)
```

#### 检查点 2：SSH 连接

```bash
# 测试 SSH 连接
ssh -p 22 user@host_ip
```

#### 检查点 3：安装日志

- 查看控制面日志：`logs/agent_install.log`
- 查看目标主机日志：`/var/log/ops-job-agent/install.log`

#### 检查点 4：Agent 状态

```bash
# 查看 Agent 状态
python manage.py shell
>>> from apps.agents.models import Agent
>>> agent = Agent.objects.get(id=1)
>>> print(agent.status)  # pending/online/offline/disabled
```

### 2.2 心跳异常排查

#### 检查点 1：Agent 心跳上报

```bash
# 查看 Agent 心跳时间
python manage.py shell
>>> from apps.agents.models import Agent
>>> agent = Agent.objects.get(id=1)
>>> print(agent.last_heartbeat_at)
```

#### 检查点 2：离线判定阈值

```bash
# 查看离线判定配置
python manage.py shell
>>> from apps.system_config.models import ConfigManager
>>> print(ConfigManager.get("agent.offline_threshold_seconds", 600))
>>> print(ConfigManager.get("agent.offline_threshold_by_env", {}))
```

#### 检查点 3：手动标记离线

```bash
# 手动扫描并标记离线 Agent
python manage.py mark_agents_offline --dry-run
python manage.py mark_agents_offline
```

#### 检查点 4：Agent 日志

```bash
# 在目标主机上查看 Agent 日志
tail -f /opt/ops-job-agent/logs/agent.log
```

### 2.3 卸载失败排查

#### 检查点 1：卸载脚本

```bash
# 查看卸载脚本
python manage.py shell
>>> from apps.agents.models import Agent
>>> agent = Agent.objects.get(id=1)
>>> print(agent.uninstall_script)
```

#### 检查点 2：Agent 进程

```bash
# 在目标主机上检查 Agent 进程
ps aux | grep ops-job-agent
```

#### 检查点 3：卸载日志

- 查看控制面日志：`logs/agent_uninstall.log`
- 查看目标主机日志：`/var/log/ops-job-agent/uninstall.log`

### 2.4 常见问题

#### 问题 1：Agent 一直处于 pending 状态

**原因**：Agent 未成功激活

**解决**：
1. 检查 Agent 是否成功执行安装脚本
2. 检查 Agent 日志：`/opt/ops-job-agent/logs/agent.log`
3. 检查 Agent 是否能访问控制面：`curl http://control-plane:8000/api/agents/me/`

#### 问题 2：Agent 频繁 offline

**原因**：心跳超时或网络问题

**解决**：
1. 检查网络连接
2. 检查 Agent-Server 连接（如果使用 Agent-Server 模式）
3. 调整离线判定阈值：`SystemConfig.agent.offline_threshold_seconds`

#### 问题 3：任务执行失败

**原因**：多种可能

**解决**：
1. 查看执行记录详情：`/execution-records/{id}/`
2. 查看 Agent 日志：`/opt/ops-job-agent/logs/agent.log`
3. 查看任务结果流：`redis-cli XREAD STREAMS agent_results:stream 0`

---

## 三、前端：Agent 状态与操作按钮的含义与联动规则

### 3.1 Agent 状态说明

| 状态 | 含义 | 操作建议 |
|------|------|----------|
| `pending` | 待激活 | 查看安装脚本、重新生成安装脚本 |
| `online` | 在线 | 正常使用，可执行任务 |
| `offline` | 离线 | 检查心跳、检查网络连接、检查 Agent 日志 |
| `disabled` | 已禁用 | 启用 Agent |

### 3.2 操作按钮联动规则

#### 3.2.1 安装相关

- **"查看安装脚本"**：仅在 `pending` 状态显示
- **"重新生成安装脚本"**：仅在 `pending` 状态显示
- **"批量安装"**：选择多个主机后显示

#### 3.2.2 状态相关

- **"启用"**：仅在 `disabled` 状态显示
- **"禁用"**：仅在 `online` 或 `offline` 状态显示
- **"批量启用"**：选择多个 `disabled` Agent 后显示
- **"批量禁用"**：选择多个 `online` 或 `offline` Agent 后显示

#### 3.2.3 管理相关

- **"查看详情"**：所有状态显示
- **"删除"**：仅在 `pending` 状态显示（删除未激活的 Agent）
- **"重新签发 Token"**：所有状态显示

### 3.3 前端组件说明

#### 3.3.1 Agent 列表 (`ops/agents/index.vue`)

- **状态筛选**：支持按状态筛选（pending/online/offline/disabled）
- **统计卡片**：显示各状态的 Agent 数量
- **批量操作**：支持批量安装、卸载、启用、禁用

#### 3.3.2 Agent 详情 (`ops/agents/detail.vue`)

- **基本信息**：Agent ID、名称、状态、版本等
- **心跳信息**：最后心跳时间、心跳间隔
- **系统信息**：操作系统、CPU、内存等
- **任务历史**：最近执行的任务列表

### 3.4 状态提示文案

#### pending 状态

```
状态：待激活
提示：Agent 已创建但尚未激活，请执行安装脚本完成激活。
操作：查看安装脚本 | 重新生成安装脚本
```

#### offline 状态

```
状态：离线
提示：Agent 长时间未上报心跳，可能已离线或网络异常。
操作：检查心跳 | 检查 Agent 日志 | 启用（如果被禁用）
```

#### online 状态

```
状态：在线
提示：Agent 正常运行，可以执行任务。
操作：禁用 | 查看详情
```

#### disabled 状态

```
状态：已禁用
提示：Agent 已被禁用，无法执行任务。
操作：启用 | 查看详情
```

---

## 四、快速参考

### 4.1 常用命令

```bash
# 标记离线 Agent
python manage.py mark_agents_offline

# 消费 Agent 结果流
python manage.py consume_agent_results

# 消费 Agent 日志流
python manage.py consume_agent_logs

# 消费 Agent 状态流
python manage.py consume_agent_status
```

### 4.2 配置文件位置

- **控制面配置**：`ops_job/settings/`
- **Agent-Server 配置**：`agent/agent-server-go/configs/config.yaml`
- **Agent 配置**：`/opt/ops-job-agent/config/config.yaml`

### 4.3 API 端点

- **控制面**：`http://control-plane:8000/api/agents/`
- **Agent-Server**：`http://agent-server:8080/api/agents/`
- **Agent（直连模式）**：`http://agent-host:8080/api/tasks`

### 4.4 日志位置

- **控制面日志**：`logs/`
- **Agent-Server 日志**：`agent/agent-server-go/logs/`
- **Agent 日志**：`/opt/ops-job-agent/logs/agent.log`

---

## 五、故障排查流程图

```
Agent 安装失败
    ↓
检查 SSH 连接
    ↓
检查安装脚本
    ↓
检查 Agent 日志
    ↓
检查控制面日志
    ↓
重新生成安装脚本

Agent 心跳异常
    ↓
检查网络连接
    ↓
检查 Agent-Server 连接（如使用）
    ↓
检查离线判定阈值
    ↓
查看 Agent 日志
    ↓
手动标记离线（如需要）

任务执行失败
    ↓
查看执行记录详情
    ↓
查看 Agent 日志
    ↓
查看任务结果流
    ↓
检查任务参数
    ↓
重试任务
```

---

## 六、联系与支持

如有问题，请：

1. 查看日志文件
2. 查看本文档
3. 联系开发团队

