#!/bin/bash

echo "========================================"
echo "🎯 Django 多服务启动器"
echo "========================================"
echo

# 检查是否在项目根目录
if [ ! -f "manage.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    echo "当前目录: $(pwd)"
    exit 1
fi

echo "🚀 启动所有后端服务..."
echo
echo "💡 提示: 按 Ctrl+C 可以停止所有服务"
echo

# 使用 uv 运行启动脚本
uv run python start_all.py

echo
echo "👋 所有服务已停止"
