package server

import (
	"context"
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
)

// downloadFile 从 URL 下载文件到指定路径
func downloadFile(ctx context.Context, url, dest string) error {
	// 创建 HTTP 请求
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	// 发送请求
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("download file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed: HTTP %d", resp.StatusCode)
	}

	// 创建目标文件
	out, err := os.Create(dest)
	if err != nil {
		return fmt.Errorf("create file: %w", err)
	}
	defer out.Close()

	// 复制内容
	if _, err := io.Copy(out, resp.Body); err != nil {
		return fmt.Errorf("save file: %w", err)
	}

	return nil
}

// verifySHA256 验证文件的 SHA256 校验和
func verifySHA256(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return fmt.Errorf("compute hash: %w", err)
	}

	actual := hex.EncodeToString(hash.Sum(nil))
	if actual != expectedHash {
		return fmt.Errorf("sha256 mismatch: expected %s, got %s", expectedHash, actual)
	}

	return nil
}

// verifyMD5 验证文件的 MD5 校验和
func verifyMD5(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer file.Close()

	hash := md5.New()
	if _, err := io.Copy(hash, file); err != nil {
		return fmt.Errorf("compute hash: %w", err)
	}

	actual := hex.EncodeToString(hash.Sum(nil))
	if actual != expectedHash {
		return fmt.Errorf("md5 mismatch: expected %s, got %s", expectedHash, actual)
	}

	return nil
}
