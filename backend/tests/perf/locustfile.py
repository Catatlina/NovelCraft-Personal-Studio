"""P2-T7 真实负载压测基线 (Locust)。

只读型基线负载脚本：对核心读端点施加并发，验证 P95 延迟与错误率落在 SLO 内。
写入型端点（生成/发布）默认排除，避免压测污染真实数据与配额。

本地运行（需可用后端 + 测试用户令牌）：
    locust -f backend/tests/perf/locustfile.py --host https://novel.xyjin.xyz -u 50 -r 10 -t 2m

环境变量：
    NC_API_KEY  测试用户 X-Api-Key（注入到请求头）
"""
from __future__ import annotations

import os

from locust import HttpUser, between, task


API_KEY = os.getenv("NC_API_KEY", "")


class NovelCraftReadUser(HttpUser):
    """模拟真实用户浏览：概览/扫榜/书库等只读操作。"""

    wait_time = between(1, 3)

    def on_start(self):
        self.headers = {"X-Api-Key": API_KEY} if API_KEY else {}

    @task(5)
    def dashboard_overview(self):
        self.client.get("/api/v1/analytics/dashboard", headers=self.headers, name="GET /dashboard")

    @task(3)
    def ranking_snapshots(self):
        self.client.get("/api/v1/ranking/snapshots", headers=self.headers, name="GET /ranking/snapshots")

    @task(2)
    def library_list(self):
        self.client.get("/api/v1/library", headers=self.headers, name="GET /library")

    @task(1)
    def health(self):
        self.client.get("/api/v1/health", name="GET /health")
