# Rainyun-Qiandao-v2.2-docker (Selenium)

**🐳 容器化部署，内置定时任务**

**v2.2-docker 版本更新！**

**雨云签到工具 容器化部署后可实现每日自动签到~**

众所周知，雨云为了防止白嫖加入了TCaptcha验证码，但主包对JS逆向一窍不通，纯请求的方法便走不通了。

因此只能曲线救国，使用 **Selenium+ddddocr** 来模拟真人操作。

经不严谨测试，目前的方案验证码识别率高达**48.3%**，不过多次重试最终也能通过验证，那么目的达成！

**本分支特色功能：**

1. ✅ Docker 一键部署 —— 提供 `Dockerfile` 与 `docker-compose`，开箱即用，无需配置环境
2. ✅ GitHub Actions —— 支持利用 GitHub Actions 免费资源进行每日自动签到，无需服务器
3. ✅ 宝塔面板 (BT Panel) / Linux 特殊虚拟主机运行 —— 提供 `script/run_bt.sh` 脚本，无需配置环境
4. ✅ 多账号支持 —— 支持单容器配置无限个账号（使用 `|` 分隔），各账号随机浏览器指纹，并发执行
5. ✅ 多通道通知 —— 集成 PushPlus、WXPusher、钉钉、邮件等多种通知方式
6. ✅ 代理 IP 池 —— 支持配置 HTTP 代理，防止因 IP 封锁导致的签到失败
7. ✅ 智能截图 —— 签到成功/失败自动截图并压缩上传，不仅有图有真相，还节省流量

## 食用方法

### 1.拉取项目
```bash
git clone --depth 1 https://github.com/LeapYa/Rainyun-Qiandao.git
cd Rainyun-Qiandao
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 文件，并填入你的账号信息：

Windows (PowerShell):
```powershell
copy .env.example .env
```

Linux/Mac:
```bash
cp .env.example .env
```

编辑 `.env` 文件，根据里面的提示填入你的雨云账号和密码，多个账号/密码之间请使用竖线 | 分隔

### 3. 启动服务（选择一种模式）

根据你的不同场景和使用需求，从以下三种模式中**选择一种**运行

#### 模式一：使用Docker定时运行（推荐）

适合长期部署，程序会持续运行，并在每天指定时间（默认08:00）自动执行签到。

```bash
# 启动定时服务
sudo docker compose up -d rainyun-schedule

# 查看实时日志
sudo docker compose logs -f rainyun-schedule

# 停止服务
sudo docker compose down
```

#### 模式二：使用Docker单次运行

适合测试账号配置是否正确，或者临时手动执行一次签到。运行结束后容器会自动退出。

```bash
# 立即执行一次签到（前台运行，可看到实时日志）
sudo docker compose --profile once up rainyun-once

# 或者后台运行
sudo docker compose --profile once up -d rainyun-once
```



#### 模式三：在宝塔面板 (BT Panel) / Linux 虚拟主机运行

适用于不方便使用 Docker，希望直接在 Linux 服务器（如宝塔面板环境）上运行本工具的用户，如果需要再虚拟主机上运行，请确保您的虚拟主机支持 Python 3.8+ 和 Chromium 浏览器，或者购买和使用**特殊虚拟主机**（任意使用所有函数/完全ROOT权限的虚拟主机）。

> **注意**：完整安装（Python环境 + Chromium浏览器）需要约 **200MB - 300MB** 的磁盘空间。如果您的主机空间不足 300MB，请勿尝试安装。

##### (1) 环境准备

确保您的服务器安装了 **Python 3.8+**。如果是宝塔面板：
1.  在“软件商店”搜索并安装 **“Python管理器”**。
2.  在 Python管理器 中安装 Python 3.9 或更高版本。

##### (2) 安装 Chromium 浏览器 

如果您拥有 root 权限或特殊虚拟主机，请务必执行此步骤以安装系统级依赖和浏览器。
(如果无法安装Chromium，只能尝试跳过此步直接运行，但极大率会因为缺失系统库而报错)

```bash
# 给予脚本执行权限
chmod +x script/install_chromium.sh

