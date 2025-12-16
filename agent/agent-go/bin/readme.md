# ops-job-agent 二进制包说明（bin/ 目录）

本目录通常由构建/打包流程自动生成，包含在部署到目标主机的压缩包中。当前内容示例：

- `agent` / `ops-job-agent`：主程序二进制文件（Linux 可执行文件）。
- `agent.zip`：打包好的压缩包，可直接作为 Agent 安装包上传到控制面。
- `config.example.yaml`：Agent 配置示例文件，用于本地调试或作为手工部署的模板。

## 推荐目录结构（解压后）

```text
/opt/ops-job-agent/           # 安装目录（示例）
  ├── ops-job-agent          # Agent 二进制文件
  └── config/
      └── config.yaml        # 由安装脚本自动生成的实际配置
```

在部署时建议：

1. 将 `agent` 或 `agent.zip` 上传到目标主机并解压到目标目录（如 `/opt/ops-job-agent`）。  
2. 使用控制面生成的安装脚本，它会：
   - 将二进制复制/移动到目标目录；
   - 在 `config/` 子目录中生成 `config.yaml`（包含 agent-server 地址、控制面地址、agent_token、direct_shared_secret 等信息）；
   - 启动 `ops-job-agent` 服务。
3. 如果需要手工部署，可以参考 `config.example.yaml` 自行编写 `config/config.yaml`，并通过环境变量或命令行启动 agent。

> 注意：**不要在打包的压缩包中直接包含真实的 `config.yaml` 或敏感的 `agent_token` / `direct_shared_secret`。**  
> token 应由控制面在安装脚本执行时为每台主机动态生成并写入本地配置文件。


