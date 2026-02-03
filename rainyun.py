import logging
import logging.handlers
import os
import random
import time
import schedule
import sys
from datetime import datetime, timedelta

# 全局变量，用于存储Selenium模块
selenium_modules = None

def import_selenium_modules():
    """导入Selenium相关模块"""
    global selenium_modules
    if selenium_modules is None:
        from selenium import webdriver
        from selenium.webdriver import ActionChains
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.webdriver import WebDriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.common import TimeoutException
        
        selenium_modules = {
            'webdriver': webdriver,
            'ActionChains': ActionChains,
            'Options': Options,
            'Service': Service,
            'WebDriver': WebDriver,
            'By': By,
            'EC': EC,
            'WebDriverWait': WebDriverWait,
            'TimeoutException': TimeoutException
        }
    return selenium_modules

def unload_selenium_modules():
    """卸载Selenium相关模块，释放内存"""
    global selenium_modules
    if selenium_modules is not None:
        # 从sys.modules中移除Selenium模块
        modules_to_remove = [
            'selenium',
            'selenium.webdriver',
            'selenium.webdriver.chrome',
            'selenium.webdriver.chrome.options',
            'selenium.webdriver.chrome.service',
            'selenium.webdriver.chrome.webdriver',
            'selenium.webdriver.common',
            'selenium.webdriver.common.by',
            'selenium.webdriver.support',
            'selenium.webdriver.support.expected_conditions',
            'selenium.webdriver.support.wait',
            'selenium.common'
        ]
        
        for module in modules_to_remove:
            if module in sys.modules:
                del sys.modules[module]
        
        selenium_modules = None


def setup_logging():
    """设置日志轮转功能，自动清理7天前的日志"""
    # 确保日志目录存在
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日志轮转处理器，保留7天的日志，每天轮转一次
    log_file = os.path.join(log_dir, "rainyun.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',  # 每天午夜轮转
        interval=1,  # 每天轮转一次
        backupCount=7,  # 保留7天的日志
        encoding='utf-8'
    )
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 清理旧的日志文件（超过7天的）
    cleanup_old_logs(log_dir, days=7)
    
    # 清理旧的日志文件（超过7天的）
    cleanup_old_logs(log_dir, days=7)
    
    return root_logger


# ==========================================
# Notification System
# ==========================================

class NotificationProvider:
    """通知提供者基类"""
    def send(self, title, context):
        """
        发送通知
        :param title: 标题
        :param context: 内容上下文，包含 {'html': str, 'markdown': str}
        """
        raise NotImplementedError

class PushPlusProvider(NotificationProvider):
    """PushPlus 推送渠道"""
    def __init__(self, token):
        self.token = token

    def send(self, title, context):
        import requests
        content = context.get('html', '')
        url = 'http://www.pushplus.plus/send'
        data = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": "html"
        }
        try:
            logging.info(f"Sending PushPlus notification: {title}")
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('code') == 200:
                logging.info("PushPlus notification sent successfully")
                return True
            else:
                logging.error(f"PushPlus notification failed: {result.get('msg')}")
                return False
        except Exception as e:
            logging.error(f"Error sending PushPlus notification: {e}")
            return False

class WXPusherProvider(NotificationProvider):
    """WXPusher 推送渠道"""
    def __init__(self, app_token, uids):
        self.app_token = app_token
        self.uids = uids if isinstance(uids, list) else [uid.strip() for uid in uids.split(',') if uid.strip()]

    def send(self, title, context):
        import requests
        content = context.get('html', '')
        url = 'https://wxpusher.zjiecode.com/api/send/message'
        data = {
            "appToken": self.app_token,
            "content": content,
            "summary": title,
            "contentType": 2,  # 1=Text, 2=HTML
            "uids": self.uids
        }
        try:
            logging.info(f"Sending WXPusher notification: {title}")
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('code') == 1000: # WXPusher success code is 1000
                logging.info("WXPusher notification sent successfully")
                return True
            else:
                logging.error(f"WXPusher notification failed: {result.get('msg')}")
                return False
        except Exception as e:
            logging.error(f"Error sending WXPusher notification: {e}")
            return False

