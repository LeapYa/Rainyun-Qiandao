import logging
import os
import random
import re
import time
import schedule
import signal
import subprocess
from datetime import datetime, timedelta

import cv2
import ddddocr
import requests
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def cleanup_zombie_processes():
    """清理可能残留的 Chrome/ChromeDriver 僵尸进程"""
    try:
        if os.name == 'posix':  # Linux/Unix 系统
            # 查找并清理僵尸 chrome 和 chromedriver 进程
            try:
                result = subprocess.run(['pgrep', '-f', 'chrome|chromedriver'], 
                                      capture_output=True, text=True, timeout=5)
                if result.stdout:
                    pids = result.stdout.strip().split('\n')
                    zombie_count = 0
                    for pid in pids:
                        if pid:
                            try:
                                # 检查进程状态
                                stat_result = subprocess.run(['ps', '-p', pid, '-o', 'stat='], 
                                                           capture_output=True, text=True, timeout=2)
                                if 'Z' in stat_result.stdout:  # 僵尸进程
                                    zombie_count += 1
                                    logger.warning(f"发现僵尸进程 PID: {pid}")
                            except:
                                pass
                    
                    if zombie_count > 0:
                        logger.info(f"检测到 {zombie_count} 个僵尸进程")
                        # 尝试清理孤儿进程（非僵尸但可能是残留的）
                        subprocess.run(['pkill', '-9', '-f', 'chrome.*--type='], 
                                     timeout=5, stderr=subprocess.DEVNULL)
                        logger.info("已尝试清理残留的 Chrome 子进程")
            except subprocess.TimeoutExpired:
                logger.warning("进程清理超时")
            except FileNotFoundError:
                # pgrep/pkill 命令不存在，跳过
                pass
            except Exception as e:
                logger.debug(f"清理进程时出现异常（可忽略）: {e}")
    except Exception as e:
        logger.debug(f"僵尸进程清理失败（可忽略）: {e}")


