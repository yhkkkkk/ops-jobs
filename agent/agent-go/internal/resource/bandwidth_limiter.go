package resource

import (
	"io"
	"time"
)

// BandwidthLimiter 带宽限制器
type BandwidthLimiter struct {
	limitBytesPerSec int64        // 每秒允许的字节数
	lastWriteTime    time.Time    // 上次写入时间
	writtenBytes     int64        // 已写入的字节数
	startTime        time.Time    // 开始时间
}

// NewBandwidthLimiter 创建带宽限制器
// bandwidthLimitKB: 带宽限制（KB/s），0表示不限制
func NewBandwidthLimiter(bandwidthLimitKB int) *BandwidthLimiter {
	limitBytesPerSec := int64(0)
	if bandwidthLimitKB > 0 {
		limitBytesPerSec = int64(bandwidthLimitKB) * 1024 // 转换为字节/秒
	}
	return &BandwidthLimiter{
		limitBytesPerSec: limitBytesPerSec,
		startTime:        time.Now(),
		lastWriteTime:    time.Now(),
	}
}

// LimitWriter 创建一个带带宽限制的 Writer
func (bl *BandwidthLimiter) LimitWriter(w io.Writer) io.Writer {
	if bl.limitBytesPerSec <= 0 {
		return w // 不限制
	}
	return &limitedWriter{
		writer:  w,
		limiter: bl,
	}
}

// limitedWriter 带带宽限制的 Writer
type limitedWriter struct {
	writer  io.Writer
	limiter *BandwidthLimiter
}

// Write 实现 io.Writer 接口，带带宽限制
func (lw *limitedWriter) Write(p []byte) (n int, err error) {
	if lw.limiter.limitBytesPerSec <= 0 {
		return lw.writer.Write(p)
	}

	now := time.Now()
	bytesToWrite := int64(len(p))

	// 计算从开始到现在的时间差
	elapsed := now.Sub(lw.limiter.startTime).Seconds()
	if elapsed > 0 {
		// 计算当前应该允许写入的最大字节数
		maxAllowedBytes := int64(elapsed * float64(lw.limiter.limitBytesPerSec))

		// 如果已写入的字节数超过限制，需要等待
		if lw.limiter.writtenBytes >= maxAllowedBytes {
			// 计算需要等待的时间
			expectedTime := float64(lw.limiter.writtenBytes) / float64(lw.limiter.limitBytesPerSec)
			waitTime := expectedTime - elapsed
			if waitTime > 0 {
				time.Sleep(time.Duration(waitTime * float64(time.Second)))
				// 更新开始时间，避免累积误差
				lw.limiter.startTime = time.Now()
				lw.limiter.writtenBytes = 0
			}
		}
	}

	// 计算本次写入的字节数（可能分块写入）
	remaining := bytesToWrite
	written := int64(0)

	for remaining > 0 {
		// 计算本次可以写入的最大字节数
		elapsed = time.Since(lw.limiter.startTime).Seconds()
		maxAllowedBytes := int64(elapsed * float64(lw.limiter.limitBytesPerSec))
		availableBytes := maxAllowedBytes - lw.limiter.writtenBytes

		if availableBytes <= 0 {
			// 需要等待
			expectedTime := float64(lw.limiter.writtenBytes) / float64(lw.limiter.limitBytesPerSec)
			waitTime := expectedTime - elapsed
			if waitTime > 0 {
				time.Sleep(time.Duration(waitTime * float64(time.Second)))
				lw.limiter.startTime = time.Now()
				lw.limiter.writtenBytes = 0
				continue
			}
		}

		// 确定本次写入的字节数
		chunkSize := remaining
		if availableBytes < remaining {
			chunkSize = availableBytes
		}

		// 写入数据
		chunk := p[written : written+chunkSize]
		n, err := lw.writer.Write(chunk)
		if err != nil {
			return int(written), err
		}

		written += int64(n)
		remaining -= int64(n)
		lw.limiter.writtenBytes += int64(n)

		if int64(n) < chunkSize {
			break // 写入的字节数少于预期，可能遇到错误
		}
	}

	return int(written), nil
}

// Reset 重置限制器状态
func (bl *BandwidthLimiter) Reset() {
	bl.startTime = time.Now()
	bl.lastWriteTime = time.Now()
	bl.writtenBytes = 0
}

// GetCurrentSpeed 获取当前速度（字节/秒）
func (bl *BandwidthLimiter) GetCurrentSpeed() float64 {
	if bl.limitBytesPerSec <= 0 {
		return 0
	}
	elapsed := time.Since(bl.startTime).Seconds()
	if elapsed <= 0 {
		return 0
	}
	return float64(bl.writtenBytes) / elapsed
}

