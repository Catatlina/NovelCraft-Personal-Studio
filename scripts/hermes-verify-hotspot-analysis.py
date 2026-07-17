#!/usr/bin/env python3
"""Verify hotspot + ten-layer analysis + API changes (AST + signature audit)."""
import ast, os, sys

BASE = "/Users/genius/NovelCraft Personal Studio"
errors = []

backend_files = [
    "backend/app/services/ten_layer_analysis.py",
    "backend/app/services/hotspot_collector.py",
    "backend/app/api/v1/hotspots.py",
    "backend/app/api/v1/ranking.py",
]
print("── Backend AST ──")
for f in backend_files:
    path = os.path.join(BASE, f)
    try:
        ast.parse(open(path).read())
        print(f"  OK  {f.split('/')[-1]}")
    except SyntaxError as e:
        errors.append(f"AST FAIL: {f} — {e}")

# ── ten_layer_analysis ──
print("── Ten-Layer Analyzer ──")
tta_path = os.path.join(BASE, backend_files[0])
tta_tree = ast.parse(open(tta_path).read())
tta_funcs = {n.name for n in ast.walk(tta_tree) if isinstance(n, ast.FunctionDef)}
layers = [f"analyze_{x}" for x in [
    "book_profile", "genre_report", "selling_points", "golden_3_chapter",
    "plot_rhythm", "characters", "world_building", "style_report",
    "reader_report", "ai_insight",
]]
for l in layers:
    status = "✓" if l in tta_funcs else "✗ MISSING"
    print(f"  {status}  {l}")
    if l not in tta_funcs: errors.append(l)
status = "✓" if "analyze" in tta_funcs else "✗"
print(f"  {status}  analyze (batch runner)")

# ── hotspot collector ──
print("── Hotspot Collector ──")
hc_src = open(os.path.join(BASE, backend_files[1])).read()
for s in ["toutiao", "kuaishou", "bilibili", "google_trends_cn"]:
    ok = f'"{s}"' in hc_src
    print(f"  {'✓' if ok else '✗'}  source: {s}")
    if not ok: errors.append(f"source:{s}")
hc_tree = ast.parse(hc_src)
hc_funcs = {n.name for n in ast.walk(hc_tree) if isinstance(n, ast.FunctionDef)}
for f in ["get_hotspot_overview", "get_hotspots_paginated", "PLATFORM_DISPLAY", "PLATFORM_CATEGORIES"]:
    ok = f in hc_funcs or f in hc_src
    print(f"  {'✓' if ok else '✗'}  {f}")
    if not ok: errors.append(f)

# ── hotspots API ──
print("── Hotspots API ──")
hapi_src = open(os.path.join(BASE, backend_files[2])).read()
for r in ['/hotspots/overview', '/hotspots/paginated', '/articles', '/articles/{article_id}']:
    ok = r in hapi_src
    print(f"  {'✓' if ok else '✗'}  route: {r}")
    if not ok: errors.append(f"route:{r}")

# ── ranking API ──
print("── Ranking API ──")
rank_src = open(os.path.join(BASE, backend_files[3])).read()
for r in ['/analyze', '/topics/{topic_id}/bookmark', '/topics/batch-delete', '/topics/bookmarked']:
    ok = r in rank_src
    print(f"  {'✓' if ok else '✗'}  route: {r}")
    if not ok: errors.append(f"route:{r}")

# ── Frontend ──
print("── Frontend Components ──")
hd = open(os.path.join(BASE, "frontend/src/components/HotspotDashboard.tsx")).read()
for f in ["selectedPlatforms", "loadOverview", "viewArticle", "deleteArticle", '"hotspots"', '"overview"', '"library"']:
    ok = f in hd
    print(f"  HotspotDashboard {'✓' if ok else '✗'}  {f}")
    if not ok: errors.append(f"HD:{f}")

rc = open(os.path.join(BASE, "frontend/src/components/RankingCenter.tsx")).read()
for f in ["toggleBookmark", "deleteTopic", "batchDeleteAll", "loadBookmarked", "topicTab"]:
    ok = f in rc
    print(f"  RankingCenter {'✓' if ok else '✗'}  {f}")
    if not ok: errors.append(f"RC:{f}")

bl = open(os.path.join(BASE, "frontend/src/components/BookLibrary.tsx")).read()
for f in ["deleteBook", "batchDelete", "selectedBooks", "deleteConfirm", "Trash2"]:
    ok = f in bl
    print(f"  BookLibrary {'✓' if ok else '✗'}  {f}")
    if not ok: errors.append(f"BL:{f}")

# ── Result ──
print(f"\n{'='*50}")
if errors:
    print(f"FAIL: {len(errors)} issues")
    for e in errors: print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
