package httpserver

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"strings"
	"time"

	"ops-job-agent/internal/api"
	"ops-job-agent/internal/logger"
)

// TaskService 抽象出 Agent 提供的任务执行与取消能力，避免循环依赖
type TaskService interface {
	// SubmitTask 提交任务执行（通常内部会异步执行）
	SubmitTask(task *api.TaskSpec)
	// CancelTask 取消任务
	CancelTask(taskID string) error
}

// Server Agent 内置 HTTP 服务，用于直连模式下控制面主动推送任务
type Server struct {
	addr         string
	authToken    string
	taskService  TaskService
	httpServer   *http.Server
	readTimeout  time.Duration
	writeTimeout time.Duration
}

// NewServer 创建 HTTP Server
func NewServer(addr, authToken string, svc TaskService) *Server {
	if addr == "" {
		addr = ":8080"
	}
	s := &Server{
		addr:         addr,
		authToken:    strings.TrimSpace(authToken),
		taskService:  svc,
		readTimeout:  30 * time.Second,
		writeTimeout: 30 * time.Second,
	}
	return s
}

// Start 启动 HTTP Server，阻塞直到 ctx 结束
func (s *Server) Start(ctx context.Context) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/tasks", s.handleTasks)
	mux.HandleFunc("/api/tasks/", s.handleTaskDetail)

	s.httpServer = &http.Server{
		Addr:         s.addr,
		Handler:      mux,
		ReadTimeout:  s.readTimeout,
		WriteTimeout: s.writeTimeout,
	}

	// 在单独的 goroutine 中启动 HTTP 服务
	errCh := make(chan error, 1)
	go func() {
		logger.GetLogger().WithField("addr", s.addr).Info("agent http server started (direct mode)")
		// 支持 :0 端口，让内核自动分配端口（如果配置如此）
		ln, err := net.Listen("tcp", s.addr)
		if err != nil {
			errCh <- err
			return
		}
		// 如果需要，后续可以将实际监听地址上报给控制面
		errCh <- s.httpServer.Serve(ln) // Serve 在 Shutdown 后返回 http.ErrServerClosed
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := s.httpServer.Shutdown(shutdownCtx); err != nil {
			logger.GetLogger().WithError(err).Error("agent http server shutdown error")
		}
		return nil
	case err := <-errCh:
		if err == http.ErrServerClosed {
			return nil
		}
		return err
	}
}

// 统一的认证检查：使用 Bearer <token>
func (s *Server) authenticate(r *http.Request) bool {
	// 为了先打通直连模式的链路，目前不强制鉴权。
	// 后续如需增强安全性，可以在此处接入 HMAC 或双向 TLS 等机制。
	_ = r
	return true
}

// handleTasks 处理 /api/tasks
//   - POST /api/tasks  : 推送新任务
func (s *Server) handleTasks(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.authenticate(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var task api.TaskSpec
	if err := json.NewDecoder(r.Body).Decode(&task); err != nil {
		http.Error(w, "invalid json body", http.StatusBadRequest)
		return
	}
	if task.ID == "" {
		http.Error(w, "task id is required", http.StatusBadRequest)
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"task_id":   task.ID,
		"task_name": task.Name,
		"type":      task.Type,
	}).Info("received task via http (direct mode)")

	// 提交任务执行（内部应异步执行，不阻塞 HTTP）
	s.taskService.SubmitTask(&task)

	resp := map[string]any{
		"task_id": task.ID,
		"status":  "accepted",
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

// handleTaskDetail 处理 /api/tasks/{id}/cancel
func (s *Server) handleTaskDetail(w http.ResponseWriter, r *http.Request) {
	// 目前只支持取消：POST /api/tasks/{id}/cancel
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.authenticate(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	path := strings.TrimPrefix(r.URL.Path, "/api/tasks/")
	parts := strings.Split(path, "/")
	if len(parts) != 2 || parts[1] != "cancel" {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	taskID := parts[0]
	if taskID == "" {
		http.Error(w, "task id is required", http.StatusBadRequest)
		return
	}

	if err := s.taskService.CancelTask(taskID); err != nil {
		logger.GetLogger().WithError(err).WithField("task_id", taskID).Error("cancel task via http failed")
		http.Error(w, fmt.Sprintf("cancel task failed: %v", err), http.StatusBadRequest)
		return
	}

	resp := map[string]any{
		"task_id": taskID,
		"status":  "cancelled",
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}


