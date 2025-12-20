#!/bin/bash
echo "=== SYSTEM_INFO_START ==="

# 基本系统信息
echo "HOSTNAME=$(hostname 2>/dev/null || echo 'unknown')"

# 操作系统版本检测 - 多种方式兼容
if [ -f /etc/os-release ]; then
    OS_VERSION=$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2 2>/dev/null)
elif [ -f /etc/redhat-release ]; then
    OS_VERSION=$(cat /etc/redhat-release 2>/dev/null)
elif [ -f /etc/debian_version ]; then
    OS_VERSION="Debian $(cat /etc/debian_version 2>/dev/null)"
else
    OS_VERSION=$(uname -s 2>/dev/null || echo 'unknown')
fi
echo "OS_VERSION=$OS_VERSION"

echo "KERNEL_VERSION=$(uname -r 2>/dev/null || echo 'unknown')"

# 硬件信息 - 多种方式兼容
# CPU核心数
if command -v nproc >/dev/null 2>&1; then
    CPU_CORES=$(nproc)
elif [ -f /proc/cpuinfo ]; then
    CPU_CORES=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 'unknown')
else
    CPU_CORES='unknown'
fi
echo "CPU_CORES=$CPU_CORES"

# CPU模型和架构
CPU_MODEL='unknown'
CPU_ARCH='unknown'
OS_ARCH='unknown'

if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo 'unknown')
fi

if command -v lscpu >/dev/null 2>&1; then
    if [ "$CPU_MODEL" = "unknown" ]; then
        CPU_MODEL=$(lscpu | grep "Model name:" | cut -d: -f2 | sed 's/^ *//' 2>/dev/null || echo 'unknown')
    fi
    CPU_ARCH=$(lscpu | grep "Architecture:" | awk '{print $2}' 2>/dev/null || echo 'unknown')
fi

if command -v uname >/dev/null 2>&1; then
    if [ "$CPU_ARCH" = "unknown" ]; then
        CPU_ARCH=$(uname -m 2>/dev/null || echo 'unknown')
    fi
    OS_ARCH=$(uname -m 2>/dev/null || echo 'unknown')
fi

echo "CPU_MODEL=$CPU_MODEL"
echo "CPU_ARCH=$CPU_ARCH"
echo "OS_ARCH=$OS_ARCH"

# 内存信息
if [ -f /proc/meminfo ]; then
    MEMORY_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}' 2>/dev/null)
    if [ -n "$MEMORY_KB" ] && [ "$MEMORY_KB" != "" ]; then
        MEMORY_GB=$((MEMORY_KB / 1024 / 1024))
    else
        MEMORY_GB='unknown'
    fi
else
    MEMORY_GB='unknown'
fi
echo "MEMORY_GB=$MEMORY_GB"

# 磁盘信息
if command -v df >/dev/null 2>&1; then
    DISK_GB=$(df / 2>/dev/null | awk 'NR==2{printf "%.0f", $2/1024/1024}' 2>/dev/null || echo 'unknown')
else
    DISK_GB='unknown'
fi
echo "DISK_GB=$DISK_GB"

# 网络信息 - 多种方式获取内网IP
INTERNAL_IP='unknown'
if command -v hostname >/dev/null 2>&1; then
    INTERNAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ "$INTERNAL_IP" = "" ] || [ "$INTERNAL_IP" = "unknown" ]; then
    if command -v ip >/dev/null 2>&1; then
        INTERNAL_IP=$(ip route get 1 2>/dev/null | awk '{print $NF;exit}' 2>/dev/null || echo 'unknown')
    fi
fi
if [ "$INTERNAL_IP" = "" ] || [ "$INTERNAL_IP" = "unknown" ]; then
    if command -v ifconfig >/dev/null 2>&1; then
        INTERNAL_IP=$(ifconfig 2>/dev/null | grep -E 'inet.*192\\.168\\.|inet.*10\\.|inet.*172\\.' | head -1 | awk '{print $2}' | cut -d: -f2 2>/dev/null || echo 'unknown')
    fi
