"""v1.1 provider-backed publication disclosure and semantic payoff review."""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_v11_disclosure_payoff"
down_revision: Union[str, None] = "nc_v092_publishing_preparation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        r"""
        INSERT INTO prompts (name, version, model, template, golden_cases)
        VALUES (
            'publishing.ai_disclosure', '1.0.0', 'deepseek',
            $$你是出版合规编辑。请根据给定的作品与平台资料，生成一段准确、克制、可供作者人工确认的 AI 使用披露文案。

硬规则：
1. 只陈述输入资料明确支持的事实，不得猜测平台规则、模型名称、使用比例或人工编辑情况。
2. 文案必须说明 AI 在创作流程中的辅助性质；如果输入给出了模型名称或使用比例，才可以写入。
3. 不得宣称已经完成平台备案、人工审核或合规确认。
4. 输出简洁的中文正文，不使用营销话术，不写免责声明之外的建议。

作品标题：$variant_title
作品简介：$variant_synopsis
发布平台：$platform
平台 AI 政策：$ai_usage_policy
已知模型：$source_models
章节上下文：$chapter_context

只输出 JSON：{"disclosure_text":"待人工确认的准确披露文案","ai_models_used":["已知模型"],"usage_estimate":null,"rationale":"事实依据"}$$,
            '[]'::jsonb
        )
        ON CONFLICT (name, version, model) DO UPDATE
        SET template = EXCLUDED.template, golden_cases = EXCLUDED.golden_cases,
            is_active = TRUE, deprecated = FALSE, updated_at = now();

        INSERT INTO prompts (name, version, model, template, golden_cases)
        VALUES (
            'publishing.payoff_semantic', '1.0.0', 'deepseek',
            $$你是严格的网文出版编辑，负责判断一章正文是否真的完成了可见爽点，而不是做关键词匹配。

判定标准：
1. payoff 只能是正文中已经发生的具体结果、身份反馈、资源收益、反击兑现或状态改变；预告、愿望、空泛情绪和关键词不能算。
2. 每个 payoff 必须给出正文中的短证据原句，并说明读者即时感受与对后续剧情的具体影响。
3. ending_pressure 只有在章末已经形成明确的新危机、代价、追问或必须继续阅读的压力时才为 true。
4. semantic_score 是 0-100 的编辑判断；证据不足时宁可给低分或 0 个 payoff，不得凑数。

平台：$platform
章节编号：$chapter_id
章节正文：
$chapter_text

只输出 JSON：{"payoff_count":1,"payoffs":[{"event":"已发生的结果","evidence_quote":"正文短引文","reader_effect":"即时爽感","consequence":"后续影响","confidence":0.9}],"ending_pressure":true,"semantic_score":80,"rationale":"判断依据"}$$,
            '[]'::jsonb
        )
        ON CONFLICT (name, version, model) DO UPDATE
        SET template = EXCLUDED.template, golden_cases = EXCLUDED.golden_cases,
            is_active = TRUE, deprecated = FALSE, updated_at = now();

        INSERT INTO model_routes (task_type, provider, model, params, fallback_json)
        VALUES
            ('publishing_ai_disclosure', 'deepseek', 'deepseek-chat', '{"temperature":0.2}'::jsonb, '[]'::jsonb),
            ('publishing_payoff_semantic', 'deepseek', 'deepseek-chat', '{"temperature":0.2}'::jsonb, '[]'::jsonb)
        ON CONFLICT (task_type) DO UPDATE
        SET provider = EXCLUDED.provider, model = EXCLUDED.model,
            params = EXCLUDED.params, fallback_json = EXCLUDED.fallback_json,
            is_active = TRUE, updated_at = now();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM model_routes
        WHERE task_type IN ('publishing_ai_disclosure', 'publishing_payoff_semantic');
        DELETE FROM prompts
        WHERE (name, version, model) IN (
            ('publishing.ai_disclosure', '1.0.0', 'deepseek'),
            ('publishing.payoff_semantic', '1.0.0', 'deepseek')
        );
        """
    )