# 运行安装脚本（需要 root 权限）
sudo ./script/install_chromium.sh
```

如果脚本执行成功，会显示 Chromium 和 ChromeDriver 的版本号。

##### (3) 安装 Python 依赖

建议使用虚拟环境（防止污染系统库）：

```bash
# 创建虚拟环境 (venv)
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

##### (4) 配置定时任务（Crontab）

我们提供了一个专门用于配合 Crontab 的启动脚本 `script/run_bt.sh`。

**在宝塔面板中添加计划任务：**

-   **任务类型**：Shell 脚本
-   **任务名称**：雨云每日签到
-   **执行周期**：每天 08:00 (或其他您想要的时间)
-   **脚本内容**：

```bash
# 请修改为实际的Rainyun-Qiandao项目所在路径
bash /www/wwwroot/Rainyun-Qiandao/script/run_bt.sh
```

## 代理IP配置（可选）

如果需要每个账号使用不同的代理IP，可以配置 `PROXY_API_URL` 环境变量。

> 由于签到任务时间比较长（大概需要三到五分钟），但免费代理的时效很短，所以如果要配置代理IP，建议购买按量付费的时间较长的代理IP，十几块钱就有一千个了，可以用很久了

### 配置方式

在 `.env` 文件中添加：

```bash
# 代理IP接口地址（不填则不使用代理）
PROXY_API_URL=http://your-proxy-api.com/get?token=xxx
```

### 支持的接口返回格式

程序支持多种常见的代理接口返回格式：

```
# 格式1：纯文本
192.168.1.1:8080

# 格式2：JSON
{"ip": "192.168.1.1", "port": 8080}

# 格式3：JSON（proxy字段）
{"proxy": "192.168.1.1:8080"}

# 格式4：嵌套JSON
{"code": 0, "data": {"ip": "192.168.1.1", "port": 8080}}

# 格式5：带协议前缀
http://192.168.1.1:8080
```

### 工作流程

1. 每个账号签到前，会单独请求一次代理接口获取新的代理IP
2. 获取代理后会自动验证连通性
3. 如果代理获取失败或验证不通过，会使用本地IP继续签到（降级策略）


## 其他注意事项

### 1. 账号安全

- 请不要将账号密码硬编码在脚本中，而是通过环境变量传递。
- 建议使用单独的账号进行签到，避免因为主账号异常而导致的影响。

### 2. 找不到元素或等待超时，报错 `NoSuchElementException`/`TimeoutException`

#### 网页加载缓慢，尝试延长超时等待时间或更换连接性更好的国内主机。

## 更新日志

### 2026-01-29
- 修复因前端弹窗导致的签到失败问题，优化自动化交互逻辑。
- 增强安全性与易用性，支持通过 `.env` 配置账号密码及运行参数，并完善文档说明。

### 2026-01-30
- 增加通知功能，支持PushPlus、WXPusher、钉钉、邮件通知。

### 2026-01-31
- 根据账号随机浏览器指纹，增加反爬虫机制。
- 增加Cookie持久化功能，避免重复登录。
- 无图模式，减少资源占用。
- 新增代理IP支持，每个账号可独立使用不同代理IP。

### 2026-02-03
- 优化点击逻辑，避免重复签到时报错显示异常
- 支持截图发送到通知功能中
- 压缩图片，减少通知大小

### 2026-02-04
- 支持多账号并发执行
- 优化日志输出，增加用户标识，提升多账号管理的可读性
- 关闭无图模式
- 调整Action默认执行时间

## 致谢

本项目基于 [Rainyun-Qiandao](https://github.com/SerendipityR-2022/Rainyun-Qiandao) 开发，感谢原作者的开源贡献。
