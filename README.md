# Rainyun-Qiandao-v2.3 (Selenium)

**🐳 容器化部署，内置定时任务**

**v2.3 版本更新！**

**雨云签到工具 容器化部署后可实现每日自动签到~**

众所周知，雨云为了防止白嫖加入了TCaptcha验证码，但主包对JS逆向一窍不通，纯请求的方法便走不通了。

因此只能曲线救国，使用 **Selenium+ddddocr** 来模拟真人操作。

经不严谨测试，目前的方案验证码识别率高达**48.3%**，不过多次重试最终也能通过验证，那么目的达成！

**本分支特色功能：**

1. ✅ Docker 一键部署 —— 提供 `Dockerfile` 与 `docker-compose`，开箱即用，无需配置环境
2. ✅ GitHub Actions —— 支持利用 GitHub Actions 免费资源进行每日自动签到，无需服务器
3. ✅ 宝塔面板 (BT Panel) / Linux 特殊虚拟主机运行 —— 提供 `script/run_bt.sh` 脚本，无需配置环境
4. ✅ 多账号支持 —— 支持配置无限个账号并发签到（使用 `|` 分隔），各账号随机浏览器指纹，并发执行
5. ✅ 多通道通知 —— 支持 PushPlus、WXPusher、钉钉、邮件等多种通知方式
6. ✅ 代理 IP 池 —— 支持配置 HTTP 代理，防止因 IP 封锁导致的签到失败
7. ✅ 智能截图 —— 签到成功/失败自动截图并压缩上传，不仅有图有真相，还节省流量
8. ✅ 拦截自动代理 —— 动态探测 `app.rainyun.com` 可达性，被拦截时自动抓取国内免费代理绕过（无需手动配置，直连可达时优先直连，覆盖海外 Actions、海外/国内 VPS、Docker 等所有环境）
9. ✅ 签到状态校验 —— 点击领取奖励后轮询检查按钮是否变为"已完成"，检测验证码加载框（三个点）防止网络慢导致误判

## 食用方法

