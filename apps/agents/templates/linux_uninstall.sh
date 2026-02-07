#!/bin/bash
set -e

# 配置
SERVICE_NAME="${SERVICE_NAME}"
INSTALL_DIR="${INSTALL_DIR}"
BACKUP_DIR="${BACKUP_DIR}"

echo "[1/3] 停止并禁用服务（如存在）..."
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\.service"; then
  systemctl stop "${SERVICE_NAME}" || true
  systemctl disable "${SERVICE_NAME}" || true
fi

echo "[2/3] 删除 systemd unit（如存在）..."
UNIT_FILE_1="/etc/systemd/system/${SERVICE_NAME}.service"
UNIT_FILE_2="/lib/systemd/system/${SERVICE_NAME}.service"
rm -f "${UNIT_FILE_1}" "${UNIT_FILE_2}" || true
systemctl daemon-reload || true

echo "[3/3] 清理安装目录（如存在）..."
if [ -d "${INSTALL_DIR}" ]; then
  # 备份配置（可选）
  if [ -f "${INSTALL_DIR}/config/config.yaml" ]; then
    ts=$(date +%Y%m%d%H%M%S)
    mkdir -p "${BACKUP_DIR}" || true
    cp "${INSTALL_DIR}/config/config.yaml" "${BACKUP_DIR}/config.yaml.${ts}.bak" || true
  fi
  rm -rf "${INSTALL_DIR}"
fi

echo "Agent 卸载完成"
