package system

import (
	"net"
	"os"
	"runtime"
	"sort"
	"strings"

	gopsutilnet "github.com/shirou/gopsutil/v3/net"

	"ops-job-agent/internal/api"
)

// CollectSystemInfo 收集系统基本信息（不再收集CPU/内存/磁盘等资源指标）
func CollectSystemInfo() api.SystemInfo {
	// 获取主机名
	hostnameStr, _ := os.Hostname()
	if hostInfo, err := os.Hostname(); err == nil {
		hostnameStr = hostInfo
	}

	info := api.SystemInfo{
		Hostname: hostnameStr,
		OS:       runtime.GOOS,
		Arch:     runtime.GOARCH,
		IPs:      listIPs(),
	}

	return info
}

// listIPs 列出所有 IP 地址（使用 gopsutil）
func listIPs() []string {
	ifaces, err := gopsutilnet.Interfaces()
	if err != nil {
		return nil
	}

	seen := map[string]struct{}{}
	for _, iface := range ifaces {
		// 检查接口是否启用
		isUp := false
		for _, flag := range iface.Flags {
			if strings.Contains(strings.ToLower(flag), "up") {
				isUp = true
				break
			}
		}
		if !isUp {
			continue
		}

		// 处理接口地址
		for _, addr := range iface.Addrs {
			// addr 格式可能是 "192.168.1.1/24" 或 "192.168.1.1"
			ipStr := addr.Addr
			if ipStr == "" {
				continue
			}

			// 解析 IP 地址（去掉 CIDR 后缀）
			parts := strings.Split(ipStr, "/")
			ipStr = parts[0]

			// 解析 IP
			ip := net.ParseIP(ipStr)
			if ip == nil || ip.IsLoopback() || ip.IsLinkLocalUnicast() {
				continue
			}

			// 只保留 IPv4 地址（或根据需要保留 IPv6）
			if ip.To4() != nil {
				seen[ip.String()] = struct{}{}
			}
		}
	}

	ips := make([]string, 0, len(seen))
	for ip := range seen {
		ips = append(ips, ip)
	}
	sort.Strings(ips)
	return ips
}
