"""星禾插件市场 — Plugin & Module Manager

Defines the module/plugin registry for the 星禾AI工作台 platform.
All features are plugins that can be installed, enabled, disabled, or uninstalled.

Plugin sources: builtin, github, marketplace.
"""
import json
from dataclasses import dataclass, field
from typing import Callable

from app.db import connect


@dataclass
class ModuleManifest:
    id: str
    name: str
    description: str
    category: str          # novel | content | ai | system | community
    version: str = "1.0.0"
    icon: str = "📦"
    source: str = "builtin"  # builtin | github | marketplace
    source_url: str = ""
    enabled: bool = True
    installed: bool = True
    depends_on: list[str] = field(default_factory=list)
    route: str = ""         # frontend route path
    component: str = ""     # React component name
    backend_module: str = ""  # Python module


# === All modules as plugins ===
MODULES: dict[str, ModuleManifest] = {}


def register(m: ModuleManifest):
    MODULES[m.id] = m


# ---- 小说创作 ----
register(ModuleManifest("novel-ranking", "扫榜选书", "多平台榜单采集与分析", "novel", icon="📊", route="ranking", component="RankingCenter", backend_module="ranking"))
register(ModuleManifest("novel-library", "书库管理", "书籍检索/导入/导出/删除", "novel", icon="📚", route="library", component="BookLibrary"))
register(ModuleManifest("novel-wizard", "灵感创作", "Bootstrap全自动成书", "novel", icon="✨", route="wizard", component="Wizard"))
register(ModuleManifest("novel-editor", "编辑器", "Tiptap富文本编辑器", "novel", icon="✏️", route="editor", component="Editor"))
register(ModuleManifest("novel-progress", "创作进度", "实时进度追踪", "novel", icon="📈", route="progress", component="Progress"))
register(ModuleManifest("novel-review", "审阅", "七维雷达图审校", "novel", icon="🔍", route="review", component="Review"))
register(ModuleManifest("novel-foreshadowing", "伏笔系统", "伏笔追踪与回收", "novel", icon="🔮", route="foreshadowing", component="ForeshadowingBoard"))
register(ModuleManifest("novel-version", "版本树", "内容版本管理与恢复", "novel", icon="🌲", route="versions", component="VersionTree"))
register(ModuleManifest("novel-publish", "发布中心", "多平台发布管理", "novel", icon="🚀", route="publish", component="PublishDashboard"))

# ---- 内容中心 ----
register(ModuleManifest("content-hotspot", "热点追踪", "多平台热点采集", "content", icon="🔥", route="hotspot", component="HotspotDashboard"))
register(ModuleManifest("content-studio", "内容工作室", "短篇/知识库创作", "content", icon="🎨", route="studio", component="Studio"))
register(ModuleManifest("content-knowledge", "知识库", "RAG向量检索知识库", "content", icon="🧠", route="knowledge", component="KnowledgeBrowser"))
register(ModuleManifest("content-fanout", "多平台分发", "跨平台内容分发", "content", icon="📡", route="fanout", component="FanoutMatrix"))

# ---- AI 平台 ----
register(ModuleManifest("ai-chat", "AI对话", "Copilot聊天助手", "ai", icon="💬", route="chat", component="AIChat"))
register(ModuleManifest("ai-prompts", "Prompt管理", "Prompt版本化管理", "ai", icon="📝", route="prompts", component="Prompts"))
register(ModuleManifest("ai-dag", "工作流", "DAG可视化编排", "ai", icon="🔀", route="dag", component="DagEditor"))
register(ModuleManifest("ai-agents", "Agent中心", "Agent注册与管理", "ai", icon="🤖", route="agents", component="AgentConsole"))
register(ModuleManifest("ai-skills", "Skill市场", "Skill安装与管理", "ai", icon="⚡", route="skills", component="SkillManager"))
register(ModuleManifest("ai-plugins", "插件市场", "插件安装与发现", "ai", icon="🔌", route="plugins", component="Plugins"))

# ---- 系统 ----
register(ModuleManifest("sys-settings", "设置", "全局配置", "system", icon="⚙️", route="settings", component="Settings"))
register(ModuleManifest("sys-costs", "成本追踪", "AI调用成本统计", "system", icon="💰", route="costs", component="Costs"))
register(ModuleManifest("sys-billing", "套餐订阅", "商业化套餐管理", "system", icon="💳", route="billing", component="Billing"))
register(ModuleManifest("sys-collaboration", "协作", "团队协作与日志", "system", icon="👥", route="collaboration", component="CollaborationPanel"))

# ---- 可选的 GitHub 社区插件 ----
register(ModuleManifest("community-book-analysis", "爆款分析(社区)", "10层深度书籍分析", "community", version="0.2.0",
    source="github", source_url="https://github.com/example/novel-analysis-skill", installed=False, enabled=False,
    icon="📖", route="", component="", backend_module=""))
register(ModuleManifest("community-hm-content", "短视频脚本(社区)", "热点→短视频脚本生成", "community", version="0.1.0",
    source="github", source_url="https://github.com/example/hm-content", installed=False, enabled=False,
    icon="🎬", route="", component="", backend_module=""))


def get_enabled_modules(category: str = "") -> list[ModuleManifest]:
    """Return all enabled + installed modules, optionally filtered by category."""
    return [
        m
        for group in get_all_modules(category).values()
        for m in group
        if m.enabled and m.installed
    ]


def _persistent_states() -> dict[str, dict[str, bool]]:
    """Read the durable global module state from the existing settings table."""
    db = connect()
    try:
        rows = db.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'module_state:%'"
        ).fetchall()
    finally:
        db.close()
    states: dict[str, dict[str, bool]] = {}
    for row in rows:
        module_id = str(row["key"])[len("module_state:"):]
        try:
            payload = json.loads(row["value"] or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("enabled"), bool):
            states[module_id] = {"enabled": payload["enabled"], "installed": True}
    return states


def get_all_modules() -> dict[str, list[ModuleManifest]]:
    """Return modules grouped by category."""
    states = _persistent_states()
    cats: dict[str, list[ModuleManifest]] = {}
    for m in MODULES.values():
        state = states.get(m.id)
        if state:
            m.enabled = state["enabled"]
            m.installed = state["installed"]
        cats.setdefault(m.category, []).append(m)
    return cats


def install_module(module_id: str) -> bool:
    """Dynamic package installation is intentionally unavailable."""
    return False


def uninstall_module(module_id: str) -> bool:
    """Dynamic package removal is intentionally unavailable."""
    return False


def toggle_module(module_id: str, enabled: bool) -> bool:
    m = MODULES.get(module_id)
    if not m or not m.installed:
        return False
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO settings (key, value, description)
            VALUES (%s, %s, %s)
            ON CONFLICT(key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = now()
            """,
            (
                f"module_state:{module_id}",
                json.dumps({"enabled": bool(enabled), "installed": True}, ensure_ascii=False),
                "Durable plugin/module lifecycle state",
            ),
        )
        db.commit()
    finally:
        db.close()
    m.enabled = enabled
    return True
