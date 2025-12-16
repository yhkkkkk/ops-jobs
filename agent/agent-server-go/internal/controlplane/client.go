package controlplane

import (
	"context"
	"fmt"
	"time"

	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/go-resty/resty/v2"
)

// Client 控制面 HTTP 客户端
type Client struct {
	baseURL string
	token   string
	scope   string
	secret  string
	timeout time.Duration
	cli     *resty.Client
}

// NewClient 创建控制面客户端
func NewClient(baseURL, token, scope string, timeout time.Duration) *Client {
	rc := resty.New().
		SetBaseURL(baseURL).
		SetTimeout(timeout).
		SetHeader("Content-Type", "application/json")

	if token != "" {
		rc.SetAuthToken(token)
	}
	if scope != "" {
		rc.SetHeader("X-Scope", scope)
	}

	return &Client{
		baseURL: baseURL,
		token:   token,
		scope:   scope,
		timeout: timeout,
		cli:     rc,
	}
}

// RegisterAgent 注册 Agent 到控制面
func (c *Client) RegisterAgent(ctx context.Context, agentInfo *api.AgentInfo) error {
	path := "/api/agents/register/"
	resp, err := c.cli.R().
		SetContext(ctx).
		SetBody(agentInfo).
		Post(path)

	if err != nil {
		return fmt.Errorf("register agent: %w", err)
	}

	if resp.IsError() {
		return fmt.Errorf("register agent: status=%d, body=%s", resp.StatusCode(), resp.String())
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":   agentInfo.ID,
		"agent_name": agentInfo.Name,
	}).Info("agent registered to control plane")

	return nil
}

// SendHeartbeat 发送心跳到控制面
func (c *Client) SendHeartbeat(ctx context.Context, agentID string, payload *api.HeartbeatPayload) error {
	path := fmt.Sprintf("/api/agents/%s/heartbeat/", agentID)
	resp, err := c.cli.R().
		SetContext(ctx).
		SetBody(payload).
		Post(path)

	if err != nil {
		return fmt.Errorf("send heartbeat: %w", err)
	}

	if resp.IsError() {
		return fmt.Errorf("send heartbeat: status=%d", resp.StatusCode())
	}

	return nil
}

// ReportTaskResult 上报任务结果到控制面
func (c *Client) ReportTaskResult(ctx context.Context, agentID string, result *api.TaskResult) error {
	path := fmt.Sprintf("/api/agents/%s/tasks/%s/report/", agentID, result.TaskID)
	resp, err := c.cli.R().
		SetContext(ctx).
		SetBody(result).
		Post(path)

	if err != nil {
		return fmt.Errorf("report task result: %w", err)
	}

	if resp.IsError() {
		return fmt.Errorf("report task result: status=%d", resp.StatusCode())
	}

	return nil
}

// PushLogs 推送日志到控制面
func (c *Client) PushLogs(ctx context.Context, agentID, taskID string, logs []api.LogEntry) error {
	if len(logs) == 0 {
		return nil
	}

	path := fmt.Sprintf("/api/agents/%s/tasks/%s/logs/", agentID, taskID)
	req := api.PushLogsRequest{
		TaskID: taskID,
		Logs:   logs,
	}

	resp, err := c.cli.R().
		SetContext(ctx).
		SetBody(req).
		Post(path)

	if err != nil {
		return fmt.Errorf("push logs: %w", err)
	}

	if resp.IsError() {
		return fmt.Errorf("push logs: status=%d", resp.StatusCode())
	}

	return nil
}
