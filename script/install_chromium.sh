#!/bin/bash
# 安装 Chromium 浏览器（轻量级替代 Chrome）
# 支持 Ubuntu/Debian 和 CentOS/RHEL

set -e

# 检查是否为 root
if [ "$(id -u)" != "0" ]; then
   echo "请使用 root 权限运行此脚本"
   exit 1
fi

echo "正在检测操作系统..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -si)
    VER=$(lsb_release -sr)
else
    echo "无法检测操作系统，请手动安装 Chromium"
    exit 1
fi

echo "检测到系统: $OS $VER"

install_debian() {
    echo "正在更新软件源..."
    apt-get update
    echo "正在安装 Chromium..."
    # 尝试安装 chromium-browser 或 chromium
    if apt-cache search chromium-browser | grep -q chromium-browser; then
        apt-get install -y chromium-browser
    else
        apt-get install -y chromium
    fi
    
    echo "正在安装 Chromedriver..."
    if apt-cache search chromium-chromedriver | grep -q chromium-chromedriver; then
        apt-get install -y chromium-chromedriver
    elif apt-cache search chromium-driver | grep -q chromium-driver; then
        apt-get install -y chromium-driver
    fi
}

install_centos() {
    echo "正在安装 EPEL 源..."
    yum install -y epel-release
    echo "正在安装 Chromium..."
    yum install -y chromium
    
    # CentOS 下通常 chromium 包已经包含了 driver，或者叫 chromedriver
    if ! command -v chromedriver &> /dev/null; then
        yum install -y chromedriver || echo "未找到单独的 chromedriver 包，假设已包含在 chromium 中"
    fi
}

if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    install_debian
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]] || [[ "$OS" == *"Alibaba"* ]]; then
    install_centos
else
    echo "不支持的系统: $OS"
    exit 1
fi

echo "安装完成！"
echo "Chromium 版本: $(chromium-browser --version 2>/dev/null || chromium --version)"
echo "ChromeDriver 版本: $(chromedriver --version)"
