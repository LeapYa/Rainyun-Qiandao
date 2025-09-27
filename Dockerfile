# 使用包含 Chrome 和 ChromeDriver 的官方 Selenium 镜像
FROM selenium/standalone-chrome:4.15.0

# 切换到 root 用户进行安装
USER root

# 镜像加速
RUN set -eux; \
    version_id=$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"'); \
    codename=$(grep '^VERSION_CODENAME=' /etc/os-release | cut -d= -f2); \
    if [ "$version_id" -ge 12 ]; then \
        # Debian 12: 先使用 TUNA 的 http 源安装 ca-certificates，再换 https
        mirror='http://mirrors.tuna.tsinghua.edu.cn/debian'; \
        security_mirror='http://mirrors.tuna.tsinghua.edu.cn/debian-security'; \
        comps='main contrib non-free non-free-firmware'; \
        rm -f /etc/apt/sources.list.d/debian.sources; \
        echo "deb ${mirror}/ ${codename} ${comps}"        >  /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-updates ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-backports ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${security_mirror}/ ${codename}-security ${comps}" >> /etc/apt/sources.list; \
        apt-get update; \
        apt-get install -y --no-install-recommends apt-transport-https ca-certificates; \
        # 替换为 https 源
        mirror='https://mirrors.tuna.tsinghua.edu.cn/debian'; \
        security_mirror='https://mirrors.tuna.tsinghua.edu.cn/debian-security'; \
        echo "deb ${mirror}/ ${codename} ${comps}"        >  /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-updates ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-backports ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${security_mirror}/ ${codename}-security ${comps}" >> /etc/apt/sources.list; \
    elif [ "$version_id" -ge 11 ]; then \
        # Debian 11: 使用 163 http 源安装 ca-certificates（如果需要 https 可再切换）
        mirror='http://mirrors.163.com/debian'; \
        security_mirror='http://mirrors.163.com/debian-security'; \
        comps='main contrib non-free'; \
        rm -f /etc/apt/sources.list.d/debian.sources; \
        echo "deb ${mirror}/ ${codename} ${comps}"        >  /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-updates ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${mirror}/ ${codename}-backports ${comps}" >> /etc/apt/sources.list; \
        echo "deb ${security_mirror}/ ${codename}-security ${comps}" >> /etc/apt/sources.list; \
        apt-get update; \
        apt-get install -y --no-install-recommends ca-certificates; \
    else \
        echo "Debian version $version_id detected; skipping mirror replacement as sources are EOL or unavailable."; \
    fi; \
    apt-get update

# 安装 Python 和 pip
RUN apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 requirements 文件
COPY requirements.txt .

# 配置pip国内镜像源并安装依赖
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip3 install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p temp logs

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# 运行应用
CMD ["python3", "rainyun.py"]