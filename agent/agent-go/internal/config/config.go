package config

import (
	"fmt"
	"ops-job-agent/internal/constants"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/fsnotify/fsnotify"
	"github.com/spf13/viper"
)

// ConnectionConfig 连接配置（仅支持 Agent-Server WS 模式）
type ConnectionConfig struct {
	AgentServerURL     string `mapstructure:"agent_server_url"`        // Agent-Server 地址
	AgentServerBackup  string `mapstructure:"agent_server_backup_url"` // 可选备用 WS 地址
	WSBackoffInitialMs int    `mapstructure:"ws_backoff_initial_ms"`
	WSBackoffMaxMs     int    `mapstructure:"ws_backoff_max_ms"`
	WSMaxRetries       int    `mapstructure:"ws_max_retries"`
	WSOutboxMaxSize    int    `mapstructure:"ws_outbox_max_size"` // WS 断线本地缓冲上限（消息条数）
	WSEnableCompression bool   `mapstructure:"ws_enable_compression"` // 是否启用 WebSocket 压缩
}

// IdentificationConfig 身份标识配置
type IdentificationConfig struct {
	AgentName  string `mapstructure:"agent_name"`
	AgentToken string `mapstructure:"agent_token"`
	HostID     int    `mapstructure:"host_id"` // 控制面主机ID，用于建立映射关系
}

// LoggingConfig 日志配置
type LoggingConfig struct {
	LogDir           string `mapstructure:"log_dir"`
	LogLevel         string `mapstructure:"log_level"`
	LogMaxSize       int    `mapstructure:"log_max_size"`       // 日志文件最大大小（MB）
	LogMaxFiles      int    `mapstructure:"log_max_files"`      // 最大保留日志文件数
	LogMaxAge        int    `mapstructure:"log_max_age"`        // 日志保留天数
	LogBatchSize     int    `mapstructure:"log_batch_size"`     // 日志批量推送大小
	LogFlushInterval int    `mapstructure:"log_flush_interval"` // 日志刷新间隔（毫秒）
}

// TaskConfig 任务配置
type TaskConfig struct {
	HeartbeatInterval   int `mapstructure:"heartbeat_interval"`     // 心跳间隔（秒）
	MaxConcurrentTasks  int `mapstructure:"max_concurrent_tasks"`   // 最大并发任务数
	MaxExecutionTimeSec int `mapstructure:"max_execution_time_sec"` // 全局最大任务执行时间（秒）
}

// ResourceLimitConfig 资源限制配置（当前仅带宽，单位 MB/s）
type ResourceLimitConfig struct {
	BandwidthLimit int `mapstructure:"bandwidth_limit"` // 带宽限制（MB/s），0表示不限制
}

// ResourceAdaptiveConfig 资源自适应配置（CPU/Load 驱动的动态限速/并发）
type ResourceAdaptiveConfig struct {
	Enabled           bool    `mapstructure:"enabled"`             // 是否启用
	SampleIntervalSec int     `mapstructure:"sample_interval_sec"` // 采样间隔（秒）
	CPUHigh           float64 `mapstructure:"cpu_high"`            // CPU 高阈值（%）
	CPULow            float64 `mapstructure:"cpu_low"`             // CPU 低阈值（%）
	LoadHighFactor    float64 `mapstructure:"load_high_factor"`    // Load 高阈值系数（*CPU核数）
	LoadLowFactor     float64 `mapstructure:"load_low_factor"`     // Load 低阈值系数（*CPU核数）
	MinFactor         float64 `mapstructure:"min_factor"`          // 动态因子最小值
	Step              float64 `mapstructure:"step"`                // 每次调整步长
	CooldownSec       int     `mapstructure:"cooldown_sec"`        // 调整冷却时间（秒）
	MinBandwidthMB    int     `mapstructure:"min_bandwidth_mb"`    // 限速下限（MB/s）
}

