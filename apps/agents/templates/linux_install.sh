#!/bin/bash
set -e

# 配置
AGENT_TOKEN="${AGENT_TOKEN}"
INSTALL_DIR="${INSTALL_DIR}"
BINARY_NAME="${BINARY_NAME}"
SERVICE_NAME="${SERVICE_NAME}"
DOWNLOAD_URL="${DOWNLOAD_URL}"
CONFIG_DIR="$INSTALL_DIR/config"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
CONFIG_EXAMPLE_SRC=""
INSTALL_TYPE="${INSTALL_TYPE}"
HOST_ID=${HOST_ID}
AGENT_SERVER_URL="${AGENT_SERVER_URL}"
CONTROL_PLANE_URL="${CONTROL_PLANE_URL}"
WS_BACKOFF_INITIAL_MS=${WS_BACKOFF_INITIAL_MS}
WS_BACKOFF_MAX_MS=${WS_BACKOFF_MAX_MS}
WS_MAX_RETRIES=${WS_MAX_RETRIES}
AGENT_SERVER_LISTEN_ADDR="${AGENT_SERVER_LISTEN_ADDR}"
MAX_CONNECTIONS=${MAX_CONNECTIONS}
HEARTBEAT_TIMEOUT=${HEARTBEAT_TIMEOUT}

# 检查是否已安装
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    echo "Agent 服务已在运行，请先停止服务"
    exit 1
fi

# 创建安装目录
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 下载并解压/放置二进制与示例配置
echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 正在下载 Agent 包..."
TMP_PKG=""
if echo "$DOWNLOAD_URL" | grep -Ei "\.zip($|\?)" >/dev/null; then
    TMP_PKG="$(mktemp /tmp/ops-agent-pkg.XXXXXX.zip)"
    (curl -fL "$DOWNLOAD_URL" -o "$TMP_PKG" || wget -O "$TMP_PKG" "$DOWNLOAD_URL")
    # unzip 使用 -q 静默模式，避免打印UTC时间戳，然后用自定义时间戳打印操作
    unzip -q -o "$TMP_PKG" -d "$INSTALL_DIR"
    echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 已解压文件到 $INSTALL_DIR"
elif echo "$DOWNLOAD_URL" | grep -Ei "\.(tar\.gz|tgz)($|\?)" >/dev/null; then
    TMP_PKG="$(mktemp /tmp/ops-agent-pkg.XXXXXX.tar.gz)"
    (curl -fL "$DOWNLOAD_URL" -o "$TMP_PKG" || wget -O "$TMP_PKG" "$DOWNLOAD_URL")
    tar -xzf "$TMP_PKG" -C "$INSTALL_DIR"
    echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 已解压文件到 $INSTALL_DIR"
else
    curl -fL -o "$INSTALL_DIR/$BINARY_NAME" "$DOWNLOAD_URL" || wget -O "$INSTALL_DIR/$BINARY_NAME" "$DOWNLOAD_URL"
fi
[ -n "$TMP_PKG" ] && rm -f "$TMP_PKG"

# 归一化二进制命名
[ -f "$INSTALL_DIR/agent" ] && mv -f "$INSTALL_DIR/agent" "$INSTALL_DIR/$BINARY_NAME"
[ -f "$INSTALL_DIR/agent-server" ] && mv -f "$INSTALL_DIR/agent-server" "$INSTALL_DIR/$BINARY_NAME"
CONFIG_EXAMPLE_SRC="$INSTALL_DIR/config.example.yaml"

chmod +x "$BINARY_NAME"

# 准备配置目录（与二进制同级的 config 目录）
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.$(date +%Y%m%d%H%M%S).bak"
fi
# 复制 example 作为基线（如果存在）
if [ -f "$CONFIG_EXAMPLE_SRC" ]; then
    cp "$CONFIG_EXAMPLE_SRC" "$CONFIG_FILE"
else
    : > "$CONFIG_FILE"
fi

# 使用 control-plane 直接渲染并嵌入的配置（由 control-plane 在生成脚本时填充 BASE64 字符串）
if [ -n "${CONFIG_B64}" ]; then
    echo "将嵌入的配置写入 ${CONFIG_FILE} ..."
    mkdir -p "$CONFIG_DIR"
    echo "${CONFIG_B64}" | base64 -d > "$CONFIG_FILE"
    if [ $? -ne 0 ]; then
        echo "Fatal: 写入嵌入配置失败" >&2
        exit 1
    fi
else
    echo "Fatal: 安装脚本未包含嵌入配置，无法生成 YAML 配置" >&2
    exit 1
fi

# 创建 systemd 服务
cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=Ops Job Agent Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/$BINARY_NAME start
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# 启动前验证
echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 验证安装..."
if [ ! -f "$INSTALL_DIR/$BINARY_NAME" ]; then
    echo "错误: 二进制文件不存在: $INSTALL_DIR/$BINARY_NAME"
    exit 1
fi
if [ ! -x "$INSTALL_DIR/$BINARY_NAME" ]; then
    echo "错误: 二进制文件没有执行权限: $INSTALL_DIR/$BINARY_NAME"
    exit 1
fi
if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 打印配置文件内容（用于调试）
echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 配置文件内容:"
cat "$CONFIG_FILE"

# 尝试验证二进制版本
echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 二进制版本信息:"
"$INSTALL_DIR/$BINARY_NAME" version 2>&1 || echo "无法获取版本信息"

# 启动服务
echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] 启动服务 $SERVICE_NAME..."
systemctl start $SERVICE_NAME

# 等待服务启动并检查状态
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] ✅ $SERVICE_NAME 服务启动成功！"
else
    echo "[$(TZ='Asia/Shanghai' date '+%Y-%m-%d %H:%M:%S')][$(hostname -s)] ❌ $SERVICE_NAME 服务启动失败"
    echo "服务状态:"
    systemctl status $SERVICE_NAME --no-pager || true
    echo ""
    echo "最近日志:"
    journalctl -u $SERVICE_NAME -n 50 --no-pager || true
    exit 1
fi

echo "Agent 安装成功！"
echo "服务状态: systemctl status $SERVICE_NAME"
echo "查看日志: journalctl -u $SERVICE_NAME -f"
