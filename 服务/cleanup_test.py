# -*- coding: utf-8 -*-
"""清理 cache 库测试数据"""
import sqlite3
import sys
sys.path.insert(0, r"F:\D\Android-Hook\服务")
import config

c = sqlite3.connect(config.CACHE_DB)
c.execute("DELETE FROM node_cache WHERE sec_uid='test_sec_uid_1'")
c.execute("DELETE FROM node_state WHERE sec_uid='test_sec_uid_1'")
c.execute("DELETE FROM req_log WHERE target='test_sec_uid_1'")
c.execute("DELETE FROM daily_stats")
c.commit()
c.close()
print("cleaned")
