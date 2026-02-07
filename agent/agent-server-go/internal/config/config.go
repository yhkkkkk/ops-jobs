package config

import (
	"fmt"
	"time"

	"github.com/spf13/viper"
)

// Config Agent-Server 配置
type Config struct {
	Server          ServerConfig          `mapstructure:"server"`
	WebSocket       WebSocketConfig       `mapstructure:"websocket"`
	Agent           AgentConfig           `mapstructure:"agent"`
	Logging         LoggingConfig         `mapstructure:"logging"`
	LogStream       LogStreamConfig       `mapstructure:"log_stream"`
	ResultStream    ResultStreamConfig    `mapstructure:"result_stream"`
	StatusStream    StatusStreamConfig    `mapstructure:"status_stream"`
	TaskStatsStream TaskStatsStreamConfig `mapstructure:"task_stats_stream"`
	Redis           RedisConfig           `mapstructure:"redis"`
	Auth            AuthConfig            `mapstructure:"auth"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// WebSocketConfig WebSocket 连接配置
type WebSocketConfig struct {
	HandshakeTimeout  time.Duration `mapstructure:"handshake_timeout"`  // WebSocket 握手超时
	ReadBufferSize    int           `mapstructure:"read_buffer_size"`   // 读取缓冲区大小（字节）
	WriteBufferSize   int           `mapstructure:"write_buffer_size"`  // 写入缓冲区大小（字节）
	EnableCompression bool          `mapstructure:"enable_compression"` // 是否启用压缩
	AllowedOrigins    []string      `mapstructure:"allowed_origins"`    // 允许的跨域来源（为空则允许所有）
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
	Enabled       bool   `mapstructure:"enabled"`
	Key           string `mapstructure:"key"`            // 统一日志流的 Redis Stream key
	BufferSize    int    `mapstructure:"buffer_size"`    // 单个连接最大缓冲日志条数
	BatchSize     int    `mapstructure:"batch_size"`     // 达到多少条时批量发送
	FlushInterval int    `mapstructure:"flush_interval"` // 刷新间隔（毫秒）
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

// TaskStatsStreamConfig Redis Stream 写任务统计配置
type TaskStatsStreamConfig struct {
	Enabled      bool   `mapstructure:"enabled"`
	Key          string `mapstructure:"key"`           // Redis Stream key
	PushInterval int    `mapstructure:"push_interval"` // 推送间隔（秒）
}

// RedisConfig Redis 配置
type RedisConfig struct {
	Enabled     bool          `mapstructure:"enabled"`
	Addr        string        `mapstructure:"addr"`
	Password    string        `mapstructure:"password"`
	DB          int           `mapstructure:"db"`
	PoolSize    int           `mapstructure:"pool_size"`
	MinIdle     int           `mapstructure:"min_idle"`
	MaxIdle     int           `mapstructure:"max_idle"`
	IdleTimeout time.Duration `mapstructure:"idle_timeout"`
	WaitTimeout time.Duration `mapstructure:"wait_timeout"`
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

	// WebSocket 默认值
	viper.SetDefault("websocket.handshake_timeout", "10s")
	viper.SetDefault("websocket.read_buffer_size", 4096)
	viper.SetDefault("websocket.write_buffer_size", 4096)
	viper.SetDefault("websocket.enable_compression", true)
	viper.SetDefault("websocket.allowed_origins", []string{}) // 空数组表示允许所有来源

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
	viper.SetDefault("log_stream.buffer_size", 1000)    // 单个连接最大缓冲日志条数
	viper.SetDefault("log_stream.batch_size", 50)       // 达到多少条时批量发送
	viper.SetDefault("log_stream.flush_interval", 2000) // 刷新间隔（毫秒）

	// Result Stream 默认值
	viper.SetDefault("result_stream.enabled", true)
	viper.SetDefault("result_stream.key", "agent_results")

	// Status Stream 默认值
	viper.SetDefault("status_stream.enabled", true)
	viper.SetDefault("status_stream.key", "agent_status")

	// Task Stats Stream 默认值
	viper.SetDefault("task_stats_stream.enabled", true)
	viper.SetDefault("task_stats_stream.key", "agent_task_stats")
	viper.SetDefault("task_stats_stream.push_interval", 30) // 30秒

	// Redis 默认值
	viper.SetDefault("redis.enabled", false)
	viper.SetDefault("redis.addr", "localhost:6379")
	viper.SetDefault("redis.db", 0)

	// Auth 默认值
	viper.SetDefault("auth.shared_secret", "")
	viper.SetDefault("auth.clock_skew", "300s")
	viper.SetDefault("auth.require_signature", false)
}
