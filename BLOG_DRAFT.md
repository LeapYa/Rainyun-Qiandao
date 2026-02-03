---
title: 2026年教你 0 元搭建雨云自动签到任务
date: 2026-02-03 14:05:00
categories: 
  - 折腾记录
tags: 
  - 雨云
  - 自动签到
  - GitHub Actions
  - 白嫖
  - Python
---

# 2026年教你 0 元搭建雨云自动签到任务

众所周知，雨云（Rainyun）的签到能领积分，积分能换主机。但是每天手动签到太麻烦，买台服务器挂脚本又有点"杀鸡焉用牛刀"（而且甚至可能签到的积分还不够服务器钱😂）。

今天教大家一个 **完全免费**、**无需服务器**、**全自动** 的方案 —— 利用 **GitHub Actions** 实现每日自动签到！

## 🤔 为什么选择这个方案？

| 方案 | 成本 | 难度 | 稳定性 |
|------|------|------|--------|
| 本地电脑挂机 | 电费感人 | 低 | 关机就没 |
| 买 VPS 挂机 | 几十块/月 | 中 | 高 |
| **GitHub Actions** | **$0 (永久免费)** | **低** | **极高** |

是的，你没看错，利用 GitHub 提供的免费 CI/CD 资源，我们可以每天定时白嫖一台服务器帮我们跑脚本，跑完即焚，不花一分钱！

## ✨ 项目亮点

这个脚本 ([Rainyun-Qiandao](https://github.com/LeapYa/Rainyun-Qiandao)) 已经针对 Actions 做了深度优化：

1.  **自动过验证**：内置 Selenium + ddddocr，自动识别滑动/文字验证码。
2.  **Cookie 持久化**：利用 Actions Cache 缓存登录凭证，避免每天重复登录风控。
3.  **多渠道通知**：支持 微信(PushPlus/WXPusher)、钉钉、邮件 推送签到结果。
4.  **无头模式**：专门适配 Linux 服务器环境，内存占用低。
5.  **失败重试**：网络波动？验证码没过？自动重试直到成功！

## 🛠️ 3步搭建教程

### 第一步：Fork 项目

访问项目仓库：[https://github.com/LeapYa/Rainyun-Qiandao](https://github.com/LeapYa/Rainyun-Qiandao)
点击右上角的 **Fork** 按钮，把项目克隆到你自己的账号下。

### 第二步：配置账号密码

在你的仓库页面，点击 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。

添加以下 Secrets（**安全提示：这里填写的密码是加密存储的，连你自己都看不见，非常安全**）：

-   `RAINYUN_USERNAME`: 你的雨云账号
-   `RAINYUN_PASSWORD`: 你的雨云密码

*(可选) 如果需要通知，可以再加一个 `PUSHPLUS_TOKEN` 等配置，详见项目文档。*

### 第三步：启用 Action

1.  点击 `Actions` 标签页。
2.  可能会看到一个绿色按钮 "I understand my workflows, go ahead and enable them"，点击它。
3.  左侧选择 "雨云每日签到"。
4.  点击右侧的 `Run workflow` 手动测试一次。

🎉 **大功告成！**
以后每天早上 8:00（北京时间），GitHub 就会自动派一台服务器帮你签到，并把结果推送到你手机上！

## 📝 避坑指南

1.  **账号被锁？** 确保你的 Secrets 没填错，特别是多账号要用 `|` 分隔。
2.  **中文乱码？** 项目已经贴心地内置了中文字体安装步骤，截图通知再也不会全是方框了！
3.  **一直运行不结束？** 我们专门加了 `RUN_MODE: once` 配置，签到完自动退出，不会浪费 Actions 分钟数。

---

**最后：**
既然都白嫖了，别忘了给原作者的仓库点个 **Star** ⭐ 哦！
仓库地址：[https://github.com/LeapYa/Rainyun-Qiandao](https://github.com/LeapYa/Rainyun-Qiandao)

#Rainyun #自动签到 #GitHubActions #白嫖 #Python
