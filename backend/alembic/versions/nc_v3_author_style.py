"""V3-P3-⑩: Author Style Card 强化 — 编辑器 diff 信号 + 风格卡持久化。

新增学习输入源（不改动现有 style_card 结构，仅扩展提取来源）：
- 修改记录 / 删除内容 / 保留内容：编辑器对 AI 生成内容的 diff 段
- 喜欢表达：用户在编辑器主动标记的偏好表达

由 Learning Agent（m3_tasks.run_author_style_learning）异步消费更新 style_card，
不阻塞实时编辑体验。
"""
from __future__ import annotations

from alembic import op

revision = "nc_v3_author_style"
down_revision = "nc_v3_timeline_anchor"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS author_style_signals (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id    UUID NOT NULL,
            content_id    UUID,
            author_id     UUID,
            signal_type   VARCHAR(16) NOT NULL DEFAULT 'edit',
            kept_text     TEXT NOT NULL DEFAULT '',
            deleted_text  TEXT NOT NULL DEFAULT '',
            edited_text   TEXT NOT NULL DEFAULT '',
            liked_text    TEXT NOT NULL DEFAULT '',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS author_style_signals_project_idx
            ON author_style_signals (project_id);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS style_cards (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id    UUID NOT NULL UNIQUE,
            card          JSONB NOT NULL DEFAULT '{}'::jsonb,
            samples_count INTEGER NOT NULL DEFAULT 0,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS style_cards;")
    op.execute("DROP TABLE IF EXISTS author_style_signals;")
