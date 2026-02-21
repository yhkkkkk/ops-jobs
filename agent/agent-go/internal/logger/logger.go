package logger

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/sirupsen/logrus"
	"gopkg.in/natefinch/lumberjack.v2"
)

var (
	// Log 全局日志实例
	Log *logrus.Logger
)

// InitLogger 初始化日志记录器
func InitLogger(logDir string, maxSize int, maxFiles int, maxAge int, level, format string, reportCaller bool) {
	if logDir == "" {
		logDir = filepath.Join(os.TempDir(), "ops-job-agent", "logs")
	}
	os.MkdirAll(logDir, 0755)

	Log = logrus.New()
	Log.SetReportCaller(reportCaller)

	callerPrettyfier := func(frame *runtime.Frame) (string, string) {
		if frame == nil {
			return "", ""
		}
		fileName := fmt.Sprintf("%s:%d", filepath.Base(frame.File), frame.Line)
		funcName := trimFuncName(frame.Function)
		return funcName, fileName
	}

	Log.SetFormatter(buildFormatter(format, callerPrettyfier))

	// 默认日志级别
	Log.SetLevel(logrus.InfoLevel)
	// 根据配置覆盖日志级别
	SetLevel(level)

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
+
+func buildFormatter(format string, callerPrettyfier func(*runtime.Frame) (string, string)) logrus.Formatter {
+	fmtLower := strings.ToLower(strings.TrimSpace(format))
+	if fmtLower == "json" {
+		return &logrus.JSONFormatter{
+			TimestampFormat:  "2006-01-02 15:04:05",
+			CallerPrettyfier: callerPrettyfier,
+		}
+	}
+	return &logrus.TextFormatter{
+		FullTimestamp:   true,
+		ForceColors:     true,
+		TimestampFormat: "2006-01-02 15:04:05",
+		CallerPrettyfier: callerPrettyfier,
+	}
+}

// GetLogger 获取日志实例
func GetLogger() *logrus.Logger {
	if Log == nil {
		// 如果没有初始化，使用默认配置
		InitLogger("", 10, 5, 7, "", "text", true)
	}
	return Log
}

// SetLevel 根据字符串设置日志级别（大小写不敏感），非法值会被忽略并保留当前级别。
func trimFuncName(name string) string {
	if name == "" {
		return ""
	}
	if idx := strings.LastIndex(name, "/"); idx >= 0 && idx+1 < len(name) {
		return name[idx+1:]
	}
	return name
}

func SetLevel(level string) {
	if Log == nil || level == "" {
		return
	}
	lvl, err := logrus.ParseLevel(strings.ToLower(strings.TrimSpace(level)))
	if err != nil {
		Log.WithError(err).WithField("level", level).Warn("invalid log level in config, keep current level")
		return
	}
	Log.SetLevel(lvl)
	Log.WithField("level", lvl.String()).Info("logger level updated from config")
}