// Config 保存 agent 配置
type Config struct {
	Connection     ConnectionConfig     `mapstructure:"connection"`
	Identification IdentificationConfig `mapstructure:"identification"`
	Logging        LoggingConfig        `mapstructure:"logging"`
	Task           TaskConfig           `mapstructure:"task"`
	ResourceLimit  ResourceLimitConfig  `mapstructure:"resource_limit"`
	ResourceAdaptive ResourceAdaptiveConfig `mapstructure:"resource_adaptive"`
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

	// 设置环境变量前缀（使用层级键，如 AGENT_CONNECTION_AGENT_SERVER_URL）
	v.SetEnvPrefix("AGENT")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

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

	if cfg.Connection.AgentServerURL == "" {
		return fmt.Errorf("agent_server_url is required")
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
	// Connection 默认值
	v.SetDefault("connection.agent_server_url", "ws://localhost:8080")
	v.SetDefault("connection.agent_server_backup_url", "")
	v.SetDefault("connection.ws_backoff_initial_ms", 1000)
	v.SetDefault("connection.ws_backoff_max_ms", 30000)
	v.SetDefault("connection.ws_max_retries", 6)
	v.SetDefault("connection.ws_outbox_max_size", 2000)
	v.SetDefault("connection.ws_enable_compression", false)

	// Identification 默认值
	v.SetDefault("identification.agent_name", getHostname())
	v.SetDefault("identification.agent_token", "")

	// Logging 默认值
	v.SetDefault("logging.log_dir", "")
	v.SetDefault("logging.log_level", "info")
	v.SetDefault("logging.log_max_size", 10) // 10MB
	v.SetDefault("logging.log_max_files", 5)
	v.SetDefault("logging.log_max_age", 7) // 7天
	v.SetDefault("logging.log_batch_size", 10)
	v.SetDefault("logging.log_flush_interval", 200)

	// Task 默认值
	v.SetDefault("task.heartbeat_interval", 10) // 10秒
	v.SetDefault("task.max_concurrent_tasks", 5)
	v.SetDefault("task.max_execution_time_sec", 7200) // 默认2小时

	// ResourceLimit 默认值
	v.SetDefault("resource_limit.bandwidth_limit", 0) // 0表示不限制

	// ResourceAdaptive 默认值
	v.SetDefault("resource_adaptive.enabled", false)
	v.SetDefault("resource_adaptive.sample_interval_sec", 5)
	v.SetDefault("resource_adaptive.cpu_high", 75.0)
	v.SetDefault("resource_adaptive.cpu_low", 55.0)
	v.SetDefault("resource_adaptive.load_high_factor", 1.2)
	v.SetDefault("resource_adaptive.load_low_factor", 0.8)
	v.SetDefault("resource_adaptive.min_factor", 0.3)
	v.SetDefault("resource_adaptive.step", 0.1)
	v.SetDefault("resource_adaptive.cooldown_sec", 15)
	v.SetDefault("resource_adaptive.min_bandwidth_mb", 1)
}

// setConfigDefaults 设置配置默认值
func setConfigDefaults(cfg *Config) {
	if cfg.Identification.AgentName == "" {
		cfg.Identification.AgentName = getHostname()
	}
	if cfg.Logging.LogMaxSize <= 0 {
		cfg.Logging.LogMaxSize = 10
	}
	if cfg.Logging.LogMaxFiles <= 0 {
		cfg.Logging.LogMaxFiles = 5
	}
	if cfg.Logging.LogMaxAge <= 0 {
		cfg.Logging.LogMaxAge = 7
	}
	if cfg.Task.HeartbeatInterval <= 0 {
		cfg.Task.HeartbeatInterval = constants.DefaultHeartbeatIntervalSec
	}
	if cfg.Task.MaxConcurrentTasks <= 0 {
		cfg.Task.MaxConcurrentTasks = constants.DefaultMaxConcurrentTasks
	}
	if cfg.Task.MaxExecutionTimeSec <= 0 {
		cfg.Task.MaxExecutionTimeSec = 7200
	}
	if cfg.Logging.LogBatchSize <= 0 {
		cfg.Logging.LogBatchSize = 10
	}
	if cfg.Logging.LogFlushInterval <= 0 {
		cfg.Logging.LogFlushInterval = 200
	}
	// ResourceAdaptive 默认/校验
	if cfg.ResourceAdaptive.SampleIntervalSec <= 0 {
		cfg.ResourceAdaptive.SampleIntervalSec = 5
	}
	if cfg.ResourceAdaptive.CPUHigh <= 0 {
		cfg.ResourceAdaptive.CPUHigh = 75.0
	}
	if cfg.ResourceAdaptive.CPULow <= 0 || cfg.ResourceAdaptive.CPULow >= cfg.ResourceAdaptive.CPUHigh {
		cfg.ResourceAdaptive.CPULow = 55.0
	}
	if cfg.ResourceAdaptive.LoadHighFactor <= 0 {
		cfg.ResourceAdaptive.LoadHighFactor = 1.2
	}
	if cfg.ResourceAdaptive.LoadLowFactor <= 0 || cfg.ResourceAdaptive.LoadLowFactor >= cfg.ResourceAdaptive.LoadHighFactor {
		cfg.ResourceAdaptive.LoadLowFactor = 0.8
	}
	if cfg.ResourceAdaptive.MinFactor <= 0 || cfg.ResourceAdaptive.MinFactor > 1 {
		cfg.ResourceAdaptive.MinFactor = 0.3
	}
	if cfg.ResourceAdaptive.Step <= 0 || cfg.ResourceAdaptive.Step > 1 {
		cfg.ResourceAdaptive.Step = 0.1
	}
	if cfg.ResourceAdaptive.CooldownSec <= 0 {
		cfg.ResourceAdaptive.CooldownSec = 15
	}
	if cfg.ResourceAdaptive.MinBandwidthMB <= 0 {
		cfg.ResourceAdaptive.MinBandwidthMB = 1
	}
}

func getHostname() string {
	h, err := os.Hostname()
	if err != nil {
		return "unknown-agent"
	}
	return h
}
