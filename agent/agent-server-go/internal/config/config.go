package config

import (
	"fmt"
	"time"

	"github.com/spf13/viper"
)

// Config Agent-Server 配置
type Config struct {
	Server       ServerConfig       `mapstructure:"server"`
	ControlPlane ControlPlaneConfig `mapstructure:"control_plane"`
	Agent        AgentConfig        `mapstructure:"agent"`
	Logging      LoggingConfig      `mapstructure:"logging"`
	LogStream    LogStreamConfig    `mapstructure:"log_stream"`
	ResultStream ResultStreamConfig `mapstructure:"result_stream"`
	StatusStream StatusStreamConfig `mapstructure:"status_stream"`
	Redis        RedisConfig        `mapstructure:"redis"`
	Asynq        AsynqConfig        `mapstructure:"asynq"`
	Auth         AuthConfig         `mapstructure:"auth"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// ControlPlaneConfig 控制面配置
type ControlPlaneConfig struct {
	URL     string        `mapstructure:"url"`
	Token   string        `mapstructure:"token"`
	Scope   string        `mapstructure:"scope"` // 作用域/租户标识，用于隔离控制面请求
	Timeout time.Duration `mapstructure:"timeout"`
}

// AgentConfig Agent 配置
type AgentConfig struct {
	HeartbeatTimeout time.Duration `mapstructure:"heartbeat_timeout"`
	MaxConnections   int           `mapstructure:"max_connections"`
	TaskQueueSize    int           `mapstructure:"task_queue_size"`
}

// LoggingConfig 日志配置
type LoggingConfig struct {
	Level    string `mapstructure:"level"`
	Dir      string `mapstructure:"dir"`
	MaxSize  int    `mapstructure:"max_size"` // MB
	MaxFiles int    `mapstructure:"max_files"`
	MaxAge   int    `mapstructure:"max_age"` // days
}

// LogStreamConfig Redis Stream 写日志配置
type LogStreamConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Key     string `mapstructure:"key"`
}

// ResultStreamConfig Redis Stream 写任务结果配置
type ResultStreamConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Key     string `mapstructure:"key"`
}

// StatusStreamConfig Redis Stream 写在线状态/心跳配置
type StatusStreamConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Key     string `mapstructure:"key"`
}

// RedisConfig Redis 配置
type RedisConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Addr     string `mapstructure:"addr"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

// AsynqConfig Asynq 配置
type AsynqConfig struct {
	Enabled     bool          `mapstructure:"enabled"`
	Concurrency int           `mapstructure:"concurrency"`
	RetryMax    int           `mapstructure:"retry_max"`
	RetryDelay  time.Duration `mapstructure:"retry_delay"`
	TaskTimeout time.Duration `mapstructure:"task_timeout"`
}

// AuthConfig API 鉴权配置
type AuthConfig struct {
	SharedSecret     string        `mapstructure:"shared_secret"`
	ClockSkew        time.Duration `mapstructure:"clock_skew"`
	RequireSignature bool          `mapstructure:"require_signature"`
}

// Load 加载配置
func Load() (*Config, error) {
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("./configs")
	viper.AddConfigPath("/etc/agent-server")

	// 设置默认值
	setDefaults()

	// 读取环境变量
	viper.SetEnvPrefix("AGENT_SERVER")
	viper.AutomaticEnv()

	// 读取配置文件
	if err := viper.ReadInConfig(); err != nil {
		// 配置文件不存在时使用默认值
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("read config file: %w", err)
		}
	}

	var cfg Config
	if err := viper.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("unmarshal config: %w", err)
	}

	return &cfg, nil
}

func setDefaults() {
	// Server 默认值
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.port", 8080)
	viper.SetDefault("server.read_timeout", "30s")
	viper.SetDefault("server.write_timeout", "30s")

	// ControlPlane 默认值
	viper.SetDefault("control_plane.timeout", "30s")
	viper.SetDefault("control_plane.scope", "default")

	// Agent 默认值
	viper.SetDefault("agent.heartbeat_timeout", "60s")
	viper.SetDefault("agent.max_connections", 1000)
	viper.SetDefault("agent.task_queue_size", 100)

	// Logging 默认值
	viper.SetDefault("logging.level", "info")
	viper.SetDefault("logging.dir", "/var/log/agent-server")
	viper.SetDefault("logging.max_size", 100)
	viper.SetDefault("logging.max_files", 10)
	viper.SetDefault("logging.max_age", 7)

	// Log Stream 默认值（统一日志流写入）
	viper.SetDefault("log_stream.enabled", true)
	viper.SetDefault("log_stream.key", "agent_logs")

	// Result Stream 默认值
	viper.SetDefault("result_stream.enabled", true)
	viper.SetDefault("result_stream.key", "agent_results")

	// Status Stream 默认值
	viper.SetDefault("status_stream.enabled", true)
	viper.SetDefault("status_stream.key", "agent_status")

	// Redis 默认值
	viper.SetDefault("redis.enabled", false)
	viper.SetDefault("redis.addr", "localhost:6379")
	viper.SetDefault("redis.db", 0)

	// Asynq 默认值
	viper.SetDefault("asynq.enabled", true)
	viper.SetDefault("asynq.concurrency", 10)
	viper.SetDefault("asynq.retry_max", 3)
	viper.SetDefault("asynq.retry_delay", "1s")
	viper.SetDefault("asynq.task_timeout", "5m")

	// Auth 默认值
	viper.SetDefault("auth.shared_secret", "")
	viper.SetDefault("auth.clock_skew", "300s")
	viper.SetDefault("auth.require_signature", false)
}
