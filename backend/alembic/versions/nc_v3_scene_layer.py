"""V3-P3-⑪: 场景层（Scene）+ Scene Director Agent。

为章节新增场景（Scene）实体，由 Scene Director 在成章前规划场景分镜
（标题/节拍/目标/场景/视角），写章节点消费该分镜保证场景推进不水字。
"""
from __future__ import annotations

from alembic import op

revision = "nc_v3_scene_layer"
down_revision = "nc_v3_author_style"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id   UUID NOT NULL,
            project_id   UUID NOT NULL,
            scene_index  INTEGER NOT NULL DEFAULT 1,
            title        VARCHAR(200) NOT NULL DEFAULT '',
            beat         VARCHAR(40) NOT NULL DEFAULT '',
            goal         TEXT NOT NULL DEFAULT '',
            setting      TEXT NOT NULL DEFAULT '',
            pov          VARCHAR(80) NOT NULL DEFAULT '',
            meta         JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS scenes_chapter_idx ON scenes (chapter_id);
        CREATE INDEX IF NOT EXISTS scenes_project_idx ON scenes (project_id);
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS scenes;")
