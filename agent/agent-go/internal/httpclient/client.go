package httpclient

import (
	"context"
	"fmt"
	"time"

	"github.com/go-resty/resty/v2"

	"ops-job-agent/internal/api"
)

// Client 与控制面交互的最小 HTTP 客户端（基于 resty 封装）
type Client struct {
	baseURL string
	token   string
	cli     *resty.Client
}

func NewClient(baseURL, token string) *Client {
	rc := resty.New().
		SetBaseURL(baseURL).
		SetTimeout(30 * time.Second)

	if token != "" {
		rc.SetAuthToken(token)
	}

	return &Client{
		baseURL: baseURL,
		token:   token,
		cli:     rc,
	}
}

func (c *Client) doJSON(ctx context.Context, method, path string, reqBody any, respBody any) error {
	req := c.cli.R().
		SetContext(ctx).
		SetHeader("Content-Type", "application/json")

	if reqBody != nil {
		req = req.SetBody(reqBody)
	}
	if respBody != nil {
		req = req.SetResult(respBody)
	}

	resp, err := req.Execute(method, path)
	if err != nil {
		return err
	}
	if resp.IsError() {
		return fmt.Errorf("http %s %s: status=%d", method, path, resp.StatusCode())
	}
	return nil
}

// Register 向控制面注册 agent，返回 agent 信息（含 id）
func (c *Client) Register(ctx context.Context, info api.AgentInfo) (*api.AgentInfo, error) {
	var resp api.AgentInfo
	if err := c.doJSON(ctx, resty.MethodPost, "/api/agents/register/", info, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}

// Heartbeat 上报心跳（可根据你的后端接口调整 payload）
func (c *Client) Heartbeat(ctx context.Context, agentID string, payload api.HeartbeatPayload) error {
	path := fmt.Sprintf("/api/agents/%s/heartbeat/", agentID)
	return c.doJSON(ctx, resty.MethodPost, path, payload, nil)
}

// FetchTask 拉取下一条任务；没有任务时应返回 (nil, nil)
func (c *Client) FetchTask(ctx context.Context, agentID string) (*api.TaskSpec, error) {
	path := fmt.Sprintf("/api/agents/%s/next-task/", agentID)
	var resp api.TaskSpec
	err := c.doJSON(ctx, resty.MethodPost, path, map[string]any{}, &resp)
	if err != nil {
		// 这里暂不区分 204/404 等情况，后续你可以按后端实际行为细化
		return nil, err
	}
	if resp.ID == "" {
		return nil, nil
	}
	return &resp, nil
}

// ReportResult 上报任务执行结果
func (c *Client) ReportResult(ctx context.Context, agentID string, result api.TaskResult) error {
	path := fmt.Sprintf("/api/agents/%s/tasks/%s/report/", agentID, result.TaskID)
	return c.doJSON(ctx, resty.MethodPost, path, result, nil)
}

// PushLogs 批量推送日志
func (c *Client) PushLogs(ctx context.Context, agentID string, taskID string, logs []api.LogEntry) error {
	path := fmt.Sprintf("/api/agents/%s/tasks/%s/logs/", agentID, taskID)
	req := api.PushLogsRequest{
		TaskID: taskID,
		Logs:   logs,
	}
	return c.doJSON(ctx, resty.MethodPost, path, req, nil)
}
