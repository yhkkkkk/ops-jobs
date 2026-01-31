package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// ComputeHMAC 构造签名摘要，保持与控制面实现一致：
// message = timestamp + "\n" + method + "\n" + path + "\n" + body
func ComputeHMAC(secret, method, path, ts string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(ts))
	mac.Write([]byte("\n"))
	mac.Write([]byte(method))
	mac.Write([]byte("\n"))
	mac.Write([]byte(path))
	mac.Write([]byte("\n"))
	mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil))
}

// AbsInt64 返回 int64 绝对值，用于时间偏移比较。
func AbsInt64(v int64) int64 {
	if v < 0 {
		return -v
	}
	return v
}
