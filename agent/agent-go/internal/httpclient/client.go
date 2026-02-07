package httpclient

import (
	"context"
	"fmt"
	"time"

	"github.com/go-resty/resty/v2"

	"ops-job-agent/internal/api"
)

// Client 面向 Agent-Server 的最小 HTTP 客户端（仅用于注册获取 ws_url）
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

// GetClient 获取底层的 resty client（用于特殊请求）
func (c *Client) GetClient() *resty.Client {
	return c.cli
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

// Register 向 Agent-Server 注册 agent，返回 agent 信息（含 id）
// 向 Agent-Server 注册 Agent
func (c *Client) Register(ctx context.Context, info api.AgentInfo) (*api.AgentInfo, error) {
	var resp api.AgentInfo
	if err := c.doJSON(ctx, resty.MethodPost, "/api/agents/register/", info, &resp); err != nil {
		return nil, err
	}
	return &resp, nil
}
