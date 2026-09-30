# -*- coding: utf-8 -*-
"""火枭服务配置"""
import os

BASE = r"F:\D\20-火枭"
OUT = os.path.join(BASE, "输出数据")
SERVICE = os.path.join(BASE, "服务")

HOST = "0.0.0.0"
PORT = 8100
API_KEY = "huoxiao-2026"          # 共享密钥（首版固定，后续可轮换）

# 缓存库（本地 SQLite，防重复劳动 + 防封核心）
CACHE_DB = os.path.join(OUT, "huoxiao_cache.db")

# 缓存 TTL（秒）
TTL_A = 7 * 24 * 3600     # A 类：用户信息/visibility/已采列表 —— 7 天
TTL_B = 3600              # B 类：detail 内容信号/直链 —— 1 小时

# 主号（开发验证专用）
# 原则：主号 = 验真仪器，仅开发期拿真实数据对照（如用户手动核对自己的收藏），
#       生产环境 100% 走游客池，主号不进生产链路。
MAIN_DAILY_BUDGET = 50    # 开发验证期主号每日硬顶

# 游客池参数
GUEST_MIN_INTERVAL = 1.5  # 游客请求最小间隔（秒）

# 下载落盘
VIDEO_DIR = os.path.join(OUT, "视频下载")
