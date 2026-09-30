# -*- coding: utf-8 -*-
"""在 server.py 中挂载 downloads router"""
import io

p = r"F:\D\Android-Hook\服务\server.py"
s = io.open(p, encoding="utf-8").read()

old = "import cache\nimport config\nimport huoxiao_client as hx\n\napp = FastAPI(title=\"火枭采集服务\", version=\"0.2.0\")"
new = ("import cache\nimport config\nimport huoxiao_client as hx\nimport downloads\n\n"
       "app = FastAPI(title=\"火枭采集服务\", version=\"0.2.0\")\napp.include_router(downloads.router)")
if old in s:
    s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("OK: downloads router mounted")
else:
    print("WARN: pattern not found")
