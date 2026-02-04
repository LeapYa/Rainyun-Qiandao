# 宝塔面板 (BT Panel) / Linux 虚拟主机部署指南

本指南适用于不方便使用 Docker，希望直接在 Linux 服务器（如宝塔面板环境）上运行本工具的用户。

> **注意**：完整安装（Python环境 + Chromium浏览器）需要约 **200MB - 300MB** 的磁盘空间。如果您的主机空间不足 300MB，请勿尝试安装。

---

## 方案一：本地安装 Chromium（推荐 >500MB 空间）

### 1. 环境准备

确保您的服务器安装了 **Python 3.8+**。如果是宝塔面板：
1.  在“软件商店”搜索并安装 **“Python管理器”**。
2.  在 Python管理器 中安装 Python 3.9 或更高版本。

### 2. 拉取项目

通过 SSH 登录服务器，进入您希望安装的目录（例如 `/www/wwwroot`）：

```bash
cd /www/wwwroot
git clone https://github.com/LeapYa/Rainyun-Qiandao.git
cd Rainyun-Qiandao
```

### 3. 安装 Chromium 浏览器 (VPS用户必做)

如果您拥有 root 权限，请务必执行此步骤以安装系统级依赖和浏览器。
(如果您是虚拟主机用户，只能尝试跳过此步直接运行，但极大率会因为缺失系统库而报错)

```bash
# 给予脚本执行权限
chmod +x script/install_chromium.sh

# 运行安装脚本（需要 root 权限）
sudo ./script/install_chromium.sh
```

如果脚本执行成功，会显示 Chromium 和 ChromeDriver 的版本号。

### 4. 安装 Python 依赖

建议使用虚拟环境（防止污染系统库）：

```bash
# 创建虚拟环境 (venv)
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 5. 配置账号

复制配置模板并编辑：

```bash
cp .env.example .env
nano .env
# 或者在宝塔文件管理中直接编辑 .env 文件
```

填入您的 `RAINYUN_USERNAME` 和 `RAINYUN_PASSWORD`。

### 6. 配置定时任务（Crontab）

我们提供了一个专门用于配合 Crontab 的启动脚本 `script/run_bt.sh`。

**在宝塔面板中添加计划任务：**

-   **任务类型**：Shell 脚本
-   **任务名称**：雨云每日签到
-   **执行周期**：每天 08:00 (或其他您想要的时间)
-   **脚本内容**：

```bash
# 请修改为实际的项目路径
bash /www/wwwroot/Rainyun-Qiandao/script/run_bt.sh
```