class DingTalkProvider(NotificationProvider):
    """钉钉机器人推送渠道"""
    def __init__(self, access_token, secret=None):
        self.access_token = access_token
        self.secret = secret

    def send(self, title, context):
        import requests
        import time
        import hmac
        import hashlib
        import base64
        import urllib.parse
        
        content = context.get('markdown', '')
        # 钉钉 Markdown 需要 title 字段
        # content 必须包含 title，这里组合一下
        md_text = f"# {title}\n\n{content}"
        
        url = 'https://oapi.dingtalk.com/robot/send'
        params = {'access_token': self.access_token}
        
        if self.secret:
            timestamp = str(round(time.time() * 1000))
            secret_enc = self.secret.encode('utf-8')
            string_to_sign = '{}\n{}'.format(timestamp, self.secret)
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            params['timestamp'] = timestamp
            params['sign'] = sign

        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": md_text
            }
        }
        
        try:
            logging.info(f"Sending DingTalk notification: {title}")
            response = requests.post(url, params=params, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                logging.info("DingTalk notification sent successfully")
                return True
            else:
                logging.error(f"DingTalk notification failed: {result.get('errmsg')}")
                return False
        except Exception as e:
            logging.error(f"Error sending DingTalk notification: {e}")
            return False

class EmailProvider(NotificationProvider):
    """邮件推送渠道"""
    def __init__(self, host, port, user, password, to_email):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.to_email = to_email

    def send(self, title, context):
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.header import Header
        
        content = context.get('html', '')
        
        try:
            message = MIMEMultipart()
            message['From'] = f"Rainyun-Qiandao <{self.user}>"
            message['To'] = self.to_email
            message['Subject'] = Header(title, 'utf-8')
            
            message.attach(MIMEText(content, 'html', 'utf-8'))
            
            logging.info(f"Sending Email notification to {self.to_email}")
            
            # 连接 SMTP 服务器
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
                # 尝试启用 TLS
                try:
                    server.starttls()
                except:
                    pass
            
            server.login(self.user, self.password)
            server.sendmail(self.user, [self.to_email], message.as_string())
            server.quit()
            
            logging.info("Email notification sent successfully")
            return True
        except Exception as e:
            logging.error(f"Error sending Email notification: {e}")
            return False

class NotificationManager:
    """通知管理器"""
    def __init__(self):
        self.providers = []

    def add_provider(self, provider):
        self.providers.append(provider)

    def send_all(self, title, context):
        if not self.providers:
            logging.info("No notification providers configured.")
            return

        logging.info(f"Sending notifications to {len(self.providers)} providers...")
        for provider in self.providers:
            provider.send(title, context)


def cleanup_old_logs(log_dir, days=7):
    """清理超过指定天数的日志文件"""
    try:
        now = time.time()
        cutoff = now - (days * 86400)  # 86400秒 = 1天
        
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            if os.path.isfile(file_path) and filename.startswith('rainyun.log.'):
                file_time = os.path.getmtime(file_path)
                if file_time < cutoff:
                    os.remove(file_path)
                    logging.info(f"已删除过期日志文件: {filename}")
    except Exception as e:
        logging.error(f"清理旧日志文件时出错: {e}")


def cleanup_logs_on_startup():
    """程序启动时执行日志清理"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        return
    
    try:
        # 统计当前日志文件数量和大小
        log_files = [f for f in os.listdir(log_dir) if f.startswith('rainyun.log.')]
        total_size = sum(os.path.getsize(os.path.join(log_dir, f)) for f in log_files if os.path.isfile(os.path.join(log_dir, f)))
        
        if log_files:
            logging.info(f"检测到 {len(log_files)} 个历史日志文件，总大小约 {total_size / 1024 / 1024:.2f} MB")
            
            # 如果日志文件过多，执行清理
            if len(log_files) > 10:  # 如果超过10个日志文件
                logging.info("历史日志文件过多，执行清理...")
                cleanup_old_logs(log_dir, days=7)
                
                # 重新统计清理后的情况
                remaining_files = [f for f in os.listdir(log_dir) if f.startswith('rainyun.log.')]
                remaining_size = sum(os.path.getsize(os.path.join(log_dir, f)) for f in remaining_files if os.path.isfile(os.path.join(log_dir, f)))
                logging.info(f"清理完成，剩余 {len(remaining_files)} 个日志文件，总大小约 {remaining_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        logging.error(f"启动时日志清理出错: {e}")


def setup_sigchld_handler():
    """设置SIGCHLD信号处理器，自动回收子进程，防止僵尸进程累积"""
    # 延迟导入signal模块
    import signal
    
    def sigchld_handler(signum, frame):
        """当子进程退出时自动回收，防止变成僵尸进程"""
        while True:
            try:
                # 非阻塞地回收所有已退出的子进程
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:  # 没有更多子进程需要回收
                    break
            except ChildProcessError:
                # 没有子进程了
                break
            except Exception:
                break
    
    if os.name == 'posix':  # 仅在Linux/Unix系统上设置
        signal.signal(signal.SIGCHLD, sigchld_handler)
        logging.info("已设置子进程自动回收机制，防止僵尸进程累积")


def cleanup_zombie_processes():
    """清理可能残留的 Chrome/ChromeDriver 僵尸进程"""
    # 延迟导入subprocess模块
    import subprocess
    
    try:
        if os.name == 'posix':  # Linux/Unix 系统
            # 查找并清理僵尸 chrome 和 chromedriver 进程
            try:
                result = subprocess.run(['pgrep', '-f', 'chrome|chromedriver'], 
                                      capture_output=True, text=True, timeout=5)
                if result.stdout:
                    pids = result.stdout.strip().split('\n')
                    zombie_count = 0
                    zombie_pids = []
                    parent_pids = set()
                    
                    for pid in pids:
                        if pid:
                            try:
                                # 检查进程状态
                                stat_result = subprocess.run(['ps', '-p', pid, '-o', 'stat='], 
                                                           capture_output=True, text=True, timeout=2)
                                if 'Z' in stat_result.stdout:  # 僵尸进程
                                    zombie_count += 1
                                    zombie_pids.append(pid)
                                    
                                    # 获取父进程PID
                                    ppid_result = subprocess.run(['ps', '-p', pid, '-o', 'ppid='], 
                                                               capture_output=True, text=True, timeout=2)
                                    if ppid_result.stdout:
                                        ppid = ppid_result.stdout.strip()
                                        if ppid and ppid != '1':  # 不处理init进程的子进程
                                            parent_pids.add(ppid)
                                            logger.warning(f"发现僵尸进程 PID: {pid}, 父进程: {ppid}")
                                        else:
                                            logger.warning(f"发现僵尸进程 PID: {pid}")
                            except:
                                pass
                    
                    if zombie_count > 0:
                        logger.info(f"检测到 {zombie_count} 个僵尸进程")
                        
                        # 尝试通过 waitpid 回收僵尸进程（非阻塞）
                        cleaned = 0
                        for zpid in zombie_pids:
                            try:
                                os.waitpid(int(zpid), os.WNOHANG)
                                cleaned += 1
                            except (ChildProcessError, ProcessLookupError, PermissionError, ValueError):
                                # 不是当前进程的子进程，无法直接回收
                                pass
                        
                        if cleaned > 0:
                            logger.info(f"成功回收 {cleaned} 个僵尸进程")
                        
                        # 对于无法回收的僵尸进程，记录父进程信息
                        if parent_pids:
                            logger.info(f"僵尸进程的父进程 PIDs: {', '.join(parent_pids)}")
                            logger.info("提示：僵尸进程由父进程创建，需要父进程调用wait()回收")
                            logger.info("这些僵尸进程不占用CPU/内存，通常会在父进程结束时被init接管并清理")
                        
                        # 清理可能残留的活跃Chrome子进程（非僵尸）
                        subprocess.run(['pkill', '-9', '-f', 'chrome.*--type='], 
                                     timeout=5, stderr=subprocess.DEVNULL)
                        logger.info("已清理残留的活跃 Chrome 子进程")
                    
            except subprocess.TimeoutExpired:
                logger.warning("进程清理超时")
            except FileNotFoundError:
                # pgrep/pkill 命令不存在，跳过
                pass
            except Exception as e:
                logger.debug(f"清理进程时出现异常（可忽略）: {e}")
    except Exception as e:
        logger.debug(f"僵尸进程清理失败（可忽略）: {e}")


def get_random_user_agent(account_id: str) -> str:
    """
    获取 User-Agent，基于当前时间动态生成版本
    """
    import hashlib
    import datetime
    # 基于时间推算当前 Chrome 版本（Chrome 100 发布于 2022-03-29）
    base_date = datetime.date(2022, 3, 29)
    base_version = 100
    days_diff = (datetime.date.today() - base_date).days
    current_ver = base_version + (days_diff // 32)
    
    # 构建 UA 列表
    user_agents = [
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{current_ver}.0.0.0 Safari/537.36",
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{current_ver-1}.0.0.0 Safari/537.36",
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{current_ver-2}.0.0.0 Safari/537.36",
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{current_ver-10}.0) Gecko/20100101 Firefox/{current_ver-10}.0",
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{current_ver}.0.0.0 Safari/537.36 Edg/{current_ver}.0.0.0"
    ]
    
    # 基于账号确定性选择
    account_hash = hashlib.md5(account_id.encode()).hexdigest()
    seed = int(account_hash[:8], 16)
    rng = random.Random(seed)
    return rng.choice(user_agents)


def generate_fingerprint_script(account_id: str):
    """
    生成浏览器指纹随机化脚本
    基于账号ID生成确定性指纹，确保：
    - 同一账号每次签到指纹相同（持久化）
    - 不同账号之间指纹不同（区分）
    
    :param account_id: 账号标识（如用户名），用于生成确定性种子
    """
    import hashlib
    
    # 基于账号生成确定性种子
    account_hash = hashlib.md5(account_id.encode()).hexdigest()
    seed = int(account_hash[:8], 16)  # 取前8位十六进制作为种子
    
    # 使用种子创建确定性随机数生成器
    rng = random.Random(seed)
    
    # 随机 WebGL 渲染器和厂商（基于账号确定性选择）
    webgl_vendors = [
        ("Intel Inc.", "Intel Iris Xe Graphics"),
        ("Intel Inc.", "Intel UHD Graphics 770"),
        ("Intel Inc.", "Intel UHD Graphics 730"),
        ("Intel Inc.", "Intel Iris Plus Graphics"),
        ("Intel Inc.", "Intel Arc A770"),
        ("Intel Inc.", "Intel Arc A750"),
        ("Intel Inc.", "Intel Arc B580"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4090/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4080 SUPER/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4070 Ti SUPER/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4070 SUPER/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4070/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4060 Ti/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 4060/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 5090/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 5080/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 5070 Ti/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 5070/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3080/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3070/PCIe/SSE2"),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3060/PCIe/SSE2"),
        ("AMD", "AMD Radeon RX 7900 XTX"),
        ("AMD", "AMD Radeon RX 7900 XT"),
        ("AMD", "AMD Radeon RX 7800 XT"),
        ("AMD", "AMD Radeon RX 7700 XT"),
        ("AMD", "AMD Radeon RX 7600 XT"),
        ("AMD", "AMD Radeon RX 7600"),
        ("AMD", "AMD Radeon RX 9070 XT"),
        ("AMD", "AMD Radeon RX 9070"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0)"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)"),
        ("Google Inc. (Intel)", "ANGLE (Intel, Intel UHD Graphics 770 Direct3D11 vs_5_0 ps_5_0)"),
        ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0)")
    ]
    vendor, renderer = rng.choice(webgl_vendors)
    
    # 确定性硬件并发数 (CPU 核心数)
    hardware_concurrency = rng.choice([4, 6, 8, 12, 16])
    
    # 确定性设备内存 (GB)
    device_memory = rng.choice([8, 16, 32])
    
    # 确定性语言
    languages = [
        ["zh-CN", "zh", "en-US", "en"],
        ["zh-CN", "zh"],
        ["en-US", "en", "zh-CN"],
        ["zh-CN", "en-US"],
    ]
    language = rng.choice(languages)
    
    # Canvas 噪声种子（基于账号确定性）
    canvas_noise_seed = rng.randint(1, 1000000)
    
    # AudioContext 噪声（基于账号确定性）
    audio_noise = rng.uniform(0.00001, 0.0001)
    
    # 插件数量（基于账号确定性）
    plugins_length = rng.randint(0, 5)
    
    logger.debug(f"账号指纹: WebGL={renderer[:30]}..., CPU={hardware_concurrency}核, 内存={device_memory}GB")
    
    fingerprint_script = f"""
    (function() {{
        'use strict';
        
        // ===============================
        // WebGL 指纹随机化
        // ===============================
        const getParameterProxyHandler = {{
            apply: function(target, thisArg, args) {{
                const param = args[0];
                const gl = thisArg;
                
                // UNMASKED_VENDOR_WEBGL
                if (param === 37445) {{
                    return '{vendor}';
                }}
                // UNMASKED_RENDERER_WEBGL
                if (param === 37446) {{
                    return '{renderer}';
                }}
                return Reflect.apply(target, thisArg, args);
            }}
        }};
        
        // 代理 WebGL getParameter
        try {{
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);
        }} catch(e) {{}}
        
        try {{
            const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = new Proxy(originalGetParameter2, getParameterProxyHandler);
        }} catch(e) {{}}
        
        // ===============================
        // Canvas 指纹随机化（添加噪声）
        // ===============================
        const noiseSeed = {canvas_noise_seed};
        
        // 简单的伪随机数生成器（基于种子）
        function seededRandom(seed) {{
            const x = Math.sin(seed) * 10000;
            return x - Math.floor(x);
        }}
        
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
            const canvas = this;
            const ctx = canvas.getContext('2d');
            if (ctx) {{
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const data = imageData.data;
                // 添加微小噪声
                for (let i = 0; i < data.length; i += 4) {{
                    // 只修改少量像素，且变化很小
                    if (seededRandom(noiseSeed + i) < 0.01) {{
                        data[i] = data[i] ^ 1;     // R
                        data[i+1] = data[i+1] ^ 1; // G
                    }}
                }}
                ctx.putImageData(imageData, 0, 0);
            }}
            return originalToDataURL.apply(this, arguments);
        }};
        
        // ===============================
        // AudioContext 指纹随机化
        // ===============================
        const audioNoise = {audio_noise};
        
        if (window.OfflineAudioContext) {{
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function(channel) {{
                const result = originalGetChannelData.call(this, channel);
                // 使用确定性种子添加噪声
                for (let i = 0; i < result.length; i += 100) {{
                    const noise = Math.sin({canvas_noise_seed} + i) * audioNoise;
                    result[i] = result[i] + noise;
                }}
                return result;
            }};
        }}
        
        // ===============================
        // 硬件信息随机化
        // ===============================
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {hardware_concurrency}
        }});
        
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {device_memory}
        }});
        
        // ===============================
        // 语言随机化
        // ===============================
        Object.defineProperty(navigator, 'languages', {{
            get: () => {language}
        }});
        
        Object.defineProperty(navigator, 'language', {{
            get: () => '{language[0]}'
        }});
        
        // ===============================
        // 插件列表随机化（返回空或伪造）
        // ===============================
        Object.defineProperty(navigator, 'plugins', {{
            get: () => {{
                return {{
                    length: {plugins_length},
                    item: () => null,
                    namedItem: () => null,
                    refresh: () => {{}},
                    [Symbol.iterator]: function* () {{}}
                }};
            }}
        }});
        
        // 屏蔽 WebDriver 检测
        Object.defineProperty(navigator, 'webdriver', {{
            get: () => undefined
        }});
        
        // 修改 chrome 对象
        window.chrome = {{
            runtime: {{}},
            loadTimes: function() {{}},
            csi: function() {{}},
            app: {{}}
        }};
        
        console.log('[Fingerprint] Browser fingerprint initialized (deterministic)');
    }})();
    """
    
    return fingerprint_script


def get_proxy_ip():
    """
    从代理接口获取代理IP
    每个账号单独调用一次，获取独立的代理IP
    """
    import requests
    import json
    
    proxy_api_url = os.getenv("PROXY_API_URL", "").strip()
    
    if not proxy_api_url:
        return None
    
    try:
        # 请求前随机延迟，防止并发打挂接口
        delay = random.uniform(0.5, 2.0)
        logger.debug(f"请求代理接口前延迟 {delay:.2f} 秒")
        time.sleep(delay)
        
        logger.info(f"正在从代理接口获取IP...")
        response = requests.get(proxy_api_url, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"代理接口请求失败，状态码: {response.status_code}")
            return None
        
        proxy = parse_proxy_response(response.text)
        
        if not proxy:
            logger.error(f"代理接口返回格式无法解析: {response.text[:100]}")
            return None
        
        logger.info(f"获取到代理IP: {proxy}")
        return proxy
        
    except requests.Timeout:
        logger.error("代理接口请求超时")
        return None
    except Exception as e:
        logger.error(f"获取代理IP失败: {e}")
        return None


def parse_proxy_response(response_text):
    """
    解析代理接口返回的内容，支持多种格式：
    - 纯文本: ip:port
    - JSON: {"ip": "x.x.x.x", "port": 8080}
    - JSON: {"proxy": "ip:port"}
    - JSON: {"code": 0, "data": {"proxy": "ip:port"}}
    - JSON: {"code": 0, "data": {"ip": "x.x.x.x", "port": 8080}}
    - 带协议: http://ip:port
    """
    import json
    
    response_text = response_text.strip()
    
    # 尝试 JSON 解析
    try:
        data = json.loads(response_text)
        
        # 处理嵌套的 data 字段
        if "data" in data and isinstance(data["data"], dict):
            data = data["data"]
        
        # 格式: {"proxy": "ip:port"}
        if "proxy" in data:
            proxy = str(data["proxy"]).strip()
            if "://" in proxy:
                proxy = proxy.split("://")[-1]
            return proxy if ":" in proxy else None
        
        # 格式: {"ip": "x.x.x.x", "port": 8080}
        if "ip" in data and "port" in data:
            return f"{data['ip']}:{data['port']}"
        
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    
    # 纯文本格式处理
    proxy = response_text.strip()
    
    # 去除可能的协议前缀
    if "://" in proxy:
        proxy = proxy.split("://")[-1]
    
    # 验证是否为有效的 ip:port 格式
    if ":" in proxy:
        parts = proxy.split(":")
        if len(parts) == 2:
            ip_part, port_part = parts
            # 简单验证IP和端口格式
            if port_part.isdigit() and 1 <= int(port_part) <= 65535:
                return proxy
    
    return None


def validate_proxy(proxy, timeout=10):
    """
    测试代理是否可用
    :param proxy: 代理地址，格式为 ip:port
    :param timeout: 超时时间（秒）
    :return: True 可用，False 不可用
    """
    import requests
    
    if not proxy:
        return False
    
    try:
        test_proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        
        # 使用雨云网站测试代理连通性（更贴近实际使用场景）
        logger.info(f"正在验证代理 {proxy} 的可用性...")
        response = requests.get(
            "https://www.rainyun.com",
            proxies=test_proxies,
            timeout=timeout
        )
        
        if response.status_code == 200:
            logger.info(f"代理 {proxy} 验证成功")
            return True
        else:
            logger.warning(f"代理验证失败，状态码: {response.status_code}")
            return False
            
    except requests.Timeout:
        logger.warning(f"代理 {proxy} 验证超时")
        return False
    except Exception as e:
        logger.warning(f"代理 {proxy} 验证失败: {e}")
        return False


# SVG图标
SVG_ICONS = {
    'success': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#10B981" width="24" height="24"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd" /></svg>''',
    'error': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#EF4444" width="24" height="24"><path fill-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clip-rule="evenodd" /></svg>''',
    'user': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#6B7280" width="20" height="20"><path fill-rule="evenodd" d="M7.5 6a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM3.751 20.105a8.25 8.25 0 0116.498 0 .75.75 0 01-.437.695A18.683 18.683 0 0112 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 01-.437-.695z" clip-rule="evenodd" /></svg>''',
    'coin': '''<svg class="icon" viewBox="0 0 1114 1024" xmlns="http://www.w3.org/2000/svg" width="200" height="200"><path d="M807.511 400.666a512 512 0 0 0-60.15-53.873c-3.072-2.345-5.427-3.983-8.15-5.98 38.066-13.077 64.7-44.38 64.7-81.434 0-49.9-47.37-88.08-103.618-88.08a99.4 99.4 0 0 0-35.558 6.498 79 79 0 0 0-11.771 5.591c-1.966.83-6.16-.097-7.312-1.53l-.05.035c-4.291-6.43-10.763-14.402-20.168-22.569-17.9-15.554-39.092-25.15-63.294-25.15s-45.384 9.596-63.288 25.15c-9.19 7.977-15.498 15.713-19.804 22.078l-.026-.02c-1.628 1.92-5.852 2.928-7.322 2.221a78.4 78.4 0 0 0-12.144-5.811 99.5 99.5 0 0 0-35.564-6.502c-56.248 0-103.613 38.185-103.613 88.079 0 31.683 19.543 59.105 48.957 74.624a495 495 0 0 0-9.405 6.84 468 468 0 0 0-60.058 53.315C244.265 452.956 210.5 520.212 210.5 594.872c0 207.022 154.28 305.48 340.131 305.48 77.891 0 154.03-15.54 215.64-52.219 83.599-49.792 131.153-133.427 131.153-253.26-.015-70.165-33.996-135.348-89.912-194.207M646.564 601.43c10.598 0 19.184 8.791 19.184 19.615 0 10.829-8.59 19.625-19.184 19.625H569.81v56.489c0 8.289-8.591 15.006-19.185 15.006-10.598 0-19.184-6.717-19.184-15.006v-56.49h-76.754c-10.599 0-19.185-8.79-19.185-19.62s8.591-19.614 19.185-19.614h76.754V581.82h-76.754c-10.599 0-19.185-8.785-19.185-19.614s8.591-19.615 19.185-19.615h78.397l-72.78-74.399a19.917 19.917 0 0 1 0-27.735 18.893 18.893 0 0 1 27.135 0l63.186 64.584 63.186-64.584a18.903 18.903 0 0 1 26.721-.425l.42.425a19.927 19.927 0 0 1 0 27.735l-72.78 74.399h78.402c10.598 0 19.18 8.78 19.18 19.615s-8.587 19.614-19.18 19.614h-76.759v19.61z" fill="#f59e0b"/></svg>'''
}


def get_screenshot_html(screenshot_path):
    """
    将截图文件转换为 Base64 嵌入的 HTML img 标签
    :param screenshot_path: 截图文件路径
    :return: HTML img 标签或空字符串
    """
    if not screenshot_path or not os.path.exists(screenshot_path):
        return ""
    
    try:
        import base64
        with open(screenshot_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        # 根据文件扩展名确定 MIME 类型
        mime_type = "image/jpeg" if screenshot_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"
        
        # 获取文件大小
        file_size = os.path.getsize(screenshot_path) / 1024  # KB
        
        return f'''
            <div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">
                <div style="font-size: 12px; color: var(--text-sub); margin-bottom: 8px;">📸 截图 ({file_size:.1f}KB)</div>
                <img src="data:{mime_type};base64,{img_data}" style="max-width: 100%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" alt="签到截图"/>
            </div>
        '''
    except Exception as e:
        logger.debug(f"生成截图 HTML 时出错: {e}")
        return ""



def generate_html_report(results):
    """生成 HTML 签到报告"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    success_count = len([r for r in results if r['status']])
    total_count = len(results)
    
    # 基础样式
    style_block = """
    <style>
        :root {
            --bg-body: #f9fafb;
            --bg-card: #ffffff;
            --text-main: #111827;
            --text-sub: #6b7280;
            --border: #e5e7eb;
            --bg-success: #ecfdf5;
            --text-success: #059669;
            --bg-error: #fef2f2;
            --text-error: #dc2626;
            --bg-footer: #f3f4f6;
            --text-footer: #9ca3af;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-body: #18181b;
                --bg-card: #27272a;
                --text-main: #f3f4f6;
                --text-sub: #9ca3af;
                --border: #3f3f46;
                --bg-success: #064e3b;
                --text-success: #34d399;
                --bg-error: #7f1d1d;
                --text-error: #f87171;
                --bg-footer: #1f2937;
                --text-footer: #6b7280;
            }
        }
        .container { max-width: 600px; margin: 0 auto; background-color: var(--bg-body); border-radius: 16px; overflow: hidden; border: 1px solid var(--border); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
        .header { background-color: var(--bg-card); padding: 24px; border-bottom: 1px solid var(--border); }
        .title { margin: 0; color: var(--text-main); font-size: 20px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        .subtitle { margin-top: 8px; color: var(--text-sub); font-size: 13px; font-weight: 500;}
        .badges { margin-top: 16px; display: flex; gap: 8px; }
        .badge-success { background-color: var(--bg-success); color: var(--text-success); padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
        .badge-error { background-color: var(--bg-error); color: var(--text-error); padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
        .content { padding: 16px; background-color: var(--bg-body); }
        .card { background-color: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06); }
        .row-item { display: flex; align-items: center; gap: 6px; }
        .footer { background-color: var(--bg-body); padding: 20px; text-align: center; font-size: 12px; color: var(--text-footer); }
        /* Fix SVG size */
        svg { width: 20px; height: 20px; display: block; }
    </style>
    """
    
    html = f"""
    {style_block}
    <div class="container">
        <div class="header">
            <h3 class="title">
                🌧️ 雨云签到报告
            </h3>
            <div class="subtitle">
                {now_str}
            </div>
            <div class="badges">
                <span class="badge-success">
                    成功: {success_count}
                </span>
                <span class="badge-error">
                    失败: {total_count - success_count}
                </span>
            </div>
        </div>
        
        <div class="content">
    """
    
        
    for res in results:
        status_color = "var(--text-success)" if res['status'] else "var(--text-error)"
        status_bg = "var(--bg-success)" if res['status'] else "var(--bg-error)"
        
        points_element = ""
        if res.get('points'):
            points = res['points']
            money = points / 2000
            points_element = f"""
            <div class="row-item" style="color: #f59e0b; font-weight: 500;">
                {SVG_ICONS['coin']}
                <span>{points} (≈￥{money:.2f})</span>
            </div>
            """
        else:
            # 失败时显示错误信息
            points_element = f"""
            <div class="row-item" style="color: var(--text-error);">
               <span>{res['msg']}</span>
            </div>
            """

        html += f"""
        <div class="card">
            <!-- 上半部分：用户信息 + 状态徽标 -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div class="row-item" style="font-weight: 600; font-size: 15px;">
                    {SVG_ICONS['user']}
                    <span>{res['username']}</span>
                </div>
                <span style="background-color: {status_bg}; color: {status_color}; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;">
                    {'签到成功' if res['status'] else '签到失败'}
                </span>
            </div>
            
            <!-- 分割线 -->
            <div style="height: 1px; background-color: var(--border); margin-bottom: 12px; opacity: 0.5;"></div>
            
            <!-- 下半部分：积分信息/错误信息 + 更多细节 -->
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
                {points_element}
                <div class="row-item" style="color: var(--text-sub); font-size: 12px;">
                    <span>重试: {res.get('retries', 0)}</span>
                </div>
            </div>
            {get_screenshot_html(res.get('screenshot'))}
        </div>
        """
        
    html += """
        </div>
        <div class="footer">
            Powered by Rainyun-Qiandao
        </div>
    </div>
    """
    return html


