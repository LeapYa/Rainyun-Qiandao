import logging
import logging.handlers
import os
import random
import time
import schedule
import sys
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Shanghai"


def get_app_timezone_name():
    """获取应用时区，默认使用上海时区。"""
    return (os.getenv("TZ", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE).strip()


def get_app_timezone():
    """返回应用使用的时区对象。"""
    tz_name = get_app_timezone_name()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning(f"未找到时区 '{tz_name}'，回退为 {DEFAULT_TIMEZONE}")
        return timezone(timedelta(hours=8), name=DEFAULT_TIMEZONE)


APP_TIMEZONE = get_app_timezone()


def now_local():
    """返回应用时区下的当前时间。"""
    return datetime.now(APP_TIMEZONE)


def configure_process_timezone():
    """尽量让日志、time.localtime 等也使用应用时区。"""
    tz_name = get_app_timezone_name()
    os.environ["TZ"] = tz_name
    if hasattr(time, "tzset"):
        try:
            time.tzset()
        except Exception as exc:
            logger.warning(f"设置进程时区失败: {exc}")


def apply_browser_timezone(driver):
    """强制浏览器内 JS 时间环境使用应用时区。"""
    tz_name = get_app_timezone_name()
    try:
        driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {
            "timezoneId": tz_name
        })
        logger.info(f"浏览器时区已设置为: {tz_name}")
    except Exception as exc:
        logger.warning(f"设置浏览器时区失败: {exc}")

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
        from selenium.common.exceptions import WebDriverException
        
        selenium_modules = {
            'webdriver': webdriver,
            'ActionChains': ActionChains,
            'Options': Options,
            'Service': Service,
            'WebDriver': WebDriver,
            'By': By,
            'EC': EC,
            'WebDriverWait': WebDriverWait,
            'TimeoutException': TimeoutException,
            'WebDriverException': WebDriverException
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
    configure_process_timezone()

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
    MAX_BYTES = 0          # 0 = 无限制，子类覆盖
    CONTENT_KEYS = []      # 降级优先级，子类覆盖

    def send(self, title, context):
        """
        发送通知
        :param title: 标题
        :param context: 内容上下文，包含多级内容版本
        """
        raise NotImplementedError

    def select_content(self, context, max_bytes_override=None):
        """
        按降级链选择不超限的内容版本
        :param context: 包含多级内容的字典
        :param max_bytes_override: 覆盖默认的 MAX_BYTES 限制
        :return: 选中的内容字符串
        """
        limit = max_bytes_override if max_bytes_override is not None else self.MAX_BYTES

        for key in self.CONTENT_KEYS:
            content = context.get(key, '')
            if not content:
                continue
            byte_size = len(content.encode('utf-8'))
            if limit == 0 or byte_size <= limit:
                if key != self.CONTENT_KEYS[0]:
                    logging.info(f"{self.__class__.__name__}: 内容降级到 {key} ({byte_size} bytes)")
                return content

        # 全部超限：用最后一个（summary）并安全截断
        last_key = self.CONTENT_KEYS[-1] if self.CONTENT_KEYS else ''
        last_content = context.get(last_key, '')
        if last_content and limit > 0:
            logging.warning(f"{self.__class__.__name__}: 所有内容版本均超限，执行安全截断")
            return self._safe_truncate(last_content, limit)
        return last_content

    @staticmethod
    def _safe_truncate(content, max_bytes):
        """
        安全截断内容，避免截坏 UTF-8 多字节字符
        :param content: 要截断的字符串
        :param max_bytes: 最大字节数
        :return: 截断后的字符串
        """
        encoded = content.encode('utf-8')
        if len(encoded) <= max_bytes:
            return content
        # 预留空间给截断提示
        suffix = '\n\n... [内容已截断]'
        suffix_bytes = len(suffix.encode('utf-8'))
        truncated = encoded[:max_bytes - suffix_bytes]
        # 确保不截断在 UTF-8 多字节字符中间
        return truncated.decode('utf-8', errors='ignore') + suffix

class PushPlusProvider(NotificationProvider):
    """PushPlus 推送渠道"""
    MAX_BYTES = 90_000     # 10 万字会员限额（预留 10% 安全余量）
    FALLBACK_MAX_BYTES = 18_000  # 2 万字实名限额（预留 10% 安全余量）
    CONTENT_KEYS = ['html_full', 'html_lite', 'summary_html']

    def __init__(self, token):
        self.token = token

    def send(self, title, context):
        import requests
        url = 'http://www.pushplus.plus/send'

        # 第一轮：按会员限额（10 万字）选择内容
        content = self.select_content(context)
        success = self._do_send(requests, url, title, content)

        if not success:
            # 第二轮：降级到实名限额（2 万字）重试
            logging.info("PushPlus: 推送失败，降级到实名用户限额 (2万字) 重试")
            content = self.select_content(context, max_bytes_override=self.FALLBACK_MAX_BYTES)
            success = self._do_send(requests, url, title, content)

        return success

    def _do_send(self, requests, url, title, content):
        """执行实际的推送请求"""
        data = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": "html"
        }
        try:
            logging.info(f"Sending PushPlus notification: {title} ({len(content.encode('utf-8'))} bytes)")
            response = requests.post(url, json=data, timeout=30)
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
    MAX_BYTES = 36_000     # 4 万字限额（预留 10% 安全余量）
    CONTENT_KEYS = ['html_full', 'html_lite', 'summary_html']

    def __init__(self, app_token, uids=None, topic_ids=None):
        self.app_token = app_token
        # 处理 UIDs
        if uids:
            self.uids = uids if isinstance(uids, list) else [uid.strip() for uid in str(uids).split(',') if uid.strip()]
        else:
            self.uids = []
            
        # 处理 Topic IDs
        if topic_ids:
            self.topic_ids = topic_ids if isinstance(topic_ids, list) else [tid.strip() for tid in str(topic_ids).split(',') if tid.strip()]
        else:
            self.topic_ids = []

    def send(self, title, context):
        import requests
        content = self.select_content(context)
        url = 'https://wxpusher.zjiecode.com/api/send/message'
        data = {
            "appToken": self.app_token,
            "content": content,
            "summary": title,
            "contentType": 2,  # 1=Text, 2=HTML
            "uids": self.uids,
            "topicIds": self.topic_ids
        }
        try:
            target_desc = f"UIDs: {len(self.uids)}" if self.uids else ""
            if self.topic_ids:
                target_desc += (" & " if target_desc else "") + f"Topics: {len(self.topic_ids)}"
                
            logging.info(f"Sending WXPusher notification to {target_desc}: {title} ({len(content.encode('utf-8'))} bytes)")
            response = requests.post(url, json=data, timeout=30)
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
    MAX_BYTES = 18_000     # ~2 万字限额（预留 10% 安全余量）
    CONTENT_KEYS = ['markdown_full', 'markdown_lite', 'summary_markdown']

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
        
        content = self.select_content(context)
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
            logging.info(f"Sending DingTalk notification: {title} ({len(md_text.encode('utf-8'))} bytes)")
            response = requests.post(url, params=params, json=data, timeout=30)
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
    MAX_BYTES = 0  # 无限制
    CONTENT_KEYS = ['html_email', 'html_full']

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
        
        content = self.select_content(context)
        
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


# 雨云拦截探测结果缓存（避免重试时反复吃 8s timeout）
# 拦截通常持续较久，缓存命中可让重试跳过重复探测；未拦截时不缓存，让重试有机会重新探测
_blocked_cache = {'blocked': None, 'expire_at': 0}
_BLOCKED_CACHE_TTL = 300  # 5 分钟


def check_rainyun_blocked(timeout=8):
    """
    检测当前网络环境是否被雨云拦截（海外 IP 无法访问 app.rainyun.com）。
    直连请求 app.rainyun.com，连接失败或超时则认为被拦截。
    被拦截的结果缓存 5 分钟（拦截通常持续较久，避免重试时反复吃 8s timeout）；
    未拦截的结果不缓存（让重试有机会重新探测，应对拦截恢复后切回直连）。
    :param timeout: 请求超时时间（秒）
    :return: True 表示被拦截（需要代理），False 表示可直连
    """
    import time as _time
    # 命中缓存：被拦截且未过期，直接返回，跳过 8s timeout 探测
    if _blocked_cache['blocked'] is True and _time.time() < _blocked_cache['expire_at']:
        logger.debug("雨云拦截探测命中缓存（被拦截），跳过重复探测")
        return True

    import requests
    try:
        resp = requests.get("https://app.rainyun.com/", timeout=timeout, allow_redirects=False)
        if resp.status_code in (200, 301, 302):
            return False
        logger.warning(f"直连 app.rainyun.com 返回异常状态码 {resp.status_code}，疑似被拦截")
        _blocked_cache['blocked'] = True
        _blocked_cache['expire_at'] = _time.time() + _BLOCKED_CACHE_TTL
        return True
    except (requests.ConnectionError, requests.Timeout, requests.exceptions.SSLError) as e:
        # 连接被拒/超时/SSL握手失败是拦截的可靠信号
        logger.warning(f"直连 app.rainyun.com 连接失败，疑似海外 IP 被拦截: {e}")
        _blocked_cache['blocked'] = True
        _blocked_cache['expire_at'] = _time.time() + _BLOCKED_CACHE_TTL
        return True
    except Exception as e:
        # 其他异常（DNS 抖动、临时网络毛刺、库内部错误等）不能可靠判断为拦截，
        # 按"未被拦截"处理走直连，避免偶发网络问题误触发慢代理分支
        logger.warning(f"直连 app.rainyun.com 探测时发生非连接类异常，按未拦截处理（走直连）: {e}")
        return False


