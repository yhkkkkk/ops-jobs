package system

import (
	"net"
	"os"
	"runtime"
	"sort"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/load"
	"github.com/shirou/gopsutil/v3/mem"
	gopsutilnet "github.com/shirou/gopsutil/v3/net"

	"ops-job-agent/internal/api"
)

// CollectSystemInfo 收集系统信息
func CollectSystemInfo() api.SystemInfo {
	// 获取主机名
	hostnameStr, _ := os.Hostname()
	if hostInfo, err := host.Info(); err == nil {
		hostnameStr = hostInfo.Hostname
	}

	info := api.SystemInfo{
		Hostname: hostnameStr,
		OS:       runtime.GOOS,
		Arch:     runtime.GOARCH,
		IPs:      listIPs(),
	}

	// 收集 CPU 使用率
	if cpuPercent, err := cpu.Percent(time.Second, false); err == nil && len(cpuPercent) > 0 {
		info.CPUUsage = cpuPercent[0]
	}

	// 收集内存使用率
	if memStat, err := mem.VirtualMemory(); err == nil {
		info.MemoryUsage = memStat.UsedPercent
	}

	// 收集磁盘使用率
	if diskUsage, err := getDiskUsage(); err == nil {
		info.DiskUsage = diskUsage
	}

	// 收集负载平均值
	if runtime.GOOS != "windows" {
		if loadAvg, err := load.Avg(); err == nil {
			info.LoadAvg = []float64{loadAvg.Load1, loadAvg.Load5, loadAvg.Load15}
		}
	}

	// 收集系统运行时间
	if hostInfo, err := host.Info(); err == nil {
		info.Uptime = int64(hostInfo.Uptime)
	} else if uptime, err := host.Uptime(); err == nil {
		info.Uptime = int64(uptime)
	}

	return info
}

// getDiskUsage 获取磁盘使用率
func getDiskUsage() (map[string]float64, error) {
	usage := make(map[string]float64)

	// 获取所有分区
	partitions, err := disk.Partitions(false)
	if err != nil {
		return usage, err
	}

	for _, partition := range partitions {
		// 跳过特殊文件系统
		if partition.Fstype == "tmpfs" || partition.Fstype == "devtmpfs" {
			continue
		}

		// 获取磁盘使用情况
		usageStat, err := disk.Usage(partition.Mountpoint)
		if err != nil {
			continue
		}

		// 只记录有意义的挂载点
		if usageStat.Total > 0 {
			usage[partition.Mountpoint] = usageStat.UsedPercent
		}
	}

	return usage, nil
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
