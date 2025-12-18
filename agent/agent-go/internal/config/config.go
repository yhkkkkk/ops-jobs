package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/fsnotify/fsnotify"
	"github.com/spf13/viper"
)

// Config 保存 agent 配置
type Config struct {
	// 连接模式：direct（直连控制面）或 agent-server（通过 Agent-Server）
	Mode               string            `mapstructure:"mode"`              // direct/agent-server
	ControlPlaneURL    string            `mapstructure:"control_plane_url"` // 控制面地址（direct 模式）
	AgentServerURL     string            `mapstructure:"agent_server_url"`  // Agent-Server 地址（agent-server 模式）
	AgentServerBackup  string            `mapstructure:"agent_server_backup_url"`
	WSBackoffInitialMs int               `mapstructure:"ws_backoff_initial_ms"`
	WSBackoffMaxMs     int               `mapstructure:"ws_backoff_max_ms"`
	WSMaxRetries       int               `mapstructure:"ws_max_retries"`
	WSOutboxMaxSize    int               `mapstructure:"ws_outbox_max_size"` // ws 断线本地缓冲上限（消息条数）
	HTTPAddr           string            `mapstructure:"http_addr"`
	DirectSharedSecret string            `mapstructure:"direct_shared_secret"` // 直连模式共享密钥（Bearer/HMAC）
	AgentName          string            `mapstructure:"agent_name"`
	AgentLabels        map[string]string `mapstructure:"agent_labels"`
	AgentToken         string            `mapstructure:"agent_token"`
	LogDir             string            `mapstructure:"log_dir"`
	LogLevel           string            `mapstructure:"log_level"`
	LogMaxSize         int               `mapstructure:"log_max_size"`         // 日志文件最大大小（MB）
	LogMaxFiles        int               `mapstructure:"log_max_files"`        // 最大保留日志文件数
	LogMaxAge          int               `mapstructure:"log_max_age"`          // 日志保留天数
	HeartbeatInterval  int               `mapstructure:"heartbeat_interval"`   // 心跳间隔（秒）
	TaskPollInterval   int               `mapstructure:"task_poll_interval"`   // 任务轮询间隔（秒，仅 direct 模式）
	MaxConcurrentTasks int               `mapstructure:"max_concurrent_tasks"` // 最大并发任务数
	LogBatchSize       int               `mapstructure:"log_batch_size"`       // 日志批量推送大小
	LogFlushInterval   int               `mapstructure:"log_flush_interval"`   // 日志刷新间隔（毫秒）
	EnableTLS          bool              `mapstructure:"enable_tls"`
	TLSCertFile        string            `mapstructure:"tls_cert_file"`
	TLSKeyFile         string            `mapstructure:"tls_key_file"`
	// 资源限制
	BandwidthLimit int     `mapstructure:"bandwidth_limit"` // 带宽限制（KB/s），0表示不限制
	CPULimit       float64 `mapstructure:"cpu_limit"`       // cpu 使用率限制（百分比），0表示不限制
	MemoryLimit    int     `mapstructure:"memory_limit"`    // 内存限制（MB），0表示不限制

	// Redis配置（用于asynq）
	Redis RedisConfig `mapstructure:"redis"`

	// Asynq配置
	Asynq AsynqConfig `mapstructure:"asynq"`
}

