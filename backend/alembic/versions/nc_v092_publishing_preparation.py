"""v0.9.2 出版准备层：平台配置、发布变体、统计快照、七道门禁、AI披露、人工编辑

Revision ID: nc_v092_publishing_preparation
Revises: nc_v7_genre_packs
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_v092_publishing_preparation"
down_revision: Union[str, None] = "nc_v7_genre_packs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 平台发布配置表 ──────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_publication_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            platform VARCHAR(50) NOT NULL,  -- fanqie / qidian / jinjiang / custom
            profile_name VARCHAR(200) NOT NULL,
            -- 平台规则状态：confirmed / stale / unknown
            policy_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            policy_version VARCHAR(100) DEFAULT '',
            last_verified_at TIMESTAMPTZ,
            -- 平台具体规则（示例配置，不写死代码）
            word_count_min INTEGER,
            word_count_max INTEGER,
            chapter_word_min INTEGER,
            chapter_word_max INTEGER,
            allowed_genres JSONB NOT NULL DEFAULT '[]',
            prohibited_content JSONB NOT NULL DEFAULT '[]',
            title_rules JSONB NOT NULL DEFAULT '{}',
            synopsis_rules JSONB NOT NULL DEFAULT '{}',
            tag_rules JSONB NOT NULL DEFAULT '{}',
            -- AI 使用政策：allowed / allowed_with_human_editing / required_disclosure / unknown / prohibited
            ai_usage_policy VARCHAR(40) NOT NULL DEFAULT 'unknown',
            ai_disclosure_template TEXT,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(project_id, platform, profile_name)
        );
        CREATE INDEX IF NOT EXISTS idx_platform_profiles_project ON platform_publication_profiles(project_id);
        CREATE INDEX IF NOT EXISTS idx_platform_profiles_platform ON platform_publication_profiles(platform);
        """
    )

    # ── 2. 发布变体表（一个基础小说 + 多平台变体）──────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_variants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            platform_profile_id UUID REFERENCES platform_publication_profiles(id),
            platform VARCHAR(50) NOT NULL,
            variant_name VARCHAR(200) NOT NULL,
            -- 三层版本追踪
            platform_profile_revision UUID,
            metadata_revision UUID REFERENCES versions(id),
            content_revision UUID REFERENCES versions(id),
            -- 元数据（平台专属）
            title VARCHAR(500),
            synopsis TEXT,
            tags JSONB NOT NULL DEFAULT '[]',
            category VARCHAR(100),
            -- 正文共用标记：TRUE=共用基础正文，FALSE=有平台专属修订版
            shares_base_content BOOLEAN NOT NULL DEFAULT TRUE,
            platform_specific_body JSONB,  -- 平台专属正文（shares_base_content=FALSE时使用）
            -- 发布状态：draft / quality_candidate / publish_ready / published / rejected
            publication_status VARCHAR(30) NOT NULL DEFAULT 'draft',
            -- AI披露状态
            ai_disclosure_status VARCHAR(30) NOT NULL DEFAULT 'pending',
            ai_disclosure_text TEXT,
            -- 外部AI检测标记（仅记录，不单独阻断）
            external_ai_flagged BOOLEAN NOT NULL DEFAULT FALSE,
            external_ai_score NUMERIC(5,2),
            external_ai_provider VARCHAR(100),
            -- 七道门门禁结果摘要
            gate_summary JSONB NOT NULL DEFAULT '{}',
            last_gate_run_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            published_url TEXT,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(novel_id, platform, variant_name)
        );
        CREATE INDEX IF NOT EXISTS idx_publication_variants_novel ON publication_variants(novel_id);
        CREATE INDEX IF NOT EXISTS idx_publication_variants_status ON publication_variants(publication_status);
        CREATE INDEX IF NOT EXISTS idx_publication_variants_platform ON publication_variants(platform);
        """
    )

    # ── 3. 章节统计快照表 ──────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chapter_statistics_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            variant_id UUID REFERENCES publication_variants(id),
            statistics_version VARCHAR(20) NOT NULL DEFAULT 'v1',
            -- 双哈希
            content_sha256 VARCHAR(64) NOT NULL,
            normalized_sha256 VARCHAR(64) NOT NULL,
            -- 核心统计
            total_chars INTEGER NOT NULL DEFAULT 0,
            total_bytes INTEGER NOT NULL DEFAULT 0,
            chapter_count INTEGER NOT NULL DEFAULT 1,
            paragraph_count INTEGER NOT NULL DEFAULT 0,
            sentence_count INTEGER NOT NULL DEFAULT 0,
            dialogue_count INTEGER NOT NULL DEFAULT 0,
            dialogue_char_count INTEGER NOT NULL DEFAULT 0,
            avg_sentence_length NUMERIC(8,2) NOT NULL DEFAULT 0,
            -- 完整统计JSON（statistics_v1输出）
            full_statistics JSONB NOT NULL DEFAULT '{}',
            anomaly_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(chapter_id, statistics_version, content_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_chapter_stats_chapter ON chapter_statistics_snapshots(chapter_id);
        CREATE INDEX IF NOT EXISTS idx_chapter_stats_hash ON chapter_statistics_snapshots(content_sha256);
        """
    )

    # ── 4. 七道质量门禁结果表 ──────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quality_gate_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            variant_id UUID REFERENCES publication_variants(id),
            -- 七道门禁：content_quality / continuity / payoff_density / readability /
            --          platform_compliance / ai_disclosure / external_risk
            gate_key VARCHAR(50) NOT NULL,
            gate_version VARCHAR(20) NOT NULL DEFAULT 'v1',
            passed BOOLEAN NOT NULL DEFAULT FALSE,
            score NUMERIC(5,2),
            threshold NUMERIC(5,2),
            -- 子门禁结果（如 platform_compliance 下的 metadata_quality）
            sub_gates JSONB NOT NULL DEFAULT '{}',
            issues JSONB NOT NULL DEFAULT '[]',
            warnings JSONB NOT NULL DEFAULT '[]',
            evidence JSONB NOT NULL DEFAULT '{}',
            -- 阻断标记：TRUE=此门禁不通过则不能 publish_ready
            is_blocking BOOLEAN NOT NULL DEFAULT TRUE,
            runner VARCHAR(100) NOT NULL DEFAULT 'system',
            content_sha256 VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(chapter_id, gate_key, content_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_quality_gates_chapter ON quality_gate_results(chapter_id);
        CREATE INDEX IF NOT EXISTS idx_quality_gates_variant ON quality_gate_results(variant_id);
        CREATE INDEX IF NOT EXISTS idx_quality_gates_key ON quality_gate_results(gate_key);
        CREATE INDEX IF NOT EXISTS idx_quality_gates_passed ON quality_gate_results(passed);
        """
    )

    # ── 5. AI披露记录表 ────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_disclosure_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            variant_id UUID NOT NULL REFERENCES publication_variants(id) ON DELETE CASCADE,
            chapter_id UUID REFERENCES contents(id),
            -- 披露状态：pending / generated / confirmed / rejected / not_required
            disclosure_status VARCHAR(30) NOT NULL DEFAULT 'pending',
            disclosure_text TEXT,
            -- 生成方式：auto / manual / template
            generation_method VARCHAR(20) NOT NULL DEFAULT 'auto',
            generated_by VARCHAR(100),
            confirmed_by VARCHAR(100),
            confirmed_at TIMESTAMPTZ,
            -- AI使用比例估算
            ai_usage_estimate NUMERIC(5,2),
            -- 涉及的AI模型
            ai_models_used JSONB NOT NULL DEFAULT '[]',
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_ai_disclosure_variant ON ai_disclosure_records(variant_id);
        CREATE INDEX IF NOT EXISTS idx_ai_disclosure_status ON ai_disclosure_records(disclosure_status);
        """
    )

    # ── 6. 人工编辑记录表 ──────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS human_editing_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            variant_id UUID REFERENCES publication_variants(id),
            editor_id UUID REFERENCES users(id),
            editor_name VARCHAR(200),
            -- 编辑类型：full_rewrite / local_repair / proofread / formatting / other
            edit_type VARCHAR(30) NOT NULL DEFAULT 'local_repair',
            -- 局部修复的句子位置（statistics_v1坐标）
            repaired_sentence_indices JSONB NOT NULL DEFAULT '[]',
            repaired_paragraph_indices JSONB NOT NULL DEFAULT '[]',
            -- 编辑前后哈希
            before_sha256 VARCHAR(64),
            after_sha256 VARCHAR(64),
            -- 编辑量统计
            chars_added INTEGER NOT NULL DEFAULT 0,
            chars_removed INTEGER NOT NULL DEFAULT 0,
            chars_modified INTEGER NOT NULL DEFAULT 0,
            -- 人工确认标记
            human_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            confirmation_note TEXT,
            edit_diff TEXT,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_human_editing_chapter ON human_editing_records(chapter_id);
        CREATE INDEX IF NOT EXISTS idx_human_editing_variant ON human_editing_records(variant_id);
        CREATE INDEX IF NOT EXISTS idx_human_editing_confirmed ON human_editing_records(human_confirmed);
        """
    )

    # ── 7. 给contents表添加出版准备状态字段（兼容旧status）────
    op.execute(
        """
        ALTER TABLE contents ADD COLUMN IF NOT EXISTS publishing_status VARCHAR(30) NOT NULL DEFAULT 'draft';
        COMMENT ON COLUMN contents.publishing_status IS 'v0.9.2 出版准备状态：draft/quality_candidate/publish_ready/published';
        """
    )

    # ── 8. 内置平台配置示例（仅示例，policy_status=stale）──────
    op.execute(
        """
        INSERT INTO platform_publication_profiles
            (project_id, platform, profile_name, policy_status, policy_version,
             word_count_min, word_count_max, chapter_word_min, chapter_word_max,
             ai_usage_policy, extra_metadata)
        SELECT p.id, 'fanqie', '番茄小说-默认', 'stale', 'example-2026',
               200000, 5000000, 2000, 5000,
               'allowed_with_human_editing',
               '{"note":"示例配置，需人工核实最新平台规则","title_rule":"不超过10字，含核心冲突"}'::jsonb
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM platform_publication_profiles pp
            WHERE pp.project_id = p.id AND pp.platform = 'fanqie' AND pp.profile_name = '番茄小说-默认'
        );

        INSERT INTO platform_publication_profiles
            (project_id, platform, profile_name, policy_status, policy_version,
             word_count_min, word_count_max, chapter_word_min, chapter_word_max,
             ai_usage_policy, extra_metadata)
        SELECT p.id, 'qidian', '起点中文-默认', 'stale', 'example-2026',
               300000, 10000000, 2000, 4000,
               'required_disclosure',
               '{"note":"示例配置，需人工核实最新平台规则"}'::jsonb
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM platform_publication_profiles pp
            WHERE pp.project_id = p.id AND pp.platform = 'qidian' AND pp.profile_name = '起点中文-默认'
        );

        INSERT INTO platform_publication_profiles
            (project_id, platform, profile_name, policy_status, policy_version,
             word_count_min, word_count_max, chapter_word_min, chapter_word_max,
             ai_usage_policy, extra_metadata)
        SELECT p.id, 'jinjiang', '晋江文学-默认', 'stale', 'example-2026',
               100000, 3000000, 1500, 5000,
               'prohibited',
               '{"note":"示例配置，晋江禁止AI生成内容发布"}'::jsonb
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM platform_publication_profiles pp
            WHERE pp.project_id = p.id AND pp.platform = 'jinjiang' AND pp.profile_name = '晋江文学-默认'
        );
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE contents DROP COLUMN IF EXISTS publishing_status")
    op.execute("DROP TABLE IF EXISTS human_editing_records")
    op.execute("DROP TABLE IF EXISTS ai_disclosure_records")
    op.execute("DROP TABLE IF EXISTS quality_gate_results")
    op.execute("DROP TABLE IF EXISTS chapter_statistics_snapshots")
    op.execute("DROP TABLE IF EXISTS publication_variants")
    op.execute("DROP TABLE IF EXISTS platform_publication_profiles")
