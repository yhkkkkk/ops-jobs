package logger

import (
	"os"

	"github.com/sirupsen/logrus"
	"gopkg.in/natefinch/lumberjack.v2"
)

var log *logrus.Logger

// InitLogger 初始化日志
func InitLogger(logDir string, maxSize, maxFiles, maxAge int, level string) {
	log = logrus.New()

	// 设置日志级别
	logLevel, err := logrus.ParseLevel(level)
	if err != nil {
		logLevel = logrus.InfoLevel
	}
	log.SetLevel(logLevel)

	// 设置日志格式
	log.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: "2006-01-02 15:04:05",
	})

	// 文件输出（使用 lumberjack 实现日志轮转）
	if logDir != "" {
		logFile := &lumberjack.Logger{
			Filename:   logDir + "/agent-server.log",
			MaxSize:    maxSize,    // MB
			MaxBackups: maxFiles,   // 保留文件数
			MaxAge:     maxAge,     // 保留天数
			Compress:   true,       // 压缩旧文件
		}
		log.SetOutput(logFile)
	} else {
		// 如果没有指定目录，输出到标准输出
		log.SetOutput(os.Stdout)
	}
}

// GetLogger 获取日志实例
func GetLogger() *logrus.Logger {
	if log == nil {
		InitLogger("", 100, 10, 7, "info")
	}
	return log
}