def generate_markdown_report(results):
    """生成 Markdown 签到报告"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    success_count = len([r for r in results if r['status']])
    total_count = len(results)
    
    md = f"> {now_str}\n\n"
    md += f"**状态**: ✅ {success_count} 成功 / ❌ {total_count - success_count} 失败\n\n"
    md += "---\n"
    
    for res in results:
        status_icon = "✅" if res['status'] else "❌"
        md += f"### {status_icon} {res['username']}\n"
        
        if res.get('points'):
            points = res['points']
            money = points / 2000
            md += f"- **积分**: {points} (≈￥{money:.2f})\n"
        
        md += f"- **消息**: {res['msg']}\n"
        if res.get('retries', 0) > 0:
            md += f"- **重试**: {res['retries']}\n"
        md += "\n"
        
    md += "---\n"
    md += "Powered by Rainyun-Qiandao"
    return md


def send_pushplus_notification(token, title, content):
    """发送 PushPlus 通知"""
    import requests
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        logging.info(f"Sending PushPlus notification: {title}")
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get('code') == 200:
            logging.info("PushPlus notification sent successfully")
            return True
        else:
            logging.error(f"PushPlus notification failed: {result.get('msg')}")
            return False
    except Exception as e:
        logging.error(f"Error sending PushPlus notification: {e}")
        return False


def save_screenshot(driver, account_id, status="success", error_msg=""):
    """
    保存签到截图（带压缩）
    :param driver: WebDriver 实例
    :param account_id: 账号标识
    :param status: 截图类型 "success" 或 "failure"
    :param error_msg: 错误信息（仅失败时使用）
    :return: 截图路径或 None
    """
    try:
        # 创建截图目录（使用 temp 目录）
        screenshot_dir = os.path.join("temp", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # 生成截图文件名（类型_账号_时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        masked_account = f"{account_id[:3]}xxx{account_id[-3:] if len(account_id) > 6 else account_id}"
        
        # 先保存原始 PNG 截图
        temp_filepath = os.path.join(screenshot_dir, f"temp_{timestamp}.png")
        driver.save_screenshot(temp_filepath)
        
        # 压缩并转换为 JPEG 格式（大幅减小文件大小）
        compressed_filename = f"{status}_{masked_account}_{timestamp}.jpg"
        compressed_filepath = os.path.join(screenshot_dir, compressed_filename)
        
        original_size = os.path.getsize(temp_filepath)
        compressed_size = compress_screenshot(temp_filepath, compressed_filepath)
        
        # 删除临时 PNG 文件
        try:
            os.remove(temp_filepath)
        except:
            pass
        
        if compressed_size:
            compression_ratio = (1 - compressed_size / original_size) * 100
            status_text = "成功" if status == "success" else "失败"
            logger.info(f"已保存{status_text}截图: {compressed_filepath} (压缩率: {compression_ratio:.1f}%, {original_size/1024:.1f}KB -> {compressed_size/1024:.1f}KB)")
            
            # 清理7天前的旧截图
            cleanup_old_screenshots(screenshot_dir, days=7)
            
            return compressed_filepath
        else:
            # 压缩失败，使用原始文件
            logger.warning("截图压缩失败，使用原始文件")
            return temp_filepath
            
    except Exception as e:
        logger.error(f"保存截图时出错: {e}")
        return None


def compress_screenshot(input_path, output_path, max_width=1280, quality=75):
    """先本地 Pillow 压缩，如果配置了 TinyPNG 则二次压缩"""
    result = compress_with_pillow(input_path, output_path, max_width, quality)
    if not result:
        return None
    
    tinypng_key = os.getenv("TINYPNG_API_KEY", "").strip()
    if tinypng_key:
        tinypng_result = compress_with_tinypng(output_path, output_path, tinypng_key)
        return tinypng_result or result
    
    return result


def compress_with_tinypng(input_path, output_path, api_key):
    """使用 TinyPNG API 压缩（每月免费 500 次，单张最大 5MB）"""
    import requests
    import base64
    
    try:
        if os.path.getsize(input_path) > 5 * 1024 * 1024:
            logger.warning("图片超过 TinyPNG 5MB 限制")
            return None
        
        with open(input_path, "rb") as f:
            image_data = f.read()
        
        auth = base64.b64encode(f"api:{api_key}".encode()).decode()
        resp = requests.post(
            "https://api.tinify.com/shrink",
            headers={"Authorization": f"Basic {auth}"},
            data=image_data,
            timeout=30
        )
        
        if resp.status_code != 201:
            error_map = {401: "API Key 无效", 429: "本月额度已用完"}
            logger.warning(f"TinyPNG: {error_map.get(resp.status_code, resp.status_code)}")
            return None
        
        compressed_url = resp.json().get("output", {}).get("url")
        if not compressed_url:
            return None
        
        img_resp = requests.get(compressed_url, timeout=30)
        if img_resp.status_code != 200:
            return None
        
        with open(output_path, "wb") as f:
            f.write(img_resp.content)
        
        used = resp.headers.get("Compression-Count", "?")
        logger.info(f"TinyPNG 压缩成功 (已用: {used}/500)")
        return os.path.getsize(output_path)
        
    except Exception as e:
        logger.debug(f"TinyPNG 出错: {e}")
        return None


def compress_with_pillow(input_path, output_path, max_width=1280, quality=75):
    """使用 Pillow 本地压缩"""
    try:
        from PIL import Image
        
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            w, h = img.size
            if w > max_width:
                img = img.resize((max_width, int(h * max_width / w)), Image.Resampling.LANCZOS)
            
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        return os.path.getsize(output_path)
    except Exception as e:
        logger.debug(f"Pillow 压缩出错: {e}")
        return None

def cleanup_old_screenshots(screenshot_dir, days=7):
    """清理超过指定天数的截图文件"""
    try:
        now = time.time()
        cutoff = now - (days * 86400)  # 86400秒 = 1天
        
        for filename in os.listdir(screenshot_dir):
            file_path = os.path.join(screenshot_dir, filename)
            # 支持 PNG 和 JPEG 格式
            if os.path.isfile(file_path) and (filename.endswith('.png') or filename.endswith('.jpg')):
                # 匹配 success_ 或 failure_ 开头的截图
                if filename.startswith('success_') or filename.startswith('failure_'):
                    file_time = os.path.getmtime(file_path)
                    if file_time < cutoff:
                        os.remove(file_path)
                        logger.debug(f"已删除过期截图: {filename}")

    except Exception as e:
        logger.debug(f"清理旧截图时出错: {e}")



def parse_accounts():
    """解析多账号配置"""
    usernames = os.getenv("RAINYUN_USERNAME", "").split("|")
    passwords = os.getenv("RAINYUN_PASSWORD", "").split("|")
    
    # 确保用户名和密码数量匹配
    if len(usernames) != len(passwords):
        logger.warning("用户名和密码数量不匹配，只使用匹配的部分")
        min_len = min(len(usernames), len(passwords))
        usernames = usernames[:min_len]
        passwords = passwords[:min_len]
    
    # 过滤空值
    accounts = [(u.strip(), p.strip()) for u, p in zip(usernames, passwords) if u.strip() and p.strip()]
    
    if not accounts:
        # 如果没有多账号配置，使用单账号兼容模式
        single_user = os.getenv("RAINYUN_USERNAME", "username")
        single_pwd = os.getenv("RAINYUN_PASSWORD", "password")
        accounts = [(single_user, single_pwd)]
    
    logger.info(f"检测到 {len(accounts)} 个账号")
    for i, (username, _) in enumerate(accounts, 1):
        masked_user = f"{username[:3]}***{username[-3:] if len(username) > 6 else username}"
        logger.info(f"账号 {i}: {masked_user}")
    
    return accounts


def run_all_accounts():
    """执行所有账号的签到任务"""
    # 任务开始前清理可能的僵尸进程
    logger.info("检查并清理可能的僵尸进程...")
    cleanup_zombie_processes()
    
    # 从环境变量获取最大重试次数，默认为2
    max_retries = int(os.getenv("CHECKIN_MAX_RETRIES", "2"))
    
    accounts = parse_accounts()
    results = {}
    
    # 初始化每个账号的结果
    for i, (username, password) in enumerate(accounts):
        results[username] = {
            'password': password,
            'result': None,
            'retry_count': 0,
            'index': i + 1
        }
    
    # 待执行的账号列表
    pending_accounts = list(accounts)
    current_attempt = 0
    
    while pending_accounts and current_attempt <= max_retries:
        if current_attempt == 0:
            logger.info(f"========== 开始执行签到任务（共 {len(pending_accounts)} 个账号） ==========")
        else:
            logger.info(f"========== 第 {current_attempt} 次重试（共 {len(pending_accounts)} 个失败账号） ==========")
        
        failed_accounts = []
        
        for i, (username, password) in enumerate(pending_accounts, 1):
            account_idx = results[username]['index']
            retry_info = f"（第 {results[username]['retry_count'] + 1} 次尝试）" if results[username]['retry_count'] > 0 else ""
            logger.info(f"========== 执行账号 {account_idx}/{len(accounts)} {retry_info} ==========")
            
            result = run_checkin(username, password)
            results[username]['result'] = result
            
            if result['status']:
                logger.info(f"✅ 账号 {account_idx} 签到成功")
            else:
                logger.error(f"❌ 账号 {account_idx} 签到失败: {result['msg']}")
                results[username]['retry_count'] += 1
                # 还没达到最大重试次数，加入待重试列表
                if results[username]['retry_count'] <= max_retries:
                    failed_accounts.append((username, password))
            
            # 每个账号执行后清理一次
            cleanup_zombie_processes()
            
            # 账号间延时（避免频繁操作）
            if i < len(pending_accounts):
                delay = random.randint(30, 120)  # 30-120秒随机延时
                logger.info(f"账号间延时等待 {delay} 秒...")
                time.sleep(delay)
        
        # 更新待执行列表为失败账号
        pending_accounts = failed_accounts
        current_attempt += 1
        
        # 如果还有待重试的账号，增加重试间隔
        if pending_accounts:
            retry_delay = random.randint(60, 180)  # 重试前等待 1-3 分钟
            logger.info(f"等待 {retry_delay} 秒后开始重试...")
            time.sleep(retry_delay)
    
    # 汇总最终结果
    final_results = [results[username]['result'] for username, _ in accounts]
    success_count = len([r for r in final_results if r and r['status']])
    
    # 统计重试信息
    retry_accounts = [(username, results[username]['retry_count']) for username, _ in accounts if results[username]['retry_count'] > 0]
    if retry_accounts:
        logger.info(f"重试统计: {len(retry_accounts)} 个账号进行了重试")
        for username, count in retry_accounts:
            masked_user = f"{username[:3]}***{username[-3:] if len(username) > 6 else username}"
            final_status = "成功" if results[username]['result'] and results[username]['result']['status'] else "失败"
            logger.info(f"  - {masked_user}: 重试 {count} 次, 最终{final_status}")

    
    # 统计结果并发送通知
    if accounts:
        # 初始化通知管理器
        notification_manager = NotificationManager()
        
        # 注册 PushPlus
        push_token = os.getenv("PUSHPLUS_TOKEN")
        if push_token:
            logger.info("Configuring PushPlus provider...")
            notification_manager.add_provider(PushPlusProvider(push_token))
            
        # 注册 WXPusher
        wx_app_token = os.getenv("WXPUSHER_APP_TOKEN")
        wx_uids = os.getenv("WXPUSHER_UIDS")
        if wx_app_token and wx_uids:
            logger.info("Configuring WXPusher provider...")
            notification_manager.add_provider(WXPusherProvider(wx_app_token, wx_uids))
            
        # 注册 DingTalk
        dingtalk_token = os.getenv("DINGTALK_ACCESS_TOKEN")
        dingtalk_secret = os.getenv("DINGTALK_SECRET")
        if dingtalk_token:
            logger.info("Configuring DingTalk provider...")
            notification_manager.add_provider(DingTalkProvider(dingtalk_token, dingtalk_secret))
            
        # 注册 Email
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        smtp_to = os.getenv("SMTP_TO")
        
        if smtp_host and smtp_port and smtp_user and smtp_pass:
            # 如果没填收件人，默认发给第一个签到账号（如果它是邮箱的话）
            if not smtp_to and accounts:
                first_account = accounts[0][0]
                if '@' in first_account:
                    smtp_to = first_account
                    logger.info(f"配置提示: 未填写 SMTP_TO，将使用第一个雨云账号 ({smtp_to}) 作为收件人")
            
            if smtp_to:
                logger.info("Configuring Email provider...")
                notification_manager.add_provider(EmailProvider(smtp_host, smtp_port, smtp_user, smtp_pass, smtp_to))
            
        # 发送通知
        if notification_manager.providers:
            logger.info("正在生成详细推送报告...")
            html_content = generate_html_report(final_results)
            markdown_content = generate_markdown_report(final_results)
            
            context = {
                'html': html_content,
                'markdown': markdown_content
            }
            
            title = f"雨云签到: {success_count}/{len(accounts)} 成功"
            notification_manager.send_all(title, context)
    
    # 任务结束后再次清理
    logger.info("任务完成，执行最终清理...")
    cleanup_zombie_processes()
    
    return success_count > 0


def init_selenium(account_id: str, proxy: str = None):
    """
    初始化 Selenium WebDriver
    :param account_id: 账号标识，用于生成该账号专属的 User-Agent
    :param proxy: 代理地址，格式为 ip:port，为 None 则不使用代理
    """
    # 导入Selenium模块
    modules = import_selenium_modules()
    webdriver = modules['webdriver']
    Options = modules['Options']
    Service = modules['Service']
    
    ops = Options()
    ops.add_argument("--no-sandbox")
    ops.add_argument("--disable-dev-shm-usage")  # Docker 环境优化
    ops.add_argument("--disable-extensions")
    ops.add_argument("--disable-plugins")
    
    # 配置代理
    if proxy:
        ops.add_argument(f"--proxy-server=http://{proxy}")
        logger.info(f"浏览器已配置代理: {proxy}")
    
    # 添加账号专属 User-Agent（相同账号每次相同）
    user_agent = get_random_user_agent(account_id)
    ops.add_argument(f"--user-agent={user_agent}")
    logger.info(f"使用 User-Agent: {user_agent[:50]}...")  # 只显示前50个字符
    
    # 开启无图模式 (加速加载)
    ops.add_argument('blink-settings=imagesEnabled=false')
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,  # 不禁止加载CSS
    }
    # 仅禁用图片，保留CSS以防元素定位失效
    prefs = {"profile.managed_default_content_settings.images": 2}
    ops.add_experimental_option("prefs", prefs)
    
    if debug:
        ops.add_experimental_option("detach", True)
    
    # 设置窗口大小（避免因窗口太小导致元素重叠或误点击）
    ops.add_argument("--window-size=1920,1080")
    
    if linux:
        ops.add_argument("--headless")
        ops.add_argument("--disable-gpu")

        # 检测 ChromeDriver 路径
        # Docker (Selenium镜像) 使用固定路径
        # GitHub Actions 等环境使用 Selenium Manager 自动管理
        chromedriver_path = "/usr/bin/chromedriver"
        
        if os.path.exists(chromedriver_path):
            # Docker 环境：使用固定路径
            logger.info(f"使用 Docker 镜像的 ChromeDriver: {chromedriver_path}")
            service = Service(chromedriver_path)
        else:
            # GitHub Actions 等环境：使用 Selenium Manager 自动管理
            logger.info("使用 Selenium Manager 自动管理 ChromeDriver")
            service = Service()
        
        return webdriver.Chrome(service=service, options=ops)
    else:
        # Windows 环境
        # 使用 Selenium Manager 自动处理驱动下载和路径匹配
        service = Service()
        return webdriver.Chrome(service=service, options=ops)


def download_image(url, filename, user_agent=None):
    # 延迟导入requests模块
    import requests
    
    os.makedirs("temp", exist_ok=True)
    
    headers = {}
    if user_agent:
        headers['User-Agent'] = user_agent
        
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            path = os.path.join("temp", filename)
            with open(path, "wb") as f:
                f.write(response.content)
            return True
        else:
            logger.error(f"下载图片失败！状态码: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"下载图片异常: {e}")
        return False


def get_url_from_style(style):
    import re
    return re.search(r'url\(["\']?(.*?)["\']?\)', style).group(1)


def get_width_from_style(style):
    import re
    return re.search(r'width:\s*([\d.]+)px', style).group(1)


def get_height_from_style(style):
    import re
    return re.search(r'height:\s*([\d.]+)px', style).group(1)


def process_captcha(driver, timeout, retry_stats=None):
    """处理验证码（延迟加载OCR模型）"""
    # 导入Selenium模块
    modules = import_selenium_modules()
    WebDriverWait = modules['WebDriverWait']
    EC = modules['EC']
    By = modules['By']
    ActionChains = modules['ActionChains']
    TimeoutException = modules['TimeoutException']
    
    if retry_stats is None:
        retry_stats = {'count': 0}
    
    try:
        wait = WebDriverWait(driver, min(timeout, 3))
        try:
            wait.until(EC.presence_of_element_located((By.ID, "slideBg")))
        except TimeoutException:
            logger.info("未检测到可处理验证码内容，跳过验证码处理")
            return

        # 延迟导入，只在需要时加载
        import cv2
        import ddddocr

        logger.info("初始化ddddocr")
        ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
        det = ddddocr.DdddOcr(det=True, show_ad=False)
        
        wait = WebDriverWait(driver, timeout)
        download_captcha_img(driver, timeout)
        if check_captcha(ocr):
            logger.info("开始识别验证码")
            captcha = cv2.imread("temp/captcha.jpg")
            with open("temp/captcha.jpg", 'rb') as f:
                captcha_b = f.read()
            bboxes = det.detection(captcha_b)
            result = dict()
            for i in range(len(bboxes)):
                x1, y1, x2, y2 = bboxes[i]
                spec = captcha[y1:y2, x1:x2]
                cv2.imwrite(f"temp/spec_{i + 1}.jpg", spec)
                for j in range(3):
                    similarity, matched = compute_similarity(f"temp/sprite_{j + 1}.jpg", f"temp/spec_{i + 1}.jpg")
                    similarity_key = f"sprite_{j + 1}.similarity"
                    position_key = f"sprite_{j + 1}.position"
                    if similarity_key in result.keys():
                        if float(result[similarity_key]) < similarity:
                            result[similarity_key] = similarity
                            result[position_key] = f"{int((x1 + x2) / 2)},{int((y1 + y2) / 2)}"
                    else:
                        result[similarity_key] = similarity
                        result[position_key] = f"{int((x1 + x2) / 2)},{int((y1 + y2) / 2)}"
            if check_answer(result):
                for i in range(3):
                    similarity_key = f"sprite_{i + 1}.similarity"
                    position_key = f"sprite_{i + 1}.position"
                    positon = result[position_key]
                    logger.info(f"图案 {i + 1} 位于 ({positon})，匹配率：{result[similarity_key]}")
                    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
                    style = slideBg.get_attribute("style")
                    x, y = int(positon.split(",")[0]), int(positon.split(",")[1])
                    width_raw, height_raw = captcha.shape[1], captcha.shape[0]
                    width, height = float(get_width_from_style(style)), float(get_height_from_style(style))
                    x_offset, y_offset = float(-width / 2), float(-height / 2)
                    final_x, final_y = int(x_offset + x / width_raw * width), int(y_offset + y / height_raw * height)
                    ActionChains(driver).move_to_element_with_offset(slideBg, final_x, final_y).click().perform()
                confirm = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="tcStatus"]/div[2]/div[2]/div/div')))
                logger.info("提交验证码")
                confirm.click()
                time.sleep(5)
                result = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="tcOperation"]')))
                if result.get_attribute("class") == 'tc-opera pointer show-success':
                    logger.info("验证码通过")
                    return
                else:
                    logger.error("验证码未通过，正在重试")
                    retry_stats['count'] += 1
            else:
                logger.error("验证码识别失败，正在重试")
                retry_stats['count'] += 1
        else:
            logger.error("当前验证码识别率低，尝试刷新")
            retry_stats['count'] += 1
        
        reload = driver.find_element(By.XPATH, '//*[@id="reload"]')
        time.sleep(5)
        reload.click()
        time.sleep(5)
        process_captcha(driver, timeout, retry_stats)
    except TimeoutException:
        logger.error("获取验证码图片失败")
    finally:
        # 函数结束后，OCR模型会自动释放内存
        logger.debug("验证码处理完成，OCR 模型将被释放")


def download_captcha_img(driver, timeout):
    # 导入Selenium模块
    modules = import_selenium_modules()
    WebDriverWait = modules['WebDriverWait']
    EC = modules['EC']
    By = modules['By']
    
    wait = WebDriverWait(driver, timeout)
    if os.path.exists("temp"):
        for filename in os.listdir("temp"):
            file_path = os.path.join("temp", filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
                
    # 获取当前浏览器的 User-Agent
    try:
        current_ua = driver.execute_script("return navigator.userAgent;")
        logger.debug(f"下载图片使用 UA: {current_ua[:50]}...")
    except Exception:
        current_ua = None
        
    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
    img1_style = slideBg.get_attribute("style")
    img1_url = get_url_from_style(img1_style)
    logger.info("开始下载验证码图片(1): " + img1_url)
    download_image(img1_url, "captcha.jpg", user_agent=current_ua)
    
    sprite = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="instruction"]/div/img')))
    img2_url = sprite.get_attribute("src")
    logger.info("开始下载验证码图片(2): " + img2_url)
    download_image(img2_url, "sprite.jpg", user_agent=current_ua)


def check_captcha(ocr) -> bool:
    """检查验证码图片质量（延迟导入cv2）"""
    import cv2
    
    raw = cv2.imread("temp/sprite.jpg")
    for i in range(3):
        w = raw.shape[1]
        temp = raw[:, w // 3 * i: w // 3 * (i + 1)]
        cv2.imwrite(f"temp/sprite_{i + 1}.jpg", temp)
        with open(f"temp/sprite_{i + 1}.jpg", mode="rb") as f:
            temp_rb = f.read()
        if ocr.classification(temp_rb) in ["0", "1"]:
            return False
    return True


# 检查是否存在重复坐标，快速判断识别错误
def check_answer(d: dict) -> bool:
    flipped = dict()
    for key in d.keys():
        flipped[d[key]] = key
    return len(d.values()) == len(flipped.keys())


def compute_similarity(img1_path, img2_path):
    """计算图片相似度（延迟导入cv2）"""
    import cv2
    
    img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    if des1 is None or des2 is None:
        return 0.0, 0

    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des1, des2, k=2)

    good = [m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.8 * n.distance]

    if len(good) == 0:
        return 0.0, 0

    similarity = len(good) / len(matches)
    return similarity, len(good)


def dismiss_modal_confirm(driver, timeout):
    modules = import_selenium_modules()
    WebDriverWait = modules['WebDriverWait']
    EC = modules['EC']
    By = modules['By']
    TimeoutException = modules['TimeoutException']

    wait = WebDriverWait(driver, min(timeout, 5))
    try:
        confirm = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//footer[contains(@id,'modal') and contains(@id,'footer')]//button[contains(normalize-space(.), '确认')]")
            )
        )
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm)
        except Exception:
            pass
        time.sleep(0.2)
        confirm.click()
        logger.info("已关闭弹窗：确认")
        time.sleep(0.5)
        return True
    except TimeoutException:
        return False
    except Exception:
        try:
            confirm = driver.find_element(By.XPATH, "//button[contains(normalize-space(.), '确认') and contains(@class,'btn')]")
            driver.execute_script("arguments[0].click();", confirm)
            logger.info("已关闭弹窗：确认")
            time.sleep(0.5)
            return True
        except Exception:
            return False


def wait_captcha_or_modal(driver, timeout):
    modules = import_selenium_modules()
    WebDriverWait = modules['WebDriverWait']
    EC = modules['EC']
    By = modules['By']
    TimeoutException = modules['TimeoutException']

    def find_visible_tcaptcha_iframe():
        try:
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[id^='tcaptcha_iframe']")
        except Exception:
            return None
        for fr in iframes:
            try:
                if fr.is_displayed() and fr.size.get("width", 0) > 0 and fr.size.get("height", 0) > 0:
                    return fr
            except Exception:
                continue
        return None

    end_time = time.time() + min(timeout, 8)
    while time.time() < end_time:
        if dismiss_modal_confirm(driver, timeout):
            return "modal"
        try:
            iframe = find_visible_tcaptcha_iframe()
            if iframe:
                return "captcha"
        except Exception:
            pass
        time.sleep(0.3)
    return "none"


def save_cookies(driver, account_id):
    """保存当前账号的 Cookie 到本地文件"""
    import json
    import hashlib
    
    if not account_id:
        return
        
    os.makedirs("temp/cookies", exist_ok=True)
    # 使用账号 Hash 作为文件名，避免特殊字符问题
    account_hash = hashlib.md5(account_id.encode()).hexdigest()[:16]
    cookie_path = os.path.join("temp", "cookies", f"{account_hash}.json")
    
    try:
        cookies = driver.get_cookies()
        with open(cookie_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False)
        logger.info(f"Cookie 已保存到本地")
    except Exception as e:
        logger.warning(f"保存 Cookie 失败: {e}")


def load_cookies(driver, account_id):
    """加载账号 Cookie 到浏览器，返回是否成功加载"""
    import json
    import hashlib
    
    if not account_id:
        return False
        
    account_hash = hashlib.md5(account_id.encode()).hexdigest()[:16]
    cookie_path = os.path.join("temp", "cookies", f"{account_hash}.json")
    
    if not os.path.exists(cookie_path):
        logger.info("未找到本地 Cookie，将使用账号密码登录")
        return False
        
    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            
        # 必须先访问域名才能设置 Cookie
        driver.get("https://app.rainyun.com/")
        time.sleep(1)
        
        for cookie in cookies:
            # 处理 expiry 字段（某些 Selenium 版本要求为整型）
            if 'expiry' in cookie:
                cookie['expiry'] = int(cookie['expiry'])
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass  # 忽略单个 cookie 添加失败
                
        logger.info(f"已加载本地 Cookie")
        return True
    except Exception as e:
        logger.warning(f"加载 Cookie 失败: {e}")
        return False


def run_checkin(account_user=None, account_pwd=None):
    """执行签到任务"""
    # 导入Selenium模块
    modules = import_selenium_modules()
    webdriver = modules['webdriver']
    ActionChains = modules['ActionChains']
    Options = modules['Options']
    Service = modules['Service']
    WebDriver = modules['WebDriver']
    By = modules['By']
    EC = modules['EC']
    WebDriverWait = modules['WebDriverWait']
    TimeoutException = modules['TimeoutException']
    import subprocess
    
    current_user = account_user or user
    current_pwd = account_pwd or pwd
    driver = None  # 初始化为 None，确保在任何情况下都能安全清理
    retry_stats = {'count': 0}
    
    try:
        logger.info(f"开始执行签到任务... 账号: {current_user[:5]}***{current_user[-5:] if len(current_user) > 10 else current_user}")
        
        # 随机延时
        delay = random.randint(0, max_delay)
        delay_sec = random.randint(0, 60)
        if not debug:
            logger.info(f"随机延时等待 {delay} 分钟 {delay_sec} 秒")
            time.sleep(delay * 60 + delay_sec)
        
        # 获取代理IP（每个账号单独获取）
        proxy = None
        proxy_api_url = os.getenv("PROXY_API_URL", "").strip()
        if proxy_api_url:
            proxy = get_proxy_ip()
            if proxy:
                # 验证代理可用性
                if validate_proxy(proxy):
                    logger.info(f"代理 {proxy} 验证通过，将使用此代理")
                else:
                    logger.warning(f"代理 {proxy} 验证失败，将使用本地IP继续")
                    proxy = None
            else:
                logger.warning("获取代理失败，将使用本地IP继续")
        
        logger.info("初始化 Selenium（账号专属配置）")
        driver = init_selenium(current_user, proxy=proxy)
        
        # 过 Selenium 检测
        with open("stealth.min.js", mode="r") as f:
            js = f.read()
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": js
        })
        
        # 注入浏览器指纹随机化脚本（基于账号生成确定性指纹）
        fingerprint_js = generate_fingerprint_script(current_user)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": fingerprint_js
        })
        logger.info("已注入浏览器指纹脚本（账号专属指纹）")
        
        wait = WebDriverWait(driver, timeout)
        
        # 加载 Cookie 并直接跳转积分页
        load_cookies(driver, current_user)
        logger.info("正在跳转积分页...")
        driver.get("https://app.rainyun.com/account/reward/earn")
        time.sleep(3)
        
        # 检查是否需要密码登录
        if "/auth/login" in driver.current_url:
            logger.info("Cookie 已失效，使用账号密码登录")
            
            try:
                username = wait.until(EC.visibility_of_element_located((By.NAME, 'login-field')))
                password = wait.until(EC.visibility_of_element_located((By.NAME, 'login-password')))
                login_button = wait.until(EC.visibility_of_element_located((By.XPATH,
                    '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
                username.send_keys(current_user)
                password.send_keys(current_pwd)
                login_button.click()
            except TimeoutException:
                logger.error("页面加载超时")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': '页面加载超时', 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path
                }
            
            # 处理登录验证码
            try:
                login_captcha = wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_iframe_dy')))
                logger.warning("触发验证码！")
                driver.switch_to.frame("tcaptcha_iframe_dy")
                process_captcha(driver, timeout, retry_stats)
            except TimeoutException:
                logger.info("未触发验证码")
            
            time.sleep(5)
            driver.switch_to.default_content()
            dismiss_modal_confirm(driver, timeout)
            
            # 验证登录结果
            if "/dashboard" in driver.current_url or "/account" in driver.current_url:
                logger.info("登录成功！")
                save_cookies(driver, current_user)
                # 跳转到积分页
                driver.get("https://app.rainyun.com/account/reward/earn")
                time.sleep(2)
            else:
                logger.error(f"登录失败，当前页面: {driver.current_url}")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': '登录失败', 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path
                }
        else:
            logger.info("Cookie 有效，免密登录成功！🎉")
        
        # 确保在积分页
        if "/account/reward/earn" not in driver.current_url:
            driver.get("https://app.rainyun.com/account/reward/earn")

        driver.implicitly_wait(5)
        time.sleep(1)
        dismiss_modal_confirm(driver, timeout)
        dismiss_modal_confirm(driver, timeout)
        
        earn = driver.find_element(By.XPATH,
                                   '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a')
        btn_text = earn.text.strip()
        logger.info(f"签到按钮文字: [{btn_text}]")
        
        # 只有"领取奖励"才需要点击，其他情况视为已完成
        if btn_text == "领取奖励":
            logger.info("点击领取奖励")
            earn.click()
            state = wait_captcha_or_modal(driver, timeout)
            if state == "captcha":
                logger.info("处理验证码")
                try:
                    captcha_iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[id^='tcaptcha_iframe']")))
                    driver.switch_to.frame(captcha_iframe)
                    process_captcha(driver, timeout, retry_stats)
                finally:
                    driver.switch_to.default_content()
                driver.implicitly_wait(5)
            else:
                logger.info("未触发验证码")
        else:
            logger.info(f"今日已签到（按钮显示: {btn_text}）")

        
        points_raw = driver.find_element(By.XPATH,
                                         '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute(
            "textContent")
        import re
        current_points = int(''.join(re.findall(r'\d+', points_raw)))
        logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
        logger.info("签到任务执行成功！")
        # 保存成功截图
        screenshot_path = save_screenshot(driver, current_user, status="success")
        return {
            'status': True,
            'msg': '签到成功',
            'points': current_points,
            'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
            'retries': retry_stats['count'],
            'screenshot': screenshot_path
        }
            
    except Exception as e:
        logger.error(f"签到任务执行失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        # 保存失败截图
        screenshot_path = None
        if driver is not None:
            screenshot_path = save_screenshot(driver, current_user, status="failure")
        return {
            'status': False,
            'msg': f'执行异常: {str(e)[:50]}...',
            'points': 0,
            'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
            'retries': retry_stats['count'],
            'screenshot': screenshot_path
        }
    finally:
        # 确保在任何情况下都关闭 WebDriver
        if driver is not None:
            try:
                logger.info("正在关闭 WebDriver...")
                
                # 首先尝试正常关闭
                try:
                    driver.quit()
                    logger.info("WebDriver 已安全关闭")
                except Exception as e:
                    logger.error(f"关闭 WebDriver 时出错: {e}")
                
                # 等待一小段时间让进程完全退出
                time.sleep(1)
                
                # 强制终止 ChromeDriver 进程及其子进程
                try:
                    if hasattr(driver, 'service') and driver.service.process:
                        process = driver.service.process
                        if process.poll() is None:  # 进程仍在运行
                            # 终止进程
                            process.terminate()
                            try:
                                # 等待最多2秒
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                # 如果还没退出，强制kill
                                process.kill()
                                process.wait()
                            logger.info("已终止 ChromeDriver 进程")
                except Exception as e:
                    logger.debug(f"清理 ChromeDriver 进程时出错: {e}")
                
                # 额外保险：清理可能残留的Chrome进程
                if os.name == 'posix':
                    try:
                        subprocess.run(['pkill', '-9', '-f', 'chrome.*--test-type'], 
                                     timeout=3, stderr=subprocess.DEVNULL)
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"WebDriver 清理过程出现异常: {e}")
        
        # 卸载Selenium模块，释放内存
        try:
            unload_selenium_modules()
            logger.debug("已卸载Selenium模块")
        except:
            pass


def scheduled_checkin():
    """定时任务包装器"""
    logger.info(f"定时任务触发 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    success = run_all_accounts()
    
    if success:
        logger.info("定时签到任务执行成功！")
    else:
        logger.error("定时签到任务执行失败！")
    
    # 显示下次执行时间
    logger.info("定时任务完成，查看下次执行安排...")
    time.sleep(1)  # 给schedule时间更新
    
    # 手动计算下次执行时间，确保是未来时间
    schedule_time = os.getenv("SCHEDULE_TIME", "08:00")
    current_time = datetime.now()
    next_run = current_time.replace(
        hour=int(schedule_time.split(':')[0]), 
        minute=int(schedule_time.split(':')[1]), 
        second=0, 
        microsecond=0
    )
    
    # 如果计算出的时间已经过去，则推到下一天
    if next_run <= current_time:
        next_run += timedelta(days=1)
    
    logger.info(f"✅ 程序继续运行，下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    time_diff = next_run - current_time
    hours, remainder = divmod(time_diff.total_seconds(), 3600)
    minutes, _ = divmod(remainder, 60)
    logger.info(f"距离下次执行还有: {int(hours)}小时{int(minutes)}分钟")
    
    return success


if __name__ == "__main__":
    # 配置参数
    timeout = int(os.getenv("TIMEOUT", "15000")) // 1000  # 转换为秒
    max_delay = int(os.getenv("MAX_DELAY", "5"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    linux = os.getenv("LINUX_MODE", "true").lower() == "true" or os.path.exists("/.dockerenv")
    
    # 兼容性变量（供单账号模式使用）
    user = os.getenv("RAINYUN_USERNAME", "username").split("|")[0]
    pwd = os.getenv("RAINYUN_PASSWORD", "password").split("|")[0]
    
    # 运行模式（once: 运行一次, schedule: 定时运行）
    run_mode = os.getenv("RUN_MODE", "schedule")
    # 定时执行时间（默认早上8点）
    schedule_time = os.getenv("SCHEDULE_TIME", "08:00")

    # 初始化日志（使用新的日志轮转功能）
    logger = setup_logging()
    ver = "2.2-docker-notify-plus"
    logger.info("------------------------------------------------------------------")
    logger.info(f"雨云签到工具 v{ver} by LeapYa ~")
    logger.info("Github发布页: https://github.com/LeapYa/Rainyun-Qiandao")
    logger.info("------------------------------------------------------------------")
    logger.info("已启用日志轮转功能，将自动清理7天前的日志")
    if debug:
        logger.info(f"当前配置: MAX_DELAY={max_delay}分钟, TIMEOUT={timeout}秒")

    
    # 程序启动时执行日志清理
    cleanup_logs_on_startup()
    
    # 设置子进程自动回收机制（必须在启动任何子进程之前）
    setup_sigchld_handler()
    
    # 程序启动时清理可能残留的僵尸进程
    logger.info("程序启动，检查系统中的僵尸进程...")
    cleanup_zombie_processes()
    
    if run_mode == "schedule":
        # 定时模式
        logger.info(f"启动定时模式，每天 {schedule_time} 自动执行签到")
        logger.info("程序将持续运行，按 Ctrl+C 退出")
        
        # 设置每日定时任务
        schedule.every().day.at(schedule_time).do(scheduled_checkin)
        
        # 显示每日定时任务时间
        tomorrow_schedule = datetime.now().replace(hour=int(schedule_time.split(':')[0]), 
                                                  minute=int(schedule_time.split(':')[1]), 
                                                  second=0, microsecond=0)
        if tomorrow_schedule <= datetime.now():
            tomorrow_schedule += timedelta(days=1)
        logger.info(f"每日执行时间: {tomorrow_schedule.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 首次启动1分钟后执行一次
        logger.info("首次启动，将在1分钟后执行首次签到任务")
        first_run_time = datetime.now() + timedelta(minutes=1)
        logger.info(f"首次执行时间: {first_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 持续运行检查定时任务
        logger.info("调度器已启动，等待执行任务...")
        first_run_done = False
        
        try:
            while True:
                current_time = datetime.now()
                
                # 检查是否到了首次执行时间
                if not first_run_done and current_time >= first_run_time:
                    logger.info("执行首次签到任务（所有账号）")
                    success = run_all_accounts()
                    if success:
                        logger.info("首次签到任务执行成功！")
                    else:
                        logger.error("首次签到任务执行失败！")
                    
                    # 显示下次执行时间
                    logger.info("首次任务完成，查看下次执行安排...")
                    logger.info(f"✅ 程序将继续运行，下次执行时间: {tomorrow_schedule.strftime('%Y-%m-%d %H:%M:%S')}")
                    time_diff = tomorrow_schedule - datetime.now()
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    logger.info(f"距离下次执行还有: {int(hours)}小时{int(minutes)}分钟")
                    
                    first_run_done = True  # 标记首次任务已完成
                
                # 检查每日定时任务
                schedule.run_pending()
                time.sleep(30)  # 每30秒检查一次
                
        except KeyboardInterrupt:
            logger.info("程序已停止")
    else:
        # 单次运行模式
        logger.info("运行模式: 单次执行（所有账号）")
        success = run_all_accounts()
        if success:
            logger.info("程序执行完成")
        else:
            logger.error("程序执行失败")