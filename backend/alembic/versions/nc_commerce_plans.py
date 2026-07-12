"""NC-COMMERCE: Create plans and subscriptions tables for commercialization."""
from alembic import op


revision = "nc_commerce_plans"
down_revision = "nc_settings_table"


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT DEFAULT '',
            price_monthly_cny DECIMAL(10, 2) DEFAULT 0,
            price_yearly_cny DECIMAL(10, 2) DEFAULT 0,
            features JSONB DEFAULT '[]',
            max_projects INTEGER DEFAULT 3,
            max_words_per_month BIGINT DEFAULT 100000,
            ai_models TEXT[] DEFAULT ARRAY['deepseek'],
            priority_support BOOLEAN DEFAULT FALSE,
            is_public BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id),
            plan_id VARCHAR(36) REFERENCES plans(id),
            status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired', 'trial')),
            started_at TIMESTAMPTZ DEFAULT now(),
            expires_at TIMESTAMPTZ,
            auto_renew BOOLEAN DEFAULT TRUE,
            payment_method VARCHAR(50) DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
    """)

    # Seed default plans
    op.execute("""
        INSERT INTO plans (id, name, description, price_monthly_cny, price_yearly_cny, features,
                           max_projects, max_words_per_month, ai_models, priority_support, is_public)
        VALUES
        ('plan_free', 'Free', '免费试用，基础功能', 0, 0,
         '["3个项目","10万字符/月","DeepSeek基础模型","基础Prompt模板","社区支持"]',
         3, 100000, ARRAY['deepseek'], FALSE, TRUE),
        ('plan_pro', 'Pro', '专业创作，进阶功能', 29.9, 299,
         '["无限制项目","100万字符/月","全部AI模型","高级Prompt编辑","优先支持","数据导出","版本历史"]',
         999, 1000000, ARRAY['deepseek','claude','openai','gemini'], TRUE, TRUE),
        ('plan_enterprise', 'Enterprise', '商业级创作平台', 99.9, 999,
         '["无限项目","无限字符","全部AI模型","自定义Prompt工作流","专属客服","API接入","团队协作","SSO","数据备份"]',
         9999, 100000000, ARRAY['deepseek','claude','openai','gemini'], TRUE, TRUE)
        ON CONFLICT (id) DO NOTHING;
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS plans")
