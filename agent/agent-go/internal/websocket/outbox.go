package websocket

import "sync"

// Outbox 是一个有界的本地待发送队列（环形/丢弃最旧），用于断线期间缓存 WS 消息。
// 目标：可观测性/不丢关键结果；实现简单，不引入额外依赖。
type Outbox struct {
	mu      sync.Mutex
	maxSize int
	msgs    []Message
	dropped int64
}

func NewOutbox(maxSize int) *Outbox {
	if maxSize <= 0 {
		maxSize = 2000
	}
	return &Outbox{
		maxSize: maxSize,
		msgs:    make([]Message, 0, maxSize),
	}
}

func (o *Outbox) Enqueue(msg Message) {
	o.mu.Lock()
	defer o.mu.Unlock()

	if len(o.msgs) >= o.maxSize {
		// 丢弃最旧的
		copy(o.msgs[0:], o.msgs[1:])
		o.msgs = o.msgs[:len(o.msgs)-1]
		o.dropped++
	}
	o.msgs = append(o.msgs, msg)
}

func (o *Outbox) Drain(max int) []Message {
	o.mu.Lock()
	defer o.mu.Unlock()

	if max <= 0 || max >= len(o.msgs) {
		out := make([]Message, len(o.msgs))
		copy(out, o.msgs)
		o.msgs = o.msgs[:0]
		return out
	}

	out := make([]Message, max)
	copy(out, o.msgs[:max])
	o.msgs = o.msgs[max:]
	return out
}

func (o *Outbox) Len() int {
	o.mu.Lock()
	defer o.mu.Unlock()
	return len(o.msgs)
}

func (o *Outbox) Dropped() int64 {
	o.mu.Lock()
	defer o.mu.Unlock()
	return o.dropped
}
