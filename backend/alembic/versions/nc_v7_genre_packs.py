"""Create the real V7 genre-pack registry used by the wizard and runtime.

Revision ID: nc_v7_genre_packs
Revises: nc_legacy_chapter_scope
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_v7_genre_packs"
down_revision: Union[str, None] = "nc_legacy_chapter_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS v7_genre_packs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(50) NOT NULL UNIQUE,
            parent_id UUID REFERENCES v7_genre_packs(id) ON DELETE SET NULL,
            description TEXT,
            scope VARCHAR(50) NOT NULL DEFAULT 'custom',
            is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            icon_url VARCHAR(500),
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_genre_packs_parent_id ON v7_genre_packs(parent_id);
        CREATE INDEX IF NOT EXISTS idx_genre_packs_scope ON v7_genre_packs(scope);
        CREATE INDEX IF NOT EXISTS idx_genre_packs_is_builtin ON v7_genre_packs(is_builtin);
        -- Production may already contain this table from the pre-migration V7
        -- bootstrap, where the ORM default was not present in PostgreSQL.
        ALTER TABLE v7_genre_packs
            ALTER COLUMN is_active SET DEFAULT TRUE;

        CREATE TABLE IF NOT EXISTS v7_genre_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            genre_id UUID NOT NULL REFERENCES v7_genre_packs(id) ON DELETE CASCADE,
            rule_type VARCHAR(50) NOT NULL,
            rule_key VARCHAR(100) NOT NULL,
            rule_value JSONB NOT NULL DEFAULT '{}',
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            priority INTEGER NOT NULL DEFAULT 50,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            inherited_from UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (genre_id, rule_key)
        );
        CREATE INDEX IF NOT EXISTS idx_genre_rules_genre_id ON v7_genre_rules(genre_id);
        CREATE INDEX IF NOT EXISTS idx_genre_rules_rule_type ON v7_genre_rules(rule_type);

        CREATE TABLE IF NOT EXISTS v7_genre_knowledge (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            genre_id UUID NOT NULL REFERENCES v7_genre_packs(id) ON DELETE CASCADE,
            knowledge_type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            tags JSONB NOT NULL DEFAULT '[]',
            priority INTEGER NOT NULL DEFAULT 50,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            inherited_from UUID,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_genre_knowledge_genre_id ON v7_genre_knowledge(genre_id);
        CREATE INDEX IF NOT EXISTS idx_genre_knowledge_type ON v7_genre_knowledge(knowledge_type);

        CREATE TABLE IF NOT EXISTS v7_genre_prompts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            genre_id UUID NOT NULL REFERENCES v7_genre_packs(id) ON DELETE CASCADE,
            prompt_type VARCHAR(50) NOT NULL,
            prompt_name VARCHAR(100) NOT NULL,
            version VARCHAR(20) NOT NULL DEFAULT '1.0',
            content TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            inherited_from UUID,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (genre_id, prompt_name)
        );
        CREATE INDEX IF NOT EXISTS idx_genre_prompts_genre_id ON v7_genre_prompts(genre_id);
        CREATE INDEX IF NOT EXISTS idx_genre_prompts_type ON v7_genre_prompts(prompt_type);
        """
    )

    # Built-in options are data, not a frontend fallback. Stable IDs let old
    # metadata and generated audit records keep pointing to the same pack.
    op.execute(
        """
        INSERT INTO v7_genre_packs
            (id, name, slug, description, scope, is_builtin, is_active, extra_metadata)
        VALUES
            ('00000000-0000-7000-8000-000000000001', '都市', 'urban', '现代城市、现实关系与高密度冲突', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000002', '玄幻', 'xuanhuan', '力量体系、升级目标与强反馈冒险', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000003', '仙侠', 'xianxia', '修行、因果、宗门与资源竞争', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000004', '悬疑', 'suspense', '线索、压力、反转与可验证推理', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000005', '科幻', 'science-fiction', '规则、未知风险与技术选择', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000006', '历史', 'history', '时代约束、身份博弈与现实目标', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000007', '游戏', 'game', '任务、数值反馈与副本推进', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'),
            ('00000000-0000-7000-8000-000000000008', '言情', 'romance', '关系推进、情感选择与即时反馈', 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}')
        ON CONFLICT (slug) DO NOTHING;

        INSERT INTO v7_genre_packs (name, slug, parent_id, description, scope, is_builtin, is_active, extra_metadata)
        SELECT child.name, child.slug, parent.id, child.description, 'fanqie', TRUE, TRUE, '{"platform":"fanqie"}'
        FROM (VALUES
            ('都市系统', 'urban-system', 'urban', '系统任务、现实资源与身份反差'),
            ('都市脑洞', 'urban-brain', 'urban', '现实场景中的异常设定与快速兑现'),
            ('都市神豪', 'urban-tycoon', 'urban', '资源碾压、公开反馈与关系变化'),
            ('传统升级流', 'xuanhuan-upgrade', 'xuanhuan', '境界、资源、对手与阶段性胜利'),
            ('苟道流', 'xuanhuan-cautious', 'xuanhuan', '低调积累、风险识别与反差兑现'),
            ('系统流', 'xuanhuan-system', 'xuanhuan', '任务驱动、能力边界与即时反馈'),
            ('长生流', 'xianxia-longlife', 'xianxia', '时间跨度、资源积累与因果压力'),
            ('规则怪谈', 'suspense-rules', 'suspense', '规则验证、错误代价与逐层揭示'),
            ('无限流', 'suspense-infinite', 'suspense', '副本目标、倒计时与生存选择'),
            ('末日生存', 'science-fiction-apocalypse', 'science-fiction', '资源约束、外部威胁与团队选择'),
            ('权谋历史', 'history-strategy', 'history', '身份伪装、利益交换与局势反转'),
            ('副本游戏', 'game-dungeon', 'game', '任务目标、机制破解与奖励反馈')
        ) AS child(name, slug, parent_slug, description)
        JOIN v7_genre_packs parent ON parent.slug = child.parent_slug
        ON CONFLICT (slug) DO NOTHING;

        WITH style(slug, value) AS (VALUES
            ('urban', '{"tone":"直接、生活化、爽快","pace":"fast","opening":"前三百字进入具体冲突","payoff_density":"high"}'::jsonb),
            ('xuanhuan', '{"tone":"强目标、强反馈、升级明确","pace":"fast","opening":"尽快亮出能力或危机","payoff_density":"high"}'::jsonb),
            ('xianxia', '{"tone":"修行感、因果感、资源竞争","pace":"fast","opening":"尽快交代修行目标与现实压力","payoff_density":"high"}'::jsonb),
            ('suspense', '{"tone":"具体、紧张、线索可验证","pace":"fast","opening":"前三百字出现异常或倒计时","payoff_density":"medium"}'::jsonb),
            ('science-fiction', '{"tone":"清晰、具体、规则可感知","pace":"fast","opening":"尽快呈现异常规则与选择","payoff_density":"high"}'::jsonb),
            ('history', '{"tone":"具体、紧迫、身份关系清楚","pace":"fast","opening":"尽快交代时代压力与个人目标","payoff_density":"high"}'::jsonb),
            ('game', '{"tone":"任务明确、反馈直接、推进迅速","pace":"fast","opening":"尽快出现任务目标与可见奖励","payoff_density":"high"}'::jsonb),
            ('romance', '{"tone":"直接、鲜明、关系变化可见","pace":"fast","opening":"前三百字出现关系张力","payoff_density":"high"}'::jsonb)
        )
        INSERT INTO v7_genre_rules (genre_id, rule_type, rule_key, rule_value, severity, priority, description)
        SELECT p.id, 'style_card', 'core_style', style.value, 'info', 100, '内置品类的基础写作气质与节奏规则'
        FROM style JOIN v7_genre_packs p ON p.slug = style.slug
        ON CONFLICT (genre_id, rule_key) DO NOTHING;

        INSERT INTO v7_genre_rules (genre_id, rule_type, rule_key, rule_value, severity, priority, description)
        SELECT p.id, 'payoff', 'chapter_payoff_contract',
               '{"must_have":"可见结果","must_show":"人物或旁观者反馈","must_leave":"下一章压力","avoid":"空泛总结和无代价碾压"}'::jsonb,
               'warning', 90, '每章爽点必须有铺垫、可见结果、反馈、代价或新压力'
        FROM v7_genre_packs p
        WHERE p.is_builtin AND p.parent_id IS NULL
        ON CONFLICT (genre_id, rule_key) DO NOTHING;

        INSERT INTO v7_genre_knowledge (genre_id, knowledge_type, title, content, tags, priority)
        SELECT p.id, 'writing_method', p.slug || chr(58) || 'core-rhythm',
               '正文以具体行动推进，不用空泛议论代替剧情。每章至少完成一个可见目标，并在章末留下可追读的新压力。',
               jsonb_build_array(p.slug, 'fast-pace', 'visible-payoff'), 100
        FROM v7_genre_packs p
        WHERE p.is_builtin AND p.parent_id IS NULL
        ON CONFLICT DO NOTHING;

        INSERT INTO v7_genre_prompts (genre_id, prompt_type, prompt_name, version, content, description)
        SELECT p.id, 'writer', p.slug || '.writer.core', '1.0',
               '你正在写番茄快节奏网文。遵守本品类规则：前三百字进入具体主题；用人物行动、对话和可见结果推进；爽点必须有铺垫、反馈与下一压力；不要写提纲、总结或作者说明。',
               '内置品类包的正文生成补充规则'
        FROM v7_genre_packs p
        WHERE p.is_builtin AND p.parent_id IS NULL
        ON CONFLICT (genre_id, prompt_name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS v7_genre_prompts;
        DROP TABLE IF EXISTS v7_genre_knowledge;
        DROP TABLE IF EXISTS v7_genre_rules;
        DROP TABLE IF EXISTS v7_genre_packs;
        """
    )
