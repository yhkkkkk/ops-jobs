package logger

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/sirupsen/logrus"
	"gopkg.in/natefinch/lumberjack.v2"
)

var log *logrus.Logger

// InitLogger 初始化日志
func InitLogger(logDir string, maxSize, maxFiles, maxAge int, level, format string, reportCaller bool) {
	log = logrus.New()

	// 设置日志级别
	logLevel, err := logrus.ParseLevel(level)
	if err != nil {
		logLevel = logrus.InfoLevel
	}
	log.SetLevel(logLevel)
	log.SetReportCaller(reportCaller)

	callerPrettyfier := func(frame *runtime.Frame) (string, string) {
		if frame == nil {
			return "", ""
		}
		funcName := trimFuncName(frame.Function)
		fileName := fmt.Sprintf("%s:%d", filepath.Base(frame.File), frame.Line)
		return funcName, fileName
	}

	// 设置日志格式
	log.SetFormatter(buildFormatter(format, callerPrettyfier))

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
+
+func buildFormatter(format string, callerPrettyfier func(*runtime.Frame) (string, string)) logrus.Formatter {
+	fmtLower := strings.ToLower(strings.TrimSpace(format))
+	if fmtLower == "text" {
+		return &logrus.TextFormatter{
+			FullTimestamp:   true,
+			TimestampFormat: "2006-01-02 15:04:05",
+			CallerPrettyfier: callerPrettyfier,
+		}
+	}
+	return &logrus.JSONFormatter{
+		TimestampFormat:  "2006-01-02 15:04:05",
+		CallerPrettyfier: callerPrettyfier,
+	}
+}
+
+func trimFuncName(name string) string {
+	if name == "" {
+		return ""
+	}
+	if idx := strings.LastIndex(name, "/"); idx >= 0 && idx+1 < len(name) {
+		return name[idx+1:]
+	}
+	return name
+}

// GetLogger 获取日志实例
func GetLogger() *logrus.Logger {
	if log == nil {
		InitLogger("", 100, 10, 7, "info", "json", true)
	}
	return log
}

