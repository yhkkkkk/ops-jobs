package core

import (
	"context"
	"math"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/load"

	"ops-job-agent/internal/config"
	"ops-job-agent/internal/logger"
)

const adaptiveEmaAlpha = 0.3

// adaptiveController 负责基于 CPU/Load 动态计算因子
// factor 范围 [min_factor, 1.0]
type adaptiveController struct {
	cfgMu      sync.RWMutex
	cfg        config.ResourceAdaptiveConfig
	factorBits uint64
	cores      float64

	emaCPU   float64
	emaLoad  float64
	inited   bool
	lastTune time.Time
	lastWarn time.Time
}

func newAdaptiveController(cfg config.ResourceAdaptiveConfig) *adaptiveController {
	c := &adaptiveController{
		cfg:   cfg,
		cores: float64(runtime.NumCPU()),
	}
	atomic.StoreUint64(&c.factorBits, math.Float64bits(1.0))
	return c
}

func (c *adaptiveController) Start(ctx context.Context) {
	go c.loop(ctx)
}

func (c *adaptiveController) UpdateConfig(cfg config.ResourceAdaptiveConfig) {
	c.cfgMu.Lock()
	c.cfg = cfg
	c.cfgMu.Unlock()
	if !cfg.Enabled {
		c.setFactor(1.0)
	}
}

func (c *adaptiveController) Factor() float64 {
	return math.Float64frombits(atomic.LoadUint64(&c.factorBits))
}

func (c *adaptiveController) loop(ctx context.Context) {
	for {
		interval := c.getInterval()
		timer := time.NewTimer(interval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
			c.sampleAndAdjust()
		}
	}
}

func (c *adaptiveController) getInterval() time.Duration {
	c.cfgMu.RLock()
	defer c.cfgMu.RUnlock()
	sec := c.cfg.SampleIntervalSec
	if sec <= 0 {
		sec = 5
	}
	return time.Duration(sec) * time.Second
}

func (c *adaptiveController) sampleAndAdjust() {
	cfg := c.getConfig()
	if !cfg.Enabled {
		c.setFactor(1.0)
		return
	}

	cpuPct, cpuOk := c.readCPU()
	load1, loadOk := c.readLoad()
	if !cpuOk && !loadOk {
		c.setFactor(1.0)
		return
	}

	if !c.inited {
		if cpuOk {
			c.emaCPU = cpuPct
		}
		if loadOk {
			c.emaLoad = load1
		}
		c.inited = true
		return
	}

	if cpuOk {
		c.emaCPU = adaptiveEmaAlpha*cpuPct + (1-adaptiveEmaAlpha)*c.emaCPU
	}
	if loadOk {
		c.emaLoad = adaptiveEmaAlpha*load1 + (1-adaptiveEmaAlpha)*c.emaLoad
	}

	if cfg.CooldownSec > 0 {
		if time.Since(c.lastTune) < time.Duration(cfg.CooldownSec)*time.Second {
			return
		}
	}

	loadHigh := c.cores * cfg.LoadHighFactor
	loadLow := c.cores * cfg.LoadLowFactor

	shouldDown := false
	shouldUp := false
	if cpuOk && c.emaCPU >= cfg.CPUHigh {
		shouldDown = true
	}
	if loadOk && c.emaLoad >= loadHigh {
		shouldDown = true
	}
	if cpuOk {
		shouldUp = c.emaCPU <= cfg.CPULow
	} else if loadOk {
		shouldUp = c.emaLoad <= loadLow
	}
	if loadOk && cpuOk {
		shouldUp = shouldUp && (c.emaLoad <= loadLow)
	}

	current := c.Factor()
	if shouldDown {
		next := current - cfg.Step
		if next < cfg.MinFactor {
			next = cfg.MinFactor
		}
		c.setFactor(next)
		c.lastTune = time.Now()
		return
	}

	if shouldUp {
		next := current + cfg.Step
		if next > 1.0 {
			next = 1.0
		}
		c.setFactor(next)
		c.lastTune = time.Now()
	}
}

func (c *adaptiveController) readCPU() (float64, bool) {
	pct, err := cpu.Percent(0, false)
	if err != nil || len(pct) == 0 {
		c.warnOnce("cpu")
		return 0, false
	}
	return pct[0], true
}

func (c *adaptiveController) readLoad() (float64, bool) {
	avg, err := load.Avg()
	if err != nil || avg == nil {
		c.warnOnce("load")
		return 0, false
	}
	return avg.Load1, true
}

func (c *adaptiveController) warnOnce(kind string) {
	if time.Since(c.lastWarn) < time.Minute {
		return
	}
	c.lastWarn = time.Now()
	logger.GetLogger().WithField("kind", kind).Warn("resource adaptive: failed to read metric, fallback to config")
}

func (c *adaptiveController) getConfig() config.ResourceAdaptiveConfig {
	c.cfgMu.RLock()
	defer c.cfgMu.RUnlock()
	return c.cfg
}

func (c *adaptiveController) setFactor(val float64) {
	if val <= 0 {
		val = 1.0
	}
	if val > 1.0 {
		val = 1.0
	}
	atomic.StoreUint64(&c.factorBits, math.Float64bits(val))
}