def get_random_user_agent():
    """获取随机 User-Agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ]
    return random.choice(user_agents)


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
    
    accounts = parse_accounts()
    success_count = 0
    
    for i, (username, password) in enumerate(accounts, 1):
        logger.info(f"========== 开始执行第 {i}/{len(accounts)} 个账号签到 ==========")
        success = run_checkin(username, password)
        
        if success:
            success_count += 1
            logger.info(f"✅ 账号 {i} 签到成功")
        else:
            logger.error(f"❌ 账号 {i} 签到失败")
        
        # 每个账号执行后清理一次
        cleanup_zombie_processes()
        
        # 账号间延时（避免频繁操作）
        if i < len(accounts):  # 不是最后一个账号
            delay = random.randint(30, 120)  # 30-120秒随机延时
            logger.info(f"账号间延时等待 {delay} 秒...")
            time.sleep(delay)
    
    logger.info(f"========== 所有账号签到完成: {success_count}/{len(accounts)} 成功 ==========")
    
    # 任务结束后再次清理
    logger.info("任务完成，执行最终清理...")
    cleanup_zombie_processes()
    
    return success_count > 0


def init_selenium() -> WebDriver:
    ops = Options()
    ops.add_argument("--no-sandbox")
    ops.add_argument("--disable-dev-shm-usage")  # Docker 环境优化
    ops.add_argument("--disable-extensions")
    ops.add_argument("--disable-plugins")
    
    # 添加随机 User-Agent
    user_agent = get_random_user_agent()
    ops.add_argument(f"--user-agent={user_agent}")
    logger.info(f"使用 User-Agent: {user_agent[:50]}...")  # 只显示前50个字符
    
    if debug:
        ops.add_experimental_option("detach", True)
    
    if linux:
        ops.add_argument("--headless")
        ops.add_argument("--disable-gpu")
        
        # Selenium 官方镜像的 ChromeDriver 路径
        chromedriver_path = "/usr/bin/chromedriver"
        
        logger.info(f"使用 Selenium 镜像的 ChromeDriver: {chromedriver_path}")
        service = Service(chromedriver_path)
        return webdriver.Chrome(service=service, options=ops)
    else:
        # Windows 环境
        service = Service("chromedriver.exe")
        return webdriver.Chrome(service=service, options=ops)


def download_image(url, filename):
    os.makedirs("temp", exist_ok=True)
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        path = os.path.join("temp", filename)
        with open(path, "wb") as f:
            f.write(response.content)
        return True
    else:
        logger.error("下载图片失败！")
        return False


def get_url_from_style(style):
    return re.search(r'url\(["\']?(.*?)["\']?\)', style).group(1)


def get_width_from_style(style):
    return re.search(r'width:\s*([\d.]+)px', style).group(1)


def get_height_from_style(style):
    return re.search(r'height:\s*([\d.]+)px', style).group(1)


def process_captcha(driver, timeout):
    try:
        wait = WebDriverWait(driver, timeout)
        download_captcha_img(driver, timeout)
        if check_captcha():
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
            else:
                logger.error("验证码识别失败，正在重试")
        else:
            logger.error("当前验证码识别率低，尝试刷新")
        reload = driver.find_element(By.XPATH, '//*[@id="reload"]')
        time.sleep(5)
        reload.click()
        time.sleep(5)
        process_captcha(driver, timeout)
    except TimeoutException:
        logger.error("获取验证码图片失败")


def download_captcha_img(driver, timeout):
    wait = WebDriverWait(driver, timeout)
    if os.path.exists("temp"):
        for filename in os.listdir("temp"):
            file_path = os.path.join("temp", filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
    slideBg = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="slideBg"]')))
    img1_style = slideBg.get_attribute("style")
    img1_url = get_url_from_style(img1_style)
    logger.info("开始下载验证码图片(1): " + img1_url)
    download_image(img1_url, "captcha.jpg")
    sprite = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="instruction"]/div/img')))
    img2_url = sprite.get_attribute("src")
    logger.info("开始下载验证码图片(2): " + img2_url)
    download_image(img2_url, "sprite.jpg")


def check_captcha() -> bool:
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


def run_checkin(account_user=None, account_pwd=None):
    """执行签到任务"""
    current_user = account_user or user
    current_pwd = account_pwd or pwd
    driver = None  # 初始化为 None，确保在任何情况下都能安全清理
    
    try:
        logger.info(f"开始执行签到任务... 账号: {current_user[:5]}***{current_user[-5:] if len(current_user) > 10 else current_user}")
        
        # 随机延时
        delay = random.randint(0, max_delay)
        delay_sec = random.randint(0, 60)
        if not debug:
            logger.info(f"随机延时等待 {delay} 分钟 {delay_sec} 秒")
            time.sleep(delay * 60 + delay_sec)
        
        logger.info("初始化 Selenium")
        driver = init_selenium()
        
        # 过 Selenium 检测
        with open("stealth.min.js", mode="r") as f:
            js = f.read()
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": js
        })
        
        logger.info("发起登录请求")
        driver.get("https://app.rainyun.com/auth/login")
        wait = WebDriverWait(driver, timeout)
        
        try:
            username = wait.until(EC.visibility_of_element_located((By.NAME, 'login-field')))
            password = wait.until(EC.visibility_of_element_located((By.NAME, 'login-password')))
            login_button = wait.until(EC.visibility_of_element_located((By.XPATH,
                                                                        '//*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button')))
            username.send_keys(current_user)
            password.send_keys(current_pwd)
            login_button.click()
        except TimeoutException:
            logger.error("页面加载超时，请尝试延长超时时间或切换到国内网络环境！")
            return False
        
        try:
            login_captcha = wait.until(EC.visibility_of_element_located((By.ID, 'tcaptcha_iframe_dy')))
            logger.warning("触发验证码！")
            driver.switch_to.frame("tcaptcha_iframe_dy")
            process_captcha(driver, timeout)
        except TimeoutException:
            logger.info("未触发验证码")
        
        time.sleep(5)
        driver.switch_to.default_content()
        
        if driver.current_url == "https://app.rainyun.com/dashboard":
            logger.info("登录成功！")
            logger.info("正在转到赚取积分页")
            driver.get("https://app.rainyun.com/account/reward/earn")
            driver.implicitly_wait(5)
            
            earn = driver.find_element(By.XPATH,
                                       '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a')
            logger.info("点击赚取积分")
            earn.click()
            logger.info("处理验证码")
            driver.switch_to.frame("tcaptcha_iframe_dy")
            process_captcha(driver, timeout)
            driver.switch_to.default_content()
            driver.implicitly_wait(5)
            
            points_raw = driver.find_element(By.XPATH,
                                             '//*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3').get_attribute(
                "textContent")
            current_points = int(''.join(re.findall(r'\d+', points_raw)))
            logger.info(f"当前剩余积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
            logger.info("签到任务执行成功！")
            return True
        else:
            logger.error("登录失败！")
            return False
            
    except Exception as e:
        logger.error(f"签到任务执行失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return False
    finally:
        # 确保在任何情况下都关闭 WebDriver
        if driver is not None:
            try:
                logger.info("正在关闭 WebDriver...")
                driver.quit()
                logger.info("WebDriver 已安全关闭")
            except Exception as e:
                logger.error(f"关闭 WebDriver 时出错: {e}")
                # 尝试强制终止进程
                try:
                    driver.service.process.kill()
                    logger.warning("已强制终止 ChromeDriver 进程")
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

    # 初始化日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    ver = "2.2-scheduler"
    logger.info("------------------------------------------------------------------")
    logger.info(f"雨云签到工具 v{ver} by SerendipityR ~")
    logger.info("Github发布页: https://github.com/SerendipityR-2022/Rainyun-Qiandao")
    logger.info("------------------------------------------------------------------")
    
    # 初始化OCR
    logger.info("初始化 ddddocr")
    ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
    det = ddddocr.DdddOcr(det=True, show_ad=False)
    
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