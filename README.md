# Rainyun-Qiandao-v2.2-docker (Selenium)

**🐳 容器化部署，内置定时任务**

**v2.2-docker 版本更新！**

**雨云签到工具 容器化部署后可实现每日自动签到~**

众所周知，雨云为了防止白嫖加入了TCaptcha验证码，但主包对JS逆向一窍不通，纯请求的方法便走不通了。

因此只能曲线救国，使用 **Selenium+ddddocr** 来模拟真人操作。

经不严谨测试，目前的方案验证码识别率高达**48.3%**，不过多次重试最终也能通过验证，那么目的达成！

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

根据你的需求，从以下两种模式中**选择一种**运行

#### 模式一：定时运行（推荐）

适合长期部署，程序会持续运行，并在每天指定时间（默认08:00）自动执行签到。

```bash
# 启动定时服务
sudo docker compose up -d rainyun-schedule

# 查看实时日志
sudo docker compose logs -f rainyun-schedule

# 停止服务
sudo docker compose down
```

#### 模式二：单次运行

适合测试账号配置是否正确，或者临时手动执行一次签到。运行结束后容器会自动退出。

```bash
# 立即执行一次签到（前台运行，可看到实时日志）
sudo docker compose --profile once up rainyun-once

# 或者后台运行
sudo docker compose --profile once up -d rainyun-once
```


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

## 致谢

本项目基于 [Rainyun-Qiandao](https://github.com/SerendipityR-2022/Rainyun-Qiandao) 开发，感谢原作者的开源贡献。
