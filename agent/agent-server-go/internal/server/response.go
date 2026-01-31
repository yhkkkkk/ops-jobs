package server

import (
	"github.com/gin-gonic/gin"

	serrors "ops-job-agent-server/internal/errors"
)

func writeError(c *gin.Context, status int, code serrors.ErrorCode, message string) {
	msg := message
	if msg == "" {
		if mapped, ok := serrors.ErrorCodeMap[code]; ok {
			msg = mapped
		}
	}
	c.JSON(status, gin.H{
		"code":  code,
		"error": msg,
	})
}