fi
echo "INTERNAL_IP=$INTERNAL_IP"

# 获取更多网络信息
PUBLIC_IP='unknown'
INTERNAL_MAC='unknown'
EXTERNAL_MAC='unknown'
GATEWAY='unknown'
DNS_SERVERS='unknown'

# 获取公网IP
if command -v curl >/dev/null 2>&1; then
    PUBLIC_IP=$(timeout 5 curl -s http://ipinfo.io/ip 2>/dev/null || timeout 5 curl -s http://icanhazip.com 2>/dev/null || echo 'unknown')
fi

# 获取MAC地址
if command -v ip >/dev/null 2>&1; then
    # 获取默认路由接口的MAC地址作为内网MAC
    DEFAULT_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -n "$DEFAULT_INTERFACE" ]; then
        INTERNAL_MAC=$(ip link show $DEFAULT_INTERFACE 2>/dev/null | grep "link/ether" | awk '{print $2}' || echo 'unknown')
    fi

    # 获取网关
    GATEWAY=$(ip route | grep default | awk '{print $3}' | head -1 || echo 'unknown')
elif command -v ifconfig >/dev/null 2>&1; then
    # 使用ifconfig获取第一个非lo接口的MAC地址
    INTERNAL_MAC=$(ifconfig 2>/dev/null | grep -E "ether|HWaddr" | head -1 | awk '{print $2}' | cut -d: -f1-6 || echo 'unknown')

    # 获取网关
    if command -v route >/dev/null 2>&1; then
        GATEWAY=$(route -n 2>/dev/null | grep "^0.0.0.0" | awk '{print $2}' | head -1 || echo 'unknown')
    fi
fi

# 获取DNS服务器
if [ -f /etc/resolv.conf ]; then
    DNS_SERVERS=$(grep nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}' | tr '\n' ',' | sed 's/,$//' || echo 'unknown')
fi

echo "PUBLIC_IP=$PUBLIC_IP"
echo "INTERNAL_MAC=$INTERNAL_MAC"
echo "EXTERNAL_MAC=$EXTERNAL_MAC"
echo "GATEWAY=$GATEWAY"
echo "DNS_SERVERS=$DNS_SERVERS"

# 云厂商检测 - 简化版本，减少网络依赖
CLOUD_PROVIDER='unknown'
INSTANCE_ID='unknown'
REGION='unknown'
ZONE='unknown'

# AWS检测
if [ -f /sys/hypervisor/uuid ] && [ "$(head -c 3 /sys/hypervisor/uuid 2>/dev/null)" = "ec2" ]; then
    CLOUD_PROVIDER='aws'
    # 尝试获取AWS元数据，但不依赖网络
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null || echo 'unknown')
    fi
# 阿里云检测
elif [ -f /sys/class/dmi/id/sys_vendor ] && grep -q "Alibaba" /sys/class/dmi/id/sys_vendor 2>/dev/null; then
    CLOUD_PROVIDER='aliyun'
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/region-id 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://100.100.100.200/latest/meta-data/zone-id 2>/dev/null || echo 'unknown')
    fi
# 腾讯云检测
elif [ -f /sys/class/dmi/id/sys_vendor ] && grep -q "Tencent" /sys/class/dmi/id/sys_vendor 2>/dev/null; then
    CLOUD_PROVIDER='tencent'
    if command -v curl >/dev/null 2>&1; then
        INSTANCE_ID=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')
        REGION=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/placement/region 2>/dev/null || echo 'unknown')
        ZONE=$(timeout 3 curl -s http://metadata.tencentyun.com/latest/meta-data/placement/zone 2>/dev/null || echo 'unknown')
    fi
fi

echo "CLOUD_PROVIDER=$CLOUD_PROVIDER"
echo "INSTANCE_ID=$INSTANCE_ID"
echo "REGION=$REGION"
echo "ZONE=$ZONE"

echo "=== SYSTEM_INFO_END ==="

