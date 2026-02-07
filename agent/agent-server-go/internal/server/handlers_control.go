package server

import (
	"context"
	"net/http"
	"os"
	"os/exec"
	"time"

	"ops-job-agent-server/internal/constants"
	serrors "ops-job-agent-server/internal/errors"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/pkg/api"

	"github.com/gin-gonic/gin"
)

// handleAgentControl 处理 Agent 控制请求（start/stop/restart）
func (s *Server) handleAgentControl(c *gin.Context) {
	agentID := c.Param("id")

	var req api.ControlRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证 action
	if req.Action != constants.ActionStart && req.Action != constants.ActionStop && req.Action != constants.ActionRestart {
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrInvalidControlAction.Error()})
		return
	}

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": serrors.ErrAgentNotFound.Error()})
		return
	}

	// 检查 Agent 是否在线
	if conn.Status != constants.StatusActive || conn.Conn == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": serrors.ErrAgentNotActive.Error()})
		return
	}

	// 通过 WebSocket 发送控制消息
	if err := conn.SendControl(req.Action, req.Reason); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id": agentID,
			"action":   req.Action,
		}).Error("send control message failed")
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id": agentID,
		"action":   req.Action,
		"reason":   req.Reason,
	}).Info("control message sent to agent")

	c.JSON(http.StatusOK, api.ControlResponse{
		Message: "control command sent to agent",
		Status:  "success",
	})
}

// handleAgentUpgrade 处理 Agent 升级请求
func (s *Server) handleAgentUpgrade(c *gin.Context) {
	agentID := c.Param("id")

	var req api.UpgradeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证必填字段
	if req.TargetVersion == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrTargetVersionRequired.Error()})
		return
	}
	if req.DownloadURL == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrDownloadURLRequired.Error()})
		return
	}

	// 获取 Agent 连接
	conn, exists := s.agentManager.Get(agentID)
	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": serrors.ErrAgentNotFound.Error()})
		return
	}

	// 检查 Agent 是否在线
	if conn.Status != constants.StatusActive || conn.Conn == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": serrors.ErrAgentNotActive.Error()})
		return
	}

	// 通过 WebSocket 发送升级消息
	if err := conn.SendUpgrade(req.TargetVersion, req.DownloadURL, req.MD5Hash, req.SHA256Hash); err != nil {
		logger.GetLogger().WithError(err).WithFields(map[string]interface{}{
			"agent_id":       agentID,
			"target_version": req.TargetVersion,
		}).Error("send upgrade message failed")
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"agent_id":       agentID,
		"target_version": req.TargetVersion,
		"download_url":   req.DownloadURL,
	}).Info("upgrade message sent to agent")

	c.JSON(http.StatusOK, api.UpgradeResponse{
		Message: "upgrade command sent to agent",
		Status:  "success",
	})
}

// handleSelfControl 处理 Agent-Server 自我控制请求
func (s *Server) handleSelfControl(c *gin.Context) {
	var req api.ControlRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证 action
	if req.Action != constants.ActionRestart {
		// Agent-Server 只支持 restart（start/stop 由进程管理器处理）
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrSelfControlOnlyRestart.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"action": req.Action,
		"reason": req.Reason,
	}).Warn("agent-server self-control requested, will restart in 3 seconds")

	// 延迟执行重启，让响应能够返回
	go func() {
		time.Sleep(3 * time.Second)
		logger.GetLogger().Info("executing agent-server restart")

		// 尝试通过 systemctl 重启（如果由 systemd 管理）
		cmd := exec.Command("systemctl", "restart", "agent-server")
		if err := cmd.Run(); err != nil {
			// 如果 systemctl 失败，尝试直接退出（由进程管理器重启）
			logger.GetLogger().WithError(err).Warn("systemctl restart failed, exiting process")
			os.Exit(0)
		}
	}()

	c.JSON(http.StatusOK, api.ControlResponse{
		Message: "agent-server will restart in 3 seconds",
		Status:  "success",
	})
}

// handleSelfUpgrade 处理 Agent-Server 自我升级请求
func (s *Server) handleSelfUpgrade(c *gin.Context) {
	var req api.UpgradeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证必填字段
	if req.TargetVersion == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrTargetVersionRequired.Error()})
		return
	}
	if req.DownloadURL == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": serrors.ErrDownloadURLRequired.Error()})
		return
	}

	logger.GetLogger().WithFields(map[string]interface{}{
		"target_version": req.TargetVersion,
		"download_url":   req.DownloadURL,
	}).Warn("agent-server self-upgrade requested")

	// 延迟执行升级，让响应能够返回
	go func() {
		time.Sleep(3 * time.Second)
		if err := s.performSelfUpgrade(&req); err != nil {
			logger.GetLogger().WithError(err).Error("agent-server self-upgrade failed")
		}
	}()

	c.JSON(http.StatusOK, api.UpgradeResponse{
		Message: "agent-server upgrade started, will restart after download",
		Status:  "success",
	})
}

// performSelfUpgrade 执行 Agent-Server 自升级
func (s *Server) performSelfUpgrade(req *api.UpgradeRequest) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	logger.GetLogger().Info("starting agent-server self-upgrade")

	// 1. 下载新版本
	tmpFile := "/tmp/agent-server-new"
	if err := downloadFile(ctx, req.DownloadURL, tmpFile); err != nil {
		return err
	}
	defer func() {
		_ = os.Remove(tmpFile)
	}()

	logger.GetLogger().Info("agent-server binary downloaded")

	// 2. 验证校验和（如果提供）
	if req.SHA256Hash != "" {
		if err := verifySHA256(tmpFile, req.SHA256Hash); err != nil {
			return err
		}
		logger.GetLogger().Info("sha256 checksum verified")
	} else if req.MD5Hash != "" {
		if err := verifyMD5(tmpFile, req.MD5Hash); err != nil {
			return err
		}
		logger.GetLogger().Info("md5 checksum verified")
	}

	// 3. 获取当前可执行文件路径
	currentExe, err := os.Executable()
	if err != nil {
		return err
	}

	// 4. 备份当前版本
	backupFile := currentExe + ".bak"
	if err = os.Rename(currentExe, backupFile); err != nil {
		return err
	}
	logger.GetLogger().WithField("backup", backupFile).Info("current version backed up")

	// 5. 替换可执行文件
	if err = os.Rename(tmpFile, currentExe); err != nil {
		// 恢复备份
		_ = os.Rename(backupFile, currentExe)
		return err
	}

	// 6. 设置执行权限
	if err = os.Chmod(currentExe, 0755); err != nil {
		logger.GetLogger().WithError(err).Warn("failed to set executable permission")
	}

	logger.GetLogger().Info("agent-server binary replaced, restarting")

	// 7. 重启进程
	cmd := exec.Command("systemctl", "restart", "agent-server")
	if err = cmd.Run(); err != nil {
		// 如果 systemctl 失败，直接退出（由进程管理器重启）
		logger.GetLogger().WithError(err).Warn("systemctl restart failed, exiting process")
		os.Exit(0)
	}

	return nil
}
