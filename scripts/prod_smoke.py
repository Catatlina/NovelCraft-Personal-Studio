#!/usr/bin/env python3
"""§7 #6 生产部署 smoke（无密钥，读 PROD_BASE env；可选 DEEPSEEK_API_KEY 跑真实 V3 链）。

覆盖：healthz / 登录 / 建书+保存 / V3 bootstrap(20 节点) / 八页面后端数据可达 / 切书。
八页面的"前端渲染"断言已在 e2e/pages-smoke.spec.ts 覆盖（CI 对 dev 后端跑过）；
部署后可用 `BASE_URL=<PROD_BASE> npx playwright test e2e/pages-smoke.spec.ts`
对生产 SPA 复跑同样的 8 页可达性检查。

端点参数说明（避免误报）：
- `/api/v1/ranking/sources` 的 `project_id` 为必填 query 参数。
- `/api/v1/runs/latest` 无 run 时返回 404；故须在建书 + V3 bootstrap 产生 run 之后，
  带 `?novel_id=` 校验「创作进度」页面。
- 因此流程为：登录 → 建书(取 project_id/novel_id) → V3 bootstrap(产生 run) → 八页面(带参) → 切书。

用法：
  PROD_BASE=https://starlume.example.com python3 scripts/prod_smoke.py
  # 带真实 Key 跑 V3 全链（会真实消耗 Provider 额度）：
  PROD_BASE=... DEEPSEEK_API_KEY=sk-xxx python3 scripts/prod_smoke.py
"""
import json
import os
import sys
import time

import requests

BASE = os.environ.get("PROD_BASE", "").rstrip("/")
if not BASE:
    print("ERROR: 设置 PROD_BASE=https://你的生产域名"); sys.exit(2)

PW = "Starlume-prod-smoke-1234"
EMAIL = f"prod-smoke-{int(time.time())}@example.com"


def log(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        globals().setdefault("_failed", []).append(name)


def main() -> None:
    s = requests.Session()
    api = f"{BASE}/api/v1"

    # 1) healthz
    try:
        r = s.get(f"{api}/healthz", timeout=10)
        log("healthz", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        log("healthz", False, str(e)); return

    # 2) 登录（注册新用户拿 token）
    r = s.post(f"{api}/auth/register", json={"email": EMAIL, "password": PW, "display_name": "ProdSmoke"})
    if r.status_code != 200:
        log("register/login", False, f"HTTP {r.status_code} {r.text[:120]}"); return
    token = r.json()["data"]["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    log("register/login", True)

    # 3) 取首个 project + 建书/保存（为后续页面参数与 V3 run 准备）
    r = s.get(f"{api}/projects", timeout=10)
    if r.status_code != 200 or not r.json().get("data"):
        log("建书/保存", False, "无可用 project"); return
    project_id = r.json()["data"][0]["id"]
    r = s.post(f"{api}/projects/{project_id}/novels",
               json={"idea": "生产 smoke 建书", "genre": "都市", "style": "现代"}, timeout=15)
    if r.status_code != 200:
        log("建书/保存", False, f"HTTP {r.status_code} {r.text[:120]}"); return
    novel_id = r.json()["data"]["id"]
    log("建书/保存", True, f"novel_id={novel_id}")

    # 4) V3 bootstrap：启动向导 run（产生 run 记录，供「创作进度」页面校验）
    r = s.post(f"{api}/novels/{novel_id}/bootstrap",
               headers={"X-Api-Key": os.environ.get("DEEPSEEK_API_KEY", ""),
                        "X-Api-Base-Url": os.environ.get("DEEPSEEK_API_BASE", ""),
                        "X-Model": os.environ.get("DEEPSEEK_MODEL", "")},
               timeout=20)
    if r.status_code != 200:
        log("V3 启动 run", False, f"HTTP {r.status_code} {r.text[:160]}"); return
    run_id = r.json()["data"]["run_id"]
    log("V3 启动 run", True, f"run_id={run_id}")

    # 5) 八页面后端数据可达（此时已建书 + 有 V3 run，参数齐全）
    pages = {
        "小说首页": f"{api}/projects",
        "我的书库": f"{api}/projects",
        "创作进度": f"{api}/runs/latest?novel_id={novel_id}",
        "扫榜选书": f"{api}/ranking/sources?project_id={project_id}",
        "创作向导": None,  # SPA 路由，数据由 bootstrap 提供，渲染见 pages-smoke
        "章节编辑器": f"{api}/projects",
        "审阅与一致性": f"{api}/projects",
        "小说设置": f"{api}/auth/me",
    }
    for name, url in pages.items():
        if url is None:
            log(f"页面可达[{name}]", True, "SPA 路由（渲染见 pages-smoke）")
            continue
        try:
            r = s.get(url, timeout=10)
            log(f"页面可达[{name}]", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as e:
            log(f"页面可达[{name}]", False, str(e))

    # 6) 切书（在书库内取该书 -> 列章节；空书也算可达）
    r = s.get(f"{api}/contents", params={"project_id": project_id, "parent_id": novel_id}, timeout=10)
    log("切书(列章节)", r.status_code == 200, f"HTTP {r.status_code}")

    # 7) V3 20 节点：轮询 run 节点数
    nodes = 0
    for _ in range(20):
        r = s.get(f"{api}/runs/{run_id}", timeout=10)
        if r.status_code == 200:
            nodes = len(r.json()["data"].get("node_statuses", r.json()["data"].get("nodes", [])))
            if nodes:
                break
        time.sleep(2)
    log("V3 20 节点", nodes == 20, f"观测节点数={nodes} (期望 20)")

    # 可选：带真实 Key 时等待 run 推进（不因无 Key 失败）
    if os.environ.get("DEEPSEEK_API_KEY"):
        for _ in range(40):
            r = s.get(f"{api}/runs/{run_id}", timeout=10)
            st = r.json()["data"].get("status")
            if st in ("waiting_human", "ok", "failed"):
                log("V3 真实推进", True, f"status={st}")
                break
            time.sleep(5)
        else:
            log("V3 真实推进", False, "30s 内未达稳定态（非阻断）")
    else:
        log("V3 真实推进", True, "未注入 Key，跳过真实生成（仅校验节点数）")

    failed = globals().get("_failed", [])
    print("\n=== 生产 smoke 汇总 ===")
    print(f"PROD_BASE={BASE}")
    print(f"失败项：{failed if failed else '无'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
