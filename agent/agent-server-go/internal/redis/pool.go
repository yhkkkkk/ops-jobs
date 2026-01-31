package redis

import (
	"context"
	"fmt"
	"time"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/logger"

	"github.com/redis/go-redis/v9"
)

// PoolManager redis连接池管理器
type PoolManager struct {
	client *redis.Client
	config *config.RedisConfig
}

// NewPoolManager 创建redis连接池管理器
func NewPoolManager(cfg *config.RedisConfig) *PoolManager {
	return &PoolManager{
		config: cfg,
	}
}

// GetClient 获取redis客户端，如果未初始化则创建
func (pm *PoolManager) GetClient() (*redis.Client, error) {
	if pm.client != nil {
		return pm.client, nil
	}

	if !pm.config.Enabled {
		return nil, fmt.Errorf("redis is not enabled")
	}

	// 设置默认值
	poolSize := pm.config.PoolSize
	if poolSize <= 0 {
		poolSize = 10
	}
	minIdle := pm.config.MinIdle
	if minIdle <= 0 {
		minIdle = 5
	}
	maxIdle := pm.config.MaxIdle
	if maxIdle <= 0 {
		maxIdle = 10
	}
	idleTimeout := pm.config.IdleTimeout
	if idleTimeout <= 0 {
		idleTimeout = 5 * time.Minute
	}
	waitTimeout := pm.config.WaitTimeout
	if waitTimeout <= 0 {
		waitTimeout = 3 * time.Second
	}

	// 创建redis客户端，使用连接池配置
	client := redis.NewClient(&redis.Options{
		Addr:            pm.config.Addr,
		Password:        pm.config.Password,
		DB:              pm.config.DB,
		PoolSize:        poolSize,
		MinIdleConns:    minIdle,
		MaxIdleConns:    maxIdle,
		ConnMaxIdleTime: idleTimeout,
		PoolTimeout:     waitTimeout,
		DialTimeout:     5 * time.Second, // 连接超时
		ReadTimeout:     3 * time.Second, // 读取超时
		WriteTimeout:    3 * time.Second, // 写入超时
	})

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		client.Close()
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	pm.client = client
	logger.GetLogger().WithFields(map[string]interface{}{
		"redis_addr": pm.config.Addr,
		"pool_size":  poolSize,
		"min_idle":   minIdle,
		"max_idle":   maxIdle,
	}).Info("redis connection pool initialized successfully")

	return pm.client, nil
}

// Close 关闭redis连接池
func (pm *PoolManager) Close() error {
	if pm.client != nil {
		err := pm.client.Close()
		pm.client = nil
		if err != nil {
			logger.GetLogger().WithError(err).Error("failed to close Redis connection pool")
			return err
		}
		logger.GetLogger().Info("redis connection pool closed successfully")
	}
	return nil
}

// IsEnabled 检查redis是否启用
func (pm *PoolManager) IsEnabled() bool {
	return pm.config.Enabled
}

// GetPoolStats 获取连接池统计信息（用于监控）
func (pm *PoolManager) GetPoolStats() map[string]interface{} {
	if pm.client == nil {
		return map[string]interface{}{
			"enabled": false,
		}
	}

	stats := pm.client.PoolStats()
	return map[string]interface{}{
		"enabled":     true,
		"total_conns": stats.TotalConns,
		"idle_conns":  stats.IdleConns,
		"stale_conns": stats.StaleConns,
		"hits":        stats.Hits,
		"misses":      stats.Misses,
		"timeouts":    stats.Timeouts,
	}
}
