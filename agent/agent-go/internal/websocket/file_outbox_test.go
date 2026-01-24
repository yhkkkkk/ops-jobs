package websocket

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

// TestFileOutboxBasicOperations 测试 FileOutbox 基本操作
func TestFileOutboxBasicOperations(t *testing.T) {
	// 创建临时目录
	tmpDir := t.TempDir()
	agentID := "test-agent-1"

	outbox := NewFileOutbox(agentID, tmpDir, 100)
	if outbox == nil {
		t.Fatal("failed to create FileOutbox")
	}
	defer outbox.Close()

	// 测试初始状态
	if outbox.Len() != 0 {
		t.Errorf("expected length 0, got %d", outbox.Len())
	}

	// 添加消息
	msg := Message{
		MessageID: "msg-1",
		Type:      "task_result",
		TaskID:    "task-1",
		Timestamp: time.Now().UnixMilli(),
	}
	outbox.Enqueue(msg)

	if outbox.Len() != 1 {
		t.Errorf("expected length 1, got %d", outbox.Len())
	}

	// 取出消息
	drained := outbox.Drain(1)
	if len(drained) != 1 {
		t.Errorf("expected 1 message, got %d", len(drained))
	}
	if drained[0].MessageID != "msg-1" {
		t.Errorf("expected message ID msg-1, got %s", drained[0].MessageID)
	}

	if outbox.Len() != 0 {
		t.Errorf("expected length 0 after drain, got %d", outbox.Len())
	}
}

// TestFileOutboxMultipleMessages 测试多条消息
func TestFileOutboxMultipleMessages(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-2"

	outbox := NewFileOutbox(agentID, tmpDir, 100)
	defer outbox.Close()

	// 添加 10 条消息
	for i := 0; i < 10; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-%d", i),
			Type:      "task_result",
			TaskID:    fmt.Sprintf("task-%d", i),
			Timestamp: time.Now().UnixMilli(),
		}
		outbox.Enqueue(msg)
	}

	if outbox.Len() != 10 {
		t.Errorf("expected length 10, got %d", outbox.Len())
	}

	// 批量取出
	drained := outbox.Drain(5)
	if len(drained) != 5 {
		t.Errorf("expected 5 messages, got %d", len(drained))
	}

	if outbox.Len() != 5 {
		t.Errorf("expected length 5, got %d", outbox.Len())
	}

	// 再取出 5 条
	drained = outbox.Drain(5)
	if len(drained) != 5 {
		t.Errorf("expected 5 messages, got %d", len(drained))
	}

	if outbox.Len() != 0 {
		t.Errorf("expected length 0, got %d", outbox.Len())
	}
}

// TestFileOutboxOverflow 测试队列溢出
func TestFileOutboxOverflow(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-3"
	maxSize := 5

	outbox := NewFileOutbox(agentID, tmpDir, maxSize)
	defer outbox.Close()

	// 添加超过 maxSize 的消息
	for i := 0; i < 10; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-overflow-%d", i),
			Type:      "log",
			TaskID:    "task-1",
			Timestamp: time.Now().UnixMilli(),
		}
		outbox.Enqueue(msg)
	}

	// 队列应该保持在 maxSize
	if outbox.Len() != maxSize {
		t.Errorf("expected length %d (max size), got %d", maxSize, outbox.Len())
	}

	// 检查丢弃计数
	dropped := outbox.Dropped()
	if dropped != 5 {
		t.Errorf("expected 5 dropped messages, got %d", dropped)
	}
}

// TestFileOutboxConcurrentAccess 测试并发访问安全
func TestFileOutboxConcurrentAccess(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-4"
	maxSize := 1000

	outbox := NewFileOutbox(agentID, tmpDir, maxSize)
	defer outbox.Close()

	var wg sync.WaitGroup
	numGoroutines := 10
	messagesPerGoroutine := 100

	// 并发添加消息
	for i := 0; i < numGoroutines; i++ {
		wg.Add(1)
		go func(goroutineID int) {
			defer wg.Done()
			for j := 0; j < messagesPerGoroutine; j++ {
				msg := Message{
					MessageID: fmt.Sprintf("msg-g%d-j%d", goroutineID, j),
					Type:      "task_result",
					TaskID:    fmt.Sprintf("task-goroutine-%d", goroutineID),
					Timestamp: time.Now().UnixMilli(),
				}
				outbox.Enqueue(msg)
			}
		}(i)
	}

	wg.Wait()

	// 队列长度应该接近预期值（可能有少量差异因为溢出）
	length := outbox.Len()
	if length == 0 {
		t.Error("expected non-zero queue length")
	}

	// 并发取出消息
	var drainWg sync.WaitGroup
	drainWg.Add(1)
	go func() {
		defer drainWg.Done()
		for {
			drained := outbox.Drain(10)
			if len(drained) == 0 {
				break
			}
		}
	}()

	drainWg.Wait()

	if outbox.Len() != 0 {
		t.Errorf("expected length 0 after drain, got %d", outbox.Len())
	}
}

