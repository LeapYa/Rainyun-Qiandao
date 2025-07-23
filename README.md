# Rainyun-Qiandao-V2 (Selenium)
**V2版本更新！**

**雨云签到工具 搭配宝塔计划任务可实现每日自动签到~**

众所周知，雨云为了防止白嫖加入了TCaptcha验证码，但主包对JS逆向一窍不通，纯请求的方法便走不通了。

因此只能曲线救国，使用 **Selenium+ddddocr** 来模拟真人操作。

经不严谨测试，目前的方案验证码识别率高达**48.3%**，不过多次重试最终也能通过验证，那么目的达成！

## 食用方法
1. 安装[Python](https://www.python.org/downloads/)作为运行环境
2. 配置好本地Selenium环境，**一般情况下你不应该使用跟随此项目上传的chromedriver**，你可以参照[这个视频](https://www.bilibili.com/video/BV1Y9UPYAEqN?p=2)
3. 第一次运行，需要安装依赖库，在项目目录下运行`python -m pip install -r requirements.txt`即可。
4. 编辑`rainyun.py`中位于入口函数的设置，保存并执行即可自动化运行签到流程。

## 常见问题
### 1. Linux系统怎么使用？
#### 参照[此处](https://github.com/SerendipityR-2022/Rainyun-Qiandao/issues/1#issuecomment-3096198779)。
### 2. 找不到元素，报错`NoSuchElementException`
#### 网页加载缓慢，尝试延长超时等待时间或更换连接性更好的国内主机。