def validate_proxy(proxy, timeout=5, max_response_time=3):
    """
    测试代理是否可用且响应足够快。
    仅能连通不够——浏览器会话需要加载多个资源，慢代理会导致页面加载不完整、
    Cookie 无法正确送达服务器，进而被误判为"Cookie 失效"。
    :param proxy: 代理地址，格式为 ip:port
    :param timeout: 请求超时时间（秒）
    :param max_response_time: 最大允许响应时间（秒），超过则认为代理过慢
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

        # 使用 app.rainyun.com 测试代理连通性（这是实际被海外 IP 拦截的目标域名）
        logger.info(f"正在验证代理 {proxy} 的可用性...")
        start_time = time.time()
        response = requests.get(
            "https://app.rainyun.com/",
            proxies=test_proxies,
            timeout=timeout
        )
        elapsed = time.time() - start_time

        if response.status_code == 200:
            if elapsed > max_response_time:
                logger.warning(f"代理 {proxy} 响应过慢（{elapsed:.1f}s > {max_response_time}s），放弃使用")
                return False
            logger.info(f"代理 {proxy} 验证成功（响应时间 {elapsed:.1f}s）")
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


# ---- 轻量级免费代理抓取（自建，无第三方依赖）----
# 替代改进版 freeproxy：5 个国内代理源并发抓取 + 探针验证找到即停，
# 避免 pip install git+https 从 GitHub 拉取依赖时受 DNS 污染影响。

_RANDOM_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


def _proxy_scraper_headers(referer=None):
    """构造反反爬 headers：随机 UA + 随机 X-Forwarded-For 公网 IP。"""
    headers = {
        "User-Agent": random.choice(_RANDOM_UA_POOL),
        "X-Forwarded-For": ".".join(str(random.randint(1, 254)) for _ in range(4)),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _extract_ip_port(text):
    """从任意文本（纯文本/HTML/JSON）中提取所有合法的 ip:port 字符串。"""
    import re
    _OCTET = r'(?:25[0-5]|2[0-4]\d|1?\d?\d)'
    # 前后加数字边界断言，避免从 999.1.1.1:80 中误提取 99.1.1.1:80
    pattern = rf'(?<!\d)((?:{_OCTET}\.){{3}}{_OCTET}):(\d{{2,5}})(?!\d)'
    return {
        f"{ip}:{port}"
        for ip, port in re.findall(pattern, text)
        if 1 <= int(port) <= 65535
    }


def _scrape_ip89():
    """89IP：国内纯文本 API，单次返回约 200 个代理。"""
    import requests
    resp = requests.get(
        "https://api.89ip.cn/tqdl.html",
        params={"api": "1", "num": "200", "port": "", "address": "", "isp": ""},
        headers=_proxy_scraper_headers(), timeout=10,
    )
    resp.raise_for_status()
    return _extract_ip_port(resp.text)


def _scrape_kuaidaili():
    """快代理：HTML 页面（HTTP 高匿），正则提取 ip:port。"""
    import requests
    headers = _proxy_scraper_headers(referer="https://www.kuaidaili.com/free/")
    result = set()
    for page in range(1, 3):
        try:
            resp = requests.get(
                f"https://www.kuaidaili.com/free/inha/{page}/",
                headers=headers, timeout=10,
            )
            resp.raise_for_status()
            result |= _extract_ip_port(resp.text)
        except Exception:
            continue
    return result


def _scrape_kxdaili():
    """开心代理：HTML 页面（高匿），正则提取 ip:port。"""
    import requests
    headers = _proxy_scraper_headers(referer="http://www.kxdaili.com/dailiip.html")
    result = set()
    for page in range(1, 3):
        try:
            resp = requests.get(
                f"http://www.kxdaili.com/dailiip/1/{page}.html",
                headers=headers, timeout=10,
            )
            resp.raise_for_status()
            result |= _extract_ip_port(resp.text)
        except Exception:
            continue
    return result


def _scrape_qiyunip():
    """齐云IP：HTML 页面，正则提取 ip:port。"""
    import requests
    result = set()
    for page in range(1, 3):
        try:
            resp = requests.get(
                f"https://www.qiyunip.com/freeProxy/{page}.html",
                headers=_proxy_scraper_headers(), timeout=10,
            )
            resp.raise_for_status()
            result |= _extract_ip_port(resp.text)
        except Exception:
            continue
    return result


def _scrape_proxyscrape():
    """ProxyScrape：JSON API，过滤中国大陆代理。"""
    import requests
    resp = requests.get(
        "https://api.proxyscrape.com/v4/free-proxy-list/get",
        params={
            "request": "get_proxies", "skip": "0",
            "proxy_format": "protocolipport", "format": "json", "limit": "1000",
        },
        headers=_proxy_scraper_headers(), timeout=10,
    )
    resp.raise_for_status()
    result = set()
    for item in resp.json().get("proxies", []):
        if not item.get("alive"):
            continue
        # 仅保留中国大陆代理，海外代理无法绕过雨云的海外 IP 拦截
        if item.get("ip_data", {}).get("countryCode", "").upper() != "CN":
            continue
        ip, port = item.get("ip", ""), str(item.get("port", ""))
        if ip and port:
            result.add(f"{ip}:{port}")
    return result


# 代理源注册表：89IP/快代理/齐云/开心均为国内源（代理本身就是 CN），
# ProxyScrape 自带国家码在 _scrape_proxyscrape 内过滤 CN，无需 ip2region 离线定位。
_PROXY_SCRAPERS = [
    _scrape_ip89, _scrape_kuaidaili, _scrape_kxdaili,
    _scrape_qiyunip, _scrape_proxyscrape,
]


def get_freeproxy_ip(exclude_ips=None):
    """
    自建轻量级代理抓取：并发抓取 5 个国内免费代理源，以 app.rainyun.com 为探针
    并发验证（状态 200 且响应 ≤3s），找到可用代理即停。无第三方依赖。
    :param exclude_ips: 本轮重试内已失败过的代理集合（"ip:port" 字符串），
                        命中即跳过，避免反复抓到同一个慢代理。
    :return: 代理地址字符串 "ip:port"，无可用代理时返回 None
    """
    import concurrent.futures
    import requests
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    exclude_ips = set(exclude_ips or [])
    # 已有失败代理时多验证几个候选，避免凑不够 need 时卡在黑名单代理上
    need = max(1, len(exclude_ips) + 3) if exclude_ips else 1

    logger.info("正在抓取国内免费代理（5 源并发，以 app.rainyun.com 为探针验证）...")

    # 阶段1：并发抓取所有源，单个源失败不影响其他源
    all_proxies = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(scraper): scraper.__name__ for scraper in _PROXY_SCRAPERS}
        try:
            for future in concurrent.futures.as_completed(future_map, timeout=20):
                name = future_map[future]
                try:
                    scraped = future.result()
                    if scraped:
                        logger.info(f"代理源 {name} 抓取到 {len(scraped)} 个代理")
                        all_proxies |= scraped
                except Exception as e:
                    logger.warning(f"代理源 {name} 抓取失败: {e}")
        except concurrent.futures.TimeoutError:
            logger.warning("部分代理源抓取超时（20s），已跳过")

    candidates = [p for p in all_proxies if p not in exclude_ips]
    if not candidates:
        logger.warning("未抓取到任何代理")
        return None

    logger.info(f"共 {len(candidates)} 个候选代理（已排除 {len(exclude_ips)} 个黑名单），开始并发验证...")

    # 阶段2：并发验证，找到 need 个可用即停
    working = []
    working_lock = threading.Lock()
    stop_event = threading.Event()

    def _validate(proxy_str):
        if stop_event.is_set():
            return None
        try:
            proxies = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
            resp = requests.get("https://app.rainyun.com/", proxies=proxies, timeout=5)
            # 慢代理（>3s）会导致页面加载不完整、Cookie 无法送达，被误判为"Cookie 失效"
            if resp.status_code == 200 and resp.elapsed.total_seconds() <= 3:
                return proxy_str
        except Exception:
            pass
        return None

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=64)
    future_map = {executor.submit(_validate, p): p for p in candidates}
    try:
        for future in concurrent.futures.as_completed(future_map):
            result = future.result()
            if result:
                with working_lock:
                    working.append(result)
                    if len(working) >= need:
                        stop_event.set()
                        break
    finally:
        executor.shutdown(wait=False)

    if not working:
        logger.warning("未找到可用的国内代理")
        return None

    proxy = working[0]
    logger.info(f"获取到可用国内代理: {proxy}（共验证通过 {len(working)} 个）")
    return proxy


# SVG图标

# 图标 (Base64)
BASE64_ICONS = {
    # 金色硬币
    'coin': 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDExMTQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTgwNy41MTEgNDAwLjY2NmE1MTIgNTEyIDAgMCAwLTYwLjE1LTUzLjg3M2MtMy4wNzItMi4zNDUtNS40MjctMy45ODMtOC4xNS01Ljk4IDM4LjA2Ni0xMy4wNzcgNjQuNy00NC4zOCA2NC43LTgxLjQzNCAwLTQ5LjktNDcuMzctODguMDgtMTAzLjYxOC04OC4wOGE5OS40IDk5LjQgMCAwIDAtMzUuNTU4IDYuNDk4IDc5IDc5IDAgMCAwLTExLjc3MSA1LjU5MWMtMS45NjYuODMtNi4xNi0uMDk3LTcuMzEyLTEuNTNsLS4wNS4wMzVjLTQuMjkxLTYuNDMtMTAuNzYzLTE0LjQwMi0yMC4xNjgtMjIuNTY5LTE3LjktMTUuNTU0LTM5LjA5Mi0yNS4xNS02My4yOTQtMjUuMTVzLTQ1LjM4NCA5LjU5Ni02My4yODggMjUuMTVjLTkuMTkgNy45NzctMTUuNDk4IDE1LjcxMy0xOS44MDQgMjIuMDc4bC0uMDI2LS4wMmMtMS42MjggMS45Mi01Ljg1MiAyLjkyOC03LjMyMiAyLjIyMWE3OC40IDc4LjQgMCAwIDAtMTIuMTQ0LTUuODExIDk5LjUgOTkuNSAwIDAgMC0zNS41NjQtNi41MDJjLTU2LjI0OCAwLTEwMy42MTMgMzguMTg1LTEwMy42MTMgODguMDc5IDAgMzEuNjgzIDE5LjU0MyA1OS4xMDUgNDguOTU3IDc0LjYyNGE0OTUgNDk1IDAgMCAwLTkuNDA1IDYuODQgNDY4IDQ2OCAwIDAgMC02MC4wNTggNTMuMzE1QzI0NC4yNjUgNDUyLjk1NiAyMTAuNSA1MjAuMjEyIDIxMC41IDU5NC44NzJjMCAyMDcuMDIyIDE1NC4yOCAzMDUuNDggMzQwLjEzMSAzMDUuNDggNzcuODkxIDAgMTU0LjAzLTE1LjU0IDIxNS42NC01Mi4yMTkgODMuNTk5LTQ5Ljc5MiAxMzEuMTUzLTEzMy40MjcgMTMxLjE1My0yNTMuMjYtLjAxNS03MC4xNjUtMzMuOTk2LTEzNS4zNDgtODkuOTEyLTE5NC4yMDdNNjQ2LjU2NCA2MDEuNDNjMTAuNTk4IDAgMTkuMTg0IDguNzkxIDE5LjE4NCAxOS42MTUgMCAxMC44MjktOC41OSAxOS42MjUtMTkuMTg0IDE5LjYyNUg1NjkuODF2NTYuNDg5YzAgOC4yODktOC41OTEgMTUuMDA2LTE5LjE4NSAxNS4wMDYtMTAuNTk4IDAtMTkuMTg0LTYuNzE3LTE5LjE4NC0xNS4wMDZ2LTU2LjQ5aC03Ni43NTRjLTEwLjU5OSAwLTE5LjE4NS04Ljc5LTE5LjE4NS0xOS42MnM4LjU5MS0xOS42MTQgMTkuMTg1LTE5LjYxNGg3Ni43NTRWNTgxLjgyaC03Ni43NTRjLTEwLjU5OSAwLTE5LjE4NS04Ljc4NS0xOS4xODUtMTkuNjE0czguNTkxLTE5LjYxNSAxOS4xODUtMTkuNjE1aDc4LjM5N2wtNzIuNzgtNzQuMzk5YTE5LjkxNyAxOS45MTcgMCAwIDEgMC0yNy43MzUgMTguODkzIDE4Ljg5MyAwIDAgMSAyNy4xMzUgMGw2My4xODYgNjQuNTg0IDYzLjE4Ni02NC41ODRhMTguOTAzIDE4LjkwMyAwIDAgMSAyNi43MjEtLjQyNWwuNDIuNDI1YTE5LjkyNyAxOS45MjcgMCAwIDEgMCAyNy43MzVsLTcyLjc4IDc0LjM5OWg3OC40MDJjMTAuNTk4IDAgMTkuMTggOC43OCAxOS4xOCAxOS42MTVzLTguNTg3IDE5LjYxNC0xOS4xOCAxOS42MTRoLTc2Ljc1OXYxOS42MXoiIGZpbGw9IiNmNTllMGIiLz48L3N2Zz4='
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



def generate_html_report(results, screenshot_mode='all'):
    """
    生成 HTML 签到报告
    :param results: 签到结果列表
    :param screenshot_mode: 截图模式 - 'all'(所有), 'failed_only'(仅失败), 'none'(无截图)
    """
    now_str = now_local().strftime('%Y-%m-%d %H:%M:%S')
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
        .icon-img { width: 20px; height: 20px; vertical-align: middle; display: inline-block; }
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
                <img src="{BASE64_ICONS['coin']}" class="icon-img" alt="coin" />
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
            {get_screenshot_html(res.get('screenshot')) if screenshot_mode == 'all' or (screenshot_mode == 'failed_only' and not res['status']) else ''}
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


def generate_markdown_report(results, compact=False):
    """
    生成 Markdown 签到报告
    :param results: 签到结果列表
    :param compact: 精简模式 - 成功账号只保留一行，失败账号保留完整信息
    """
    now_str = now_local().strftime('%Y-%m-%d %H:%M:%S')
    success_count = len([r for r in results if r['status']])
    total_count = len(results)
    
    md = f"> {now_str}\n\n"
    md += f"**状态**: ✅ {success_count} 成功 / ❌ {total_count - success_count} 失败\n\n"
    md += "---\n"
    
    for res in results:
        status_icon = "✅" if res['status'] else "❌"
        
        if compact and res['status']:
            # 精简模式：成功账号一行搞定
            points_str = f" | {res['points']}积分" if res.get('points') else ""
            md += f"- {status_icon} {res['username']}{points_str}\n"
        else:
            # 完整模式 或 失败账号
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


def generate_summary_report(results, fmt='html'):
    """
    生成极精简的摘要报告（兜底版本）
    :param results: 签到结果列表
    :param fmt: 'html' 或 'markdown'
    :return: 摘要内容字符串
    """
    now_str = now_local().strftime('%Y-%m-%d %H:%M:%S')
    success_count = len([r for r in results if r['status']])
    fail_count = len(results) - success_count
    total_count = len(results)
    
    if fmt == 'html':
        lines = []
        lines.append(f'<div style="font-family: sans-serif; padding: 16px;">')
        lines.append(f'<h3>🌧️ 雨云签到摘要</h3>')
        lines.append(f'<p style="color: #6b7280; font-size: 13px;">{now_str}</p>')
        lines.append(f'<p><b>✅ 成功: {success_count}</b> / <b>❌ 失败: {fail_count}</b> / 共 {total_count}</p>')
        lines.append('<hr>')
        
        for res in results:
            icon = '✅' if res['status'] else '❌'
            detail = ''
            if res['status'] and res.get('points'):
                detail = f" — {res['points']}积分"
            elif not res['status']:
                detail = f" — {res['msg']}"
                if res.get('retries', 0) > 0:
                    detail += f" (重试{res['retries']}次)"
            lines.append(f'<p>{icon} {res["username"]}{detail}</p>')
        
        lines.append('<hr>')
        lines.append('<p style="font-size: 12px; color: #9ca3af;">Powered by Rainyun-Qiandao</p>')
        lines.append('</div>')
        return '\n'.join(lines)
    else:
        # Markdown 格式
        lines = []
        lines.append(f'> {now_str}')
        lines.append(f'')
        lines.append(f'**✅ 成功: {success_count}** / **❌ 失败: {fail_count}** / 共 {total_count}')
        lines.append('---')
        
        for res in results:
            icon = '✅' if res['status'] else '❌'
            detail = ''
            if res['status'] and res.get('points'):
                detail = f" — {res['points']}积分"
            elif not res['status']:
                detail = f" — {res['msg']}"
                if res.get('retries', 0) > 0:
                    detail += f" (重试{res['retries']}次)"
            lines.append(f'- {icon} {res["username"]}{detail}')
        
        lines.append('---')
        lines.append('Powered by Rainyun-Qiandao')
        return '\n'.join(lines)


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
        # 创建截图目录（使用 temp 目录的绝对路径）
        screenshot_dir = os.path.abspath(os.path.join("temp", "screenshots"))
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # 生成截图文件名（类型_账号_时间戳）
        timestamp = now_local().strftime("%Y%m%d_%H%M%S")
        masked_account = f"{account_id[:3]}xxx{account_id[-3:] if len(account_id) > 6 else account_id}"
        
        # 先保存原始 PNG 截图（文件名带账号，避免多账号同秒截图时互相覆盖）
        temp_filepath = os.path.join(screenshot_dir, f"temp_{masked_account}_{timestamp}.png")
        if not driver.save_screenshot(temp_filepath):
            logger.error(f"无法保存截图到: {temp_filepath}")
            return None

        # 再次确认文件存在（防止 save_screenshot 返回 True 但实际上文件未创建）
        if not os.path.exists(temp_filepath):
            logger.error(f"截图文件未创建: {temp_filepath}")
            return None
        
        # 压缩并转换为 JPEG 格式（大幅减小文件大小）
        compressed_filename = f"{status}_{masked_account}_{timestamp}.jpg"
        compressed_filepath = os.path.join(screenshot_dir, compressed_filename)
        
        original_size = os.path.getsize(temp_filepath)
        compressed_size = compress_screenshot(temp_filepath, compressed_filepath)
        
        if compressed_size:
            # 压缩成功后才删除临时 PNG 文件
            try:
                os.remove(temp_filepath)
            except:
                pass
            compression_ratio = (1 - compressed_size / original_size) * 100
            status_text = "成功" if status == "success" else "失败"
            logger.info(f"已保存{status_text}截图: {compressed_filepath} (压缩率: {compression_ratio:.1f}%, {original_size/1024:.1f}KB -> {compressed_size/1024:.1f}KB)")
            
            # 清理7天前的旧截图
            cleanup_old_screenshots(screenshot_dir, days=7)
            
            return compressed_filepath
        else:
            # 压缩失败：删除临时文件，返回 None（不回退原始 PNG，避免邮件体积过大）
            logger.error(f"截图压缩失败，放弃截图（原始 PNG {original_size/1024:.1f}KB 过大，不回退）")
            try:
                os.remove(temp_filepath)
            except:
                pass
            return None
            
    except Exception as e:
        logger.error(f"保存截图时出错: {e}")
        return None


def compress_screenshot(input_path, output_path, max_width=800, quality=None):
    """先本地 OpenCV 压缩，如果配置了 TinyPNG 则二次压缩"""
    if quality is None:
        try:
            quality = int(os.getenv("SCREENSHOT_QUALITY", "35"))
        except ValueError:
            quality = 35
        quality = max(10, min(100, quality))
    result = compress_with_cv2(input_path, output_path, max_width, quality)
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


def _ssim_channel(gray_a, gray_b):
    import cv2

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    a = gray_a.astype("float64")
    b = gray_b.astype("float64")
    mu_a = cv2.GaussianBlur(a, (7, 7), 1.5)
    mu_b = cv2.GaussianBlur(b, (7, 7), 1.5)
    var_a = cv2.GaussianBlur(a * a, (7, 7), 1.5) - mu_a * mu_a
    var_b = cv2.GaussianBlur(b * b, (7, 7), 1.5) - mu_b * mu_b
    cov_ab = cv2.GaussianBlur(a * b, (7, 7), 1.5) - mu_a * mu_b
    ssim_map = ((2 * mu_a * mu_b + C1) * (2 * cov_ab + C2)) / \
               ((mu_a * mu_a + mu_b * mu_b + C1) * (var_a + var_b + C2))
    return float(ssim_map.mean())


def _ssim(img_a, img_b):
    """两张彩色图的结构相似度（0~1），取三通道最差值，数值越低画质损失越大"""
    return min(_ssim_channel(img_a[:, :, c], img_b[:, :, c]) for c in range(3))


# 自适应压缩的可读性底线：SSIM 低于此值视为「看不清了」
SSIM_FLOOR = 0.95
# 自适应搜索的最低质量档，再低文字笔画会明显崩坏
MIN_JPEG_QUALITY = 15


def compress_with_cv2(input_path, output_path, max_width=1280, quality=40):
    """OpenCV 压缩截图。quality 为上限：从上限逐档下调，取 SSIM 仍达标的最低档"""
    try:
        import cv2

        img = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning(f"OpenCV 无法读取截图: {input_path}")
            return None

        h, w = img.shape[:2]
        if w > max_width:
            img = cv2.resize(img, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)

        # 4:4:4：色度不降采样，避免彩色文字边缘串色
        encode_params = [cv2.IMWRITE_JPEG_OPTIMIZE, 1, cv2.IMWRITE_JPEG_PROGRESSIVE, 1,
                         cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444]

        chosen_buf = None
        chosen_q = quality
        chosen_ssim = 1.0
        for q in range(quality, MIN_JPEG_QUALITY - 1, -5):
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q] + encode_params)
            if not ok:
                continue
            ssim = _ssim(img, cv2.imdecode(buf, cv2.IMREAD_COLOR))
            if ssim < SSIM_FLOOR:
                break
            chosen_buf, chosen_q, chosen_ssim = buf, q, ssim

        if chosen_buf is None:
            # 上限档位自己就不达标，尊重上限原样输出
            ok, chosen_buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality] + encode_params)
            if not ok:
                logger.warning(f"OpenCV 无法编码 JPEG: {input_path}")
                return None
        elif chosen_q < quality:
            logger.info(f"自适应压缩: 上限 q{quality} -> q{chosen_q} (SSIM {chosen_ssim:.3f})")

        with open(output_path, "wb") as f:
            f.write(chosen_buf.tobytes())

        return os.path.getsize(output_path)
    except Exception as e:
        logger.warning(f"OpenCV 压缩出错: {e}")
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

    import concurrent.futures

    # 从环境变量获取最大重试次数，默认为2
    max_retries = int(os.getenv("CHECKIN_MAX_RETRIES", "2"))
    # 并发相关配置
    max_workers = int(os.getenv("MAX_WORKERS", "3"))
    stagger_delay = int(os.getenv("MAX_DELAY", "15"))  # 账号间错开启动时间（秒）
    
    accounts = parse_accounts()
    results = {}
    
    # 初始化每个账号的结果
    for i, (username, password) in enumerate(accounts):
        results[username] = {
            'password': password,
            'result': None,
            'retry_count': 0,
            'index': i + 1,
            'failed_proxies': set(),  # 本轮重试内已失败过的代理 IP，下次抓取时跳过
        }
    
    # 待执行的账号列表
    pending_accounts = list(accounts)
    current_attempt = 0
    
    while pending_accounts and current_attempt <= max_retries:
        if current_attempt == 0:
            logger.info(f"========== 开始执行签到任务（共 {len(pending_accounts)} 个账号，并发数: {max_workers}） ==========")
        else:
            logger.info(f"========== 第 {current_attempt} 次重试（共 {len(pending_accounts)} 个失败账号） ==========")
        
        failed_accounts = []
        future_to_account = {}
        
        # 使用线程池并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            for i, (username, password) in enumerate(pending_accounts):
                if i > 0 and stagger_delay > 0:
                     # 最小延时为 5 秒
                     lower_bound = 5
                     upper_bound = max(5, stagger_delay)
                     actual_delay = random.randint(lower_bound, upper_bound)
                     logger.info(f"随机等待 {actual_delay} 秒后启动下一个账号任务...")
                     time.sleep(actual_delay)
                
                account_idx = results[username]['index']
                retry_info = f"（第 {results[username]['retry_count'] + 1} 次尝试）" if results[username]['retry_count'] > 0 else ""
                logger.info(f"========== 启动账号 {account_idx}/{len(accounts)} {retry_info} ==========")

                # 重试时复用上次代理，避免换 IP 导致 Cookie 失效。
                # 但如果上次失败是代理问题（proxy_failed），则不复用——慢代理通过了 validate_proxy
                # 却无法支撑浏览器会话，复用只会重复同样的失败。
                reuse_proxy = None
                if results[username]['result'] and results[username]['result'].get('proxy'):
                    if not results[username]['result'].get('proxy_failed'):
                        reuse_proxy = results[username]['result']['proxy']
                    else:
                        logger.info(f"上次失败由代理引起，不复用旧代理，重新抓取")

                # 传入本轮已失败过的代理集合，重新抓取时跳过这些 IP，
                # 避免源抓取顺序固定导致反复命中同一个慢代理
                failed_proxies = results[username]['failed_proxies']
                future = executor.submit(run_checkin, username, password, reuse_proxy, failed_proxies)
                future_to_account[future] = username

            # 获取结果
            for future in concurrent.futures.as_completed(future_to_account):
                username = future_to_account[future]
                account_idx = results[username]['index']
                
                try:
                    result = future.result()
                    results[username]['result'] = result
                    
                    if result['status']:
                        logger.info(f"✅ 账号 {account_idx} 签到成功")
                    else:
                        logger.error(f"❌ 账号 {account_idx} 签到失败: {result['msg']}")
                        # 代理确认失败时，把该代理 IP 记入黑名单，下次重试抓取时跳过，
                        # 避免源抓取顺序固定导致反复命中同一个慢代理（密码错误等非代理失败不记）
                        if result.get('proxy_failed') and result.get('proxy'):
                            results[username]['failed_proxies'].add(result['proxy'])
                        results[username]['retry_count'] += 1
                        # 还没达到最大重试次数，加入待重试列表
                        if results[username]['retry_count'] <= max_retries:
                            # 注意：这里不能直接 append 到 failed_accounts，因为主线程在等待所有 future 完成
                            # 但在这里 append 是安全的，因为 failed_accounts 是局部变量，且只在当前 while 循环迭代中使用
                            failed_accounts.append((username, results[username]['password']))
                except Exception as e:
                    logger.error(f"❌ 账号 {account_idx} 执行异常: {e}")
                    results[username]['retry_count'] += 1
                    if results[username]['retry_count'] <= max_retries:
                        failed_accounts.append((username, results[username]['password']))

        # 更新待执行列表为失败账号
        pending_accounts = failed_accounts
        current_attempt += 1
        
        # 如果还有待重试的账号，增加重试间隔
        if pending_accounts:
            retry_wait = 60  # 固定重试等待 60 秒
            logger.info(f"等待 {retry_wait} 秒后开始重试 {len(pending_accounts)} 个失败账号...")
            time.sleep(retry_wait)
    

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
        wx_topics = os.getenv("WXPUSHER_TOPIC_IDS")
        if wx_app_token and (wx_uids or wx_topics):
            logger.info("Configuring WXPusher provider...")
            notification_manager.add_provider(WXPusherProvider(wx_app_token, wx_uids, wx_topics))
            
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
            
            # 从环境变量读取截图策略：all(所有账号) / failed_only(仅失败) / none(不带截图)
            screenshot_mode = os.getenv("SCREENSHOT_MODE", "failed_only").strip().lower()
            if screenshot_mode not in ('all', 'failed_only', 'none'):
                logger.warning(f"无效的 SCREENSHOT_MODE '{screenshot_mode}'，使用默认值 'failed_only'")
                screenshot_mode = 'failed_only'
            logger.info(f"截图策略: {screenshot_mode}")
            
            # 一次性生成 7 份内容，由各 Provider 按自身限制自动选择
            context = {
                'html_email':        generate_html_report(final_results, screenshot_mode='all'), # 邮件无限制，强制全带截图
                'html_full':         generate_html_report(final_results, screenshot_mode=screenshot_mode),
                'html_lite':         generate_html_report(final_results, screenshot_mode='none'),
                'markdown_full':     generate_markdown_report(final_results, compact=False),
                'markdown_lite':     generate_markdown_report(final_results, compact=True),
                'summary_html':      generate_summary_report(final_results, fmt='html'),
                'summary_markdown':  generate_summary_report(final_results, fmt='markdown'),
            }
            
            # 记录各版本大小，便于调试
            for key, content in context.items():
                byte_size = len(content.encode('utf-8'))
                logger.info(f"内容版本 {key}: {byte_size} bytes ({byte_size/1024:.1f} KB)")
            
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
    # 开启性能日志：页面加载超时时可 dump 网络时间线，定位是 DNS/TTFB/资源下载哪个环节卡住
    ops.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    # 页面加载策略用 eager：DOMContentLoaded 即返回，不等慢子资源挂起卡满超时造成假失败；
    # 后续流程靠 WebDriverWait 等元素渲染，不依赖 load 事件
    ops.page_load_strategy = "eager"
    
    # 配置代理
    if proxy:
        ops.add_argument(f"--proxy-server=http://{proxy}")
        logger.info(f"浏览器已配置代理: {proxy}")
    
    # 添加账号专属 User-Agent（相同账号每次相同）
    user_agent = get_random_user_agent(account_id)
    ops.add_argument(f"--user-agent={user_agent}")
    logger.info(f"使用 User-Agent: {user_agent[:50]}...")  # 只显示前50个字符
    
    
    if debug:
        ops.add_experimental_option("detach", True)
    
    # 设置窗口大小（避免因窗口太小导致元素重叠或误点击）
    ops.add_argument("--window-size=1920,1080")
    
    if linux:
        ops.add_argument("--headless")
        ops.add_argument("--disable-gpu")

        # 检测 ChromeDriver 路径
        # 仅 Docker 使用固定路径 /usr/bin/chromedriver；Actions runner 预装的同名文件
        # 版本与 setup-chrome 装的 Chrome 不一致，故仅 /.dockerenv 存在时才用
        chromedriver_path = "/usr/bin/chromedriver"

        if os.path.exists("/.dockerenv") and os.path.exists(chromedriver_path):
            logger.info(f"使用 Docker 镜像的 ChromeDriver: {chromedriver_path}")
            service = Service(chromedriver_path)
        else:
            logger.info("使用 Selenium Manager 自动管理 ChromeDriver")
            service = Service()
        
        driver = webdriver.Chrome(service=service, options=ops)
        # 限制页面加载时间：慢代理下防止 driver.get() 无限阻塞
        driver.set_page_load_timeout(30)
        return driver
    else:
        # Windows 环境
        # 使用 Selenium Manager 自动处理驱动下载和路径匹配
        service = Service()
        driver = webdriver.Chrome(service=service, options=ops)
        driver.set_page_load_timeout(30)
        return driver


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


class CaptchaProvider:
    """验证码提供者基类"""
    def solve(self, driver, timeout, retry_stats, logger_adapter):
        """
        执行验证码破解逻辑
        :param driver: WebDriver 实例
        :param timeout: 超时时间
        :param retry_stats: 重试统计字典 {'count': 0}
        :param logger_adapter: 日志记录器
        """
        raise NotImplementedError


class TencentCaptchaProvider(CaptchaProvider):
    """腾讯滑块验证码处理"""
    
    def solve(self, driver, timeout, retry_stats, logger_adapter):
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
                logger_adapter.info("未检测到可处理验证码内容，跳过验证码处理")
                return

            # 延迟导入，只在需要时加载
            import cv2
            import ICR

            wait = WebDriverWait(driver, timeout)
            self._download_captcha_img(driver, timeout, logger_adapter)

            logger_adapter.info("开始处理验证码图片并识别")

            captcha = cv2.imread("temp/captcha.jpg")

            # ICR 纯算法识别：黑色区域分割 + 多角度模板匹配，一次出全部目标坐标
            matches = ICR.main("temp/captcha.jpg", "temp/sprite.jpg")
            final_click_positions = []
            for match in matches:
                rect = match['bg_rect']
                x, y = int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)
                logger_adapter.info(
                    f"--> 图案 {match['sprite_idx'] + 1} 位于 ({x}, {y})，"
                    f"旋转 {match['angle']}°，相似度 {match['similarity']:.1f}%"
                )
                final_click_positions.append(f"{x},{y}")

            if len(final_click_positions) != 3:
                logger_adapter.error(
                    f"识别出的目标数为 {len(final_click_positions)}（期望 3 个），放弃提交并刷新"
                )
                self._save_captcha_debug_bundle(
                    logger_adapter,
                    stage="recognition_count_mismatch",
                    retry_count=retry_stats['count'],
                    extra={"click_positions": final_click_positions},
                )
                retry_stats['count'] += 1
            else:
                for positon in final_click_positions:
                    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
                    style = slideBg.get_attribute("style")
                    x, y = int(positon.split(",")[0]), int(positon.split(",")[1])
                    width_raw, height_raw = captcha.shape[1], captcha.shape[0]
                    width, height = float(get_width_from_style(style)), float(get_height_from_style(style))
                    x_offset, y_offset = float(-width / 2), float(-height / 2)
                    final_x, final_y = int(x_offset + x / width_raw * width), int(y_offset + y / height_raw * height)
                    ActionChains(driver).move_to_element_with_offset(slideBg, final_x, final_y).click().perform()
                    time.sleep(0.3)

                confirm = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="tcStatus"]/div[2]/div[2]/div/div')))
                logger_adapter.info("提交验证码")
                time.sleep(0.5)
                confirm.click()
                time.sleep(3)

                # 检查是否通过
                result_elem = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="tcOperation"]')))
                if result_elem.get_attribute("class") == 'tc-opera pointer show-success':
                    logger_adapter.info("验证码通过 🎉")
                    return
                else:
                    logger_adapter.error("验证码提交后未通过，匹配坐标可能存在偏移。")
                    self._save_captcha_debug_bundle(
                        logger_adapter,
                        stage="submit_failed",
                        retry_count=retry_stats['count'],
                        extra={"click_positions": final_click_positions},
                    )
                    retry_stats['count'] += 1

            # 执行提早换图逻辑
            reload_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="reload"]')))
            time.sleep(1)
            reload_btn.click()
            time.sleep(3)
            logger_adapter.info(f"重新发起验证码挑战 (当前重试: {retry_stats['count']})")
            return self.solve(driver, timeout, retry_stats, logger_adapter)

        except TimeoutException:
            logger_adapter.error("获取验证码图片等元素超时")
        except Exception as e:
            logger_adapter.error(f"验证码执行流程中发生未知错误: {e}")
            import traceback
            logger_adapter.debug(traceback.format_exc())
            # 如果发生错误，不妨尝试重试
            retry_stats['count'] += 1
            try:
                reload_btn = driver.find_element(By.XPATH, '//*[@id="reload"]')
                reload_btn.click()
                time.sleep(3)
                return self.solve(driver, timeout, retry_stats, logger_adapter)
            except:
                pass
        finally:
            logger_adapter.debug("验证码单次处理周期完毕")

    def _download_captcha_img(self, driver, timeout, logger_adapter):
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
            logger_adapter.debug(f"下载图片使用 UA: {current_ua[:50]}...")
        except Exception:
            current_ua = None
            
        slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
        img1_style = slideBg.get_attribute("style")
        img1_url = get_url_from_style(img1_style)
        logger_adapter.info("开始下载验证码图片(1): " + img1_url)
        download_image(img1_url, "captcha.jpg", user_agent=current_ua)
        
        sprite = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="instruction"]/div/img')))
        img2_url = sprite.get_attribute("src")
        logger_adapter.info("开始下载验证码图片(2): " + img2_url)
        download_image(img2_url, "sprite.jpg", user_agent=current_ua)

    def _make_safe_name(self, raw_name):
        import re

        safe_name = re.sub(r'[^0-9A-Za-z._-]+', '_', raw_name or "unknown")
        return safe_name.strip("._") or "unknown"

    def _save_captcha_debug_bundle(self, logger_adapter, stage, retry_count, extra=None):
        import json
        import shutil
        from datetime import datetime

        account_prefix = self._make_safe_name(getattr(logger_adapter, "extra", {}).get("prefix", "unknown"))
        bundle_name = f"{now_local().strftime('%Y%m%d_%H%M%S_%f')[:-3]}_{stage}_r{retry_count}"
        bundle_dir = os.path.join("logs", "captcha_debug", account_prefix, bundle_name)
        os.makedirs(bundle_dir, exist_ok=True)

        temp_dir = "temp"
        copied_files = []
        if os.path.isdir(temp_dir):
            for filename in sorted(os.listdir(temp_dir)):
                if not (
                    filename in {"captcha.jpg", "sprite.jpg"}
                    or filename.startswith("sprite_")
                    or filename.startswith("spec_")
                ):
                    continue
                source_path = os.path.join(temp_dir, filename)
                if not os.path.isfile(source_path):
                    continue
                shutil.copy2(source_path, os.path.join(bundle_dir, filename))
                copied_files.append(filename)

        metadata = {
            "stage": stage,
            "retry_count": retry_count,
            "account_prefix": getattr(logger_adapter, "extra", {}).get("prefix", "unknown"),
            "captured_at": now_local().isoformat(timespec="seconds"),
            "copied_files": copied_files,
            "extra": extra or {},
        }
        metadata_path = os.path.join(bundle_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger_adapter.info(f"已保存验证码调试样本到 {bundle_dir}")


class CaptchaFactory:
    """验证码工厂类"""
    @classmethod
    def create_provider(cls, captcha_type: str = "tencent") -> CaptchaProvider:
        if captcha_type == "tencent":
            return TencentCaptchaProvider()
        raise ValueError(f"Unknown captcha type: {captcha_type}")


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


def diagnose_page_load_failure(driver, proxy=None):
    """页面加载超时时记录诊断信息，便于区分网络波动/服务端慢/页面资源卡住"""
    # requests/json 非模块级导入，函数内显式导入，避免诊断流程自身报 NameError 失效
    import json
    import requests
    # 浏览器状态：看 driver 卡在哪一步
    try:
        cur_url = driver.current_url or "(空)"
        title = driver.title or "(空)"
        ready_state = driver.execute_script("return document.readyState") or "unknown"
        page_len = len(driver.page_source or "")
        logger.warning(f"[诊断] 浏览器状态: URL={cur_url}, title={title}, readyState={ready_state}, page_source={page_len} 字符")
    except Exception as diag_e:
        logger.warning(f"[诊断] 无法获取浏览器状态: {diag_e}")
    # 服务端连通性：走相同代理探测，看雨云是否可达、多快响应
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = requests.get("https://app.rainyun.com/", timeout=8, allow_redirects=False, proxies=proxies)
        logger.warning(f"[诊断] 服务端探测: GET app.rainyun.com → {r.status_code}, 耗时 {r.elapsed.total_seconds():.2f}s")
    except Exception as diag_e:
        logger.warning(f"[诊断] 服务端探测失败: {str(diag_e)[:200]}")
    # Chrome 性能日志：提取卡住期间的网络请求时间线，定位是 DNS/TTFB/资源下载哪个环节卡住
    try:
        entries = driver.get_log("performance")
        slow_or_failed = []
        for entry in entries:
            try:
                msg = json.loads(entry["message"])["message"]
                method = msg.get("method", "")
                params = msg.get("params", {})
                # 只记录关键事件：请求失败、响应慢、主文档请求
                if method == "Network.loadingFailed":
                    url = params.get("requestId", "")[:120]
                    err = params.get("errorText", "unknown")
                    slow_or_failed.append(f"FAIL {url} ({err})")
                elif method == "Network.responseReceived":
                    resp = params.get("response", {})
                    url = resp.get("url", "")[:120]
                    mime = resp.get("mimeType", "")
                    # 只关注主文档和慢响应，跳过图片/css 等小资源
                    if mime.startswith("text/html") or "rainyun" in url:
                        timing = resp.get("timing", {})
                        ttfb_ms = timing.get("receiveHeadersEnd", 0) - timing.get("sendStart", 0)
                        if ttfb_ms > 1000:  # TTFB 超过 1 秒标记为慢
                            slow_or_failed.append(f"SLOW {url} TTFB={ttfb_ms:.0f}ms ({mime})")
                        else:
                            slow_or_failed.append(f"OK {url} TTFB={ttfb_ms:.0f}ms ({mime})")
            except Exception:
                continue
        if slow_or_failed:
            logger.warning(f"[诊断] 性能日志({len(slow_or_failed)} 条关键请求):")
            for line in slow_or_failed[:20]:  # 最多输出 20 条避免日志过长
                logger.warning(f"  {line}")
        else:
            logger.warning("[诊断] 性能日志: 无关键请求记录")
    except Exception as diag_e:
        logger.warning(f"[诊断] 无法获取性能日志: {diag_e}")


def safe_get(driver, url):
    """
    带容错的主文档跳转。
    page_load_timeout 触发后先 window.stop()，再检查页面实际状态：
    主文档已加载（readyState interactive/complete 且源码长度正常）则继续流程，
    避免「页面卡住」的假失败；确实没加载出来才原样抛 TimeoutException 走失败处理。
    :return: True 页面可用（含超时后抢救成功）
    """
    modules = import_selenium_modules()
    TimeoutException = modules['TimeoutException']
    try:
        driver.get(url)
        return True
    except TimeoutException:
        logger.warning(f"页面加载超时（{url}），停止加载并检查页面实际状态...")
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
        time.sleep(1)
        # 浏览器连查询都响应不了 = 真卡死，此处会抛异常向上传播
        ready_state = driver.execute_script("return document.readyState") or "unknown"
        page_len = len(driver.page_source or "")
        if ready_state in ("interactive", "complete") and page_len > 500:
            logger.warning(
                f"超时但主文档已就绪（readyState={ready_state}, {page_len} 字符），"
                "忽略未完成的慢子资源，继续流程"
            )
            return True
        logger.error(f"超时且页面未加载出来（readyState={ready_state}, 源码仅 {page_len} 字符）")
        raise


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
        safe_get(driver, "https://app.rainyun.com/")
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
        # 代理异常（ERR_PROXY_CONNECTION_FAILED、ERR_CONNECTION_RESET、renderer 超时等）
        # 会抛 WebDriverException，需要向上传播以便调用方区分"代理失败"和"Cookie 文件缺失"
        error_msg = str(e)
        if any(kw in error_msg for kw in (
            "ERR_PROXY", "ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED",
            "ERR_CONNECTION", "ERR_TIMED_OUT", "Timed out receiving message from renderer"
        )):
            logger.warning(f"加载 Cookie 时页面连接失败: {e}")
            raise
        logger.warning(f"加载 Cookie 失败: {e}")
        return False


def run_checkin(account_user=None, account_pwd=None, reuse_proxy=None, failed_proxies=None):
    """执行签到任务

    :param failed_proxies: 本轮重试内已失败过的代理集合（"ip:port" 字符串），
                            重新抓取代理时跳过这些 IP，避免反复命中同一个慢代理。
    """
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
    WebDriverException = modules['WebDriverException']
    import subprocess
    
    current_user = account_user or user
    current_pwd = account_pwd or pwd
    driver = None  # 初始化为 None，确保在任何情况下都能安全清理
    retry_stats = {'count': 0}

    # 创建带前缀的 Log Adapter
    masked_user = f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}"
    
    class PrefixAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return '[%s] %s' % (self.extra['prefix'], msg), kwargs

    # 使用 Adapter 替换原有的 logger
    logger_adapter = PrefixAdapter(logger, {'prefix': masked_user})
    
    proxy = None  # 提前初始化，确保异常处理中可安全引用
    try:
        logger_adapter.info(f"开始执行签到任务...")
        
        # 获取代理IP（每个账号单独获取）
        proxy_api_url = os.getenv("PROXY_API_URL", "").strip()
        if proxy_api_url:
            # 优先使用配置的代理接口（付费/自建）
            proxy = get_proxy_ip()
            if proxy:
                # 验证代理可用性
                if validate_proxy(proxy):
                    logger_adapter.info(f"代理 {proxy} 验证通过，将使用此代理")
                else:
                    logger_adapter.warning(f"代理 {proxy} 验证失败，将使用本地IP继续")
                    proxy = None
            else:
                logger_adapter.warning("获取代理失败，将使用本地IP继续")
        elif check_rainyun_blocked():
            # 实时探测 app.rainyun.com 可达性：雨云的海外 IP 拦截策略是动态的，
            # 可能间歇性放开或收紧，因此不按环境硬编码，统一以探测结果决定是否走代理。
            # 被拦截时自动抓取国内免费代理绕过（覆盖 GitHub Actions、海外 VPS、Docker 等）。
            # 重试时优先复用上次的代理：换 IP 会导致服务器 Cookie 失效，
            # 进而被迫走密码登录，而慢代理下密码登录容易超时失败。
            if reuse_proxy:
                if validate_proxy(reuse_proxy):
                    proxy = reuse_proxy
                    logger_adapter.info(f"复用上次代理: {proxy}（避免换 IP 导致 Cookie 失效）")
                else:
                    logger_adapter.warning(f"上次代理 {reuse_proxy} 已失效，重新抓取国内代理")
                    proxy = get_freeproxy_ip(exclude_ips=failed_proxies)
            else:
                proxy = get_freeproxy_ip(exclude_ips=failed_proxies)
            if proxy:
                logger_adapter.info(f"国内代理 {proxy} 已就绪，用于绕过海外 IP 拦截")
            else:
                logger_adapter.warning("未获取到可用国内代理，直连可能被拒绝连接")
        
        logger_adapter.info("初始化 Selenium（账号专属配置）")
        driver = init_selenium(current_user, proxy=proxy)
        apply_browser_timezone(driver)
        
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
        logger_adapter.info("已注入浏览器指纹脚本（账号专属指纹）")
        
        wait = WebDriverWait(driver, timeout)
        
        # 加载 Cookie 并直接跳转积分页
        # 慢代理或断连会导致 driver.get() 抛 WebDriverException（ERR_PROXY_CONNECTION_FAILED 等），
        # 需要捕获并标记为代理失败，让重试机制换新代理而非复用旧代理。
        proxy_failed = False
        try:
            load_cookies(driver, current_user)
            logger_adapter.info("正在跳转积分页...")
            safe_get(driver, "https://app.rainyun.com/account/reward/earn")
            time.sleep(3)
        except WebDriverException as e:
            error_msg = str(e)
            if any(kw in error_msg for kw in ("ERR_PROXY", "ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED", "ERR_TIMED_OUT", "ERR_CONNECTION", "Timed out receiving message from renderer")):
                # 直连场景下页面加载超时通常是网络波动或服务端响应慢，不是代理问题，不应判为 proxy_failed
                diagnose_page_load_failure(driver, proxy)
                is_proxy_issue = proxy is not None
                failure_label = "代理连接失败" if is_proxy_issue else "页面连接超时"
                logger_adapter.error(f"{failure_label}，页面无法加载: {error_msg[:200]}")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': f'{failure_label}，页面无法加载', 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path,
                    'proxy': proxy, 'proxy_failed': is_proxy_issue
                }
            raise
        
        # 检查是否需要密码登录
        if "/auth/login" in driver.current_url:
            # 慢代理下页面可能加载不完整就被重定向到 /auth/login，
            # 需要确认登录表单是否真正渲染——如果页面源码过短说明页面没加载完，是代理问题。
            page_src = driver.page_source or ""
            if len(page_src) < 500:
                logger_adapter.error(f"页面加载不完整（源码仅 {len(page_src)} 字符），疑似代理过慢")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': '代理过慢导致页面加载不完整', 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path,
                    'proxy': proxy, 'proxy_failed': True
                }
            logger_adapter.info("Cookie 已失效，使用账号密码登录")
            
            try:
                username = wait.until(EC.visibility_of_element_located((By.NAME, 'login-field')))
                password = wait.until(EC.visibility_of_element_located((By.NAME, 'login-password')))
                username.send_keys(current_user)
                password.send_keys(current_pwd)
                # 填充账号密码可能触发 Vue 重渲染，按钮在填完后重新获取，避免引用失效
                login_button = wait.until(EC.element_to_be_clickable((By.XPATH,
                    '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
                login_button.click()
            except TimeoutException:
                # 登录表单元素超时未找到：通常是代理太慢导致 JS bundle 没下载完，页面没渲染
                logger_adapter.error("登录表单加载超时，疑似代理过慢导致页面未渲染完成")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': '代理过慢导致登录表单加载超时', 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path,
                    'proxy': proxy, 'proxy_failed': True
                }
            
            # 处理登录验证码：同时检测验证码 iframe、URL 跳转和 toast 错误提示
            # 密码错误时 API 快速返回 400 → 页面弹出 Vue-Toastification toast（仅存在约5秒）
            # 必须在验证码等待期间同时轮询 toast，否则等验证码超时后 toast 早已消失
            # toast xpath: /html/body/div[4]/div[2]/div/div/div[1]/div/div/div/div/small
            TOAST_ERROR_XPATH = '/html/body/div[4]/div[2]/div/div/div[1]/div/div/div/div/small'
            _login_error_keywords = ("密码错误", "账号不存在", "用户名或密码", "登录失败",
                                     "账户或密码", "账号或密码", "验证失败")
            _captcha_deadline = time.time() + 30
            captcha_handled = False
            while time.time() < _captcha_deadline:
                # 检测 URL 跳转（登录成功，无需验证码）
                if "/dashboard" in driver.current_url or "/account" in driver.current_url:
                    break
                # 检测 toast 错误提示（密码错误时快速出现，5秒后消失）
                try:
                    toast_elems = driver.find_elements(By.XPATH, TOAST_ERROR_XPATH)
                    for el in toast_elems:
                        toast_text = el.text or ""
                        if any(kw in toast_text for kw in _login_error_keywords):
                            fail_reason = f"账号或密码错误（{toast_text}），请检查环境变量/GitHub Secrets 中的 RAINYUN_USERNAME / RAINYUN_PASSWORD"
                            logger_adapter.error(f"登录失败: {fail_reason}")
                            screenshot_path = save_screenshot(driver, current_user, status="failure")
                            return {
                                'status': False, 'msg': fail_reason, 'points': 0,
                                'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                                'retries': retry_stats['count'], 'screenshot': screenshot_path,
                                'proxy': proxy, 'proxy_failed': False
                            }
                except Exception:
                    pass
                # 检测验证码 iframe
                try:
                    captcha_elems = driver.find_elements(By.ID, 'tcaptcha_iframe_dy')
                    if captcha_elems and captcha_elems[0].is_displayed():
                        logger_adapter.warning("触发验证码！")
                        driver.switch_to.frame("tcaptcha_iframe_dy")
                        captcha_provider = CaptchaFactory.create_provider("tencent")
                        captcha_provider.solve(driver, timeout, retry_stats, logger_adapter)
                        captcha_handled = True
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            if not captcha_handled:
                logger_adapter.info("未触发验证码")

            driver.switch_to.default_content()
            dismiss_modal_confirm(driver, timeout)

            # 等待登录结果：轮询同时检测 URL 跳转（成功）和 toast 错误提示（密码错误）
            # 验证码处理完成后，登录请求可能仍在进行中，继续轮询30秒
            def _check_login_result(d):
                """返回 'success' / ('error', msg) / None（继续等待）"""
                if "/dashboard" in d.current_url or "/account" in d.current_url:
                    return "success"
                try:
                    toast_elems = d.find_elements(By.XPATH, TOAST_ERROR_XPATH)
                    for el in toast_elems:
                        toast_text = el.text or ""
                        if any(kw in toast_text for kw in _login_error_keywords):
                            return ("error", toast_text)
                except Exception:
                    pass
                return None

            try:
                login_outcome = WebDriverWait(driver, 30).until(_check_login_result)
                if login_outcome == "success":
                    logger_adapter.info("登录成功！")
                    save_cookies(driver, current_user)
                    safe_get(driver, "https://app.rainyun.com/account/reward/earn")
                    time.sleep(2)
                else:
                    # 页面显示了 toast 错误提示 → 账号密码错误，非代理问题
                    toast_msg = login_outcome[1] if isinstance(login_outcome, tuple) else ""
                    fail_reason = f"账号或密码错误（{toast_msg}），请检查环境变量/GitHub Secrets 中的 RAINYUN_USERNAME / RAINYUN_PASSWORD"
                    logger_adapter.error(f"登录失败: {fail_reason}")
                    screenshot_path = save_screenshot(driver, current_user, status="failure")
                    return {
                        'status': False, 'msg': fail_reason, 'points': 0,
                        'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                        'retries': retry_stats['count'], 'screenshot': screenshot_path,
                        'proxy': proxy, 'proxy_failed': False
                    }
            except TimeoutException:
                # 30秒内既没有跳转也没有 toast 错误 → 登录请求未完成 → 代理过慢
                if "/auth/login" in driver.current_url:
                    if current_user in ("username", "") or current_pwd in ("password", ""):
                        fail_reason = "未配置雨云账号密码（请检查环境变量/GitHub Secrets: RAINYUN_USERNAME / RAINYUN_PASSWORD）"
                        is_proxy_fail = False
                    elif proxy:
                        fail_reason = "代理过慢导致登录超时（30秒内无跳转且无错误提示），已标记代理失败将换新代理重试"
                        is_proxy_fail = True
                    else:
                        fail_reason = "登录超时（30秒内无跳转且无错误提示），请检查网络或账号密码"
                        is_proxy_fail = False
                else:
                    fail_reason = f"登录后跳转异常（当前页面: {driver.current_url}）"
                    is_proxy_fail = False
                logger_adapter.error(f"登录失败: {fail_reason}")
                screenshot_path = save_screenshot(driver, current_user, status="failure")
                return {
                    'status': False, 'msg': fail_reason, 'points': 0,
                    'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
                    'retries': retry_stats['count'], 'screenshot': screenshot_path,
                    'proxy': proxy, 'proxy_failed': is_proxy_fail
                }
        else:
            logger_adapter.info("Cookie 有效，免密登录成功！🎉")
        
        # 确保在积分页
        if "/account/reward/earn" not in driver.current_url:
            safe_get(driver, "https://app.rainyun.com/account/reward/earn")

        driver.implicitly_wait(5)
        time.sleep(1)
        dismiss_modal_confirm(driver, timeout)
        dismiss_modal_confirm(driver, timeout)
        
        # 每日签到按钮 xpath：通过父级 span[1] 文字"每日签到"精确定位，
        # 避免误匹配"关注雨云"旁边同样显示"领取奖励"的按钮。
        # 注意：末尾用 span[2] 而非 span[2]/a —— 签到完成后按钮变为"已完成"，
        # 此时 span[2] 下没有 <a> 子元素，带 /a 会抛 NoSuchElementException。
        CHECKIN_BTN_XPATH = '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div//div/div[1]/div[span[1][normalize-space(text())="每日签到"]]/span[2]'
        earn = driver.find_element(By.XPATH, CHECKIN_BTN_XPATH)
        btn_text = earn.text.strip()
        logger_adapter.info(f"签到按钮文字: [{btn_text}]")

        # 只有"领取奖励"才需要点击，其他情况视为已完成
        if btn_text == "领取奖励":
            logger_adapter.info("点击领取奖励")
            # 优先点击 span 内的 <a> 链接，无 <a> 时点击 span 本身
            links = earn.find_elements(By.XPATH, "./a")
            if links:
                links[0].click()
            else:
                earn.click()
            state = wait_captcha_or_modal(driver, timeout)
            if state == "captcha":
                logger_adapter.info("处理验证码")
                try:
                    captcha_iframe = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[id^='tcaptcha_iframe']")))
                    driver.switch_to.frame(captcha_iframe)
                    captcha_provider = CaptchaFactory.create_provider("tencent")
                    captcha_provider.solve(driver, timeout, retry_stats, logger_adapter)
                finally:
                    driver.switch_to.default_content()
                driver.implicitly_wait(5)
            else:
                logger_adapter.info("未触发验证码")
            
            # 轮询等待按钮变为"已完成"：点击后可能因网络问题导致验证码弹窗（t_verify 三个点加载框）
            # 迟迟未加载出 tcaptcha_iframe，wait_captcha_or_modal 误判为"未触发验证码"。
            # 此时按钮仍为"领取奖励"，需检测 t_verify 加载框并等待真正的验证码弹窗出现后处理。
            poll_deadline = time.time() + 60
            while time.time() < poll_deadline:
                time.sleep(3)
                try:
                    earn = driver.find_element(By.XPATH, CHECKIN_BTN_XPATH)
                    btn_text = earn.text.strip()
                except Exception:
                    btn_text = ""

                if btn_text == "已完成":
                    logger_adapter.info("按钮已变为「已完成」，签到确认成功")
                    break
                if btn_text != "领取奖励":
                    logger_adapter.info(f"按钮显示「{btn_text}」，视为签到已完成")
                    break

                # 按钮仍为"领取奖励"：检查验证码加载框（三个点）是否在加载
                t_verify_elems = driver.find_elements(By.CSS_SELECTOR, "div#t_verify")
                if t_verify_elems:
                    logger_adapter.info("检测到验证码加载框（三个点）仍在加载，等待验证码弹窗出现...")
                    try:
                        captcha_iframe = wait.until(EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, "iframe[id^='tcaptcha_iframe']")))
                        driver.switch_to.frame(captcha_iframe)
                        captcha_provider = CaptchaFactory.create_provider("tencent")
                        captcha_provider.solve(driver, timeout, retry_stats, logger_adapter)
                    except TimeoutException:
                        logger_adapter.warning("等待验证码弹窗超时，验证码可能已消失")
                    finally:
                        driver.switch_to.default_content()
                    driver.implicitly_wait(5)
                    logger_adapter.info("验证码处理完成，继续检查签到状态")
                else:
                    logger_adapter.warning("按钮仍为「领取奖励」且无验证码加载框，继续等待...")
            else:
                logger_adapter.warning("轮询等待签到完成超时（60秒），继续后续流程")
        else:
            logger_adapter.info(f"今日已签到（按钮显示: {btn_text}）")

        
        points_raw = driver.find_element(By.XPATH,
                                         '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute(
            "textContent")
        import re
        current_points = int(''.join(re.findall(r'\d+', points_raw)))
        if not os.getenv('CI'):
            logger_adapter.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
        logger_adapter.info("签到任务执行成功！")
        # 保存成功截图
        screenshot_path = save_screenshot(driver, current_user, status="success")
        return {
            'status': True,
            'msg': '签到成功',
            'points': current_points,
            'username': f"{current_user[:3]}***{current_user[-3:] if len(current_user) > 6 else current_user}",
            'retries': retry_stats['count'],
            'screenshot': screenshot_path,
            'proxy': proxy
        }
            
    except Exception as e:
        error_msg = str(e)
        # 判断异常是否由代理引起（ERR_PROXY_CONNECTION_FAILED、renderer 超时等）
        is_proxy_error = any(kw in error_msg for kw in (
            "ERR_PROXY", "ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED",
            "ERR_TIMED_OUT", "ERR_CONNECTION", "Timed out receiving message from renderer"
        ))
        # 代理环境下，元素找不到通常是代理过慢导致页面 JS 未完整渲染
        if proxy and not is_proxy_error and "no such element" in error_msg.lower():
            is_proxy_error = True
        logger_adapter.error(f"签到任务执行失败: {e}")
        import traceback
        logger_adapter.error(f"详细错误信息: {traceback.format_exc()}")
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
            'screenshot': screenshot_path,
            'proxy': proxy,
            'proxy_failed': is_proxy_error
        }
    finally:
        # 确保在任何情况下都关闭 WebDriver
        if driver is not None:
            try:
                logger_adapter.info("正在关闭 WebDriver...")
                
                # 首先尝试正常关闭
                try:
                    driver.quit()
                    logger_adapter.info("WebDriver 已安全关闭")
                except Exception as e:
                    logger_adapter.error(f"关闭 WebDriver 时出错: {e}")
                
                # 等待一小段时间让进程完全退出
                time.sleep(1)
                
                # 强制终止 ChromeDriver 进程及其子进程
                try:
                    if hasattr(driver, 'service') and driver.service.process:
                        process = driver.service.process
                        pid = process.pid
                        
                        # 1. 先尝试杀掉该 ChromeDriver 衍生的子进程 (Chrome 浏览器)
                        # 避免僵尸 Chrome 进程残留
                        if os.name == 'posix' and pid:
                            try:
                                # pkill -P <pid> 仅杀掉指定父进程的子进程
                                logger_adapter.info(f"正在清理 PID {pid} 的衍生进程...")
                                subprocess.run(['pkill', '-9', '-P', str(pid)], 
                                             stderr=subprocess.DEVNULL)
                            except Exception:
                                pass

                        # 2. 再杀掉 ChromeDriver 本身
                        if process.poll() is None:  # 进程仍在运行
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                            logger_adapter.info(f"已终止 ChromeDriver 进程 (PID: {pid})")
                except Exception as e:
                    logger_adapter.debug(f"清理 ChromeDriver 进程时出错: {e}")
                

                        
            except Exception as e:
                logger_adapter.error(f"WebDriver 清理过程出现异常: {e}")
        
        # 卸载Selenium模块，释放内存
        try:
            unload_selenium_modules()
            logger.debug("已卸载Selenium模块")
        except:
            pass


def scheduled_checkin():
    """定时任务包装器"""
    logger.info(f"定时任务触发 - {now_local().strftime('%Y-%m-%d %H:%M:%S')}")
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
    current_time = now_local()
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
    ver = "2.3"
    logger.info("===================================================================")
    logger.info(f"🌧️ Rainyun-Qiandao v{ver} (Selenium)")
    logger.info("👨‍💻 Based on original project by: SerendipityR-2022")
    logger.info("🚀 Maintained & Extended by: LeapYa")
    logger.info("🔗 GitHub: https://github.com/LeapYa/Rainyun-Qiandao")
    logger.info("💡 开源不易，感谢原作者。请二、三次修改者能够保留源出处，谢谢！")
    logger.info("===================================================================")
    print("")
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
        logger.info(f"当前应用时区: {get_app_timezone_name()}")
        
        # 设置每日定时任务
        schedule.every().day.at(schedule_time).do(scheduled_checkin)
        
        # 显示每日定时任务时间
        tomorrow_schedule = now_local().replace(hour=int(schedule_time.split(':')[0]),
                                               minute=int(schedule_time.split(':')[1]),
                                               second=0, microsecond=0)
        if tomorrow_schedule <= now_local():
            tomorrow_schedule += timedelta(days=1)
        logger.info(f"每日执行时间: {tomorrow_schedule.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 首次启动1分钟后执行一次
        logger.info("首次启动，将在1分钟后执行首次签到任务")
        first_run_time = now_local() + timedelta(minutes=1)
        logger.info(f"首次执行时间: {first_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 持续运行检查定时任务
        logger.info("调度器已启动，等待执行任务...")
        first_run_done = False
        
        try:
            while True:
                current_time = now_local()
                
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
                    time_diff = tomorrow_schedule - now_local()
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
            sys.exit(1)
