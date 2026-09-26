# -*- coding: utf-8 -*-
"""server.py 添加 vault/status 路由 + 面板主号预算卡"""
import io

p = r"F:\D\Android-Hook\服务\server.py"
s = io.open(p, encoding="utf-8").read()

# 1. vault 路由
old = '''@app.get("/v1/health")
def health_v1(x_api_key: str = Header("")):
    _check_key(x_api_key)
    return health()'''
new = '''@app.get("/v1/health")
def health_v1(x_api_key: str = Header("")):
    _check_key(x_api_key)
    return health()


@app.get("/v1/vault/status")
def vault_status_api(x_api_key: str = Header("")):
    """主号隔离：vault cookie 有效性检测（仅开发验真）"""
    _check_key(x_api_key)
    st = hx.vault_status()
    st["main_budget_used"] = cache.main_budget_used()
    st["main_budget_limit"] = config.MAIN_DAILY_BUDGET
    return {"code": 0, "data": st, "meta": {}}'''
assert old in s, "vault route pattern missing"
s = s.replace(old, new, 1)

# 2. 面板 overview 加主号预算卡
old2 = "card('活跃节点',ov.nodes_active)+card('缓存库',ov.cache_db_mb+'MB');"
new2 = ("card('活跃节点',ov.nodes_active)+card('缓存库',ov.cache_db_mb+'MB')+\n"
        "    card('主号预算',(ov.main_budget_used||0)+'/'+ov.main_budget_limit);")
assert old2 in s, "panel pattern missing"
s = s.replace(old2, new2, 1)

# 3. panel_overview 返回追加主号预算
old3 = '''    return {"code": 0, "data": cache.panel_overview()}'''
new3 = '''    ov = cache.panel_overview()
    ov["main_budget_used"] = cache.main_budget_used()
    ov["main_budget_limit"] = config.MAIN_DAILY_BUDGET
    return {"code": 0, "data": ov}'''
assert old3 in s, "overview pattern missing"
s = s.replace(old3, new3, 1)

io.open(p, "w", encoding="utf-8").write(s)
print("OK: vault route + panel budget card mounted")
