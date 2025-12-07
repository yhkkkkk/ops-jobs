package logger

import (
	"io"
	"os"
	"path/filepath"

	"github.com/sirupsen/logrus"
	"gopkg.in/natefinch/lumberjack.v2"
)

var (
	// Log 全局日志实例
	Log *logrus.Logger
)

// InitLogger 初始化日志记录器
func InitLogger(logDir string, maxSize int, maxFiles int, maxAge int) {
	if logDir == "" {
		logDir = filepath.Join(os.TempDir(), "ops-job-agent", "logs")
	}
	os.MkdirAll(logDir, 0755)

	Log = logrus.New()
	Log.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
		ForceColors:   true,
	})

	// 设置日志级别
	Log.SetLevel(logrus.InfoLevel)

	// 配置日志轮转
	logFile := filepath.Join(logDir, "agent.log")
	lumberjackLogger := &lumberjack.Logger{
		Filename:   logFile,
		MaxSize:    maxSize,  // 单位：MB
		MaxBackups: maxFiles, // 保留的旧日志文件数量
		MaxAge:     maxAge,   // 保留天数
		Compress:   true,     // 压缩旧日志文件
	}

	// 同时输出到标准输出和文件
	Log.SetOutput(io.MultiWriter(os.Stdout, lumberjackLogger))
}

// GetLogger 获取日志实例
func GetLogger() *logrus.Logger {
	if Log == nil {
		// 如果没有初始化，使用默认配置
		InitLogger("", 10, 5, 7)
	}
	return Log
}