> [!NOTE]
> **GitHub Actions 配置教程**：[https://www.leapya.com/article/2](https://www.leapya.com/article/2) —— Fork 后配置 Secrets 即可每日自动签到，无需服务器。
>
> 下方文档主要针对 Docker / 宝塔面板等自建部署方式。
> 青龙面板部署方式独立于下方步骤，请见 [青龙面板部署教程](https://www.leapya.com/article/22)。

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

<details>
<summary>📋 <b>完整参数列表（点击展开）</b></summary>

#### 🔐 雨云登录凭据（必填）

| 变量名               | 说明                         | 示例                           |
| -------------------- | ---------------------------- | ------------------------------ |
| `RAINYUN_USERNAME` | 雨云账号，多账号用`\|` 分隔 | `user1@qq.com\|user2@163.com` |
| `RAINYUN_PASSWORD` | 对应密码，多账号用`\|` 分隔 | `pass1\|pass2`                |

#### 📢 通知渠道配置（可选，至少配一个才能收到推送）

| 变量名                    | 说明                                                     | 备注                           |
| ------------------------- | -------------------------------------------------------- | ------------------------------ |
| `PUSHPLUS_TOKEN`        | [PushPlus](http://www.pushplus.plus/) Token               | 实名用户 2 万字 / 会员 10 万字 |
| `WXPUSHER_APP_TOKEN`    | [WXPusher](http://wxpusher.zjiecode.com/admin/) App Token | 限制 4 万字                    |
| `WXPUSHER_UIDS`         | WXPusher 接收者 UID，多个用`,` 分隔                    | 个人标识                       |
| `WXPUSHER_TOPIC_IDS`    | WXPusher 主题 ID，多个用`,` 分隔                       | 群发标识                       |
| `DINGTALK_ACCESS_TOKEN` | 钉钉机器人 Access Token                                  | 限制约 2 万字                  |
| `DINGTALK_SECRET`       | 钉钉机器人加签密钥                                       | 可选                           |
| `SMTP_HOST`             | SMTP 服务器地址                                          | 如`smtp.qq.com`              |
| `SMTP_PORT`             | SMTP 端口                                                | `465`(SSL) 或 `587`(TLS)   |
| `SMTP_USER`             | SMTP 登录用户名                                          |                                |
| `SMTP_PASS`             | SMTP 授权码                                              | 不是登录密码                   |
| `SMTP_TO`               | 收件人邮箱                                               | 不填则默认发给第一个签到账号   |

> **关于推送内容超长**：当推送内容超过渠道字符限制时，程序会自动降级：完整报告 → 无截图报告 → 精简摘要，**无需手动处理**。PushPlus 还会先按 10 万字（会员）尝试，失败后自动降级到 2 万字（实名）重试。

#### ⚙️ 运行参数（可选）

| 变量名                  | 说明                             | 默认值    |
| ----------------------- | -------------------------------- | --------- |
| `SCHEDULE_TIME`       | 定时执行时间（仅 schedule 模式） | `08:00` |
| `DEBUG`               | 开启调试日志                     | `false` |
| `MAX_DELAY`           | 多账号错峰启动最大随机延时（秒） | `15`    |
| `MAX_WORKERS`         | 最大并发线程数                   | `3`     |
| `TIMEOUT`             | 请求超时时间（毫秒）             | `30000` |
| `CHECKIN_MAX_RETRIES` | 签到失败最大重试次数             | `2`     |

#### 🌐 代理 IP（可选）

| 变量名            | 说明             | 默认值           |
| ----------------- | ---------------- | ---------------- |
| `PROXY_API_URL` | 代理 IP 接口地址 | 不填则不使用代理 |

#### 📸 截图与压缩（可选）

| 变量名              | 说明                                                                  | 默认值          |
| ------------------- | --------------------------------------------------------------------- | --------------- |
| `SCREENSHOT_MODE` | 截图嵌入策略：`all` 全部 / `failed_only` 仅失败 / `none` 无截图 | `failed_only` |
| `SCREENSHOT_QUALITY` | 截图 JPEG 质量上限（10-100），实际只会更低：逐档下调取画质仍达标的最低档，设得很低时等同固定质量 | `35` |
| `TINYPNG_API_KEY` | [TinyPNG](https://tinypng.com/developers) API Key（每月免费 500 次）   | 不填则本地压缩  |

</details>

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

1. 在“软件商店”搜索并安装 **“Python管理器”**。
2. 在 Python管理器 中安装 Python 3.9 或更高版本。

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

- **任务类型**：Shell 脚本
- **任务名称**：雨云每日签到
- **执行周期**：每天 08:00 (或其他您想要的时间)
- **脚本内容**：

```bash
# 请修改为实际的Rainyun-Qiandao项目所在路径
bash /www/wwwroot/Rainyun-Qiandao/script/run_bt.sh
```

## 代理IP配置（可选）

项目支持两种代理方式：**拦截自动代理**（免配置）和 **自建代理接口**（可选）。

### 拦截自动代理（免配置）

雨云会动态拦截部分 IP（覆盖海外数据中心、部分国内云服务器等），表现为 `ERR_CONNECTION_REFUSED`。

脚本会动态探测 `app.rainyun.com` 可达性，被拦截时自动抓取国内免费代理绕过：

- 内置 5 个国内免费代理源（89IP、快代理、齐云IP、开心代理、ProxyScrape）并发抓取，无第三方依赖，无需从 GitHub 安装额外库（代理源选取参考了 [freeproxy](https://github.com/CharlesPikachu/freeproxy)，感谢原作者开源）
- 以 `app.rainyun.com` 为探针并发验证（状态 200 且响应 ≤3s），找到可用代理即停，确保代理能真正连上雨云
- 每个账号每次签到独立获取代理，失败自动重试
- **无需任何配置**，直连可达时优先直连，被拦截时自动启用代理

> 本地运行（国内网络）不受影响，直连即可。

### 自建代理接口（可选）

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

### 账号安全

- **请不要将账号密码硬编码在脚本中，而是通过环境变量传递**。
- 建议使用单独的账号进行签到，避免因为主账号异常而导致的影响。

## 更新日志

### 2026-08-10

- 修复登录按钮 `StaleElementReferenceException`：填账号密码可能触发 Vue 重渲染导致 `login_button` 引用失效，改为填完后重新获取按钮再点击；同时 `visibility_of_element_located` 改为 `element_to_be_clickable` 确保 `enabled` 状态
- 修复代理重试反复命中慢代理：删除 `_IN_ACTIONS` 硬编码，改为 `check_rainyun_blocked()` 实时探测 `app.rainyun.com` 可达性决定是否走代理（雨云拦截为动态策略，未拦截时直连）；`get_freeproxy_ip` 新增 `exclude_ips` 参数，重试时跳过本轮已失败代理；`check_rainyun_blocked` 异常分支细化（仅连接类异常判拦截，网络毛刺不误判）；拦截探测结果缓存 5 分钟避免重试反复吃 timeout
- 修复直连场景下 renderer 超时误判为代理失败：动态探测改为直连后，Actions runner 性能波动导致的 renderer 超时被误判为 `proxy_failed=True`。区分代理/直连场景，有代理时触发换代理，直连时走普通重试
- 新增页面加载超时诊断信息：记录浏览器状态（URL/title/readyState/page_source 长度）和服务端连通性（requests 探测响应时间），区分网络波动/服务端慢/页面资源卡住三种场景
- 新增 Chrome 性能日志：页面超时时 dump 卡住期间的关键网络请求（失败请求/慢响应 TTFB>1s/主文档请求），可直接看出是 DNS/TTFB/资源下载哪个环节卡住
- 移除改进版 freeproxy 依赖：拦截自动代理改用自建轻量级抓取模块（5 个国内代理源并发抓取 + 探针验证找到即停），`requirements.txt` 不再包含 `git+https` 的 GitHub 依赖，国内安装不受 DNS 污染影响
- 移除 ip2region 离线定位依赖：国内源（89IP/快代理/齐云/开心）代理本身即 CN，ProxyScrape 自带国家码过滤，无需 ip2region.xdb

### 2026-08-03 (v2.3)

- 新增海外 IP 自动代理：海外环境（GitHub Actions、海外 VPS、Docker 等）被雨云拦截时，自动检测并抓取国内免费代理绕过拦截（基于改进版 freeproxy，找到可用即停，免配置）
- 新增签到状态校验：点击领取奖励后轮询检查按钮是否变为"已完成"，检测验证码加载框（三个点）防止网络慢导致误判
- 修复密码错误检测遗漏：密码错误时 toast 弹出后仅存在约 5 秒，但代码先等验证码超时后才检测，导致 toast 早已消失。改为验证码等待期间每 0.5 秒同时轮询 toast 错误提示，使用精确 XPath 定位 Vue-Toastification toast 元素，密码错误时秒级捕获
- 修复签到按钮 XPath：去掉末尾 `/a`，签到完成后按钮变为"已完成"时不再抛 `NoSuchElementException`
- 修复慢代理登录超时：用 `WebDriverWait` 轮询 URL 跳转替换固定 `sleep(5)`，最长等待 30 秒，避免代理慢导致误判"账号密码错误"
- 修复重试代理复用：重试时复用上次代理 IP，避免换 IP 导致服务器 Cookie 失效进而被迫走密码登录
- 修复截图并发竞争：多账号同秒截图时临时 PNG 文件名带账号标识，避免互相覆盖导致压缩失败
- 修复截图压缩失败回退逻辑：压缩失败时不再回退原始 PNG（避免邮件体积过大），改为放弃截图
- 优化登录失败诊断：区分"未配置账号密码"/"账号密码错误"/"跳转异常"，提示检查环境变量/GitHub Secrets
- 修复签到失败时 Actions 仍显示绿色成功的问题（补 `sys.exit(1)`）
- 精确化领取奖励按钮 xpath，避免误匹配"关注雨云"旁的同名按钮
- 推送通知响应超时从 10 秒延长到 30 秒

<details>
<summary>📜 历史更新日志（点击展开）</summary>

### 2026-03-30

- CI环境下隐藏积分信息
- 修复通知内容超长被截断问题，自动降级报告格式
- 增加截图嵌入策略配置（all / failed_only / none）

### 2026-02-04

- 支持多账号并发执行
- 优化日志输出，增加用户标识，提升多账号管理的可读性
- 关闭无图模式
- 调整Action默认执行时间

### 2026-02-03

- 优化点击逻辑，避免重复签到时报错显示异常
- 支持截图发送到通知功能中
- 压缩图片，减少通知大小

### 2026-01-31

- 根据账号随机浏览器指纹，增加反爬虫机制。
- 增加Cookie持久化功能，避免重复登录。
- 无图模式，减少资源占用。
- 新增代理IP支持，每个账号可独立使用不同代理IP。

### 2026-01-30

- 增加通知功能，支持PushPlus、WXPusher、钉钉、邮件通知。

### 2026-01-29

- 修复因前端弹窗导致的签到失败问题，优化自动化交互逻辑。
- 增强安全性与易用性，支持通过 `.env` 配置账号密码及运行参数，并完善文档说明。

</details>

## 常见问题

### Q: GitHub Actions / 海外 VPS 环境下签到失败，提示"代理过慢导致登录超时"或浏览器显示 This site can't be reached？

雨云于 2026 年 8 月更新了海外 IP 拦截策略，海外环境（GitHub Actions、海外 VPS、Docker 等）访问 `app.rainyun.com` 会被拒绝连接。程序会自动检测拦截并抓取国内免费代理绕过。免费代理质量参差不齐，慢代理可能导致登录请求未在 30 秒内完成。程序会自动标记失败代理并换新代理重试，最多重试 3 次。如果所有代理都太慢，可以尝试：

- 重新触发一次运行（每次抓取的代理不同）
- 自行配置优质代理（设置环境变量 `HTTP_PROXY` / `HTTPS_PROXY`）

### Q: 提示"账号或密码错误"但我的密码没问题？

请先到 [雨云登录页](https://app.rainyun.com/auth/login) 手动登录确认账号密码是否正确。如果手动登录正常但签到仍报错，请提 [Issue](https://github.com/LeapYa/Rainyun-Qiandao/issues)。

### Q: 日志显示"代理过慢"但实际上是密码错误？

代理太慢时，登录 API 请求无法完成，页面既不跳转也不弹出错误提示，程序无法区分是代理问题还是密码问题。只有代理够快时，API 返回 400 后页面才会弹出 toast 错误提示，程序才能捕获并报告"账号或密码错误"。这种情况下多试几次（或换好代理）就能看到真正的错误原因。

### Q: 提示"未配置雨云账号密码"？

说明 `RAINYUN_USERNAME` 或 `RAINYUN_PASSWORD` 环境变量为空。请按 [食用方法](#食用方法) 中的步骤配置 GitHub Secrets。

### Q: 签到成功但 Actions 显示红色失败？

这通常是因为签到过程中出现了非致命异常（如截图保存失败），但签到本身已成功。查看日志中是否有"签到成功"字样即可确认。如果确实签到失败，日志会明确标注失败原因。

### Q: 报错 `NoSuchElementException` / `TimeoutException`，提示找不到元素或等待超时？

网页加载缓慢导致元素未及时渲染。可尝试延长超时等待时间，或更换连接性更好的国内主机。

### Q: Fork 后定时任务不执行？

GitHub 对 Fork 仓库的定时任务有限制，需要手动激活：

1. 进入 Fork 仓库的 **Actions** 页面
2. 点击 **I understand my workflows, go ahead and enable**
3. 首次需要手动触发一次运行，之后定时任务才会生效

## 致谢

本项目基于 [Rainyun-Qiandao](https://github.com/SerendipityR-2022/Rainyun-Qiandao) 开发，感谢原作者的开源贡献。

> [!NOTE]
> **免责声明与致谢**
>
> - ⚠️ 本项目仅供技术交流与学习参考，请严格遵守相关法律法规，切勿将其用于任何商业或非法用途。
> - 🚫 将本项目分享到任何雨云官方相关讨论社区/群组是极其不明智的行为，请不要这么做！
> - 💡 开源不易，在您进行分发、搬运或二次开源时，请务必保留原项目出处及致谢信息，感谢您的理解与尊重！
