package server

import (
	"context"
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"

	"github.com/go-resty/resty/v2"
)

// downloadFile 从url下载文件到指定路径
func downloadFile(ctx context.Context, url, dest string) error {
	// 使用 resty 下载文件（SetOutput 直接写入文件）
	_, err := resty.New().R().
		SetContext(ctx).
		SetOutput(dest).
		Get(url)

	if err != nil {
		return fmt.Errorf("download failed: %w", err)
	}

	return nil
}

// verifySHA256 验证文件的 SHA256 校验和
func verifySHA256(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("open file: %w", err)
	}
	defer func() {
		_ = file.Close()
	}()

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
	defer func() {
		_ = file.Close()
	}()

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
