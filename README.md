# Rainyun-Qiandao-V2 (Selenium)

**🐳 容器化部署，内置定时任务**

**V2版本更新！**

**雨云签到工具 搭配宝塔计划任务可实现每日自动签到~**

众所周知，雨云为了防止白嫖加入了TCaptcha验证码，但主包对JS逆向一窍不通，纯请求的方法便走不通了。

因此只能曲线救国，使用 **Selenium+ddddocr** 来模拟真人操作。

经不严谨测试，目前的方案验证码识别率高达**48.3%**，不过多次重试最终也能通过验证，那么目的达成！

## 食用方法

### 单次运行模式

适用于测试或手动执行：

```bash
# 立即执行一次签到
docker-compose --profile once up rainyun-once

# 后台运行（会自动退出）
docker-compose --profile once up -d rainyun-once
```

### 定时运行模式（推荐）

程序会持续运行，每天指定时间自动执行：

```bash
# 启动定时服务
docker-compose up -d rainyun-schedule

# 查看实时日志
docker-compose logs -f rainyun-schedule

# 停止服务
docker-compose down
```

### 手动控制

```bash
# 构建镜像
docker-compose build

# 重启定时服务
docker-compose restart rainyun-schedule

# 查看服务状态
docker-compose ps
```

### 1. Linux系统怎么使用？

#### 参照[此处](https://github.com/SerendipityR-2022/Rainyun-Qiandao/issues/1#issuecomment-3096198779)。

### 2. 找不到元素或等待超时，报错 `NoSuchElementException`/`TimeoutException`

#### 网页加载缓慢，尝试延长超时等待时间或更换连接性更好的国内主机。