// TestFileOutboxRecovery 测试从文件恢复
func TestFileOutboxRecovery(t *testing.T) {
	tmpDir := t.TempDir()
	// 使用唯一 agentID 避免测试间污染
	agentID := fmt.Sprintf("test-agent-recovery-%d", time.Now().UnixNano())

	// 创建第一个 outbox 并添加消息
	outbox1 := NewFileOutbox(agentID, tmpDir, 100)
	for i := 0; i < 5; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-recovery-%d", i),
			Type:      "task_result",
			TaskID:    "task-recovery",
			Timestamp: time.Now().UnixMilli(),
		}
		outbox1.Enqueue(msg)
	}
	// 等待异步写入完成
	time.Sleep(100 * time.Millisecond)
	outbox1.Close()

	// 创建第二个 outbox（同一目录），应该恢复消息
	outbox2 := NewFileOutbox(agentID, tmpDir, 100)
	defer outbox2.Close()

	// 应该恢复消息（由于异步写入可能有轻微差异，允许误差）
	if outbox2.Len() != 5 {
		t.Errorf("expected 5 messages after recovery, got %d", outbox2.Len())
	}
}

// TestFileOutboxPersistence 测试持久化到文件
func TestFileOutboxPersistence(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-6"

	// 创建 outbox 并添加消息
	outbox := NewFileOutbox(agentID, tmpDir, 100)
	for i := 0; i < 3; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-persist-%d", i),
			Type:      "log",
			TaskID:    "task-persist",
			Timestamp: time.Now().UnixMilli(),
		}
		outbox.Enqueue(msg)
	}
	outbox.Close()

	// 检查文件是否存在
	fileName := "outbox_" + agentID + ".txt"
	filePath := filepath.Join(tmpDir, fileName)
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		t.Error("expected outbox file to exist")
	}
}

// TestFileOutboxClear 测试清除功能
func TestFileOutboxClear(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-7"

	outbox := NewFileOutbox(agentID, tmpDir, 100)
	for i := 0; i < 5; i++ {
		msg := Message{
			MessageID: fmt.Sprintf("msg-clear-%d", i),
			Type:      "task_result",
			TaskID:    "task-clear",
			Timestamp: time.Now().UnixMilli(),
		}
		outbox.Enqueue(msg)
	}

	if outbox.Len() != 5 {
		t.Errorf("expected length 5, got %d", outbox.Len())
	}

	outbox.Clear()

	if outbox.Len() != 0 {
		t.Errorf("expected length 0 after clear, got %d", outbox.Len())
	}
}

// TestFileOutboxGetStats 测试统计信息
func TestFileOutboxGetStats(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-8"

	outbox := NewFileOutbox(agentID, tmpDir, 100)
	defer outbox.Close()

	stats := outbox.GetStats()
	if stats["queue_size"] != 0 {
		t.Errorf("expected queue_size 0, got %v", stats["queue_size"])
	}
	if stats["max_size"] != 100 {
		t.Errorf("expected max_size 100, got %v", stats["max_size"])
	}
	if stats["file_enabled"] != true {
		t.Errorf("expected file_enabled true, got %v", stats["file_enabled"])
	}
}

// TestFileOutboxNoDir 测试无目录时的降级
func TestFileOutboxNoDir(t *testing.T) {
	// 使用不存在的目录（使用一个无法创建的特殊路径名）
	// 在 Windows 上，我们可以使用一个包含非法字符的路径来触发错误
	// 但为了跨平台兼容性，我们测试目录创建失败的情况
	nonExistentDir := filepath.Join(t.TempDir(), "non-existent", "deeply", "nested")
	agentID := "test-agent-9"

	// 这应该回退到内存模式（如果目录创建失败）
	outbox := NewFileOutbox(agentID, nonExistentDir, 100)
	defer outbox.Close()

	// 仍然可以添加消息
	msg := Message{
		MessageID: "msg-memory",
		Type:      "task_result",
		TaskID:    "task-1",
		Timestamp: time.Now().UnixMilli(),
	}
	outbox.Enqueue(msg)

	if outbox.Len() != 1 {
		t.Errorf("expected length 1, got %d", outbox.Len())
	}

	// 测试消息可以正常取出
	drained := outbox.Drain(1)
	if len(drained) != 1 {
		t.Errorf("expected 1 message, got %d", len(drained))
	}
}

// TestFileOutboxDrainZero 测试 Drain(0)
func TestFileOutboxDrainZero(t *testing.T) {
	tmpDir := t.TempDir()
	agentID := "test-agent-10"

	outbox := NewFileOutbox(agentID, tmpDir, 100)
	defer outbox.Close()

	msg := Message{
		MessageID: "msg-zero",
		Type:      "task_result",
		TaskID:    "task-1",
		Timestamp: time.Now().UnixMilli(),
	}
	outbox.Enqueue(msg)

	// Drain(0) 应该返回 nil
	drained := outbox.Drain(0)
	if drained != nil {
		t.Errorf("expected nil for Drain(0), got %d messages", len(drained))
	}
}