// RedisConfig Redis配置
type RedisConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Addr     string `mapstructure:"addr"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

// AsynqConfig Asynq配置
type AsynqConfig struct {
	Enabled     bool `mapstructure:"enabled"`
	Concurrency int  `mapstructure:"concurrency"`
}

var (
	cfgMu        sync.RWMutex
	currentCfg   *Config
	vp           *viper.Viper
	initOnce     sync.Once
	subscribers  []func(*Config)
	subscriberMu sync.Mutex
)

// initViper 初始化全局 viper，并启用 WatchConfig。
func initViper() error {
	v := viper.New()

	// 设置默认值
	setDefaults(v)

	// 设置环境变量前缀
	v.SetEnvPrefix("AGENT")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	// 绑定环境变量
	bindEnvVars(v)

	// 尝试从配置文件加载
	configFile := v.GetString("config_file")
	if configFile == "" {
		// 优先使用二进制同目录下的 config/config.yaml
		if exePath, err := os.Executable(); err == nil {
			exeDir := filepath.Dir(exePath)
			localCfg := filepath.Join(exeDir, "config", "config.yaml")
			if _, err := os.Stat(localCfg); err == nil {
				configFile = localCfg
			}
		}
	}

	// 如果配置文件存在，读取它
	if configFile != "" {
		if _, err := os.Stat(configFile); err == nil {
			v.SetConfigFile(configFile)
			v.SetConfigType("yaml")
			if err := v.ReadInConfig(); err != nil {
				return fmt.Errorf("read config file failed: %w", err)
			}
		}
	}

	// 第一次解析配置
	if err := reloadFromViper(v); err != nil {
		return err
	}

	// 启用 WatchConfig
	v.WatchConfig()
	v.OnConfigChange(func(e fsnotify.Event) {
		_ = reloadFromViper(v)
	})

	vp = v
	return nil
}

// reloadFromViper 从给定 viper 实例重新解析配置并更新全局快照与订阅者。
func reloadFromViper(v *viper.Viper) error {
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return fmt.Errorf("unmarshal config failed: %w", err)
	}

	cfg.Mode = strings.ToLower(strings.TrimSpace(cfg.Mode))
	if cfg.Mode == "" {
		cfg.Mode = "direct"
	}
	switch cfg.Mode {
	case "direct":
		if cfg.ControlPlaneURL == "" {
			return fmt.Errorf("control_plane_url is required in direct mode")
		}
	case "agent-server":
		if cfg.AgentServerURL == "" {
			return fmt.Errorf("agent_server_url is required in agent-server mode")
		}
	default:
		return fmt.Errorf("invalid mode %q, must be direct or agent-server", cfg.Mode)
	}

	// 处理标签字符串（如果从环境变量读取）
	if len(cfg.AgentLabels) == 0 {
		if labelsStr := v.GetString("labels"); labelsStr != "" {
			cfg.AgentLabels = parseLabels(labelsStr)
		}
	}

	// 设置默认值（如果未配置）
	setConfigDefaults(&cfg)

	cfgMu.Lock()
	currentCfg = &cfg
	cfgMu.Unlock()

	// 通知订阅者
	subscriberMu.Lock()
	subs := append([]func(*Config){}, subscribers...)
	subscriberMu.Unlock()
	for _, fn := range subs {
		fn(&cfg)
	}

	return nil
}

// Load 返回当前配置快照（每次返回拷贝，避免被调用方修改内部状态）。
func Load() (*Config, error) {
	var err error
	initOnce.Do(func() {
		err = initViper()
	})
	if err != nil {
		return nil, err
	}

	cfgMu.RLock()
	defer cfgMu.RUnlock()
	if currentCfg == nil {
		return nil, fmt.Errorf("config not initialized")
	}
	cpy := *currentCfg
	return &cpy, nil
}

// Subscribe 注册配置变更回调，首次注册时会立即收到当前配置一次。
func Subscribe(fn func(*Config)) {
	if fn == nil {
		return
	}
	subscriberMu.Lock()
	subscribers = append(subscribers, fn)
	subscriberMu.Unlock()

	cfgMu.RLock()
	defer cfgMu.RUnlock()
	if currentCfg != nil {
		fn(currentCfg)
	}
}

// setDefaults 设置默认值
func setDefaults(v *viper.Viper) {
	v.SetDefault("mode", "direct") // 默认直连模式
	v.SetDefault("control_plane_url", "http://localhost:8000")
	v.SetDefault("agent_server_url", "ws://localhost:8080")
	v.SetDefault("agent_server_backup_url", "")
	v.SetDefault("ws_backoff_initial_ms", 1000)
	v.SetDefault("ws_backoff_max_ms", 30000)
	v.SetDefault("ws_max_retries", 6)
	v.SetDefault("ws_outbox_max_size", 2000)
	v.SetDefault("http_addr", ":8080")
	v.SetDefault("direct_shared_secret", "")
	v.SetDefault("agent_name", getHostname())
	v.SetDefault("agent_token", "")
	v.SetDefault("log_dir", "")
	v.SetDefault("log_level", "info")
	v.SetDefault("log_max_size", 10) // 10MB
	v.SetDefault("log_max_files", 5)
	v.SetDefault("log_max_age", 7)         // 7天
	v.SetDefault("heartbeat_interval", 10) // 10秒
	v.SetDefault("task_poll_interval", 5)  // 5秒
	v.SetDefault("max_concurrent_tasks", 5)
	v.SetDefault("enable_tls", false)
	v.SetDefault("tls_cert_file", "")
	v.SetDefault("tls_key_file", "")
	v.SetDefault("bandwidth_limit", 0) // 0表示不限制
	v.SetDefault("cpu_limit", 0.0)     // 0表示不限制
	v.SetDefault("memory_limit", 0)    // 0表示不限制

	// Redis默认值
	v.SetDefault("redis.enabled", false)
	v.SetDefault("redis.addr", "localhost:6379")
	v.SetDefault("redis.db", 0)

	// Asynq默认值
	v.SetDefault("asynq.enabled", false)
	v.SetDefault("asynq.concurrency", 5)
}

// bindEnvVars 绑定环境变量
func bindEnvVars(v *viper.Viper) {
	if val := os.Getenv("CONTROL_PLANE_URL"); val != "" {
		v.Set("control_plane_url", val)
	}
	if val := os.Getenv("AGENT_MODE"); val != "" {
		v.Set("mode", val)
	}
	if val := os.Getenv("AGENT_SERVER_URL"); val != "" {
		v.Set("agent_server_url", val)
	}
	if val := os.Getenv("AGENT_SERVER_BACKUP_URL"); val != "" {
		v.Set("agent_server_backup_url", val)
	}
	if val := os.Getenv("AGENT_WS_BACKOFF_INITIAL_MS"); val != "" {
		v.Set("ws_backoff_initial_ms", val)
	}
	if val := os.Getenv("AGENT_WS_BACKOFF_MAX_MS"); val != "" {
		v.Set("ws_backoff_max_ms", val)
	}
	if val := os.Getenv("AGENT_WS_MAX_RETRIES"); val != "" {
		v.Set("ws_max_retries", val)
	}
	if val := os.Getenv("AGENT_WS_OUTBOX_MAX_SIZE"); val != "" {
		v.Set("ws_outbox_max_size", val)
	}
	if val := os.Getenv("AGENT_HTTP_ADDR"); val != "" {
		v.Set("http_addr", val)
	}
	if val := os.Getenv("AGENT_DIRECT_SHARED_SECRET"); val != "" {
		v.Set("direct_shared_secret", val)
	}
	if val := os.Getenv("AGENT_NAME"); val != "" {
		v.Set("agent_name", val)
	}
	if val := os.Getenv("AGENT_TOKEN"); val != "" {
		v.Set("agent_token", val)
	}
	if val := os.Getenv("AGENT_LABELS"); val != "" {
		v.Set("labels", val)
	}
	if val := os.Getenv("AGENT_LOG_DIR"); val != "" {
		v.Set("log_dir", val)
	}
	if val := os.Getenv("AGENT_LOG_LEVEL"); val != "" {
		v.Set("log_level", val)
	}
	if val := os.Getenv("AGENT_LOG_MAX_SIZE"); val != "" {
		v.Set("log_max_size", val)
	}
	if val := os.Getenv("AGENT_LOG_MAX_FILES"); val != "" {
		v.Set("log_max_files", val)
	}
	if val := os.Getenv("AGENT_LOG_MAX_AGE"); val != "" {
		v.Set("log_max_age", val)
	}
	if val := os.Getenv("AGENT_HEARTBEAT_INTERVAL"); val != "" {
		v.Set("heartbeat_interval", val)
	}
	if val := os.Getenv("AGENT_TASK_POLL_INTERVAL"); val != "" {
		v.Set("task_poll_interval", val)
	}
	if val := os.Getenv("AGENT_MAX_CONCURRENT_TASKS"); val != "" {
		v.Set("max_concurrent_tasks", val)
	}
	if val := os.Getenv("AGENT_ENABLE_TLS"); val != "" {
		v.Set("enable_tls", val == "true")
	}
	if val := os.Getenv("AGENT_TLS_CERT_FILE"); val != "" {
		v.Set("tls_cert_file", val)
	}
	if val := os.Getenv("AGENT_TLS_KEY_FILE"); val != "" {
		v.Set("tls_key_file", val)
	}
	if val := os.Getenv("AGENT_CONFIG_FILE"); val != "" {
		v.Set("config_file", val)
	}
}

// setConfigDefaults 设置配置默认值
func setConfigDefaults(cfg *Config) {
	if cfg.AgentName == "" {
		cfg.AgentName = getHostname()
	}
	if cfg.LogMaxSize <= 0 {
		cfg.LogMaxSize = 10
	}
	if cfg.LogMaxFiles <= 0 {
		cfg.LogMaxFiles = 5
	}
	if cfg.LogMaxAge <= 0 {
		cfg.LogMaxAge = 7
	}
	if cfg.HeartbeatInterval <= 0 {
		cfg.HeartbeatInterval = 30
	}
	if cfg.TaskPollInterval <= 0 {
		cfg.TaskPollInterval = 10
	}
	if cfg.MaxConcurrentTasks <= 0 {
		cfg.MaxConcurrentTasks = 5
	}
	if cfg.LogBatchSize <= 0 {
		cfg.LogBatchSize = 10
	}
	if cfg.LogFlushInterval <= 0 {
		cfg.LogFlushInterval = 200
	}
	if cfg.AgentLabels == nil {
		cfg.AgentLabels = make(map[string]string)
	}
}

// parseLabels 解析标签字符串（格式：key1=value1,key2=value2）
func parseLabels(s string) map[string]string {
	labels := make(map[string]string)
	if s == "" {
		return labels
	}
	for _, pair := range strings.Split(s, ",") {
		parts := strings.SplitN(pair, "=", 2)
		if len(parts) == 2 {
			labels[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return labels
}

func getHostname() string {
	h, err := os.Hostname()
	if err != nil {
		return "unknown-agent"
	}
	return h
}
